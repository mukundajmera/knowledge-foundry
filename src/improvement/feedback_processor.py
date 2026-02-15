"""Knowledge Foundry — Feedback Processing Pipeline.

Collects, categorizes, and processes user feedback for continuous improvement.
Supports close-the-loop tracking per Phase 8.1 §5.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

class FeedbackCategory(str, Enum):
    QUALITY_ISSUES = "quality_issues"
    PERFORMANCE_ISSUES = "performance_issues"
    FEATURE_REQUESTS = "feature_requests"
    BUGS = "bugs"
    POSITIVE = "positive"


class FeedbackStatus(str, Enum):
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


@dataclass
class FeedbackEntry:
    """A single piece of user feedback."""

    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Source
    tenant_id: str = ""
    user_id: str = ""
    query_id: str = ""

    # Content
    rating: float = 0.0  # 0.0 (thumbs down) to 1.0 (thumbs up)
    comment: str = ""
    category: FeedbackCategory = FeedbackCategory.POSITIVE

    # Status tracking (close-the-loop)
    status: FeedbackStatus = FeedbackStatus.RECEIVED
    resolution_note: str = ""

    # Context
    model_used: str = ""
    confidence: float = 0.0


@dataclass
class FeedbackTheme:
    """An extracted theme from feedback comments."""

    theme: str
    count: int
    avg_rating: float
    example_comments: list[str] = field(default_factory=list)
    priority: str = "LOW"


@dataclass
class FeedbackSummary:
    """Aggregated feedback statistics."""

    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_feedback: int = 0
    avg_rating: float = 0.0
    thumbs_up_pct: float = 0.0

    by_category: dict[str, int] = field(default_factory=dict)
    themes: list[FeedbackTheme] = field(default_factory=list)
    pending_count: int = 0
    resolved_count: int = 0


# ──────────────────────────────────────────────────────────────
# Processor
# ──────────────────────────────────────────────────────────────

class FeedbackProcessor:
    """Collects and processes user feedback."""

    # Keywords for auto-categorization
    CATEGORY_KEYWORDS: dict[FeedbackCategory, list[str]] = {
        FeedbackCategory.QUALITY_ISSUES: [
            "wrong", "incorrect", "inaccurate", "hallucinate", "irrelevant",
            "outdated", "misleading", "missing",
        ],
        FeedbackCategory.PERFORMANCE_ISSUES: [
            "slow", "timeout", "lag", "loading", "wait", "latency",
        ],
        FeedbackCategory.FEATURE_REQUESTS: [
            "wish", "would be nice", "feature", "add", "support", "integrate",
            "could you", "please add",
        ],
        FeedbackCategory.BUGS: [
            "error", "crash", "bug", "broken", "doesn't work", "fails",
            "exception", "500",
        ],
    }

    def __init__(self) -> None:
        self._entries: list[FeedbackEntry] = []

    @property
    def count(self) -> int:
        return len(self._entries)

    def submit(
        self,
        *,
        rating: float,
        comment: str = "",
        tenant_id: str = "",
        user_id: str = "",
        query_id: str = "",
        model_used: str = "",
        confidence: float = 0.0,
    ) -> FeedbackEntry:
        """Submit a new feedback entry with auto-categorization."""
        category = self._categorize(rating, comment)

        entry = FeedbackEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            query_id=query_id,
            rating=rating,
            comment=comment,
            category=category,
            model_used=model_used,
            confidence=confidence,
        )
        self._entries.append(entry)

        logger.info(
            "Feedback received: id=%s rating=%.1f category=%s",
            entry.feedback_id[:8],
            rating,
            category.value,
        )

        # Auto-acknowledge negative feedback
        if rating < 0.5 and comment:
            entry.status = FeedbackStatus.ACKNOWLEDGED

        return entry

    def _categorize(self, rating: float, comment: str) -> FeedbackCategory:
        """Auto-categorize feedback based on rating and keywords."""
        if rating >= 0.5 and not comment:
            return FeedbackCategory.POSITIVE

        comment_lower = comment.lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in comment_lower for kw in keywords):
                return category

        return FeedbackCategory.POSITIVE if rating >= 0.5 else FeedbackCategory.QUALITY_ISSUES

    def get_entries(
        self,
        *,
        tenant_id: str | None = None,
        category: FeedbackCategory | None = None,
        status: FeedbackStatus | None = None,
    ) -> list[FeedbackEntry]:
        """Filter feedback entries."""
        entries = self._entries
        if tenant_id:
            entries = [e for e in entries if e.tenant_id == tenant_id]
        if category:
            entries = [e for e in entries if e.category == category]
        if status:
            entries = [e for e in entries if e.status == status]
        return entries

    def resolve(self, feedback_id: str, resolution_note: str) -> bool:
        """Mark feedback as resolved (close-the-loop)."""
        for entry in self._entries:
            if entry.feedback_id == feedback_id:
                entry.status = FeedbackStatus.RESOLVED
                entry.resolution_note = resolution_note
                logger.info("Feedback %s resolved: %s", feedback_id[:8], resolution_note)
                return True
        return False

    def extract_themes(self, min_count: int = 2) -> list[FeedbackTheme]:
        """Extract recurring themes from feedback comments."""
        negative = [e for e in self._entries if e.rating < 0.5 and e.comment]
        if not negative:
            return []

        # Simple word-frequency theme extraction
        word_feedback: dict[str, list[FeedbackEntry]] = {}
        stop_words = {"the", "a", "an", "is", "it", "to", "and", "or", "i", "my", "in", "of", "for"}

        for entry in negative:
            words = set(entry.comment.lower().split()) - stop_words
            for word in words:
                if len(word) >= 4:  # Skip short words
                    word_feedback.setdefault(word, []).append(entry)

        themes: list[FeedbackTheme] = []
        for word, entries in sorted(word_feedback.items(), key=lambda x: -len(x[1])):
            if len(entries) >= min_count:
                avg_r = sum(e.rating for e in entries) / len(entries)
                themes.append(FeedbackTheme(
                    theme=word,
                    count=len(entries),
                    avg_rating=round(avg_r, 2),
                    example_comments=[e.comment for e in entries[:3]],
                    priority="HIGH" if len(entries) >= 5 else "MEDIUM",
                ))

        return themes[:10]  # Top 10 themes

    def get_summary(self) -> FeedbackSummary:
        """Generate an aggregate feedback summary."""
        entries = self._entries
        if not entries:
            return FeedbackSummary()

        total = len(entries)
        avg_rating = sum(e.rating for e in entries) / total
        thumbs_up = sum(1 for e in entries if e.rating >= 0.5)

        by_cat: dict[str, int] = Counter(e.category.value for e in entries)
        pending = sum(1 for e in entries if e.status != FeedbackStatus.RESOLVED)
        resolved = sum(1 for e in entries if e.status == FeedbackStatus.RESOLVED)

        return FeedbackSummary(
            total_feedback=total,
            avg_rating=round(avg_rating, 2),
            thumbs_up_pct=round(thumbs_up / total, 2),
            by_category=dict(by_cat),
            themes=self.extract_themes(),
            pending_count=pending,
            resolved_count=resolved,
        )
