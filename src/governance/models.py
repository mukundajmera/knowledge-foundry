"""Knowledge Foundry — Governance Domain Models.

Defines SafetyPolicy, EvalSuite, EvalRun, and supporting types
for the safety, evaluation, and governance layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================
# ENUMS
# =============================================================


class SafetyAction(str, Enum):
    """Action to take when a safety violation is detected."""

    BLOCK = "block"
    FLAG = "flag"
    TRANSFORM = "transform"
    LOG_ONLY = "log_only"


class BlockedCategory(str, Enum):
    """Categories of content that can be blocked or flagged."""

    HALLUCINATION = "hallucination"
    TOXICITY = "toxicity"
    BIAS = "bias"
    PII_LEAK = "pii_leak"
    DATA_EXFILTRATION = "data_exfiltration"
    PROMPT_INJECTION = "prompt_injection"
    OFF_TOPIC = "off_topic"
    HARMFUL_CONTENT = "harmful_content"


class EvalMetricType(str, Enum):
    """Types of evaluation metrics."""

    FAITHFULNESS = "faithfulness"
    RELEVANCY = "relevancy"
    GROUNDEDNESS = "groundedness"
    TOXICITY = "toxicity"
    BIAS = "bias"
    LATENCY = "latency"
    COMPLETENESS = "completeness"
    CUSTOM = "custom"


class EvalRunStatus(str, Enum):
    """Status of an evaluation run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvalScheduleType(str, Enum):
    """When evaluations run."""

    ON_DEMAND = "on_demand"
    PRE_DEPLOYMENT = "pre_deployment"
    CONTINUOUS = "continuous"
    SCHEDULED = "scheduled"


class ViolationSeverity(str, Enum):
    """Severity level of a safety violation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# =============================================================
# SAFETY POLICY MODEL
# =============================================================


class SafetyRule(BaseModel):
    """A single rule within a safety policy."""

    rule_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    category: BlockedCategory
    action: SafetyAction = SafetyAction.BLOCK
    threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence threshold above which the action is triggered",
    )
    enabled: bool = True


class SafetyPolicy(BaseModel):
    """A safety policy that governs request/response behavior.

    Can be attached to a KnowledgeBase or ClientApp to enforce
    content safety, hallucination control, and data protection.
    """

    policy_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    rules: list[SafetyRule] = Field(default_factory=list)
    blocked_categories: list[BlockedCategory] = Field(default_factory=list)
    default_action: SafetyAction = SafetyAction.FLAG
    require_grounding: bool = Field(
        default=False,
        description="When true, responses must be grounded in retrieved context",
    )
    add_disclaimers: bool = Field(
        default=False,
        description="When true, add safety disclaimers to responses",
    )
    max_response_tokens: int | None = Field(
        default=None,
        description="Optional cap on response length for safety",
    )
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_active_rules(self) -> list[SafetyRule]:
        """Return only enabled rules."""
        return [r for r in self.rules if r.enabled]


# =============================================================
# EVALUATION SUITE MODEL
# =============================================================


class EvalProbe(BaseModel):
    """A single evaluation probe (test case) within a suite."""

    probe_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    input_query: str
    expected_output: str | None = None
    expected_citations: list[str] = Field(default_factory=list)
    metric_type: EvalMetricType = EvalMetricType.FAITHFULNESS
    threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable score for this probe",
    )
    tags: list[str] = Field(default_factory=list)


class EvalSuite(BaseModel):
    """An evaluation suite containing probes, metrics, and schedule.

    Can be attached to a KnowledgeBase or ClientApp for pre-deployment
    and continuous evaluation.
    """

    suite_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    probes: list[EvalProbe] = Field(default_factory=list)
    metrics: list[EvalMetricType] = Field(
        default_factory=lambda: [EvalMetricType.FAITHFULNESS, EvalMetricType.RELEVANCY],
    )
    schedule: EvalScheduleType = EvalScheduleType.ON_DEMAND
    sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fraction of production traffic to sample for continuous eval",
    )
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================
# EVALUATION RUN MODEL
# =============================================================


class EvalMetricResult(BaseModel):
    """Result of a single metric evaluation."""

    metric_type: EvalMetricType
    score: float = Field(ge=0.0, le=1.0)
    passed: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class EvalProbeResult(BaseModel):
    """Result of evaluating a single probe."""

    probe_id: UUID
    probe_name: str
    input_query: str
    actual_output: str | None = None
    metric_results: list[EvalMetricResult] = Field(default_factory=list)
    passed: bool = True
    latency_ms: int = 0
    error: str | None = None


class EvalRun(BaseModel):
    """An execution of an evaluation suite.

    Captures all probe results, aggregate metrics, and pass/fail status.
    """

    run_id: UUID = Field(default_factory=uuid4)
    suite_id: UUID
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    status: EvalRunStatus = EvalRunStatus.PENDING
    probe_results: list[EvalProbeResult] = Field(default_factory=list)
    aggregate_scores: dict[str, float] = Field(default_factory=dict)
    passed: bool = True
    total_probes: int = 0
    passed_probes: int = 0
    failed_probes: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================
# TELEMETRY & VIOLATION LOGGING
# =============================================================


class SafetyViolation(BaseModel):
    """A recorded safety violation or near-miss.

    Feeds into dashboards and governance reports.
    """

    violation_id: UUID = Field(default_factory=uuid4)
    policy_id: UUID
    rule_id: UUID | None = None
    category: BlockedCategory
    severity: ViolationSeverity
    action_taken: SafetyAction
    query: str = ""
    response_snippet: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    blocked: bool = False
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
