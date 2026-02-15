"""Tests for the compliance health endpoint.

Validates that the /compliance/health endpoint correctly reports
audit trail integrity, EU AI Act compliance status, and field coverage.
"""

from __future__ import annotations

import pytest

from src.compliance.audit import AuditAction, AuditTrail
from src.api.routes.compliance_health import (
    compliance_health,
    get_audit_trail,
    set_audit_trail,
)


@pytest.fixture(autouse=True)
def fresh_trail():
    """Inject a fresh audit trail for each test."""
    trail = AuditTrail()
    set_audit_trail(trail)
    yield trail
    set_audit_trail(None)  # type: ignore[arg-type]


class TestComplianceHealth:
    """Verify /compliance/health endpoint behavior."""

    @pytest.mark.asyncio
    async def test_empty_trail_is_compliant(self) -> None:
        result = await compliance_health()
        assert result["status"] == "compliant"
        assert result["checks"]["audit_trail_integrity"] == "ok"
        assert result["checks"]["audit_entry_count"] == 0

    @pytest.mark.asyncio
    async def test_compliant_after_entries(self, fresh_trail: AuditTrail) -> None:
        fresh_trail.log(
            AuditAction.QUERY,
            tenant_id="t-1",
            user_id="u-1",
            input_text="test query",
            model_used="claude-sonnet-3.5",
            confidence=0.95,
        )
        fresh_trail.log(
            AuditAction.RESPONSE,
            tenant_id="t-1",
            user_id="u-1",
            output_text="test answer",
            model_used="claude-sonnet-3.5",
        )

        result = await compliance_health()
        assert result["status"] == "compliant"
        assert result["checks"]["audit_entry_count"] == 2
        assert result["checks"]["hash_chain_algorithm"] == "SHA-256"

    @pytest.mark.asyncio
    async def test_reports_eu_ai_act_standards(self) -> None:
        result = await compliance_health()
        standards = result["standards"]
        assert any("EU AI Act" in s for s in standards)
        assert any("Article 12" in s for s in standards)
        assert any("SOC2" in s for s in standards)

    @pytest.mark.asyncio
    async def test_has_timestamp(self) -> None:
        result = await compliance_health()
        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO format

    @pytest.mark.asyncio
    async def test_checks_contain_expected_fields(self) -> None:
        result = await compliance_health()
        checks = result["checks"]
        expected = {
            "audit_trail_integrity",
            "audit_entry_count",
            "hash_chain_algorithm",
            "eu_ai_act_art12_fields",
            "eu_ai_act_field_coverage",
            "immutable_logging",
            "export_capability",
            "tenant_isolation",
        }
        assert expected.issubset(set(checks.keys()))

    @pytest.mark.asyncio
    async def test_field_coverage_is_complete(self) -> None:
        result = await compliance_health()
        assert result["checks"]["eu_ai_act_field_coverage"] == 1.0

    @pytest.mark.asyncio
    async def test_get_audit_trail_creates_default(self) -> None:
        """If no trail is set, get_audit_trail creates one."""
        set_audit_trail(None)  # type: ignore[arg-type]
        trail = get_audit_trail()
        assert trail is not None
        assert isinstance(trail, AuditTrail)
