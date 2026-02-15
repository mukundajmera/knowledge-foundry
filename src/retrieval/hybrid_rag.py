"""Knowledge Foundry — Hybrid VectorCypher RAG Pipeline.

Extends the Milestone 1 vector-only RAG with three retrieval strategies:
- VECTOR_ONLY: Qdrant search (original M1 behaviour)
- GRAPH_ONLY: Neo4j traversal
- HYBRID: Parallel vector + graph search → merged context

Per phase-1.3 spec §4.1–4.3.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.core.interfaces import (
    Citation,
    EmbeddingProvider,
    GraphEntity,
    GraphRelationship,
    GraphStore,
    LLMConfig,
    LLMProvider,
    ModelTier,
    RAGResponse,
    RetrievalStrategy,
    RoutingDecision,
    SearchResult,
    TraversalResult,
    VectorStore,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

DEFAULT_RAG_SYSTEM_PROMPT = """You are Knowledge Foundry, an enterprise AI knowledge assistant.
Answer the user's question based ONLY on the provided context.
If the context doesn't contain enough information, say so clearly.

Rules:
1. Be precise and factual — cite your sources using [Source N] markers.
2. Do not make up information not present in the context.
3. If multiple sources conflict, present both perspectives.
4. Structure your response clearly with headings if appropriate.
5. Keep responses concise but comprehensive.
"""

HYBRID_PROMPT_TEMPLATE = """\
## Direct Knowledge (Vector Search)
{vector_chunks_formatted}

## Knowledge Graph Structure
The following entities and relationships are relevant to your question:

### Entities
{entities_table}

### Relationships
{relationships_list}

### Graph Summary
{graph_summary}

## Related Documents (via Knowledge Graph)
{related_chunks_formatted}

---
## Question
{user_query}

