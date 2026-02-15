"""Knowledge Foundry — Document Ingestion Route.

POST /v1/documents/ingest — ingest documents into the knowledge base.
DELETE /v1/documents/{document_id} — remove a document and its chunks.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.core.dependencies import ServiceContainer
from src.core.interfaces import Document

router = APIRouter(prefix="/v1/documents", tags=["documents"])
logger = logging.getLogger(__name__)


# --- Request / Response Schemas ---


class DocumentInput(BaseModel):
    """A single document to ingest."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, description="Document text content")
    source_system: str = Field(default="manual", max_length=100)
    source_url: str | None = Field(default=None, max_length=2000)
    author: str | None = Field(default=None, max_length=200)
    content_type: str = Field(default="documentation", max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=20)
    visibility: str = Field(default="internal")


class IngestRequest(BaseModel):
    """Request body for POST /v1/documents/ingest."""

    tenant_id: UUID = Field(..., description="Tenant ID for data isolation")
    documents: list[DocumentInput] = Field(
        ..., min_length=1, max_length=50, description="Documents to ingest"
    )


class IngestedDocumentInfo(BaseModel):
    """Info about a single ingested document."""

    document_id: str
    title: str
    chunk_count: int = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0


class IngestResponse(BaseModel):
    """Response body for POST /v1/documents/ingest."""

    ingested: list[IngestedDocumentInfo] = Field(default_factory=list)
    total_documents: int = 0
    total_chunks: int = 0


class DeleteResponse(BaseModel):
    """Response body for DELETE /v1/documents/{document_id}."""

    document_id: str
    chunks_deleted: int = 0


def _get_services(request: Request) -> ServiceContainer:
    """Get the service container from app state or raise 503."""
    container: ServiceContainer | None = getattr(request.app.state, "services", None)
    if not container:
        raise HTTPException(
            status_code=503,
            detail="Services not initialized. Start infrastructure services first.",
        )
    return container


# --- Routes ---


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(request_body: IngestRequest, request: Request) -> IngestResponse:
    """Ingest documents: chunk → embed → upsert into vector store.

    For each document:
    1. Create a Document model with a generated UUID.
    2. Chunk the document with the semantic chunker.
    3. Generate embeddings for each chunk.
    4. Upsert the embedded chunks into the vector store.
    """
    container = _get_services(request)

    if not container.chunker or not container.embedding_service or not container.vector_store:
        raise HTTPException(
            status_code=503,
            detail="Ingestion pipeline not fully initialized (missing chunker, embedding, or vector store).",
        )

    logger.info(
        "Ingest request: tenant=%s, documents=%d",
        request_body.tenant_id,
        len(request_body.documents),
    )

    try:
        # Ensure tenant collection exists
        await container.vector_store.ensure_collection(str(request_body.tenant_id))

        ingested: list[IngestedDocumentInfo] = []
        total_chunks = 0

        for doc_input in request_body.documents:
            # 1. Create Document model
            doc = Document(
                document_id=uuid4(),
                tenant_id=request_body.tenant_id,
                title=doc_input.title,
                content=doc_input.content,
                source_system=doc_input.source_system,
                source_url=doc_input.source_url,
                content_type=doc_input.content_type,
                tags=doc_input.tags,
                visibility=doc_input.visibility,
            )

            # 2. Chunk the document
            chunks = container.chunker.chunk_document(doc)

            # 3. Generate embeddings for chunk texts
            chunk_texts = [c.text for c in chunks]
            embeddings = await container.embedding_service.embed(chunk_texts)

            # 4. Attach embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

            # 5. Upsert to vector store
            upserted_count = await container.vector_store.upsert(chunks)

            # 6. (Optional) Extract entities and store in graph
            entities_count = 0
            rels_count = 0
            if container.entity_extractor and container.graph_store:
                try:
                    extraction_result = await container.entity_extractor.extract_from_document(
                        chunks=chunk_texts,
                        document_id=str(doc.document_id),
                    )
                    entities, relationships = container.entity_extractor.to_graph_models(
                        result=extraction_result,
                        tenant_id=str(request_body.tenant_id),
                    )
                    if entities or relationships:
                        await container.graph_store.add_entities(entities, relationships)
                    entities_count = len(entities)
                    rels_count = len(relationships)
                    logger.info(
                        "Extracted graph data: doc=%s, entities=%d, relationships=%d",
                        doc.document_id,
                        entities_count,
                        rels_count,
                    )
                except Exception as graph_exc:
                    logger.warning(
                        "Graph extraction failed (non-fatal): doc=%s, error=%s",
                        doc.document_id,
                        graph_exc,
                    )

            ingested.append(
                IngestedDocumentInfo(
                    document_id=str(doc.document_id),
                    title=doc.title,
                    chunk_count=len(chunks),
                    entities_extracted=entities_count,
                    relationships_extracted=rels_count,
                )
            )
            total_chunks += len(chunks)

            logger.info(
                "Ingested document: id=%s, title=%s, chunks=%d",
                doc.document_id,
                doc.title,
                len(chunks),
            )

        return IngestResponse(
            ingested=ingested,
            total_documents=len(ingested),
            total_chunks=total_chunks,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Ingestion failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {type(exc).__name__}",
        ) from exc


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: UUID, tenant_id: UUID, request: Request
) -> DeleteResponse:
    """Delete a document and all its chunks from the vector store."""
    container = _get_services(request)

    if not container.vector_store:
        raise HTTPException(
            status_code=503,
            detail="Vector store not initialized. Start infrastructure services first.",
        )

    logger.info(
        "Delete request: tenant=%s, document=%s",
        tenant_id,
        document_id,
    )

    try:
        chunks_deleted = await container.vector_store.delete_by_document(
            document_id=str(document_id),
            tenant_id=str(tenant_id),
        )

        return DeleteResponse(
            document_id=str(document_id),
            chunks_deleted=chunks_deleted,
        )

    except Exception as exc:
        logger.exception("Delete failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Delete failed: {type(exc).__name__}",
        ) from exc
