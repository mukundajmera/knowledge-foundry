"""Knowledge Foundry — Custom Exception Hierarchy.

All application-specific exceptions inherit from KnowledgeFoundryError.
Each subsystem has its own exception class for precise error handling.
"""

from __future__ import annotations


class KnowledgeFoundryError(Exception):
    """Base exception for all Knowledge Foundry errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# --- LLM Errors ---


class LLMError(KnowledgeFoundryError):
    """Base error for LLM-related failures."""


class LLMProviderError(LLMError):
    """Error communicating with an LLM provider (Anthropic API failure, timeout)."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "anthropic",
        model: str | None = None,
        status_code: int | None = None,
        details: dict | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.status_code = status_code
        super().__init__(message, details=details)


class LLMRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""

    def __init__(
        self,
        message: str = "LLM provider rate limit exceeded",
        *,
        retry_after_seconds: float | None = None,
        details: dict | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, details=details)


class LLMContentFilterError(LLMError):
    """LLM provider refused the request on safety grounds."""


# --- Router Errors ---


class RouterError(KnowledgeFoundryError):
    """Error in the LLM routing layer."""


class CircuitBreakerOpenError(RouterError):
    """Circuit breaker is open — requests are being rejected to protect downstream."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        *,
        service: str = "",
        details: dict | None = None,
    ) -> None:
        self.service = service
        super().__init__(message, details=details)


class EscalationExhaustedError(RouterError):
    """All escalation tiers have been tried and failed."""


# --- Retrieval Errors ---


class VectorStoreError(KnowledgeFoundryError):
    """Error communicating with the vector store (Qdrant)."""


class CollectionNotFoundError(VectorStoreError):
    """Requested Qdrant collection does not exist."""

    def __init__(
        self,
        collection_name: str,
        *,
        details: dict | None = None,
    ) -> None:
        self.collection_name = collection_name
        super().__init__(
            f"Collection '{collection_name}' not found",
            details=details,
        )


class EmbeddingError(KnowledgeFoundryError):
    """Error generating embeddings."""


class ChunkingError(KnowledgeFoundryError):
    """Error during document chunking."""


# --- Security & Auth Errors ---


class AuthenticationError(KnowledgeFoundryError):
    """Authentication failure (invalid/expired token)."""


class AuthorizationError(KnowledgeFoundryError):
    """Authorization failure (insufficient permissions)."""


class RateLimitError(KnowledgeFoundryError):
    """Application-level rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after_seconds: int | None = None,
        details: dict | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, details=details)


# --- Configuration Errors ---


class ConfigurationError(KnowledgeFoundryError):
    """Invalid or missing configuration."""


class TenantNotFoundError(KnowledgeFoundryError):
    """Requested tenant does not exist."""

    def __init__(self, tenant_id: str, *, details: dict | None = None) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Tenant '{tenant_id}' not found", details=details)


# --- Document Errors ---


class DocumentError(KnowledgeFoundryError):
    """Error during document processing."""


class DocumentNotFoundError(DocumentError):
    """Requested document does not exist."""

    def __init__(self, document_id: str, *, details: dict | None = None) -> None:
        self.document_id = document_id
        super().__init__(f"Document '{document_id}' not found", details=details)
