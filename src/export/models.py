"""Knowledge Foundry — Export Domain Models.

Defines canonical data structures for exportable entities and export configuration.
These models provide a unified representation that all exporters consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    """Types of entities that can be exported."""

    CONVERSATION = "conversation"
    MESSAGE = "message"
    RAG_RUN = "rag_run"
    EVALUATION_REPORT = "evaluation_report"


class ExportFormat(str, Enum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    JSON = "json"
    TEXT = "text"


@dataclass
class ExportOptions:
    """Configuration options for export generation.

    Attributes:
        include_metadata: Include entity metadata (timestamps, IDs, etc.)
        include_citations: Include source citations in export
        anonymize_user: Mask user identifiers for privacy
        include_raw_json_appendix: Append raw JSON data at end
        locale: Locale for date/time formatting
    """

    include_metadata: bool = True
    include_citations: bool = True
    anonymize_user: bool = False
    include_raw_json_appendix: bool = False
    locale: str = "en-US"


@dataclass
class ExportContext:
    """Context for export operations.

    Carries information about the user and tenant requesting the export.
    Used for authorization and audit logging.
    """

    user_id: str | None = None
    tenant_id: str | None = None
    request_id: str | None = None
    ip_address: str | None = None


@dataclass
class Citation:
    """A source citation in an exportable entity."""

    document_id: str
    title: str
    chunk_id: str | None = None
    section: str | None = None
    relevance_score: float = 0.0
    source_url: str | None = None


@dataclass
class ExportableMessage:
    """Canonical representation of an exportable message.

    Used for both individual message exports and as part of conversations.
    """

    id: str
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    citations: list[Citation] = field(default_factory=list)
    model: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportableConversation:
    """Canonical representation of an exportable conversation.

    Contains all messages and metadata for a complete conversation export.
    """

    id: str
    title: str
    messages: list[ExportableMessage]
    created_at: datetime
    updated_at: datetime
    tenant_id: str | None = None
    user_id: str | None = None
    model_info: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedContext:
    """A piece of retrieved context in a RAG run."""

    chunk_id: str
    document_id: str
    title: str
    text: str
    score: float
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportableRAGRun:
    """Canonical representation of an exportable RAG run.

    Contains the query, response, retrieved contexts, and evaluation metrics.
    """

    id: str
    query: str
    answer: str
    timestamp: datetime
    contexts: list[RetrievedContext] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    model: str | None = None
    model_tier: str | None = None
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    confidence: float | None = None
    # Evaluation metrics (if available)
    evaluation_metrics: dict[str, float] = field(default_factory=dict)
    tenant_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationMetric:
    """A single evaluation metric with name and value."""

    name: str
    value: float
    description: str | None = None
    threshold: float | None = None
    passed: bool | None = None


@dataclass
class EvaluationExample:
    """An example case from an evaluation report."""

    query: str
    expected: str | None
    actual: str
    metrics: dict[str, float] = field(default_factory=dict)
    passed: bool = True
    notes: str | None = None


@dataclass
class ExportableEvaluationReport:
    """Canonical representation of an exportable evaluation report.

    Contains metrics, scores, and example cases from RAG evaluation.
    """

    id: str
    title: str
    timestamp: datetime
    metrics: list[EvaluationMetric] = field(default_factory=list)
    examples: list[EvaluationExample] = field(default_factory=list)
    overall_score: float | None = None
    dataset_size: int = 0
    passed_count: int = 0
    failed_count: int = 0
    tenant_id: str | None = None
    model_info: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportRequest:
    """Request to generate an export.

    Encapsulates all information needed to perform an export operation.
    """

    entity_type: EntityType
    entity_id: str
    format_id: ExportFormat
    options: ExportOptions
    context: ExportContext


@dataclass
class ExportResult:
    """Result of an export operation.

    Contains either the generated content or error information.
    """

    success: bool
    content: bytes | None = None
    mime_type: str | None = None
    filename: str | None = None
    error: str | None = None
    # For audit
    entity_type: EntityType | None = None
    entity_id: str | None = None
    format_id: ExportFormat | None = None
    size_bytes: int = 0
    generation_time_ms: int = 0


@dataclass
class ExporterInfo:
    """Information about an available exporter.

    Returned by the registry to inform clients about available export options.
    """

    format_id: str
    label: str
    description: str
    mime_type: str
    extension: str
    supported_entity_types: list[EntityType]
    options_schema: dict[str, Any] = field(default_factory=dict)
