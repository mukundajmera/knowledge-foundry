"""Knowledge Foundry — Langfuse Tracing Integration.

Provides instrumentation decorators and context managers for tracing
LLM calls, RAG pipeline queries, and agent executions via Langfuse.

If Langfuse is not configured (missing env vars), all operations
gracefully degrade to no-ops.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator
from uuid import uuid4

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

@dataclass
class LangfuseConfig:
    """Langfuse connection settings from environment."""

    secret_key: str = ""
    public_key: str = ""
    host: str = "https://cloud.langfuse.com"
    enabled: bool = False

    @classmethod
    def from_env(cls) -> LangfuseConfig:
        """Load config from environment variables."""
        secret = os.getenv("LANGFUSE_SECRET_KEY", "")
        public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        return cls(
            secret_key=secret,
            public_key=public,
            host=host,
            enabled=bool(secret and public),
        )


# ──────────────────────────────────────────────────────────────
# Trace Span Data
# ──────────────────────────────────────────────────────────────

@dataclass
class TraceSpan:
    """A trace span recording timing and metadata for an operation."""

    span_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    trace_id: str = ""
    parent_id: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None

    @property
    def duration_ms(self) -> float:
        """Duration of this span in milliseconds."""
        if self.end_time > 0:
            return (self.end_time - self.start_time) * 1000
        return 0.0


# ──────────────────────────────────────────────────────────────
# Tracer
# ──────────────────────────────────────────────────────────────

class LangfuseTracer:
    """Langfuse tracer with graceful degradation.

    In production, this would use the langfuse Python SDK to send
    traces to the Langfuse server. This implementation provides the
    interface and local recording, with the SDK integration point
    clearly marked.
    """

    def __init__(self, config: LangfuseConfig | None = None) -> None:
        self._config = config or LangfuseConfig.from_env()
        self._client: Any | None = None
        self._spans: list[TraceSpan] = []

        if self._config.enabled:
            try:
                from langfuse import Langfuse  # type: ignore[import-untyped]
                self._client = Langfuse(
                    secret_key=self._config.secret_key,
                    public_key=self._config.public_key,
                    host=self._config.host,
                )
                logger.info("Langfuse tracing enabled: %s", self._config.host)
            except ImportError:
                logger.warning(
                    "Langfuse SDK not installed — tracing will record locally only. "
                    "Install with: pip install langfuse"
                )
            except Exception as exc:
                logger.warning("Langfuse initialization failed: %s", exc)
        else:
            logger.info("Langfuse tracing disabled (no credentials configured)")

    @property
    def enabled(self) -> bool:
        """Whether Langfuse client is active."""
        return self._client is not None

    @property
    def spans(self) -> list[TraceSpan]:
        """All recorded spans (for testing/local inspection)."""
        return list(self._spans)

    @asynccontextmanager
    async def trace_llm_call(
        self,
        *,
        model: str,
        prompt: str,
        tenant_id: str = "",
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[TraceSpan, None]:
        """Context manager for tracing LLM calls.

        Usage:
            async with tracer.trace_llm_call(model="sonnet", prompt="...") as span:
                response = await llm.generate(prompt)
                span.output_data = {"response": response.text}
        """
        span = TraceSpan(
            name=f"llm:{model}",
            trace_id=trace_id or str(uuid4()),
            start_time=time.monotonic(),
            input_data={"prompt": prompt[:500], "model": model},
            metadata={**(metadata or {}), "tenant_id": tenant_id},
        )
        try:
            yield span
        except Exception as exc:
            span.status = "error"
            span.error = str(exc)
            raise
        finally:
            span.end_time = time.monotonic()
            self._spans.append(span)
            self._send_span(span)

    @asynccontextmanager
    async def trace_rag_query(
        self,
        *,
        query: str,
        tenant_id: str = "",
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[TraceSpan, None]:
        """Context manager for tracing RAG pipeline queries."""
        span = TraceSpan(
            name="rag:query",
            trace_id=trace_id or str(uuid4()),
            start_time=time.monotonic(),
            input_data={"query": query[:500]},
            metadata={**(metadata or {}), "tenant_id": tenant_id},
        )
        try:
            yield span
        except Exception as exc:
            span.status = "error"
            span.error = str(exc)
            raise
        finally:
            span.end_time = time.monotonic()
            self._spans.append(span)
            self._send_span(span)

    @asynccontextmanager
    async def trace_agent(
        self,
        *,
        agent_name: str,
        task: str = "",
        tenant_id: str = "",
        trace_id: str | None = None,
    ) -> AsyncGenerator[TraceSpan, None]:
        """Context manager for tracing agent executions."""
        span = TraceSpan(
            name=f"agent:{agent_name}",
            trace_id=trace_id or str(uuid4()),
            start_time=time.monotonic(),
            input_data={"task": task[:500]},
            metadata={"tenant_id": tenant_id},
        )
        try:
            yield span
        except Exception as exc:
            span.status = "error"
            span.error = str(exc)
            raise
        finally:
            span.end_time = time.monotonic()
            self._spans.append(span)
            self._send_span(span)

    def _send_span(self, span: TraceSpan) -> None:
        """Send span to Langfuse (or log locally)."""
        if self._client:
            try:
                trace = self._client.trace(
                    id=span.trace_id,
                    name=span.name,
                    metadata=span.metadata,
                    input=span.input_data,
                    output=span.output_data,
                )
                trace.span(
                    name=span.name,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    metadata=span.metadata,
                    input=span.input_data,
                    output=span.output_data,
                    status_message=span.error if span.status == "error" else None,
                )
            except Exception as exc:
                logger.debug("Failed to send span to Langfuse: %s", exc)
        else:
            logger.debug(
                "Trace [%s] %s: %.1fms status=%s",
                span.trace_id[:8],
                span.name,
                span.duration_ms,
                span.status,
            )

    def flush(self) -> None:
        """Flush any pending spans to Langfuse."""
        if self._client:
            try:
                self._client.flush()
            except Exception as exc:
                logger.debug("Langfuse flush failed: %s", exc)

    def shutdown(self) -> None:
        """Shutdown the Langfuse client."""
        if self._client:
            try:
                self._client.shutdown()
            except Exception as exc:
                logger.debug("Langfuse shutdown failed: %s", exc)


# ──────────────────────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────────────────────

_tracer: LangfuseTracer | None = None


def get_tracer() -> LangfuseTracer:
    """Get or create the module-level tracer singleton."""
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer()
    return _tracer
