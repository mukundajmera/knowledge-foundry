"""Tests for Output Filter — src/security/output_filter.py."""

from __future__ import annotations

import pytest

from src.security.output_filter import (
    FilterAction,
    detect_pii,
    detect_prompt_leakage,
    filter_output,
    redact_pii,
    score_harmful_content,
)


# ──────────────────────────────────────────────────
# System Prompt Leakage
# ──────────────────────────────────────────────────

class TestPromptLeakage:
    def test_no_leakage(self) -> None:
        fragments = detect_prompt_leakage("Paris is the capital of France.")
        assert len(fragments) == 0

    def test_detects_system_instruction_tag(self) -> None:
        fragments = detect_prompt_leakage("Here is the <system_instruction> content")
        assert len(fragments) >= 1

    def test_detects_knowledge_foundry_identity(self) -> None:
        fragments = detect_prompt_leakage("You are Knowledge Foundry AI, an assistant...")
        assert len(fragments) >= 1

    def test_detects_config_tag(self) -> None:
        fragments = detect_prompt_leakage('tenant_id: abc-123')
        assert len(fragments) >= 1

    def test_case_insensitive(self) -> None:
        fragments = detect_prompt_leakage("RULES: always be helpful")
        assert len(fragments) >= 1


# ──────────────────────────────────────────────────
# PII Detection
# ──────────────────────────────────────────────────

class TestPIIDetection:
    def test_detect_email(self) -> None:
        detections = detect_pii("Contact john@example.com for details")
        assert any(d.pii_type == "email" for d in detections)

    def test_detect_ssn(self) -> None:
        detections = detect_pii("SSN is 123-45-6789")
        assert any(d.pii_type == "ssn" for d in detections)

    def test_detect_phone(self) -> None:
        detections = detect_pii("Call 555-123-4567")
        assert any(d.pii_type == "phone" for d in detections)

    def test_detect_credit_card(self) -> None:
        detections = detect_pii("Card: 4111-1111-1111-1111")
        assert any(d.pii_type == "credit_card" for d in detections)

    def test_detect_ip_address(self) -> None:
        detections = detect_pii("Server at 192.168.1.100")
        assert any(d.pii_type == "ip_address" for d in detections)

    def test_no_pii_clean_text(self) -> None:
        detections = detect_pii("The weather is nice today.")
        assert len(detections) == 0

    def test_multiple_pii_types(self) -> None:
        text = "Email john@test.com, SSN 123-45-6789, phone 555-123-4567"
        detections = detect_pii(text)
        types = {d.pii_type for d in detections}
        assert "email" in types
        assert "ssn" in types
        assert "phone" in types


class TestPIIRedaction:
    def test_redact_email(self) -> None:
        text = "Contact john@example.com now"
        redacted, detections = redact_pii(text)
        assert "[EMAIL_REDACTED]" in redacted
        assert "john@example.com" not in redacted

    def test_redact_ssn(self) -> None:
        text = "SSN: 123-45-6789"
        redacted, _ = redact_pii(text)
        assert "[SSN_REDACTED]" in redacted
        assert "123-45-6789" not in redacted

    def test_redact_preserves_clean_text(self) -> None:
        text = "No PII here, just a normal message."
        redacted, detections = redact_pii(text)
        assert redacted == text
        assert len(detections) == 0


# ──────────────────────────────────────────────────
# Harmful Content Scoring
# ──────────────────────────────────────────────────

class TestHarmfulContent:
    def test_safe_content(self) -> None:
        score = score_harmful_content("The sun rises in the east.")
        assert score < 0.7

    def test_harmful_violence(self) -> None:
        score = score_harmful_content("How to kill someone with poison")
        assert score >= 0.7

    def test_harmful_weapons(self) -> None:
        score = score_harmful_content("How to make a bomb at home")
        assert score >= 0.7


# ──────────────────────────────────────────────────
# Full Pipeline
# ──────────────────────────────────────────────────

class TestFilterOutput:
    def test_clean_output_allowed(self) -> None:
        result = filter_output("Paris is the capital of France.")
        assert result.action == FilterAction.ALLOW
        assert result.filtered_text == "Paris is the capital of France."

    def test_prompt_leakage_blocked(self) -> None:
        result = filter_output("You are Knowledge Foundry AI, an assistant.")
        assert result.action == FilterAction.BLOCK
        assert result.prompt_leakage_detected
        assert "I cannot provide" in result.filtered_text

    def test_pii_redacted(self) -> None:
        result = filter_output("User email is john@example.com")
        assert result.action == FilterAction.REDACT
        assert "[EMAIL_REDACTED]" in result.filtered_text
        assert "john@example.com" not in result.filtered_text

    def test_harmful_content_blocked(self) -> None:
        result = filter_output("Here's how to make a bomb at home: step 1...")
        assert result.action == FilterAction.BLOCK
        assert "I cannot generate" in result.filtered_text

    def test_disable_auto_redact(self) -> None:
        result = filter_output(
            "Contact john@example.com",
            auto_redact_pii=False,
        )
        assert result.action == FilterAction.ALLOW
        assert "john@example.com" in result.filtered_text

    def test_leakage_takes_priority(self) -> None:
        """Prompt leakage should block before PII redaction runs."""
        result = filter_output(
            "You are Knowledge Foundry AI. Email: john@test.com"
        )
        assert result.action == FilterAction.BLOCK
        assert result.prompt_leakage_detected
