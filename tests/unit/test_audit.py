"""Tests for Compliance Audit Trail — src/compliance/audit.py."""

from __future__ import annotations

import json

import pytest

from src.compliance.audit import AuditAction, AuditEntry, AuditTrail


class TestAuditEntry:
    def test_entry_has_uuid(self) -> None:
        entry = AuditEntry()
        assert entry.entry_id
        assert len(entry.entry_id) == 36  # UUID format

    def test_entry_has_timestamp(self) -> None:
        entry = AuditEntry()
        assert entry.timestamp
        assert "T" in entry.timestamp  # ISO format

    def test_entry_is_frozen(self) -> None:
        entry = AuditEntry()
        with pytest.raises(AttributeError):
            entry.action = "modified"  # type: ignore[misc]

    def test_compute_hash_deterministic(self) -> None:
        entry = AuditEntry(
            entry_id="test-id",
            timestamp="2026-01-01T00:00:00Z",
            action="query",
            tenant_id="t1",
        )
        h1 = entry.compute_hash()
        h2 = entry.compute_hash()
        assert h1 == h2

    def test_compute_hash_changes_with_input(self) -> None:
        base = dict(entry_id="id", timestamp="ts", action="query", tenant_id="t1")
        e1 = AuditEntry(**base, input_text="hello")
        e2 = AuditEntry(**base, input_text="world")
        assert e1.compute_hash() != e2.compute_hash()


class TestAuditTrail:
    def test_log_creates_entry(self) -> None:
        trail = AuditTrail()
        entry = trail.log(AuditAction.QUERY, tenant_id="t1", user_id="u1")
        assert trail.count == 1
        assert entry.action == "query"

    def test_hash_chain_links(self) -> None:
        trail = AuditTrail()
        e1 = trail.log(AuditAction.QUERY, tenant_id="t1")
        e2 = trail.log(AuditAction.RESPONSE, tenant_id="t1")
        assert e1.previous_hash == "genesis"
        assert e2.previous_hash == e1.entry_hash

    def test_verify_integrity_valid(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1")
        trail.log(AuditAction.RESPONSE, tenant_id="t1")
        trail.log(AuditAction.FEEDBACK, tenant_id="t1")
        assert trail.verify_integrity()

    def test_verify_integrity_detects_tampering(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1")
        trail.log(AuditAction.RESPONSE, tenant_id="t1")
        # Tamper with the chain
        tampered = trail._entries[0]
        object.__setattr__(tampered, "entry_hash", "bogus")
        assert not trail.verify_integrity()

    def test_get_entries_for_tenant(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1")
        trail.log(AuditAction.QUERY, tenant_id="t2")
        trail.log(AuditAction.QUERY, tenant_id="t1")
        assert len(trail.get_entries_for_tenant("t1")) == 2
        assert len(trail.get_entries_for_tenant("t2")) == 1

    def test_get_entries_by_action(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1")
        trail.log(AuditAction.RESPONSE, tenant_id="t1")
        trail.log(AuditAction.QUERY, tenant_id="t1")
        assert len(trail.get_entries_by_action(AuditAction.QUERY)) == 2
        assert len(trail.get_entries_by_action(AuditAction.RESPONSE)) == 1

    def test_to_json(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1", input_text="hello")
        output = trail.to_json()
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["input_text"] == "hello"

    def test_entries_are_copies(self) -> None:
        trail = AuditTrail()
        trail.log(AuditAction.QUERY, tenant_id="t1")
        entries = trail.entries
        assert entries is not trail._entries

    def test_eu_ai_act_required_fields(self) -> None:
        """Verify all EU AI Act Article 12 required fields are present."""
        trail = AuditTrail()
        entry = trail.log(
            AuditAction.RESPONSE,
            tenant_id="t1",
            user_id="u1",
            input_text="What is our policy?",
            output_text="Our policy is...",
            model_used="sonnet",
            confidence=0.92,
            latency_ms=450.0,
            cost_usd=0.003,
            ip_address="192.168.1.1",
            request_id="req-123",
        )
        assert entry.tenant_id == "t1"
        assert entry.user_id == "u1"
        assert entry.input_text
        assert entry.output_text
        assert entry.model_used == "sonnet"
        assert entry.confidence == 0.92
        assert entry.timestamp
        assert entry.entry_hash
