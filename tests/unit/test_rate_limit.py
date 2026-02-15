"""Tests for Rate Limiter — src/api/middleware/rate_limit.py."""

from __future__ import annotations

import pytest

from src.api.middleware.rate_limit import (
    InMemorySlidingWindow,
    RateLimiter,
    RateTier,
    TierLimits,
    TIER_LIMITS,
)


# ──────────────────────────────────────────────────
# Sliding Window
# ──────────────────────────────────────────────────

class TestSlidingWindow:
    def test_allows_within_limit(self) -> None:
        window = InMemorySlidingWindow()
        allowed, remaining = window.check_and_increment("key", limit=5, window_seconds=60)
        assert allowed
        assert remaining == 4

    def test_blocks_at_limit(self) -> None:
        window = InMemorySlidingWindow()
        for _ in range(5):
            window.check_and_increment("key", limit=5, window_seconds=60)
        allowed, remaining = window.check_and_increment("key", limit=5, window_seconds=60)
        assert not allowed
        assert remaining == 0

    def test_separate_keys(self) -> None:
        window = InMemorySlidingWindow()
        for _ in range(5):
            window.check_and_increment("key-a", limit=5, window_seconds=60)
        # Key B should still be allowed
        allowed, _ = window.check_and_increment("key-b", limit=5, window_seconds=60)
        assert allowed

    def test_get_count(self) -> None:
        window = InMemorySlidingWindow()
        window.check_and_increment("key", limit=10, window_seconds=60)
        window.check_and_increment("key", limit=10, window_seconds=60)
        assert window.get_count("key", 60) == 2

    def test_reset(self) -> None:
        window = InMemorySlidingWindow()
        window.check_and_increment("key", limit=10, window_seconds=60)
        window.reset("key")
        assert window.get_count("key", 60) == 0


# ──────────────────────────────────────────────────
# Tier Limits
# ──────────────────────────────────────────────────

class TestTierLimits:
    def test_free_tier(self) -> None:
        limits = TIER_LIMITS[RateTier.FREE]
        assert limits.queries_per_minute == 10
        assert limits.queries_per_hour == 100
        assert limits.queries_per_day == 500

    def test_pro_tier(self) -> None:
        limits = TIER_LIMITS[RateTier.PRO]
        assert limits.queries_per_minute == 50

    def test_enterprise_tier(self) -> None:
        limits = TIER_LIMITS[RateTier.ENTERPRISE]
        assert limits.queries_per_minute == 200


# ──────────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────────

class TestRateLimiter:
    def test_allows_within_quota(self) -> None:
        limiter = RateLimiter()
        result = limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.FREE)
        assert result.allowed
        assert result.remaining >= 0

    def test_blocks_at_quota(self) -> None:
        limiter = RateLimiter()
        for _ in range(10):
            limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.FREE)
        result = limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.FREE)
        assert not result.allowed
        assert result.window == "minute"

    def test_different_users_independent(self) -> None:
        limiter = RateLimiter()
        for _ in range(10):
            limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.FREE)
        # Different user should still be allowed
        result = limiter.check(tenant_id="t1", user_id="u2", tier=RateTier.FREE)
        assert result.allowed

    def test_adaptive_reduction(self) -> None:
        limiter = RateLimiter()
        limiter.set_abuse_score("u1", 0.8)  # Flag as abusive
        limits = limiter.get_effective_limits(RateTier.FREE, "u1")
        assert limits.queries_per_minute == 5  # 10 // 2
        assert limits.queries_per_hour == 50  # 100 // 2

    def test_no_reduction_low_abuse(self) -> None:
        limiter = RateLimiter()
        limiter.set_abuse_score("u1", 0.3)  # Below threshold
        limits = limiter.get_effective_limits(RateTier.FREE, "u1")
        assert limits.queries_per_minute == 10  # Unchanged

    def test_pro_tier_higher_quota(self) -> None:
        limiter = RateLimiter()
        for _ in range(10):
            result = limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.PRO)
        # PRO allows 50/min — should still be allowed after 10
        result = limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.PRO)
        assert result.allowed

    def test_result_contains_tier(self) -> None:
        limiter = RateLimiter()
        result = limiter.check(tenant_id="t1", user_id="u1", tier=RateTier.PRO)
        assert result.tier == "pro"
