"""Tests for src.core.exceptions — Exception hierarchy and metadata."""

from __future__ import annotations

from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ChunkingError,
    CircuitBreakerOpenError,
    CollectionNotFoundError,
    ConfigurationError,
    DocumentNotFoundError,
    EmbeddingError,
    EscalationExhaustedError,
    KnowledgeFoundryError,
    LLMContentFilterError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    RateLimitError,
    RouterError,
    TenantNotFoundError,
    VectorStoreError,
)


class TestExceptionHierarchy:
    """Verify the inheritance chain is correct."""

    def test_base_exception(self) -> None:
        exc = KnowledgeFoundryError("test", details={"key": "val"})
        assert str(exc) == "test"
        assert exc.message == "test"
        assert exc.details == {"key": "val"}

    def test_llm_errors_inherit(self) -> None:
        assert issubclass(LLMError, KnowledgeFoundryError)
        assert issubclass(LLMProviderError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)
        assert issubclass(LLMContentFilterError, LLMError)

    def test_router_errors_inherit(self) -> None:
        assert issubclass(RouterError, KnowledgeFoundryError)
        assert issubclass(CircuitBreakerOpenError, RouterError)
        assert issubclass(EscalationExhaustedError, RouterError)

    def test_retrieval_errors_inherit(self) -> None:
        assert issubclass(VectorStoreError, KnowledgeFoundryError)
        assert issubclass(CollectionNotFoundError, VectorStoreError)
        assert issubclass(EmbeddingError, KnowledgeFoundryError)
        assert issubclass(ChunkingError, KnowledgeFoundryError)


class TestExceptionMetadata:
    """Verify exception-specific metadata fields."""

    def test_llm_provider_error(self) -> None:
        exc = LLMProviderError(
            "API down",
            provider="anthropic",
            model="claude-opus-4-20250514",
            status_code=500,
        )
        assert exc.provider == "anthropic"
        assert exc.model == "claude-opus-4-20250514"
        assert exc.status_code == 500

    def test_rate_limit_error(self) -> None:
        exc = LLMRateLimitError(retry_after_seconds=30.0)
        assert exc.retry_after_seconds == 30.0

    def test_circuit_breaker_error(self) -> None:
        exc = CircuitBreakerOpenError(service="opus")
        assert exc.service == "opus"

    def test_collection_not_found(self) -> None:
        exc = CollectionNotFoundError("kf_tenant_abc123")
        assert "kf_tenant_abc123" in str(exc)
        assert exc.collection_name == "kf_tenant_abc123"

    def test_tenant_not_found(self) -> None:
        exc = TenantNotFoundError("t-001")
        assert "t-001" in str(exc)
        assert exc.tenant_id == "t-001"

    def test_document_not_found(self) -> None:
        exc = DocumentNotFoundError("d-001")
        assert "d-001" in str(exc)
        assert exc.document_id == "d-001"

    def test_app_rate_limit(self) -> None:
        exc = RateLimitError(retry_after_seconds=60)
        assert exc.retry_after_seconds == 60
