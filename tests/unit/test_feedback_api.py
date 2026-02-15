"""Tests for Feedback API routes — POST /v1/feedback, GET /v1/feedback/summary."""

from __future__ import annotations

import pytest

from src.improvement.feedback_processor import FeedbackProcessor
from src.api.routes.feedback import (
    submit_feedback,
    feedback_summary,
    set_feedback_processor,
    get_feedback_processor,
    FeedbackRequest,
)


@pytest.fixture(autouse=True)
def fresh_processor():
    """Inject a fresh processor for each test."""
    proc = FeedbackProcessor()
    set_feedback_processor(proc)
    yield proc
    set_feedback_processor(None)  # type: ignore[arg-type]


class TestFeedbackAPI:
    @pytest.mark.asyncio
    async def test_submit_positive_feedback(self) -> None:
        req = FeedbackRequest(rating=1.0, comment="Great answer!")
        resp = await submit_feedback(req)
        assert resp.feedback_id
        assert resp.status == "received"
        assert resp.category == "positive"
        assert resp.message == "Thank you for your feedback!"

    @pytest.mark.asyncio
    async def test_submit_negative_feedback(self) -> None:
        req = FeedbackRequest(rating=0.1, comment="Wrong answer, very inaccurate")
        resp = await submit_feedback(req)
        assert resp.category == "quality_issues"
        assert resp.status == "acknowledged"  # Auto-acknowledged

    @pytest.mark.asyncio
    async def test_submit_with_context(self) -> None:
        req = FeedbackRequest(
            rating=0.8,
            tenant_id="t1",
            user_id="u1",
            query_id="q1",
            model_used="claude-sonnet-3.5",
            confidence=0.95,
        )
        resp = await submit_feedback(req)
        assert resp.feedback_id

    @pytest.mark.asyncio
    async def test_feedback_summary_empty(self) -> None:
        result = await feedback_summary()
        assert result["total_feedback"] == 0

    @pytest.mark.asyncio
    async def test_feedback_summary_with_data(self) -> None:
        await submit_feedback(FeedbackRequest(rating=1.0))
        await submit_feedback(FeedbackRequest(rating=0.0, comment="Bad"))
        await submit_feedback(FeedbackRequest(rating=0.8))

        result = await feedback_summary()
        assert result["total_feedback"] == 3
        assert result["avg_rating"] == pytest.approx(0.6, abs=0.01)
        assert "by_category" in result

    @pytest.mark.asyncio
    async def test_get_feedback_processor_creates_default(self) -> None:
        set_feedback_processor(None)  # type: ignore[arg-type]
        proc = get_feedback_processor()
        assert proc is not None
        assert isinstance(proc, FeedbackProcessor)
