"""Knowledge Foundry — Feedback API Routes.

POST /v1/feedback — submit user feedback (rating + optional comment).
GET  /v1/feedback/summary — aggregate feedback statistics.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.improvement.feedback_processor import FeedbackProcessor

router = APIRouter(prefix="/v1", tags=["feedback"])
logger = logging.getLogger(__name__)

# Module-level processor (injected at app startup)
_feedback_processor: FeedbackProcessor | None = None


def set_feedback_processor(processor: FeedbackProcessor) -> None:
    """Inject the feedback processor instance."""
    global _feedback_processor
    _feedback_processor = processor


def get_feedback_processor() -> FeedbackProcessor:
    """Get or create the feedback processor."""
    global _feedback_processor
    if _feedback_processor is None:
        _feedback_processor = FeedbackProcessor()
    return _feedback_processor


# ── Request / Response Models ──

class FeedbackRequest(BaseModel):
    """POST /v1/feedback request body."""

    rating: float = Field(..., ge=0.0, le=1.0, description="Rating from 0 (bad) to 1 (great)")
    comment: str = Field("", max_length=2000, description="Optional text feedback")
    query_id: str = Field("", description="ID of the query being rated")
    tenant_id: str = Field("", description="Tenant ID")
    user_id: str = Field("", description="User ID")
    model_used: str = Field("", description="Model that generated the response")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence of the response")


class FeedbackResponse(BaseModel):
    """POST /v1/feedback response."""

    feedback_id: str
    status: str
    category: str
    message: str


# ── Routes ──

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(body: FeedbackRequest) -> FeedbackResponse:
    """Submit user feedback for a query response."""
    processor = get_feedback_processor()

    entry = processor.submit(
        rating=body.rating,
        comment=body.comment,
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        query_id=body.query_id,
        model_used=body.model_used,
        confidence=body.confidence,
    )

    return FeedbackResponse(
        feedback_id=entry.feedback_id,
        status=entry.status.value,
        category=entry.category.value,
        message="Thank you for your feedback!",
    )


@router.get("/feedback/summary")
async def feedback_summary() -> dict[str, Any]:
    """Get aggregated feedback statistics."""
    processor = get_feedback_processor()
    summary = processor.get_summary()

    return {
        "total_feedback": summary.total_feedback,
        "avg_rating": summary.avg_rating,
        "thumbs_up_pct": summary.thumbs_up_pct,
        "by_category": summary.by_category,
        "themes": [
            {
                "theme": t.theme,
                "count": t.count,
                "avg_rating": t.avg_rating,
                "priority": t.priority,
            }
            for t in summary.themes
        ],
        "pending_count": summary.pending_count,
        "resolved_count": summary.resolved_count,
    }
