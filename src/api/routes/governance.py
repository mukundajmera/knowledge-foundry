"""Knowledge Foundry — Governance API.

Endpoints for managing safety policies, evaluation suites, and running
evaluations against knowledge bases.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.governance.models import (
    BlockedCategory,
    EvalMetricType,
    EvalProbe,
    EvalRun,
    EvalScheduleType,
    EvalSuite,
    SafetyAction,
    SafetyPolicy,
    SafetyRule,
    SafetyViolation,
)
from src.governance.safety import SafetyEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/governance", tags=["Governance"])

# In-memory stores (replaced by DB in production)
_safety_policies: dict[UUID, SafetyPolicy] = {}
_eval_suites: dict[UUID, EvalSuite] = {}
_eval_runs: dict[UUID, EvalRun] = {}
_safety_engine = SafetyEngine()


# =============================================================
# REQUEST SCHEMAS
# =============================================================


class CreateSafetyPolicyRequest(BaseModel):
    """Request to create a safety policy."""

    name: str
    description: str = ""
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    blocked_categories: list[BlockedCategory] = Field(default_factory=list)
    default_action: SafetyAction = SafetyAction.FLAG
    require_grounding: bool = False
    add_disclaimers: bool = False
    rules: list[dict[str, Any]] = Field(default_factory=list)


class CreateEvalSuiteRequest(BaseModel):
    """Request to create an evaluation suite."""

    name: str
    description: str = ""
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    metrics: list[EvalMetricType] = Field(
        default_factory=lambda: [EvalMetricType.FAITHFULNESS, EvalMetricType.RELEVANCY],
    )
    schedule: EvalScheduleType = EvalScheduleType.ON_DEMAND
    sample_rate: float = 0.1
    probes: list[dict[str, Any]] = Field(default_factory=list)


class SafetyCheckRequest(BaseModel):
    """Request to check content against safety policies."""

    text: str
    knowledge_base_id: UUID | None = None
    client_id: UUID | None = None
    check_type: str = "request"  # "request" or "response"


# =============================================================
# SAFETY POLICY ENDPOINTS
# =============================================================


@router.post("/safety-policies", status_code=201)
async def create_safety_policy(req: CreateSafetyPolicyRequest) -> dict[str, Any]:
    """Create a new safety policy."""
    rules = [
        SafetyRule(
            name=r.get("name", f"rule-{i}"),
            category=BlockedCategory(r["category"]),
            action=SafetyAction(r.get("action", "flag")),
            threshold=r.get("threshold", 0.8),
        )
        for i, r in enumerate(req.rules)
    ]

    policy = SafetyPolicy(
        name=req.name,
        description=req.description,
        knowledge_base_id=req.knowledge_base_id,
        client_id=req.client_id,
        rules=rules,
        blocked_categories=req.blocked_categories,
        default_action=req.default_action,
        require_grounding=req.require_grounding,
        add_disclaimers=req.add_disclaimers,
    )
    _safety_policies[policy.policy_id] = policy
    _safety_engine.add_policy(policy)

    return {
        "policy_id": str(policy.policy_id),
        "name": policy.name,
        "rule_count": len(policy.rules),
    }


@router.get("/safety-policies")
async def list_safety_policies() -> list[dict[str, Any]]:
    """List all safety policies."""
    return [
        {
            "policy_id": str(p.policy_id),
            "name": p.name,
            "rule_count": len(p.rules),
            "enabled": p.enabled,
            "knowledge_base_id": str(p.knowledge_base_id) if p.knowledge_base_id else None,
            "client_id": str(p.client_id) if p.client_id else None,
        }
        for p in _safety_policies.values()
    ]


@router.get("/safety-policies/{policy_id}")
async def get_safety_policy(policy_id: UUID) -> dict[str, Any]:
    """Get details of a safety policy."""
    policy = _safety_policies.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Safety policy not found")
    return policy.model_dump(mode="json")


@router.post("/safety-check")
async def check_safety(req: SafetyCheckRequest) -> dict[str, Any]:
    """Check content against active safety policies."""
    if req.check_type == "response":
        result = _safety_engine.check_response(
            response_text=req.text,
            knowledge_base_id=req.knowledge_base_id,
            client_id=req.client_id,
        )
    else:
        result = _safety_engine.check_request(
            query=req.text,
            knowledge_base_id=req.knowledge_base_id,
            client_id=req.client_id,
        )

    return {
        "allowed": result.allowed,
        "blocked": result.blocked,
        "violation_count": len(result.violations),
        "violations": [
            {
                "category": v.category.value,
                "severity": v.severity.value,
                "action": v.action_taken.value,
                "confidence": v.confidence,
            }
            for v in result.violations
        ],
    }


@router.get("/violations")
async def list_violations() -> list[dict[str, Any]]:
    """List all recorded safety violations."""
    return [
        {
            "violation_id": str(v.violation_id),
            "category": v.category.value,
            "severity": v.severity.value,
            "action_taken": v.action_taken.value,
            "confidence": v.confidence,
            "blocked": v.blocked,
            "timestamp": v.timestamp.isoformat(),
        }
        for v in _safety_engine.violations
    ]


# =============================================================
# EVALUATION SUITE ENDPOINTS
# =============================================================


@router.post("/eval-suites", status_code=201)
async def create_eval_suite(req: CreateEvalSuiteRequest) -> dict[str, Any]:
    """Create an evaluation suite."""
    probes = [
        EvalProbe(
            name=p.get("name", f"probe-{i}"),
            input_query=p["input_query"],
            expected_output=p.get("expected_output"),
            metric_type=EvalMetricType(p.get("metric_type", "faithfulness")),
            threshold=p.get("threshold", 0.9),
        )
        for i, p in enumerate(req.probes)
    ]

    suite = EvalSuite(
        name=req.name,
        description=req.description,
        knowledge_base_id=req.knowledge_base_id,
        client_id=req.client_id,
        probes=probes,
        metrics=req.metrics,
        schedule=req.schedule,
        sample_rate=req.sample_rate,
    )
    _eval_suites[suite.suite_id] = suite

    return {
        "suite_id": str(suite.suite_id),
        "name": suite.name,
        "probe_count": len(suite.probes),
    }


@router.get("/eval-suites")
async def list_eval_suites() -> list[dict[str, Any]]:
    """List all evaluation suites."""
    return [
        {
            "suite_id": str(s.suite_id),
            "name": s.name,
            "probe_count": len(s.probes),
            "schedule": s.schedule.value,
            "enabled": s.enabled,
        }
        for s in _eval_suites.values()
    ]


@router.get("/eval-suites/{suite_id}")
async def get_eval_suite(suite_id: UUID) -> dict[str, Any]:
    """Get details of an evaluation suite."""
    suite = _eval_suites.get(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Evaluation suite not found")
    return suite.model_dump(mode="json")


@router.get("/eval-runs")
async def list_eval_runs() -> list[dict[str, Any]]:
    """List all evaluation runs."""
    return [
        {
            "run_id": str(r.run_id),
            "suite_id": str(r.suite_id),
            "status": r.status.value,
            "passed": r.passed,
            "total_probes": r.total_probes,
            "passed_probes": r.passed_probes,
            "failed_probes": r.failed_probes,
            "created_at": r.created_at.isoformat(),
        }
        for r in _eval_runs.values()
    ]


@router.get("/eval-runs/{run_id}")
async def get_eval_run(run_id: UUID) -> dict[str, Any]:
    """Get details of an evaluation run."""
    run = _eval_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run.model_dump(mode="json")
