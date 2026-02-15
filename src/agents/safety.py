"""Knowledge Foundry — Safety Agent.

Always-on guardrail agent that checks for prompt injection, PII exposure,
harmful content, and jailbreak attempts. Uses Haiku for fast, deterministic checks.
Per phase-2.1 spec §2.5.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier

logger = structlog.get_logger(__name__)

# Regex patterns for common threats
INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions?|prompts?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|a)\s+", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(instructions?|system)", re.IGNORECASE),
    re.compile(r"<\s*/?system\s*>", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]

PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{16}\b"),  # Credit card (simple)
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # Phone (US)
]

SAFETY_SYSTEM_PROMPT = """\
You are a safety check agent. Analyze the following output for:
1. Harmful content (violence, hate speech, illegal activities)
2. PII exposure (personal data, credentials)
3. Prompt injection artifacts (system prompt leaks)
4. Misinformation (fabricated facts without source)

Return JSON:
{{
  "safe": true/false,
  "threats": [
    {{"type": "...", "severity": "low|medium|high|critical", "description": "..."}}
  ],
  "action": "ALLOW|BLOCK|SANITIZE",
  "sanitized_output": null
}}
"""


class ThreatDetection:
    """A detected threat in input or output."""

    def __init__(
        self,
        threat_type: str,
        severity: str,
        description: str,
        evidence: str = "",
    ) -> None:
        self.threat_type = threat_type
        self.severity = severity
        self.description = description
        self.evidence = evidence

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.threat_type,
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence,
        }


def check_input_safety(text: str) -> list[ThreatDetection]:
    """Fast regex-based input safety check (no LLM required)."""
    threats: list[ThreatDetection] = []

    # Prompt injection
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            threats.append(
                ThreatDetection(
                    threat_type="prompt_injection",
                    severity="high",
                    description="Potential prompt injection detected",
                    evidence=match.group(),
                )
            )
            break  # One injection detection is enough

    return threats


def check_output_safety(text: str) -> list[ThreatDetection]:
    """Fast regex-based output safety check for PII."""
    threats: list[ThreatDetection] = []

    for pattern in PII_PATTERNS:
        match = pattern.search(text)
        if match:
            threats.append(
                ThreatDetection(
                    threat_type="pii_exposure",
                    severity="high",
                    description="Potential PII detected in output",
                    evidence=match.group()[:20] + "***",
                )
            )

    return threats


async def safety_check_node(state: OrchestratorState) -> dict[str, Any]:
    """Safety agent node — validates final answer before delivery.

    Combines fast regex checks with optional LLM-based analysis.
    """
    final_answer = state.get("final_answer", "")
    user_query = state.get("user_query", "")

    # Phase 1: Fast regex checks
    input_threats = check_input_safety(user_query)
    output_threats = check_output_safety(final_answer)
    all_threats = input_threats + output_threats

    # Determine action based on threat severity
    action = "ALLOW"
    if any(t.severity == "critical" for t in all_threats):
        action = "BLOCK"
    elif any(t.severity == "high" for t in all_threats):
        action = "SANITIZE"

    # Phase 2: LLM-based check (if provider available and answer exists)
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if llm_provider and final_answer and action == "ALLOW":
        try:
            config = LLMConfig(
                model="",
                tier=ModelTier.HAIKU,
                temperature=0.0,
                max_tokens=512,
                system_prompt=SAFETY_SYSTEM_PROMPT,
            )
            response = await llm_provider.generate(
                f"User input: {user_query[:500]}\n\nSystem output: {final_answer[:2000]}",
                config,
            )

            # Parse LLM safety verdict
            try:
                verdict = json.loads(response.text)
                if not verdict.get("safe", True):
                    llm_threats = verdict.get("threats", [])
                    for t in llm_threats:
                        all_threats.append(
                            ThreatDetection(
                                threat_type=t.get("type", "unknown"),
                                severity=t.get("severity", "medium"),
                                description=t.get("description", ""),
                            )
                        )
                    action = verdict.get("action", "ALLOW")
            except (json.JSONDecodeError, AttributeError):
                pass  # LLM returned non-JSON; treat as safe
        except Exception as exc:
            logger.warning("safety.llm_check_failed", error=str(exc))

    # Build verdict
    safe = action == "ALLOW"
    safety_verdict = {
        "safe": safe,
        "threats": [t.to_dict() for t in all_threats],
        "action": action,
    }

    # Block: replace answer with safe message
    blocked_answer = final_answer
    if action == "BLOCK":
        blocked_answer = (
            "I'm unable to provide a response to this query as it was flagged "
            "by our safety system. Please rephrase your question."
        )

    return {
        "safety_verdict": safety_verdict,
        "final_answer": blocked_answer,
        "next_agent": "hitl_gate",
    }


async def hitl_gate_node(state: OrchestratorState) -> dict[str, Any]:
    """Human-in-the-loop gate — determines if human review is needed."""
    hitl_required = state.get("hitl_required", False)
    confidence = state.get("confidence", 0.0)
    deployment_context = state.get("deployment_context", "general")

    # Require HITL for low confidence or high-risk contexts
    if confidence < 0.6:
        hitl_required = True
        hitl_reason = f"Low confidence: {confidence:.2f}"
    elif deployment_context in ("hr_screening", "financial", "legal"):
        hitl_required = True
        hitl_reason = f"High-risk deployment context: {deployment_context}"
    else:
        hitl_reason = None

    safety_verdict = state.get("safety_verdict") or {}
    if safety_verdict.get("action") == "SANITIZE":
        hitl_required = True
        hitl_reason = "Content was sanitized by safety agent"

    return {
        "hitl_required": hitl_required,
        "hitl_reason": hitl_reason,
        "next_agent": None,  # End of graph
    }