## Instructions
1. Answer using ONLY the context provided above.
2. Cite sources using [Source N] notation.
3. If multi-hop reasoning is needed, show the chain: Entity A → [RELATIONSHIP] → Entity B.
4. If the context is insufficient, say "I don't have enough information to fully answer this."
"""


class RAGPipeline:
    """Hybrid VectorCypher RAG pipeline.

    Supports three retrieval strategies and assembles structured context
    from both vector and graph sources.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingProvider,
        llm_provider: LLMProvider,
        graph_store: GraphStore | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_provider = llm_provider
        self._graph_store = graph_store
        self._system_prompt = system_prompt or DEFAULT_RAG_SYSTEM_PROMPT

    async def query(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 10,
        similarity_threshold: float = 0.65,
        filters: dict[str, Any] | None = None,
        model_tier: ModelTier = ModelTier.SONNET,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        strategy: RetrievalStrategy = RetrievalStrategy.VECTOR_ONLY,
        max_hops: int = 2,
    ) -> RAGResponse:
        """Execute a RAG query with the specified retrieval strategy.

        Args:
            query: The user's question.
            tenant_id: Tenant for data isolation.
            top_k: Number of chunks to retrieve.
            similarity_threshold: Minimum similarity score.
            filters: Optional metadata filters.
            model_tier: LLM tier to use for synthesis.
            max_tokens: Max tokens for LLM response.
            temperature: LLM temperature.
            strategy: Retrieval strategy (vector, graph, hybrid).
            max_hops: Graph traversal depth (for graph/hybrid).

        Returns:
            RAGResponse with text, citations, and metadata.
        """
        start_time = time.monotonic()

        # Select retrieval path
        if strategy == RetrievalStrategy.GRAPH_ONLY:
            context, search_results, citations = await self._graph_only_retrieval(
                query, tenant_id, top_k, max_hops,
            )
        elif strategy == RetrievalStrategy.HYBRID and self._graph_store:
            context, search_results, citations = await self._hybrid_retrieval(
                query, tenant_id, top_k, similarity_threshold, filters, max_hops,
            )
        else:
            context, search_results, citations = await self._vector_only_retrieval(
                query, tenant_id, top_k, similarity_threshold, filters,
            )

        # Handle empty results
        if not context:
            return RAGResponse(
                text="I couldn't find any relevant information in the knowledge base "
                     "to answer your question. Please try rephrasing or broadening your query.",
                citations=[],
                search_results=[],
                total_latency_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Generate response with LLM
        full_prompt = self._build_prompt(query, context)
        config = LLMConfig(
            model="",
            tier=model_tier,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=self._system_prompt,
        )
        llm_response = await self._llm_provider.generate(full_prompt, config)
        total_latency_ms = int((time.monotonic() - start_time) * 1000)

        logger.info(
            "RAG query completed: strategy=%s, results=%d, latency=%dms",
            strategy.value,
            len(search_results),
            total_latency_ms,
        )

        return RAGResponse(
            text=llm_response.text,
            citations=citations,
            llm_response=llm_response,
            search_results=search_results,
            routing_decision=RoutingDecision(
                initial_tier=model_tier,
                final_tier=model_tier,
                complexity_score=0.0,
                task_type_detected=f"rag_{strategy.value}",
            ),
            total_latency_ms=total_latency_ms,
        )

    # ==================================================================
    # Retrieval strategies
    # ==================================================================

    async def _vector_only_retrieval(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
        similarity_threshold: float,
        filters: dict[str, Any] | None,
    ) -> tuple[str, list[SearchResult], list[Citation]]:
        """Original vector-only retrieval path."""
        query_embedding = await self._embedding_service.embed_query(query)
        search_results = await self._vector_store.search(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=top_k,
            filters=filters,
            similarity_threshold=similarity_threshold,
        )
        if not search_results:
            return "", [], []

        context = self._assemble_vector_context(search_results)
        citations = self._build_citations(search_results)
        return context, search_results, citations

    async def _graph_only_retrieval(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
        max_hops: int,
    ) -> tuple[str, list[SearchResult], list[Citation]]:
        """Graph-only retrieval — entity search + traversal."""
        if not self._graph_store:
            return "", [], []

        # Search for entry entities
        entities = await self._graph_store.search_entities(query, tenant_id, limit=top_k)
        if not entities:
            return "", [], []

        entry_ids = [e.id for e in entities]
        traversal = await self._graph_store.traverse(
            entry_entity_ids=entry_ids,
            tenant_id=tenant_id,
            max_hops=max_hops,
            max_results=top_k * 5,
        )

        context = self._assemble_graph_context(entities, traversal)
        return context, [], []

    async def _hybrid_retrieval(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
        similarity_threshold: float,
        filters: dict[str, Any] | None,
        max_hops: int,
    ) -> tuple[str, list[SearchResult], list[Citation]]:
        """Hybrid VectorCypher retrieval — parallel vector + graph search.

        Per phase-1.3 spec §4.1:
        1. Parallel: vector search + graph entity text search
        2. Merge entity IDs
        3. Graph traversal from merged entry points
        4. Fetch related chunks for connected documents
        5. Assemble structured context
        """
        if not self._graph_store:
            return await self._vector_only_retrieval(
                query, tenant_id, top_k, similarity_threshold, filters,
            )

        # Phase 2a/2b: parallel vector + graph search
        query_embedding = await self._embedding_service.embed_query(query)

        vector_task = self._vector_store.search(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=top_k,
            filters=filters,
            similarity_threshold=similarity_threshold,
        )
        graph_task = self._graph_store.search_entities(query, tenant_id, limit=10)

        search_results, graph_entities = await asyncio.gather(vector_task, graph_task)

        # Phase 3: Merge entity IDs from vector payloads + graph search
        entry_entity_ids: set[str] = set()
        for sr in search_results:
            graph_ids = sr.metadata.get("graph_entity_ids", [])
            if isinstance(graph_ids, list):
                entry_entity_ids.update(str(gid) for gid in graph_ids)
        for ge in graph_entities:
            entry_entity_ids.add(ge.id)

        # Phase 4: Graph traversal from merged entry points
        traversal = TraversalResult()
        if entry_entity_ids:
            traversal = await self._graph_store.traverse(
                entry_entity_ids=list(entry_entity_ids),
                tenant_id=tenant_id,
                max_hops=max_hops,
                max_results=50,
            )

        # Phase 5: Assemble hybrid context
        vector_context = self._assemble_vector_context(search_results) if search_results else ""
        graph_context = self._assemble_graph_context(graph_entities, traversal)
        citations = self._build_citations(search_results)

        # Use hybrid template
        context = HYBRID_PROMPT_TEMPLATE.format(
            vector_chunks_formatted=vector_context or "(No vector results)",
            entities_table=self._format_entities_table(
                graph_entities + traversal.entities,
            ),
            relationships_list=self._format_relationships(traversal.relationships),
            graph_summary=f"Explored {traversal.nodes_explored} nodes across "
                          f"{traversal.traversal_depth_reached} hops "
                          f"({traversal.latency_ms}ms).",
            related_chunks_formatted="(Connected documents identified for further retrieval)",
            user_query=query,
        )

        return context, search_results, citations

    # ==================================================================
    # Context formatting helpers
    # ==================================================================

    def _assemble_vector_context(self, results: list[SearchResult]) -> str:
        """Assemble context string from vector search results."""
        parts: list[str] = []
        for i, result in enumerate(results, 1):
            title = result.metadata.get("title", "Unknown Source")
            source_system = result.metadata.get("source_system", "")
            source_info = f" ({source_system})" if source_system else ""
            parts.append(
                f"[Source {i}] {title}{source_info}\n"
                f"Relevance: {result.score:.2f}\n"
                f"{result.text}"
            )
        return "\n\n---\n\n".join(parts)

    def _assemble_graph_context(
        self,
        entities: list[GraphEntity],
        traversal: TraversalResult,
    ) -> str:
        """Assemble context from graph results."""
        parts: list[str] = []

        if entities:
            parts.append("**Entities found:**")
            for e in entities[:20]:
                parts.append(f"- {e.type}: {e.name}")

        if traversal.relationships:
            parts.append("\n**Relationships:**")
            for r in traversal.relationships[:20]:
                parts.append(f"- [{r.from_entity_id}] —{r.type}→ [{r.to_entity_id}]")

        return "\n".join(parts) if parts else ""

    def _format_entities_table(self, entities: list[GraphEntity]) -> str:
        """Format entities as a markdown table."""
        if not entities:
            return "(No entities found)"
        seen: set[str] = set()
        lines = ["| Type | Name | Centrality |", "|------|------|------------|"]
        for e in entities:
            if e.id in seen:
                continue
            seen.add(e.id)
            score = f"{e.centrality_score:.3f}" if e.centrality_score else "—"
            lines.append(f"| {e.type} | {e.name} | {score} |")
        return "\n".join(lines)

    def _format_relationships(self, rels: list[GraphRelationship]) -> str:
        """Format relationships as a bullet list."""
        if not rels:
            return "(No relationships found)"
        lines: list[str] = []
        for r in rels[:30]:
            lines.append(
                f"- {r.from_entity_id} —[{r.type}]→ {r.to_entity_id} "
                f"(confidence: {r.confidence:.2f})"
            )
        return "\n".join(lines)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build the full prompt with context and query."""
        return (
            f"<context>\n{context}\n</context>\n\n"
            f"<question>\n{query}\n</question>\n\n"
            f"Please answer the question based on the context provided above. "
            f"Cite your sources using [Source N] markers."
        )

    def _build_citations(self, results: list[SearchResult]) -> list[Citation]:
        """Build citation objects from search results."""
        citations: list[Citation] = []
        seen_docs: set[str] = set()

        for result in results:
            doc_id = result.document_id
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            citations.append(
                Citation(
                    document_id=doc_id,
                    title=result.metadata.get("title", "Unknown"),
                    chunk_id=result.chunk_id,
                    relevance_score=result.score,
                )
            )
        return citations
