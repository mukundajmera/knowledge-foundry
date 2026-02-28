"""Knowledge Foundry — Evaluation Engine.

Executes evaluation suites against knowledge bases, running probes
and computing aggregate metrics for pre-deployment and continuous eval.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from src.governance.models import (
    EvalMetricResult,
    EvalMetricType,
    EvalProbe,
    EvalProbeResult,
    EvalRun,
    EvalRunStatus,
    EvalSuite,
)

logger = logging.getLogger(__name__)


class RetrievalCallable(Protocol):
    """Protocol for a callable that performs retrieval."""

    async def __call__(self, query: str, knowledge_base_id: UUID | None = None) -> str: ...


class EvalEngine:
    """Executes evaluation suites and produces EvalRun results.

    Usage::

        engine = EvalEngine(retrieval_fn=my_retrieval_function)
        run = await engine.run_suite(suite)
    """

    def __init__(
        self,
        retrieval_fn: RetrievalCallable | None = None,
    ) -> None:
        self._retrieval_fn = retrieval_fn

    async def run_suite(
        self,
        suite: EvalSuite,
        knowledge_base_id: UUID | None = None,
        client_id: UUID | None = None,
    ) -> EvalRun:
        """Execute all probes in an evaluation suite.

        Returns an EvalRun with per-probe results and aggregate scores.
        """
        run = EvalRun(
            suite_id=suite.suite_id,
            knowledge_base_id=knowledge_base_id or suite.knowledge_base_id,
            client_id=client_id or suite.client_id,
            status=EvalRunStatus.RUNNING,
            total_probes=len(suite.probes),
            started_at=datetime.now(timezone.utc),
        )

        probe_results: list[EvalProbeResult] = []
        passed_count = 0

        for probe in suite.probes:
            result = await self._run_probe(probe, knowledge_base_id)
            probe_results.append(result)
            if result.passed:
                passed_count += 1

        # Compute aggregate scores per metric type
        aggregate: dict[str, list[float]] = {}
        for pr in probe_results:
            for mr in pr.metric_results:
                key = mr.metric_type.value
                aggregate.setdefault(key, []).append(mr.score)

        aggregate_scores = {
            k: sum(v) / len(v) if v else 0.0 for k, v in aggregate.items()
        }

        run.probe_results = probe_results
        run.aggregate_scores = aggregate_scores
        run.passed_probes = passed_count
        run.failed_probes = len(suite.probes) - passed_count
        run.passed = run.failed_probes == 0
        run.status = EvalRunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Eval suite completed: suite=%s passed=%d/%d",
            suite.name,
            passed_count,
            len(suite.probes),
        )
        return run

    async def _run_probe(
        self,
        probe: EvalProbe,
        knowledge_base_id: UUID | None = None,
    ) -> EvalProbeResult:
        """Execute a single evaluation probe."""
        start = time.monotonic()
        actual_output: str | None = None
        error: str | None = None

        try:
            if self._retrieval_fn:
                actual_output = await self._retrieval_fn(
                    probe.input_query,
                    knowledge_base_id,
                )
        except Exception as exc:
            error = str(exc)
            logger.warning("Probe %s failed: %s", probe.name, error)

        latency_ms = int((time.monotonic() - start) * 1000)

        # Score the probe
        metric_results = self._score_probe(probe, actual_output)
        all_passed = all(mr.passed for mr in metric_results)

        return EvalProbeResult(
            probe_id=probe.probe_id,
            probe_name=probe.name,
            input_query=probe.input_query,
            actual_output=actual_output,
            metric_results=metric_results,
            passed=all_passed and error is None,
            latency_ms=latency_ms,
            error=error,
        )

    def _score_probe(
        self,
        probe: EvalProbe,
        actual_output: str | None,
    ) -> list[EvalMetricResult]:
        """Score a probe's output against expected results."""
        results: list[EvalMetricResult] = []

        if actual_output is None:
            results.append(
                EvalMetricResult(
                    metric_type=probe.metric_type,
                    score=0.0,
                    passed=False,
                    details={"reason": "No output produced"},
                )
            )
            return results

        # Basic scoring based on metric type
        score = self._compute_metric(probe, actual_output)
        passed = score >= probe.threshold

        results.append(
            EvalMetricResult(
                metric_type=probe.metric_type,
                score=score,
                passed=passed,
                details={
                    "threshold": probe.threshold,
                    "output_length": len(actual_output),
                },
            )
        )
        return results

    def _compute_metric(self, probe: EvalProbe, actual_output: str) -> float:
        """Compute a metric score for a probe.

        Uses simple heuristics; in production this would delegate to
        specialized metric evaluators (RAGAS, custom classifiers, etc.).
        """
        if probe.metric_type == EvalMetricType.FAITHFULNESS:
            return self._score_faithfulness(probe, actual_output)
        if probe.metric_type == EvalMetricType.RELEVANCY:
            return self._score_relevancy(probe, actual_output)
        if probe.metric_type == EvalMetricType.GROUNDEDNESS:
            return self._score_groundedness(probe, actual_output)
        if probe.metric_type == EvalMetricType.COMPLETENESS:
            return self._score_completeness(probe, actual_output)
        # Default: basic non-empty check
        return 1.0 if actual_output.strip() else 0.0

    def _score_faithfulness(self, probe: EvalProbe, output: str) -> float:
        """Score how faithful the output is to expected output."""
        if not probe.expected_output:
            return 1.0 if output.strip() else 0.0
        expected_words = set(probe.expected_output.lower().split())
        output_words = set(output.lower().split())
        if not expected_words:
            return 1.0
        overlap = expected_words & output_words
        return len(overlap) / len(expected_words)

    def _score_relevancy(self, probe: EvalProbe, output: str) -> float:
        """Score how relevant the output is to the query."""
        query_words = set(probe.input_query.lower().split())
        output_words = set(output.lower().split())
        if not query_words:
            return 1.0
        overlap = query_words & output_words
        return min(1.0, len(overlap) / max(len(query_words) * 0.5, 1))

    def _score_groundedness(self, probe: EvalProbe, output: str) -> float:
        """Score whether output is grounded (contains citations)."""
        has_citations = "[source" in output.lower() or "[" in output
        return 1.0 if has_citations else 0.5

    def _score_completeness(self, probe: EvalProbe, output: str) -> float:
        """Score output completeness based on length heuristic."""
        if not output.strip():
            return 0.0
        # Simple length-based heuristic: at least 50 chars for a complete answer
        return min(1.0, len(output.strip()) / 50)
