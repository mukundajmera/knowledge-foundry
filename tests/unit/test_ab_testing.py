"""Tests for A/B Testing Framework — experiments, assignment, analysis."""

from __future__ import annotations

import pytest

from src.improvement.ab_testing import (
    ExperimentManager,
    ExperimentDecision,
    ExperimentStatus,
)


class TestExperimentManager:
    def test_create_experiment(self) -> None:
        mgr = ExperimentManager()
        exp = mgr.create_experiment(
            experiment_id="exp-1",
            name="Test Experiment",
            hypothesis="Treatment improves quality",
        )
        assert exp.experiment_id == "exp-1"
        assert exp.status == ExperimentStatus.DRAFT

    def test_start_experiment(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        mgr.start_experiment("exp-1")
        assert mgr.get_experiment("exp-1").status == ExperimentStatus.RUNNING

    def test_deterministic_assignment(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        mgr.start_experiment("exp-1")

        # Same user always gets the same assignment
        v1 = mgr.assign_variant("exp-1", "user-abc")
        v2 = mgr.assign_variant("exp-1", "user-abc")
        assert v1 == v2
        assert v1 in ("control", "treatment")

    def test_assignment_not_running_returns_control(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        # Not started
        assert mgr.assign_variant("exp-1", "user-1") == "control"

    def test_assignment_nonexistent_returns_control(self) -> None:
        mgr = ExperimentManager()
        assert mgr.assign_variant("no-such", "user-1") == "control"

    def test_record_metrics(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        mgr.start_experiment("exp-1")
        mgr.record_metric("exp-1", "control", 0.90)
        mgr.record_metric("exp-1", "treatment", 0.95)
        exp = mgr.get_experiment("exp-1")
        assert exp.control.count == 1
        assert exp.treatment.count == 1

    def test_analyze_insufficient_data_extends(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        mgr.start_experiment("exp-1")
        mgr.record_metric("exp-1", "control", 0.90)
        # Only 1 per variant → too few
        result = mgr.analyze("exp-1")
        assert result.decision == ExperimentDecision.EXTEND_EXPERIMENT

    def test_analyze_significant_improvement_deploys(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment(
            "exp-1", "Test", "Treatment is better",
            primary_metric="quality",
            success_direction="higher",
        )
        mgr.start_experiment("exp-1")

        import random
        random.seed(42)
        # Control: centered around 0.80 with variance
        for _ in range(50):
            mgr.record_metric("exp-1", "control", 0.80 + random.gauss(0, 0.02))
        # Treatment: centered around 0.95 with variance (clearly better)
        for _ in range(50):
            mgr.record_metric("exp-1", "treatment", 0.95 + random.gauss(0, 0.02))

        result = mgr.analyze("exp-1")
        assert result.is_significant is True
        assert result.decision == ExperimentDecision.DEPLOY_TREATMENT
        assert result.improvement_pct > 0

    def test_analyze_no_improvement_keeps_control(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment(
            "exp-1", "Test", "No difference",
        )
        mgr.start_experiment("exp-1")

        import random
        random.seed(99)
        # Both variants roughly identical with variance
        for _ in range(50):
            val = 0.90 + random.gauss(0, 0.02)
            mgr.record_metric("exp-1", "control", val)
            mgr.record_metric("exp-1", "treatment", val + random.gauss(0, 0.001))

        result = mgr.analyze("exp-1")
        assert result.decision == ExperimentDecision.KEEP_CONTROL

    def test_experiment_concludes_after_analysis(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        mgr.start_experiment("exp-1")
        for _ in range(10):
            mgr.record_metric("exp-1", "control", 0.80)
            mgr.record_metric("exp-1", "treatment", 0.95)
        mgr.analyze("exp-1")
        assert mgr.get_experiment("exp-1").status == ExperimentStatus.CONCLUDED

    def test_list_experiments(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "First", "H1")
        mgr.create_experiment("exp-2", "Second", "H2")
        assert len(mgr.experiments) == 2

    def test_cohens_d_computed(self) -> None:
        mgr = ExperimentManager()
        mgr.create_experiment("exp-1", "Test", "Hypothesis")
        mgr.start_experiment("exp-1")
        import random
        random.seed(77)
        for _ in range(30):
            mgr.record_metric("exp-1", "control", 0.70 + random.gauss(0, 0.03))
            mgr.record_metric("exp-1", "treatment", 0.95 + random.gauss(0, 0.03))
        result = mgr.analyze("exp-1")
        assert result.cohens_d != 0.0
