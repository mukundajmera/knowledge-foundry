"""Knowledge Foundry — Qdrant Vector Store.

Async Qdrant client implementing the VectorStore interface.
Collection-per-tenant model with HNSW tuning per phase-1.2 spec.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from qdrant_client import AsyncQdrantClient, models

from src.core.config import QdrantSettings, get_settings
from src.core.exceptions import CollectionNotFoundError, VectorStoreError
from src.core.interfaces import Chunk, SearchResult, VectorStore

logger = logging.getLogger(__name__)


class QdrantVectorStore(VectorStore):
    """Qdrant-backed vector store with collection-per-tenant isolation.

    Each tenant gets a dedicated Qdrant collection named
    ``{prefix}{tenant_id}`` with HNSW index tuning and int8
    scalar quantization per phase-1.2 spec.
    """

    def __init__(
        self,
        client: AsyncQdrantClient | None = None,
        settings: QdrantSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings().qdrant
        self._client = client or AsyncQdrantClient(
            host=self._settings.host,
            port=self._settings.port,
            api_key=self._settings.api_key or None,
        )

    def _collection_name(self, tenant_id: str) -> str:
        """Build collection name from tenant ID."""
        return f"{self._settings.collection_prefix}{tenant_id}"

    async def ensure_collection(self, tenant_id: str) -> None:
        """Create tenant collection if it doesn't exist.

        Configures HNSW with m=16, ef_construct=200, int8 quantization,
        and payload indices for tenant_id, content_type, tags, etc.
        """
        collection_name = self._collection_name(tenant_id)
        try:
            collections = await self._client.get_collections()
            existing = {c.name for c in collections.collections}

            if collection_name in existing:
                logger.debug("Collection %s already exists", collection_name)
                return

            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=get_settings().openai.embedding_dimensions,
                    distance=models.Distance.COSINE,
                    on_disk=False,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=self._settings.hnsw_m,
                    ef_construct=self._settings.hnsw_ef_construct,
                ),
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    ),
                ),
            )

            # Create payload indices for filtering
            for field_name, field_type in [
                ("tenant_id", models.PayloadSchemaType.KEYWORD),
                ("document_id", models.PayloadSchemaType.KEYWORD),
                ("content_type", models.PayloadSchemaType.KEYWORD),
                ("source_system", models.PayloadSchemaType.KEYWORD),
                ("tags", models.PayloadSchemaType.KEYWORD),
                ("visibility", models.PayloadSchemaType.KEYWORD),
            ]:
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )

            logger.info("Created collection %s with HNSW + int8 quantization", collection_name)

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to ensure collection for tenant {tenant_id}: {exc}",
                details={"tenant_id": tenant_id},
            ) from exc

    async def search(
        self,
        query_embedding: list[float],
        tenant_id: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        similarity_threshold: float = 0.65,
    ) -> list[SearchResult]:
        """Search for similar vectors with tenant isolation and metadata filtering.

        Args:
            query_embedding: Query vector (3072-dim).
            tenant_id: Tenant for isolation.
            top_k: Number of results.
            filters: Optional metadata filters (content_type, tags, etc.).
            similarity_threshold: Minimum similarity score.

        Returns:
            List of SearchResult ordered by similarity score (descending).
        """
        collection_name = self._collection_name(tenant_id)

        try:
            # Build Qdrant filter conditions
            must_conditions: list[models.FieldCondition] = [
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=tenant_id),
                ),
            ]

            if filters:
                if "content_type" in filters:
                    must_conditions.append(
                        models.FieldCondition(
                            key="content_type",
                            match=models.MatchValue(value=filters["content_type"]),
                        )
                    )
                if "tags" in filters:
                    must_conditions.append(
                        models.FieldCondition(
                            key="tags",
                            match=models.MatchAny(any=filters["tags"]),
                        )
                    )
                if "source_system" in filters:
                    must_conditions.append(
                        models.FieldCondition(
                            key="source_system",
                            match=models.MatchValue(value=filters["source_system"]),
                        )
                    )
                if "visibility" in filters:
                    must_conditions.append(
                        models.FieldCondition(
                            key="visibility",
                            match=models.MatchAny(any=filters["visibility"]),
                        )
                    )

            qdrant_filter = models.Filter(must=must_conditions)

            results = await self._client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                query_filter=qdrant_filter,
                limit=top_k,
                score_threshold=similarity_threshold,
                search_params=models.SearchParams(
                    hnsw_ef=self._settings.hnsw_ef_search,
                    exact=False,
                ),
                with_payload=True,
            )

            # query_points returns a QueryResponse object with a .points attribute
            search_hits = results.points

            search_results: list[SearchResult] = []
            for hit in search_hits:
                payload = hit.payload or {}
                search_results.append(
                    SearchResult(
                        chunk_id=str(hit.id),
                        document_id=payload.get("document_id", ""),
                        text=payload.get("text", ""),
                        score=hit.score,
                        metadata={
                            k: v
                            for k, v in payload.items()
                            if k not in ("text", "embedding")
                        },
                    )
                )

            return search_results

        except Exception as exc:
            if "not found" in str(exc).lower():
                raise CollectionNotFoundError(collection_name) from exc
            raise VectorStoreError(
                f"Search failed for tenant {tenant_id}: {exc}",
                details={"tenant_id": tenant_id},
            ) from exc

    async def upsert(self, chunks: list[Chunk]) -> int:
        """Upsert chunks with their embeddings into the tenant's collection.

        Args:
            chunks: List of Chunk objects with embeddings populated.

        Returns:
            Number of chunks upserted.
        """
        if not chunks:
            return 0

        # Group by tenant
        by_tenant: dict[str, list[Chunk]] = {}
        for chunk in chunks:
            by_tenant.setdefault(chunk.tenant_id, []).append(chunk)

        total_upserted = 0
        for tenant_id, tenant_chunks in by_tenant.items():
            collection_name = self._collection_name(tenant_id)

            points: list[models.PointStruct] = []
            for chunk in tenant_chunks:
                if not chunk.embedding:
                    logger.warning(
                        "Skipping chunk %s — no embedding", chunk.chunk_id
                    )
                    continue

                point_id = chunk.chunk_id or str(uuid4())
                payload = {
                    "document_id": chunk.document_id,
                    "tenant_id": chunk.tenant_id,
                    "text": chunk.text,
                    "text_hash": chunk.text_hash,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks,
                    "title": chunk.title,
                    "source_system": chunk.source_system,
                    "source_url": chunk.source_url,
                    "content_type": chunk.content_type,
                    "tags": chunk.tags,
                    "visibility": chunk.visibility,
                }

                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=chunk.embedding,
                        payload=payload,
                    )
                )

            if points:
                try:
                    # Batch upsert (Qdrant handles up to ~1000 per call)
                    batch_size = 500
                    for i in range(0, len(points), batch_size):
                        batch = points[i : i + batch_size]
                        await self._client.upsert(
                            collection_name=collection_name,
                            points=batch,
                        )
                    total_upserted += len(points)
                    logger.info(
                        "Upserted %d chunks to %s", len(points), collection_name
                    )
                except Exception as exc:
                    raise VectorStoreError(
                        f"Upsert failed for tenant {tenant_id}: {exc}",
                        details={"tenant_id": tenant_id, "count": len(points)},
                    ) from exc

        return total_upserted

    async def delete_by_document(self, document_id: str, tenant_id: str) -> int:
        """Delete all chunks belonging to a document.

        Returns:
            Estimated number of chunks deleted.
        """
        collection_name = self._collection_name(tenant_id)
        try:
            # Count before delete for reporting
            count_result = await self._client.count(
                collection_name=collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        ),
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                    ]
                ),
            )

            await self._client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            ),
                            models.FieldCondition(
                                key="tenant_id",
                                match=models.MatchValue(value=tenant_id),
                            ),
                        ]
                    )
                ),
            )

            deleted = count_result.count
            logger.info(
                "Deleted %d chunks for document %s in tenant %s",
                deleted,
                document_id,
                tenant_id,
            )
            return deleted

        except Exception as exc:
            raise VectorStoreError(
                f"Delete failed for document {document_id}: {exc}",
                details={"document_id": document_id, "tenant_id": tenant_id},
            ) from exc

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        await self._client.close()
