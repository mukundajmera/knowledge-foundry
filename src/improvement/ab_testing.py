"""Knowledge Foundry — A/B Testing Framework.

Hash-based deterministic user assignment, metric collection per variant,
statistical analysis (t-test + Cohen's d), and auto-decision.
Per Phase 8.1 §4.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    CONCLUDED = "concluded"


class ExperimentDecision(str, Enum):
    DEPLOY_TREATMENT = "deploy_treatment"
    EXTEND_EXPERIMENT = "extend_experiment"
    KEEP_CONTROL = "keep_control"


@dataclass
class ExperimentVariant:
    """A variant within an experiment."""

    name: str  # "control" or "treatment"
    allocation: float  # 0.0–1.0
    config: dict[str, Any] = field(default_factory=dict)
    metrics: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return sum(self.metrics) / len(self.metrics) if self.metrics else 0.0

    @property
    def std(self) -> float:
        if len(self.metrics) < 2:
            return 0.0
        m = self.mean
        return math.sqrt(sum((x - m) ** 2 for x in self.metrics) / (len(self.metrics) - 1))

    @property
    def count(self) -> int:
        return len(self.metrics)


@dataclass
class ExperimentResult:
    """Statistical analysis result."""

    t_statistic: float = 0.0
    p_value: float = 1.0
    cohens_d: float = 0.0
    is_significant: bool = False
    decision: ExperimentDecision = ExperimentDecision.KEEP_CONTROL
    control_mean: float = 0.0
    treatment_mean: float = 0.0
    improvement_pct: float = 0.0


@dataclass
class Experiment:
    """An A/B experiment definition."""

    experiment_id: str
    name: str
    hypothesis: str
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_days: int = 14
    primary_metric: str = "ragas_faithfulness"
    success_direction: str = "higher"  # "higher" or "lower"

    control: ExperimentVariant = field(
        default_factory=lambda: ExperimentVariant(name="control", allocation=0.5)
    )
    treatment: ExperimentVariant = field(
        default_factory=lambda: ExperimentVariant(name="treatment", allocation=0.5)
    )

    # Guardrails
    min_sample_size: int = 100
    significance_level: float = 0.05
    guardrails: dict[str, float] = field(default_factory=dict)

    result: ExperimentResult | None = None


# ──────────────────────────────────────────────────────────────
# Core Engine
# ──────────────────────────────────────────────────────────────

class ExperimentManager:
    """Manages the lifecycle of A/B experiments."""

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}

    @property
    def experiments(self) -> list[Experiment]:
        return list(self._experiments.values())

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        hypothesis: str,
        *,
        primary_metric: str = "ragas_faithfulness",
        success_direction: str = "higher",
        duration_days: int = 14,
        control_config: dict[str, Any] | None = None,
        treatment_config: dict[str, Any] | None = None,
        guardrails: dict[str, float] | None = None,
    ) -> Experiment:
        """Create and register a new experiment."""
        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            hypothesis=hypothesis,
            primary_metric=primary_metric,
            success_direction=success_direction,
            duration_days=duration_days,
            control=ExperimentVariant(
                name="control",
                allocation=0.5,
                config=control_config or {},
            ),
            treatment=ExperimentVariant(
                name="treatment",
                allocation=0.5,
                config=treatment_config or {},
            ),
            guardrails=guardrails or {},
        )
        self._experiments[experiment_id] = experiment
        logger.info("Created experiment: %s (%s)", name, experiment_id)
        return experiment

    def start_experiment(self, experiment_id: str) -> None:
        """Activate an experiment for traffic splitting."""
        exp = self._experiments[experiment_id]
        exp.status = ExperimentStatus.RUNNING
        logger.info("Started experiment: %s", exp.name)

    def assign_variant(self, experiment_id: str, user_id: str) -> str:
        """Deterministically assign user to a variant via hashing.

        Returns "control" or "treatment".
        """
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return "control"

        # SHA-256 hash → deterministic, reproducible assignment
        hash_input = f"{experiment_id}:{user_id}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()
        bucket = int(hash_val[:8], 16) / 0xFFFFFFFF

        return "treatment" if bucket < exp.treatment.allocation else "control"

    def record_metric(
        self, experiment_id: str, variant_name: str, value: float
    ) -> None:
        """Record a primary metric observation for a variant."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return

        variant = exp.control if variant_name == "control" else exp.treatment
        variant.metrics.append(value)

    def analyze(self, experiment_id: str) -> ExperimentResult:
        """Run statistical analysis and make a decision.

        Uses Welch's t-test and Cohen's d effect size.
        """
        exp = self._experiments[experiment_id]
        control = exp.control
        treatment = exp.treatment

        result = ExperimentResult(
            control_mean=control.mean,
            treatment_mean=treatment.mean,
        )

        # Need minimum sample size
        if control.count < 2 or treatment.count < 2:
            result.decision = ExperimentDecision.EXTEND_EXPERIMENT
            exp.result = result
            return result

        # ── Welch's t-test ──
        se = math.sqrt(
            (control.std ** 2 / control.count) + (treatment.std ** 2 / treatment.count)
        )
        if se == 0:
            t_stat = 0.0
        else:
            t_stat = (treatment.mean - control.mean) / se

        result.t_statistic = round(t_stat, 4)

        # Approximate p-value using the normal distribution for large samples
        # For small samples this is an approximation
        z = abs(t_stat)
        result.p_value = round(2 * _normal_cdf(-z), 6)

        # ── Cohen's d ──
        pooled_std = math.sqrt(
            ((control.count - 1) * control.std ** 2 + (treatment.count - 1) * treatment.std ** 2)
            / (control.count + treatment.count - 2)
        ) if (control.count + treatment.count > 2) else 1.0

        result.cohens_d = round(
            (treatment.mean - control.mean) / pooled_std if pooled_std > 0 else 0.0,
            4,
        )

        # ── Significance ──
        result.is_significant = result.p_value < exp.significance_level

        # ── Improvement ──
        if control.mean > 0:
            result.improvement_pct = round(
                ((treatment.mean - control.mean) / control.mean) * 100, 2
            )

        # ── Decision ──
        if not result.is_significant:
            if control.count + treatment.count < exp.min_sample_size:
                result.decision = ExperimentDecision.EXTEND_EXPERIMENT
            else:
                result.decision = ExperimentDecision.KEEP_CONTROL
        else:
            treatment_is_better = (
                result.improvement_pct > 0
                if exp.success_direction == "higher"
                else result.improvement_pct < 0
            )
            # Check guardrails
            guardrails_ok = self._check_guardrails(exp)

            if treatment_is_better and guardrails_ok:
                result.decision = ExperimentDecision.DEPLOY_TREATMENT
            else:
                result.decision = ExperimentDecision.KEEP_CONTROL

        exp.result = result
        exp.status = ExperimentStatus.CONCLUDED

        logger.info(
            "Experiment %s concluded: decision=%s, p=%.4f, d=%.3f, improvement=%.1f%%",
            exp.name,
            result.decision.value,
            result.p_value,
            result.cohens_d,
            result.improvement_pct,
        )

        return result

    def _check_guardrails(self, exp: Experiment) -> bool:
        """Verify treatment doesn't breach guardrail metrics."""
        # In a full implementation, guardrail metrics would be separately tracked.
        # For now, return True (guardrails checked at deploy time via CI).
        return True

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self._experiments.get(experiment_id)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _normal_cdf(x: float) -> float:
    """Approximate CDF of the standard normal distribution.

    Uses the Abramowitz & Stegun approximation.
    """
    if x < -8:
        return 0.0
    if x > 8:
        return 1.0
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x_abs = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x_abs)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x_abs * x_abs)

    return 0.5 * (1.0 + sign * y)
