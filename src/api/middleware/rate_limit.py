"""Knowledge Foundry — Rate Limiting Middleware.

Defence Layer 5 per phase-3.1 spec: Redis sliding-window rate limiter
with per-tenant tier quotas, adaptive reduction, and 429 responses.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Tier definitions (from phase-3.1 spec §2.5)
# ──────────────────────────────────────────────────────────────

class RateTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class TierLimits:
    """Rate limits for a tier."""
    queries_per_minute: int
    queries_per_hour: int
    queries_per_day: int


TIER_LIMITS: dict[RateTier, TierLimits] = {
    RateTier.FREE: TierLimits(
        queries_per_minute=10,
        queries_per_hour=100,
        queries_per_day=500,
    ),
    RateTier.PRO: TierLimits(
        queries_per_minute=50,
        queries_per_hour=1000,
        queries_per_day=10000,
    ),
    RateTier.ENTERPRISE: TierLimits(
        queries_per_minute=200,
        queries_per_hour=100_000,
        queries_per_day=1_000_000,
    ),
}


@dataclass
class RateLimitResult:
    """Result of a rate-limit check."""
    allowed: bool
    remaining: int
    limit: int
    retry_after_seconds: int = 0
    tier: str = "free"
    window: str = "minute"


# ──────────────────────────────────────────────────────────────
# In-Memory Sliding Window (no-Redis fallback)
# ──────────────────────────────────────────────────────────────

class InMemorySlidingWindow:
    """Simple in-memory sliding window counter for rate limiting.

    In production this would use Redis MULTI/EXEC with sorted sets.
    This implementation is sufficient for single-instance deployments
    and testing.
    """

    def __init__(self) -> None:
        # {key: [timestamps]}
        self._windows: dict[str, list[float]] = {}

    def _prune(self, key: str, window_seconds: int) -> None:
        """Remove timestamps outside the current window."""
        now = time.monotonic()
        cutoff = now - window_seconds
        if key in self._windows:
            self._windows[key] = [
                ts for ts in self._windows[key] if ts > cutoff
            ]

    def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Check if the request is within rate limit, increment if allowed.

        Args:
            key: Unique identifier (e.g. "rl:tenant_id:user_id:minute").
            limit: Maximum requests in window.
            window_seconds: Window duration in seconds.

        Returns:
            Tuple of (allowed, remaining_requests).
        """
        self._prune(key, window_seconds)

        if key not in self._windows:
            self._windows[key] = []

        current_count = len(self._windows[key])
        if current_count >= limit:
            return False, 0

        self._windows[key].append(time.monotonic())
        remaining = limit - current_count - 1
        return True, remaining

    def get_count(self, key: str, window_seconds: int) -> int:
        """Get current request count in window."""
        self._prune(key, window_seconds)
        return len(self._windows.get(key, []))

    def reset(self, key: str) -> None:
        """Reset counter for a key."""
        self._windows.pop(key, None)


# ──────────────────────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Multi-tier rate limiter with adaptive reduction.

    Checks per-minute, per-hour, and per-day windows.
    Reduces quota by 50% for flagged users (abuse_score > 0.5).
    """

    def __init__(
        self,
        window: InMemorySlidingWindow | None = None,
        abuse_scores: dict[str, float] | None = None,
    ) -> None:
        self._window = window or InMemorySlidingWindow()
        self._abuse_scores = abuse_scores or {}

    def set_abuse_score(self, user_id: str, score: float) -> None:
        """Set abuse score for adaptive rate limiting."""
        self._abuse_scores[user_id] = min(max(score, 0.0), 1.0)

    def get_effective_limits(
        self, tier: RateTier, user_id: str,
    ) -> TierLimits:
        """Get effective limits after adaptive adjustment."""
        base = TIER_LIMITS[tier]
        abuse_score = self._abuse_scores.get(user_id, 0.0)

        if abuse_score > 0.5:
            # Reduce by 50% for flagged users
            return TierLimits(
                queries_per_minute=max(1, base.queries_per_minute // 2),
                queries_per_hour=max(1, base.queries_per_hour // 2),
                queries_per_day=max(1, base.queries_per_day // 2),
            )
        return base

    def check(
        self,
        *,
        tenant_id: str,
        user_id: str,
        tier: RateTier = RateTier.FREE,
    ) -> RateLimitResult:
        """Check rate limit across all windows.

        Returns the most restrictive failing window, or the tightest
        passing window with remaining quota.
        """
        limits = self.get_effective_limits(tier, user_id)
        base_key = f"rl:{tenant_id}:{user_id}"

        windows = [
            ("minute", limits.queries_per_minute, 60),
            ("hour", limits.queries_per_hour, 3600),
            ("day", limits.queries_per_day, 86400),
        ]

        # Check all windows — block if any is exhausted
        for window_name, limit, window_seconds in windows:
            key = f"{base_key}:{window_name}"
            allowed, remaining = self._window.check_and_increment(
                key, limit, window_seconds,
            )
            if not allowed:
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    limit=limit,
                    retry_after_seconds=window_seconds,
                    tier=tier.value,
                    window=window_name,
                )

        # All windows passed — return tightest remaining
        minute_remaining = limits.queries_per_minute - self._window.get_count(
            f"{base_key}:minute", 60,
        )
        return RateLimitResult(
            allowed=True,
            remaining=max(0, minute_remaining),
            limit=limits.queries_per_minute,
            tier=tier.value,
            window="minute",
        )
