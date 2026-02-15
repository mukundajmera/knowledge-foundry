"""Knowledge Foundry — Export API Routes.

REST API endpoints for the export system.
Provides endpoints for listing available formats and generating exports.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.compliance.audit import AuditAction
from src.export import (
    EntityType,
    ExportableConversation,
    ExportableEvaluationReport,
    ExportableMessage,
    ExportableRAGRun,
    ExportContext,
    ExportFormat,
    ExportOptions,
    get_export_registry,
)
from src.export.models import Citation, RetrievedContext, EvaluationMetric, EvaluationExample

router = APIRouter(prefix="/v1/export", tags=["export"])
logger = logging.getLogger(__name__)


# Request/Response schemas


class ExportOptionSchema(BaseModel):
    """Export options from client."""

    include_metadata: bool = Field(default=True, description="Include entity metadata")
    include_citations: bool = Field(default=True, description="Include source citations")
    anonymize_user: bool = Field(default=False, description="Anonymize user identifiers")
    include_raw_json_appendix: bool = Field(default=False, description="Include raw JSON data")
    locale: str = Field(default="en-US", description="Locale for formatting")


class ExportFormatInfo(BaseModel):
    """Information about an available export format."""

    format_id: str
    label: str
    description: str
    mime_type: str
    extension: str
    supported_entity_types: list[str]
    options_schema: dict[str, Any] = Field(default_factory=dict)


class ListFormatsResponse(BaseModel):
    """Response from list formats endpoint."""

    formats: list[ExportFormatInfo]
    entity_type: str | None = None


class ExportRequest(BaseModel):
    """Request to generate an export."""

    entity_type: str = Field(..., description="Type of entity to export")
    entity_id: str = Field(..., description="ID of the entity to export")
    format_id: str = Field(..., description="Export format ID")
    options: ExportOptionSchema = Field(default_factory=ExportOptionSchema)
    # For inline data (frontend-provided)
    entity_data: dict[str, Any] | None = Field(
        default=None,
        description="Optional inline entity data (for client-side data)",
    )


class ExportStatusResponse(BaseModel):
    """Response with export status information."""

    success: bool
    message: str | None = None
    error: str | None = None
    filename: str | None = None
    size_bytes: int = 0
    generation_time_ms: int = 0


# Helper functions


def _parse_entity_type(entity_type_str: str) -> EntityType:
    """Parse entity type string to enum."""
    try:
        return EntityType(entity_type_str.lower())
    except ValueError:
        valid_types = [e.value for e in EntityType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type '{entity_type_str}'. Valid types: {valid_types}",
        )


def _parse_format_id(format_id_str: str) -> ExportFormat:
    """Parse format ID string to enum."""
    try:
        return ExportFormat(format_id_str.lower())
    except ValueError:
        valid_formats = [f.value for f in ExportFormat]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format '{format_id_str}'. Valid formats: {valid_formats}",
        )


def _build_conversation_from_data(data: dict[str, Any]) -> ExportableConversation:
    """Build ExportableConversation from client-provided data."""
    messages = []
    for msg_data in data.get("messages", []):
        citations = [
            Citation(
                document_id=c.get("document_id", ""),
                title=c.get("title", "Unknown"),
                chunk_id=c.get("chunk_id"),
                section=c.get("section"),
                relevance_score=c.get("relevance_score", 0.0),
            )
            for c in msg_data.get("citations", [])
        ]
        messages.append(
            ExportableMessage(
                id=msg_data.get("id", str(uuid4())),
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                timestamp=datetime.fromisoformat(msg_data["timestamp"])
                if isinstance(msg_data.get("timestamp"), str)
                else datetime.fromtimestamp(msg_data.get("timestamp", 0) / 1000)
                if isinstance(msg_data.get("timestamp"), (int, float))
                else datetime.now(),
                citations=citations,
                model=msg_data.get("model"),
                confidence=msg_data.get("confidence"),
                latency_ms=msg_data.get("latency_ms"),
                cost_usd=msg_data.get("cost_usd"),
            )
        )

    created_at = data.get("createdAt") or data.get("created_at")
    updated_at = data.get("updatedAt") or data.get("updated_at")

    return ExportableConversation(
        id=data.get("id", str(uuid4())),
        title=data.get("title", "Conversation"),
        messages=messages,
        created_at=datetime.fromtimestamp(created_at / 1000) if isinstance(created_at, (int, float)) else datetime.now(),
        updated_at=datetime.fromtimestamp(updated_at / 1000) if isinstance(updated_at, (int, float)) else datetime.now(),
        tenant_id=data.get("tenant_id"),
        user_id=data.get("user_id"),
        model_info=data.get("model_info"),
    )


def _build_message_from_data(data: dict[str, Any]) -> ExportableMessage:
    """Build ExportableMessage from client-provided data."""
    citations = [
        Citation(
            document_id=c.get("document_id", ""),
            title=c.get("title", "Unknown"),
            chunk_id=c.get("chunk_id"),
            section=c.get("section"),
            relevance_score=c.get("relevance_score", 0.0),
        )
        for c in data.get("citations", [])
    ]

    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        ts = datetime.fromisoformat(timestamp)
    elif isinstance(timestamp, (int, float)):
        ts = datetime.fromtimestamp(timestamp / 1000)
    else:
        ts = datetime.now()

    return ExportableMessage(
        id=data.get("id", str(uuid4())),
        role=data.get("role", "assistant"),
        content=data.get("content", ""),
        timestamp=ts,
        citations=citations,
        model=data.get("model"),
        confidence=data.get("confidence"),
        latency_ms=data.get("latency_ms"),
        cost_usd=data.get("cost_usd"),
    )


def _build_rag_run_from_data(data: dict[str, Any]) -> ExportableRAGRun:
    """Build ExportableRAGRun from client-provided data."""
    contexts = [
        RetrievedContext(
            chunk_id=c.get("chunk_id", ""),
            document_id=c.get("document_id", ""),
            title=c.get("title", "Unknown"),
            text=c.get("text", ""),
            score=c.get("score", 0.0),
        )
        for c in data.get("contexts", [])
    ]

    citations = [
        Citation(
            document_id=c.get("document_id", ""),
            title=c.get("title", "Unknown"),
            chunk_id=c.get("chunk_id"),
            section=c.get("section"),
            relevance_score=c.get("relevance_score", 0.0),
        )
        for c in data.get("citations", [])
    ]

    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        ts = datetime.fromisoformat(timestamp)
    elif isinstance(timestamp, (int, float)):
        ts = datetime.fromtimestamp(timestamp / 1000)
    else:
        ts = datetime.now()

    return ExportableRAGRun(
        id=data.get("id", str(uuid4())),
        query=data.get("query", ""),
        answer=data.get("answer", ""),
        timestamp=ts,
        contexts=contexts,
        citations=citations,
        model=data.get("model"),
        model_tier=data.get("model_tier"),
        latency_ms=data.get("latency_ms", 0),
        input_tokens=data.get("input_tokens", 0),
        output_tokens=data.get("output_tokens", 0),
        cost_usd=data.get("cost_usd", 0.0),
        confidence=data.get("confidence"),
        evaluation_metrics=data.get("evaluation_metrics", {}),
        tenant_id=data.get("tenant_id"),
    )


def _build_evaluation_report_from_data(data: dict[str, Any]) -> ExportableEvaluationReport:
    """Build ExportableEvaluationReport from client-provided data."""
    metrics = [
        EvaluationMetric(
            name=m.get("name", "Unknown"),
            value=m.get("value", 0.0),
            description=m.get("description"),
            threshold=m.get("threshold"),
            passed=m.get("passed"),
        )
        for m in data.get("metrics", [])
    ]

    examples = [
        EvaluationExample(
            query=e.get("query", ""),
            expected=e.get("expected"),
            actual=e.get("actual", ""),
            metrics=e.get("metrics", {}),
            passed=e.get("passed", True),
            notes=e.get("notes"),
        )
        for e in data.get("examples", [])
    ]

    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        ts = datetime.fromisoformat(timestamp)
    elif isinstance(timestamp, (int, float)):
        ts = datetime.fromtimestamp(timestamp / 1000)
    else:
        ts = datetime.now()

    return ExportableEvaluationReport(
        id=data.get("id", str(uuid4())),
        title=data.get("title", "Evaluation Report"),
        timestamp=ts,
        metrics=metrics,
        examples=examples,
        overall_score=data.get("overall_score"),
        dataset_size=data.get("dataset_size", 0),
        passed_count=data.get("passed_count", 0),
        failed_count=data.get("failed_count", 0),
        tenant_id=data.get("tenant_id"),
        model_info=data.get("model_info"),
    )


# API Endpoints


@router.get("/formats", response_model=ListFormatsResponse)
async def list_formats(
    entity_type: str | None = None,
) -> ListFormatsResponse:
    """List available export formats.

    Optionally filter by entity type to show only formats that support
    exporting that type of entity.

    Args:
        entity_type: Optional filter by entity type (conversation, message, rag_run, evaluation_report)

    Returns:
        List of available export formats with their metadata
    """
    registry = get_export_registry()

    # Parse entity type if provided
    entity_type_enum = None
    if entity_type:
        entity_type_enum = _parse_entity_type(entity_type)

    # Get formats from registry
    formats = registry.list_formats(entity_type_enum)

    return ListFormatsResponse(
        formats=[
            ExportFormatInfo(
                format_id=f.format_id,
                label=f.label,
                description=f.description,
                mime_type=f.mime_type,
                extension=f.extension,
                supported_entity_types=[e.value for e in f.supported_entity_types],
                options_schema=f.options_schema,
            )
            for f in formats
        ],
        entity_type=entity_type,
    )


@router.post("/generate")
async def generate_export(
    request_body: ExportRequest,
    request: Request,
) -> Response:
    """Generate an export for an entity.

    Creates an export in the specified format and returns it as a downloadable file.

    For entities stored in the backend, provide entity_type and entity_id.
    For client-side data (e.g., conversations stored in localStorage),
    provide entity_data with the full entity structure.

    Args:
        request_body: Export request with entity info and options

    Returns:
        File response with the exported content
    """
    registry = get_export_registry()

    # Parse request
    entity_type = _parse_entity_type(request_body.entity_type)
    format_id = _parse_format_id(request_body.format_id)

    # Build export options
    options = ExportOptions(
        include_metadata=request_body.options.include_metadata,
        include_citations=request_body.options.include_citations,
        anonymize_user=request_body.options.anonymize_user,
        include_raw_json_appendix=request_body.options.include_raw_json_appendix,
        locale=request_body.options.locale,
    )

    # Build context
    context = ExportContext(
        request_id=str(uuid4()),
    )

    # Build entity from provided data or fetch from backend
    entity = None
    if request_body.entity_data:
        # Client-provided data
        if entity_type == EntityType.CONVERSATION:
            entity = _build_conversation_from_data(request_body.entity_data)
        elif entity_type == EntityType.MESSAGE:
            entity = _build_message_from_data(request_body.entity_data)
        elif entity_type == EntityType.RAG_RUN:
            entity = _build_rag_run_from_data(request_body.entity_data)
        elif entity_type == EntityType.EVALUATION_REPORT:
            entity = _build_evaluation_report_from_data(request_body.entity_data)
    else:
        # TODO: Fetch from backend storage when implemented
        raise HTTPException(
            status_code=400,
            detail="entity_data is required. Backend entity fetching not yet implemented.",
        )

    if not entity:
        raise HTTPException(
            status_code=400,
            detail="Failed to build entity from provided data",
        )

    # Execute export
    result = registry.export(
        entity=entity,
        entity_type=entity_type,
        format_id=format_id,
        options=options,
        context=context,
    )

    if not result.success:
        logger.error("Export failed: %s", result.error)
        raise HTTPException(
            status_code=500,
            detail=result.error or "Export generation failed",
        )

    # Log to audit trail if available
    audit_trail = getattr(request.app.state, "audit_trail", None)
    if audit_trail:
        audit_trail.log(
            AuditAction.QUERY,  # Reuse query action for now
            tenant_id=context.tenant_id or "",
            user_id=context.user_id or "",
            input_text=f"Export {entity_type.value} to {format_id.value}",
            output_text=f"Generated {result.size_bytes} bytes",
            metadata={
                "action": "export",
                "entity_type": entity_type.value,
                "entity_id": request_body.entity_id,
                "format": format_id.value,
                "size_bytes": result.size_bytes,
                "generation_time_ms": result.generation_time_ms,
            },
        )

    # Return file response
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Export-Size-Bytes": str(result.size_bytes),
            "X-Export-Generation-Time-Ms": str(result.generation_time_ms),
        },
    )


@router.get("/formats/{format_id}")
async def get_format_info(format_id: str) -> ExportFormatInfo:
    """Get detailed information about a specific export format.

    Args:
        format_id: The format ID to get info for

    Returns:
        Format information including options schema
    """
    registry = get_export_registry()

    exporter = registry.get_exporter(format_id)
    if not exporter:
        raise HTTPException(
            status_code=404,
            detail=f"Export format '{format_id}' not found",
        )

    return ExportFormatInfo(
        format_id=exporter.format_id,
        label=exporter.label,
        description=exporter.description,
        mime_type=exporter.mime_type,
        extension=exporter.extension,
        supported_entity_types=[e.value for e in exporter.supported_entity_types],
        options_schema=exporter.get_options_schema(),
    )
