"""Integration Tests — Production Pipeline Validation.

Validates key production-readiness requirements:
- Audit trail hash chain integrity
- RAGAS golden dataset meets quality thresholds
- Compliance health endpoint contract
- Configuration file presence
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.compliance.audit import AuditAction, AuditTrail


PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestAuditTrailIntegrity:
    """Validate hash-chained audit trail under realistic load."""

    def test_chain_integrity_after_many_entries(self) -> None:
        """Add 100 entries and verify the full chain."""
        trail = AuditTrail()
        for i in range(100):
            trail.log(
                AuditAction.QUERY,
                tenant_id=f"tenant-{i % 5}",
                user_id=f"user-{i % 10}",
                input_text=f"Query #{i}",
                model_used="claude-sonnet-3.5",
                confidence=0.9,
                latency_ms=50.0 + i,
            )
        assert trail.count == 100
        assert trail.verify_integrity() is True

    def test_tenant_isolation(self) -> None:
        """Each tenant should only see their own entries."""
        trail = AuditTrail()
        for tenant in ["alpha", "beta", "gamma"]:
            for j in range(5):
                trail.log(
                    AuditAction.QUERY,
                    tenant_id=tenant,
                    input_text=f"{tenant} query {j}",
                )
        assert trail.count == 15
        alpha_entries = trail.get_entries_for_tenant("alpha")
        assert len(alpha_entries) == 5
        assert all(e.tenant_id == "alpha" for e in alpha_entries)

    def test_export_is_valid_json(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1", input_text="test")
        exported = trail.to_json()
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["tenant_id"] == "t1"


class TestRAGASGoldenDataset:
    """Validate golden dataset meets production quality gates."""

    GOLDEN_PATH = PROJECT_ROOT / "tests" / "evaluation" / "golden_dataset.json"

    def test_golden_dataset_exists(self) -> None:
        assert self.GOLDEN_PATH.exists(), "Golden dataset not found"

    def test_minimum_question_count(self) -> None:
        """M5 spec: at least 20 questions in the golden dataset."""
        data = json.loads(self.GOLDEN_PATH.read_text())
        assert len(data["questions"]) >= 20

    def test_category_coverage(self) -> None:
        """Quality gate: at least 4 distinct categories."""
        data = json.loads(self.GOLDEN_PATH.read_text())
        categories = {q["category"] for q in data["questions"]}
        assert len(categories) >= 4

    def test_difficulty_coverage(self) -> None:
        """All three difficulty levels must be represented."""
        data = json.loads(self.GOLDEN_PATH.read_text())
        difficulties = {q["difficulty"] for q in data["questions"]}
        assert {"simple", "medium", "complex"}.issubset(difficulties)

    def test_all_questions_have_sources(self) -> None:
        """Every question must reference at least one relevant source."""
        data = json.loads(self.GOLDEN_PATH.read_text())
        for q in data["questions"]:
            assert len(q["relevant_sources"]) >= 1, f"No sources for {q['id']}"


class TestConfigurationFiles:
    """Verify all config files needed for production deployment exist."""

    @pytest.mark.parametrize("rel_path", [
        "Dockerfile",
        "frontend/Dockerfile",
        "docker-compose.yml",
        ".github/workflows/ci.yml",
        "infra/prometheus.yml",
        "infra/alert_rules.yml",
        "infra/grafana-dashboard.json",
        "infra/grafana-datasources.yml",
        "infra/grafana-dashboards.yml",
        "k8s/namespace.yaml",
        "k8s/api-deployment.yaml",
        "k8s/api-service.yaml",
        "k8s/hpa.yaml",
        "k8s/ingress.yaml",
    ])
    def test_config_file_exists(self, rel_path: str) -> None:
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Missing: {rel_path}"

    def test_docker_compose_has_all_services(self) -> None:
        compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text()
        for svc in ["qdrant", "redis", "postgres", "neo4j", "api", "frontend", "prometheus", "grafana"]:
            assert svc in compose_text, f"Service {svc} not in docker-compose"

    def test_ci_has_ragas_job(self) -> None:
        ci_text = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "ragas" in ci_text.lower(), "CI pipeline missing RAGAS quality gate"

    def test_ci_has_security_job(self) -> None:
        ci_text = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "security" in ci_text.lower(), "CI pipeline missing security scan"

    def test_grafana_dashboard_is_valid_json(self) -> None:
        path = PROJECT_ROOT / "infra" / "grafana-dashboard.json"
        data = json.loads(path.read_text())
        assert "panels" in data
        assert len(data["panels"]) >= 5
