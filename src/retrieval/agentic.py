"""Knowledge Foundry — Agentic Retrieval Engine.

Implements both simple retrieval (single KB, top-K) and agentic retrieval
(multi-hop, multi-KB, query rewriting) as described in the retrieval spec.

The agentic retrieval engine plans, iterates, and respects context constraints
(token budgets, latency limits) while producing structured intermediate artifacts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.core.interfaces import (
    EmbeddingProvider,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    ModelTier,
    SearchResult,
    VectorStore,
)

logger = logging.getLogger(__name__)


# =============================================================
# ENUMS & CONFIG
# =============================================================


class RetrievalMode(str, Enum):
    """Retrieval mode for search operations."""

    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"


class AgenticReasoningEffort(str, Enum):
    """How much reasoning effort the agentic engine should spend."""

    LOW = "low"       # Single retrieval pass
    MEDIUM = "medium"  # Query decomposition + single pass per sub-query
    HIGH = "high"      # Multi-hop with iterative refinement


# =============================================================
# REQUEST / RESPONSE MODELS
# =============================================================


@dataclass
class BasicRetrievalRequest:
    """Request for simple top-K retrieval from a single knowledge base."""

    kb_id: UUID
    query: str
    tenant_id: str
    top_k: int = 10
    mode: RetrievalMode = RetrievalMode.VECTOR
    filters: dict[str, Any] = field(default_factory=dict)
    similarity_threshold: float = 0.65


@dataclass
class AgenticRetrievalRequest:
    """Request for agentic multi-hop retrieval."""

    query: str
    tenant_id: str
    kb_ids: list[UUID] = field(default_factory=list)
    max_steps: int = 5
    reasoning_effort: AgenticReasoningEffort = AgenticReasoningEffort.MEDIUM
    top_k_per_step: int = 5
    token_budget: int = 8000
    max_latency_ms: int = 30000
    mode: RetrievalMode = RetrievalMode.HYBRID
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubQuery:
    """A decomposed sub-query generated during planning."""

    sub_query_id: UUID = field(default_factory=uuid4)
    text: str = ""
    kb_id: UUID | None = None
    rationale: str = ""
    results: list[SearchResult] = field(default_factory=list)
    token_count: int = 0


@dataclass
class RetrievalStep:
    """A single step in the agentic retrieval process."""

    step_number: int = 0
    action: str = ""  # "decompose", "retrieve", "synthesize", "refine"
    sub_queries: list[SubQuery] = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)
    synthesis: str = ""
    tokens_used: int = 0
    latency_ms: int = 0


@dataclass
class RetrievalResponse:
    """Response from the retrieval engine (basic or agentic)."""

    request_id: UUID = field(default_factory=uuid4)
    answer: str = ""
    results: list[SearchResult] = field(default_factory=list)
    steps: list[RetrievalStep] = field(default_factory=list)
    total_tokens_used: int = 0
    total_latency_ms: int = 0
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================
# AGENTIC RETRIEVAL ENGINE
# =============================================================


class AgenticRetrievalEngine:
    """Multi-hop, multi-KB agentic retrieval engine.

    Supports both simple retrieval (single pass) and agentic retrieval
    (query decomposition → sub-query planning → iterative retrieval → synthesis).

    The engine enforces token budgets and latency constraints, producing
    structured intermediate artifacts at each step for observability.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingProvider,
        llm_provider: LLMProvider,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_provider = llm_provider

    async def basic_retrieve(self, request: BasicRetrievalRequest) -> RetrievalResponse:
        """Simple single-KB top-K retrieval.

        Embeds the query, searches the vector store, and returns results
        without LLM synthesis.
        """
        start = time.monotonic()
        query_embedding = await self._embedding_service.embed_query(request.query)

        results = await self._vector_store.search(
            query_embedding=query_embedding,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
            filters=request.filters or None,
            similarity_threshold=request.similarity_threshold,
        )

        latency_ms = int((time.monotonic() - start) * 1000)

        return RetrievalResponse(
            answer="",
            results=results,
            steps=[
                RetrievalStep(
                    step_number=1,
                    action="retrieve",
                    results=results,
                    latency_ms=latency_ms,
                )
            ],
            total_latency_ms=latency_ms,
        )

    async def agentic_retrieve(self, request: AgenticRetrievalRequest) -> RetrievalResponse:
        """Agentic multi-hop retrieval with planning and iterative refinement.

        Flow:
        1. Query understanding and decomposition
        2. Sub-query planning across KBs
        3. Iterative retrieval per sub-query
        4. Synthesis of gathered context
        5. Optional refinement if answer is incomplete
        """
        start = time.monotonic()
        steps: list[RetrievalStep] = []
        all_results: list[SearchResult] = []
        total_tokens = 0

        # Step 1: Decompose the query into sub-queries
        decompose_start = time.monotonic()
        sub_queries = await self._decompose_query(request)
        decompose_ms = int((time.monotonic() - decompose_start) * 1000)

        steps.append(RetrievalStep(
            step_number=1,
            action="decompose",
            sub_queries=sub_queries,
            latency_ms=decompose_ms,
        ))

        # Step 2-N: Iterative retrieval for each sub-query
        step_num = 2
        for sq in sub_queries:
            if total_tokens >= request.token_budget:
                break
            elapsed = int((time.monotonic() - start) * 1000)
            if elapsed >= request.max_latency_ms:
                break
            if step_num - 1 > request.max_steps:
                break

            retrieve_start = time.monotonic()
            results = await self._retrieve_for_subquery(sq, request)
            retrieve_ms = int((time.monotonic() - retrieve_start) * 1000)

            sq.results = results
            sq.token_count = sum(len(r.text.split()) for r in results)
            total_tokens += sq.token_count
            all_results.extend(results)

            steps.append(RetrievalStep(
                step_number=step_num,
                action="retrieve",
                sub_queries=[sq],
                results=results,
                tokens_used=sq.token_count,
                latency_ms=retrieve_ms,
            ))
            step_num += 1

        # Final step: Synthesize all results
        synth_start = time.monotonic()
        answer = await self._synthesize(request.query, all_results, request.token_budget)
        synth_ms = int((time.monotonic() - synth_start) * 1000)

        synth_tokens = len(answer.split())
        total_tokens += synth_tokens

        steps.append(RetrievalStep(
            step_number=step_num,
            action="synthesize",
            results=all_results,
            synthesis=answer,
            tokens_used=synth_tokens,
            latency_ms=synth_ms,
        ))

        total_latency_ms = int((time.monotonic() - start) * 1000)
        truncated = total_tokens >= request.token_budget or total_latency_ms >= request.max_latency_ms

        logger.info(
            "Agentic retrieval completed: steps=%d results=%d tokens=%d latency=%dms truncated=%s",
            len(steps),
            len(all_results),
            total_tokens,
            total_latency_ms,
            truncated,
        )

        return RetrievalResponse(
            answer=answer,
            results=all_results,
            steps=steps,
            total_tokens_used=total_tokens,
            total_latency_ms=total_latency_ms,
            truncated=truncated,
        )

    # ==================================================================
    # Internal methods
    # ==================================================================

    async def _decompose_query(self, request: AgenticRetrievalRequest) -> list[SubQuery]:
        """Decompose a complex query into sub-queries using the LLM.

        For LOW effort: return the original query as a single sub-query.
        For MEDIUM/HIGH: use LLM to decompose into targeted sub-queries.
        """
        if request.reasoning_effort == AgenticReasoningEffort.LOW:
            return [SubQuery(text=request.query, rationale="Direct query (low effort)")]

        prompt = (
            f"Decompose the following question into 2-4 focused sub-questions "
            f"that can be answered independently. Return each sub-question on "
            f"a new line prefixed with '- '.\n\n"
            f"Question: {request.query}"
        )

        config = LLMConfig(
            model="",
            tier=ModelTier.HAIKU,
            temperature=0.1,
            max_tokens=500,
        )
        response = await self._llm_provider.generate(prompt, config)

        sub_queries: list[SubQuery] = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                line = line[2:]
            if line:
                kb_id = request.kb_ids[0] if request.kb_ids else None
                sub_queries.append(SubQuery(text=line, kb_id=kb_id, rationale="LLM decomposition"))

        # Fallback: if decomposition produced nothing, use original query
        if not sub_queries:
            sub_queries = [SubQuery(text=request.query, rationale="Fallback to original query")]

        return sub_queries

    async def _retrieve_for_subquery(
        self,
        sub_query: SubQuery,
        request: AgenticRetrievalRequest,
    ) -> list[SearchResult]:
        """Retrieve results for a single sub-query."""
        query_embedding = await self._embedding_service.embed_query(sub_query.text)

        results = await self._vector_store.search(
            query_embedding=query_embedding,
            tenant_id=request.tenant_id,
            top_k=request.top_k_per_step,
            filters=request.filters or None,
            similarity_threshold=0.6,
        )
        return results

    async def _synthesize(
        self,
        original_query: str,
        results: list[SearchResult],
        token_budget: int,
    ) -> str:
        """Synthesize a final answer from all retrieved results.

        Respects token budget by truncating context if necessary.
        """
        if not results:
            return "No relevant information found across the knowledge bases."

        # Build context from results, respecting token budget
        context_parts: list[str] = []
        token_count = 0
        for i, result in enumerate(results, 1):
            chunk_text = f"[Source {i}] {result.text}"
            chunk_tokens = len(chunk_text.split())
            if token_count + chunk_tokens > token_budget * 0.7:
                break
            context_parts.append(chunk_text)
            token_count += chunk_tokens

        context = "\n\n".join(context_parts)

        prompt = (
            f"Based on the following context, answer the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {original_query}\n\n"
            f"Answer concisely, citing sources with [Source N] markers."
        )

        config = LLMConfig(
            model="",
            tier=ModelTier.SONNET,
            temperature=0.2,
            max_tokens=min(2000, token_budget // 2),
        )

        response = await self._llm_provider.generate(prompt, config)
        return response.text
