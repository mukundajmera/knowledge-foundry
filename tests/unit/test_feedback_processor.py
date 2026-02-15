"""Tests for FeedbackProcessor — submission, categorization, themes, summary."""

from __future__ import annotations

import pytest

from src.improvement.feedback_processor import (
    FeedbackCategory,
    FeedbackProcessor,
    FeedbackStatus,
)


class TestFeedbackProcessor:
    def test_submit_positive(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=1.0, user_id="u1")
        assert entry.category == FeedbackCategory.POSITIVE
        assert entry.status == FeedbackStatus.RECEIVED
        assert fp.count == 1

    def test_submit_negative_auto_acknowledges(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=0.0, comment="This is wrong")
        assert entry.status == FeedbackStatus.ACKNOWLEDGED

    def test_categorize_quality_issues(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=0.2, comment="The answer is incorrect and inaccurate")
        assert entry.category == FeedbackCategory.QUALITY_ISSUES

    def test_categorize_performance(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=0.3, comment="Very slow response time")
        assert entry.category == FeedbackCategory.PERFORMANCE_ISSUES

    def test_categorize_feature_request(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=0.5, comment="Would be nice to add export feature")
        assert entry.category == FeedbackCategory.FEATURE_REQUESTS

    def test_categorize_bug(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=0.1, comment="Got a 500 error when querying")
        assert entry.category == FeedbackCategory.BUGS

    def test_filter_by_category(self) -> None:
        fp = FeedbackProcessor()
        fp.submit(rating=1.0)  # positive
        fp.submit(rating=0.1, comment="Very slow")  # performance
        fp.submit(rating=0.9)  # positive
        entries = fp.get_entries(category=FeedbackCategory.POSITIVE)
        assert len(entries) == 2

    def test_filter_by_tenant(self) -> None:
        fp = FeedbackProcessor()
        fp.submit(rating=0.8, tenant_id="alpha")
        fp.submit(rating=0.6, tenant_id="beta")
        entries = fp.get_entries(tenant_id="alpha")
        assert len(entries) == 1

    def test_resolve_feedback(self) -> None:
        fp = FeedbackProcessor()
        entry = fp.submit(rating=0.2, comment="Wrong answer")
        result = fp.resolve(entry.feedback_id, "Fixed retrieval pipeline")
        assert result is True
        resolved = fp.get_entries(status=FeedbackStatus.RESOLVED)
        assert len(resolved) == 1
        assert resolved[0].resolution_note == "Fixed retrieval pipeline"

    def test_resolve_nonexistent_returns_false(self) -> None:
        fp = FeedbackProcessor()
        assert fp.resolve("no-such-id", "note") is False

    def test_extract_themes(self) -> None:
        fp = FeedbackProcessor()
        for _ in range(5):
            fp.submit(rating=0.1, comment="The answer is wrong and irrelevant")
        for _ in range(3):
            fp.submit(rating=0.2, comment="Response was slow and incorrect")

        themes = fp.extract_themes(min_count=2)
        assert len(themes) >= 1
        theme_words = {t.theme for t in themes}
        assert "wrong" in theme_words or "answer" in theme_words or "irrelevant" in theme_words

    def test_extract_themes_empty_when_no_negatives(self) -> None:
        fp = FeedbackProcessor()
        fp.submit(rating=1.0, comment="Great!")
        themes = fp.extract_themes()
        assert len(themes) == 0

    def test_get_summary(self) -> None:
        fp = FeedbackProcessor()
        fp.submit(rating=1.0)
        fp.submit(rating=0.0, comment="Bad answer")
        fp.submit(rating=0.8)

        summary = fp.get_summary()
        assert summary.total_feedback == 3
        assert summary.avg_rating == pytest.approx(0.6, abs=0.01)
        assert summary.thumbs_up_pct == pytest.approx(2 / 3, abs=0.01)
        assert summary.pending_count >= 0

    def test_get_summary_empty(self) -> None:
        fp = FeedbackProcessor()
        summary = fp.get_summary()
        assert summary.total_feedback == 0
        assert summary.avg_rating == 0.0
