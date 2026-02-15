"""Tests for src.observability.tracing — Langfuse tracer."""

from __future__ import annotations

import pytest

from src.observability.tracing import LangfuseConfig, LangfuseTracer, TraceSpan, get_tracer


class TestLangfuseConfig:
    """Tests for LangfuseConfig."""

    def test_default_disabled(self):
        """Config with no keys should be disabled."""
        config = LangfuseConfig()
        assert config.enabled is False

    def test_enabled_with_both_keys(self):
        """Config with both keys should be enabled."""
        config = LangfuseConfig(
            secret_key="sk-test",
            public_key="pk-test",
            enabled=True,
        )
        assert config.enabled is True

    def test_from_env_disabled(self, monkeypatch):
        """from_env should return disabled when env vars missing."""
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        config = LangfuseConfig.from_env()
        assert config.enabled is False

    def test_from_env_enabled(self, monkeypatch):
        """from_env should return enabled when env vars are set."""
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        config = LangfuseConfig.from_env()
        assert config.enabled is True
        assert config.secret_key == "sk-test"


class TestTraceSpan:
    """Tests for TraceSpan."""

    def test_duration_ms(self):
        """duration_ms should compute correctly."""
        span = TraceSpan(start_time=0.0, end_time=1.5)
        assert span.duration_ms == 1500.0

    def test_duration_ms_zero_when_no_end(self):
        """duration_ms should be 0 when end_time not set."""
        span = TraceSpan(start_time=1.0)
        assert span.duration_ms == 0.0

    def test_default_status_ok(self):
        """Default status should be 'ok'."""
        span = TraceSpan()
        assert span.status == "ok"
        assert span.error is None


class TestLangfuseTracer:
    """Tests for LangfuseTracer — always runs without actual Langfuse SDK."""

    @pytest.fixture
    def tracer(self) -> LangfuseTracer:
        """Create a tracer with disabled config (no SDK needed)."""
        config = LangfuseConfig(enabled=False)
        return LangfuseTracer(config=config)

    def test_disabled_by_default(self, tracer: LangfuseTracer):
        """Tracer should not be enabled without credentials."""
        assert tracer.enabled is False

    @pytest.mark.asyncio
    async def test_trace_llm_call(self, tracer: LangfuseTracer):
        """trace_llm_call should record a span."""
        async with tracer.trace_llm_call(
            model="sonnet-3.5",
            prompt="What is AI?",
            tenant_id="tenant1",
        ) as span:
            span.output_data = {"response": "AI is..."}

        assert len(tracer.spans) == 1
        recorded = tracer.spans[0]
        assert recorded.name == "llm:sonnet-3.5"
        assert recorded.status == "ok"
        assert recorded.duration_ms > 0

    @pytest.mark.asyncio
    async def test_trace_llm_call_error(self, tracer: LangfuseTracer):
        """trace_llm_call should capture errors."""
        with pytest.raises(ValueError, match="test error"):
            async with tracer.trace_llm_call(
                model="opus-4",
                prompt="fail",
            ):
                raise ValueError("test error")

        assert len(tracer.spans) == 1
        recorded = tracer.spans[0]
        assert recorded.status == "error"
        assert "test error" in recorded.error

    @pytest.mark.asyncio
    async def test_trace_rag_query(self, tracer: LangfuseTracer):
        """trace_rag_query should record a span."""
        async with tracer.trace_rag_query(
            query="Search for something",
            tenant_id="tenant1",
        ) as span:
            span.output_data = {"results": 5}

        assert len(tracer.spans) == 1
        assert tracer.spans[0].name == "rag:query"

    @pytest.mark.asyncio
    async def test_trace_agent(self, tracer: LangfuseTracer):
        """trace_agent should record a span."""
        async with tracer.trace_agent(
            agent_name="researcher",
            task="Find market data",
            tenant_id="tenant1",
        ) as span:
            span.output_data = {"findings": "..."}

        assert len(tracer.spans) == 1
        assert tracer.spans[0].name == "agent:researcher"

    @pytest.mark.asyncio
    async def test_multiple_spans(self, tracer: LangfuseTracer):
        """Multiple trace calls should accumulate spans."""
        async with tracer.trace_llm_call(model="haiku", prompt="q1"):
            pass
        async with tracer.trace_rag_query(query="q2"):
            pass
        async with tracer.trace_agent(agent_name="coder", task="code"):
            pass

        assert len(tracer.spans) == 3

    def test_flush_no_error(self, tracer: LangfuseTracer):
        """Flush should not raise when client is disabled."""
        tracer.flush()  # Should be a no-op

    def test_shutdown_no_error(self, tracer: LangfuseTracer):
        """Shutdown should not raise when client is disabled."""
        tracer.shutdown()  # Should be a no-op


class TestGetTracer:
    """Tests for module-level get_tracer singleton."""

    def test_get_tracer_returns_instance(self):
        """get_tracer should return a LangfuseTracer."""
        tracer = get_tracer()
        assert isinstance(tracer, LangfuseTracer)

    def test_get_tracer_singleton(self):
        """get_tracer should return the same instance."""
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2
