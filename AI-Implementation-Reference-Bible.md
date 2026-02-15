# Knowledge Foundry: AI Implementation Reference Bible
## The Single Source of Truth for AI-Assisted Development

**Version**: 1.0  
**Purpose**: Comprehensive reference for Claude Opus during implementation  
**Usage**: Include this document in context for ALL development prompts  
**Last Updated**: February 8, 2026

---

## 📐 Project Architecture Blueprint

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        KNOWLEDGE FOUNDRY                         │
│              Ultra-Configurable Enterprise RAG Platform          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         LAYER 1: UI                              │
│  React 18 + TypeScript + Tailwind + shadcn/ui                   │
│  - Chat Interface (Chainlit WebSocket)                          │
│  - Document Management                                           │
│  - Admin Dashboard                                               │
│  - Settings & Configuration                                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │ REST API + WebSocket
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 2: API GATEWAY                          │
│  FastAPI + Chainlit                                             │
│  - Authentication (JWT/OAuth2/SAML)                             │
│  - Rate Limiting (Redis Token Bucket)                           │
│  - Request Validation (Pydantic)                                │
│  - API Versioning (/api/v1/*)                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LAYER 3: CORE PLATFORM                          │
│  Plugin-Based Architecture (8 Core Interfaces)                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ LLM Router   │  │ Vector DB    │  │ Embedding    │         │
│  │ (Custom)     │  │ (Qdrant)     │  │ (SentTrans)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Doc Parser   │  │ Auth Manager │  │ Cache Layer  │         │
│  │ (Unstruct)   │  │ (JWT/OAuth)  │  │ (Redis)      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ Rate Limiter │  │ Notifier     │                            │
│  │ (Redis)      │  │ (Email/Slack)│                            │
│  └──────────────┘  └──────────────┘                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 4: DATA LAYER                            │
│  PostgreSQL 16 + Qdrant                                          │
│  - Multi-tenant data isolation                                   │
│  - Full-text search (PostgreSQL TSVector)                       │
│  - Vector search (Qdrant cosine similarity)                     │
│  - Hybrid search (BM25 + Vector)                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                LAYER 5: BACKGROUND WORKERS                       │
│  Celery + Redis                                                  │
│  - Document ingestion pipeline                                   │
│  - Embedding generation                                          │
│  - Batch processing                                              │
│  - Scheduled tasks                                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 6: OBSERVABILITY                              │
│  Prometheus + Grafana + LangFuse + ELK                          │
│  - Metrics (Prometheus)                                          │
│  - Tracing (LangFuse)                                           │
│  - Logging (ELK Stack)                                          │
│  - Alerting (Alertmanager)                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Core Design Principles (ALWAYS FOLLOW)

### 1. Plugin-First Architecture
**Rule**: Every component MUST be swappable via YAML configuration.

```python
# ✅ CORRECT: Plugin-based
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        pass

# Configuration controls implementation
# config/plugins.yaml
llm_providers:
  - name: openai
    plugin: plugins.llm.openai:OpenAIProvider
    enabled: true

# ❌ WRONG: Hardcoded implementation
def generate_completion(prompt: str):
    client = OpenAI(api_key="sk-...")  # Hardcoded!
    return client.chat.completions.create(...)
```

### 2. Configuration Over Code
**Rule**: NO hardcoded values. ALL behavior defined in YAML.

```yaml
# ✅ CORRECT: Configuration-driven
database:
  host: ${DB_HOST}
  port: ${DB_PORT:5432}
  pool_size: ${DB_POOL_SIZE:20}

# ❌ WRONG: Hardcoded in Python
DATABASE_HOST = "localhost"  # Never do this!
```

### 3. Type Safety Everywhere
**Rule**: Full type hints. Must pass `mypy --strict`.

```python
# ✅ CORRECT: Fully typed
from typing import List, Optional
from pydantic import BaseModel

class CompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: str
    temperature: float = 0.7

async def complete(request: CompletionRequest) -> CompletionResponse:
    ...

# ❌ WRONG: No type hints
def complete(request):  # What type is request?
    ...
```

### 4. Async-First Operations
**Rule**: All I/O operations MUST be async.

```python
# ✅ CORRECT: Async I/O
async def fetch_document(doc_id: UUID) -> Document:
    async with get_db() as session:
        result = await session.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

# ❌ WRONG: Synchronous I/O (blocks event loop)
def fetch_document(doc_id: UUID) -> Document:
    session = get_sync_db()
    return session.query(Document).filter_by(id=doc_id).first()
```

### 5. Observable by Default
**Rule**: Every operation tracked with metrics, logs, traces.

```python
# ✅ CORRECT: Instrumented
from prometheus_client import Counter, Histogram
from langfuse import Langfuse

llm_requests = Counter('llm_requests_total', 'Total LLM requests', ['provider', 'model'])
llm_latency = Histogram('llm_latency_seconds', 'LLM request latency', ['provider'])

@trace_llm_call  # LangFuse tracing
async def complete(request: CompletionRequest) -> CompletionResponse:
    start = time.time()
    llm_requests.labels(provider='openai', model=request.model).inc()
    
    try:
        response = await provider.complete(request)
        llm_latency.labels(provider='openai').observe(time.time() - start)
        logger.info("completion_success", model=request.model, tokens=response.token_count)
        return response
    except Exception as e:
        logger.error("completion_failed", error=str(e))
        raise

# ❌ WRONG: No observability
async def complete(request):
    return await provider.complete(request)  # Silent failure!
```

### 6. Security-First Development
**Rule**: Validate all inputs. Never trust user data.

```python
# ✅ CORRECT: Input validation
from pydantic import BaseModel, Field, validator

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    model: str = Field(..., regex=r'^(gpt-4|gpt-3\.5|claude-3).*$')
    
    @validator('message')
    def sanitize_message(cls, v):
        # Prevent prompt injection
        if any(keyword in v.lower() for keyword in ['ignore previous', 'system:', 'assistant:']):
            raise ValueError("Potential prompt injection detected")
        return v

# ❌ WRONG: No validation
@app.post("/chat")
async def chat(message: str):  # Accepts anything!
    return await llm.complete(message)
```

---

## 📦 Technology Stack Reference

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Backend Framework** | FastAPI | 0.110+ | API server |
| **UI Framework** | React | 18+ | Frontend |
| **Database** | PostgreSQL | 16+ | Primary data store |
| **Vector DB** | Qdrant | 1.7+ | Vector search |
| **Task Queue** | Celery | 5.3+ | Background jobs |
| **Cache** | Redis | 7.2+ | Caching + rate limiting |
| **LLM Gateway** | Custom Router | - | LLM abstraction |
| **Chat UI** | Chainlit | 1.0+ | Chat interface |
| **ORM** | SQLAlchemy | 2.0+ | Database ORM (async) |
| **Validation** | Pydantic | 2.6+ | Data validation |
| **Observability** | LangFuse | 2.0+ | LLM tracing |
| **Metrics** | Prometheus | 2.49+ | Metrics collection |
| **Logging** | Structlog | 24.1+ | Structured logging |

### Python Dependencies (requirements.txt)

```txt
# Core Framework
fastapi==0.110.0
uvicorn[standard]==0.27.0
pydantic==2.6.0
pydantic-settings==2.1.0

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
alembic==1.13.1
psycopg2-binary==2.9.9

# Vector DB
qdrant-client==1.7.3

# LLM Providers
openai==1.12.0
anthropic==0.18.1
httpx==0.26.0

# Task Queue
celery==5.3.6
redis==5.0.1

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9

# Observability
langfuse==2.0.0
prometheus-client==0.19.0
structlog==24.1.0

# Document Processing
unstructured==0.12.4
sentence-transformers==2.3.1

# Testing
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-cov==4.1.0
httpx==0.26.0

# Development
mypy==1.8.0
ruff==0.2.0
black==24.1.0
```

---

## 🗂️ Project Structure (Complete File Tree)

```
knowledge-foundry/
├── .antigravity/
│   └── workspace.json              # Antigravity IDE config
├── config/
│   ├── base.yaml                   # Base configuration
│   ├── dev.yaml                    # Development overrides
│   ├── staging.yaml                # Staging overrides
│   ├── prod.yaml                   # Production overrides
│   ├── plugins.yaml                # Plugin configuration
│   ├── models.py                   # Pydantic config models
│   ├── loader.py                   # Config loader
│   └── schemas/
│       ├── database.schema.json    # Database config schema
│       ├── llm.schema.json         # LLM config schema
│       └── plugins.schema.json     # Plugin config schema
├── core/
│   ├── interfaces.py               # All base interfaces (8 interfaces)
│   ├── plugin_manager.py           # Plugin discovery & loading
│   ├── plugin_factory.py           # Plugin factory pattern
│   ├── plugin_registry.py          # Plugin registration
│   ├── plugin_sandbox.py           # Security sandbox
│   ├── plugin_health.py            # Health monitoring
│   ├── router.py                   # LLM router
│   ├── circuit_breaker.py          # Circuit breaker
│   ├── load_balancer.py            # Load balancing
│   └── rate_limiter.py             # Rate limiting
├── db/
│   ├── base.py                     # Base model
│   ├── session.py                  # Session management
│   ├── models/
│   │   ├── user.py                 # User model
│   │   ├── organization.py         # Organization model
│   │   ├── document.py             # Document model
│   │   ├── chunk.py                # Chunk model
│   │   ├── chat.py                 # Chat model
│   │   ├── message.py              # Message model
│   │   ├── task.py                 # Task model
│   │   ├── audit_log.py            # Audit log model
│   │   ├── semantic_cache.py       # Cache model
│   │   └── api_key.py              # API key model
│   └── repositories/
│       ├── base.py                 # Base repository
│       ├── user.py                 # User repository
│       ├── document.py             # Document repository
│       └── ...                     # One per model
├── plugins/
│   ├── llm/
│   │   ├── openai/
│   │   │   ├── plugin.yaml         # Plugin manifest
│   │   │   ├── provider.py         # Implementation
│   │   │   ├── config.schema.json  # Config schema
│   │   │   ├── tests/              # Plugin tests
│   │   │   └── README.md           # Documentation
│   │   ├── anthropic/
│   │   ├── ollama/
│   │   └── azure/
│   ├── vector_db/
│   │   ├── qdrant/
│   │   ├── chroma/
│   │   └── pinecone/
│   ├── embedding/
│   │   ├── openai/
│   │   └── sentence_transformers/
│   ├── auth/
│   │   ├── jwt/
│   │   ├── oauth2/
│   │   └── saml/
│   └── notifier/
│       ├── email/
│       └── slack/
├── modules/
│   ├── ingestion/
│   │   ├── parser.py               # Document parsing
│   │   ├── chunker.py              # Text chunking
│   │   ├── embedder.py             # Embedding generation
│   │   └── indexer.py              # Vector indexing
│   ├── retrieval/
│   │   ├── hybrid_search.py        # Hybrid search
│   │   ├── reranker.py             # Re-ranking
│   │   └── context_builder.py     # Context assembly
│   └── observability/
│       ├── tracing.py              # LangFuse tracing
│       ├── metrics.py              # Prometheus metrics
│       └── logging.py              # Structured logging
├── api/
│   ├── v1/
│   │   ├── auth.py                 # Auth endpoints
│   │   ├── documents.py            # Document endpoints
│   │   ├── chat.py                 # Chat endpoints
│   │   ├── users.py                # User endpoints
│   │   └── admin.py                # Admin endpoints
│   ├── dependencies.py             # FastAPI dependencies
│   └── middleware.py               # Custom middleware
├── workers/
│   ├── celery_app.py               # Celery configuration
│   ├── ingestion_worker.py         # Ingestion tasks
│   └── maintenance_worker.py       # Maintenance tasks
├── migrations/
│   ├── env.py                      # Alembic environment
│   └── versions/
│       ├── 001_initial_schema.py   # Initial migration
│       └── 002_full_text_search.py # Full-text search
├── tests/
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   ├── validation/                 # Phase 0 validation
│   ├── load/                       # Load tests
│   └── security/                   # Security tests
├── docs/
│   ├── architecture/               # Architecture docs
│   ├── ADRs/                       # Architecture decisions
│   ├── api/                        # API documentation
│   ├── guides/                     # User guides
│   └── runbooks/                   # Operational runbooks
├── prompts/
│   ├── system/                     # System prompts
│   ├── phase0-architecture/        # Phase 0 prompts
│   ├── phase1-implementation/      # Phase 1 prompts
│   ├── phase2-plugins/             # Phase 2 prompts
│   ├── phase3-security/            # Phase 3 prompts
│   └── phase5-ui/                  # Phase 5 prompts
├── deploy/
│   ├── docker/
│   │   ├── Dockerfile              # Application container
│   │   ├── Dockerfile.worker       # Worker container
│   │   └── docker-compose.yml      # Local development
│   ├── kubernetes/
│   │   ├── api-deployment.yaml     # API deployment
│   │   ├── worker-deployment.yaml  # Worker deployment
│   │   └── ingress.yaml            # Ingress config
│   ├── prometheus/
│   │   ├── prometheus.yml          # Prometheus config
│   │   └── alerts.yml              # Alert rules
│   └── grafana/
│       └── dashboards/             # Grafana dashboards
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/               # Chat components
│   │   │   ├── documents/          # Document components
│   │   │   ├── settings/           # Settings components
│   │   │   └── admin/              # Admin components
│   │   ├── hooks/
│   │   │   ├── useChainlit.ts      # Chainlit hook
│   │   │   └── useWebSocket.ts     # WebSocket hook
│   │   ├── lib/
│   │   │   └── api.ts              # API client
│   │   └── styles/
│   │       └── globals.css         # Global styles
│   ├── public/
│   ├── package.json
│   └── tailwind.config.js
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI/CD pipeline
├── .gitignore
├── requirements.txt                # Python dependencies
├── requirements-dev.txt            # Dev dependencies
├── pyproject.toml                  # Project metadata
├── pytest.ini                      # Pytest configuration
├── mypy.ini                        # MyPy configuration
├── .env.example                    # Environment variables template
└── README.md                       # Project README
```

---

## 🎨 Code Style Guide (STRICT ENFORCEMENT)

### Python Style Standards

```python
# Module docstring
"""
Module for LLM provider abstraction.

This module defines the base interface for all LLM providers and implements
the routing logic for selecting the optimal provider based on model, cost,
and availability.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from pydantic import BaseModel, Field
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Constants (UPPER_CASE_WITH_UNDERSCORES)
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3

# Pydantic models (for validation)
class ChatMessage(BaseModel):
    """Chat message with role and content."""
    
    role: str = Field(..., regex=r'^(system|user|assistant)$')
    content: str = Field(..., min_length=1, max_length=100000)
    
    class Config:
        """Pydantic configuration."""
        frozen = True  # Immutable

class CompletionRequest(BaseModel):
    """Request for LLM completion."""
    
    messages: List[ChatMessage]
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=32000)
    stream: bool = False

class CompletionResponse(BaseModel):
    """Response from LLM completion."""
    
    text: str
    model: str
    token_count: int
    latency_ms: float
    cost_usd: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Abstract base class (interface)
class LLMProvider(ABC):
    """
    Base interface for all LLM providers.
    
    All providers (OpenAI, Anthropic, Ollama, etc.) must implement this interface.
    This ensures consistent API across all providers and enables plugin-based swapping.
    
    Attributes:
        name: Provider name (e.g., "openai", "anthropic")
        config: Provider-specific configuration
    """
    
    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        """
        Initialize LLM provider.
        
        Args:
            name: Provider name
            config: Provider configuration from YAML
        """
        self.name = name
        self.config = config
        logger.info(f"Initialized {name} provider", extra={"provider": name})
    
    @abstractmethod
    async def complete(
        self,
        request: CompletionRequest
    ) -> CompletionResponse | AsyncIterator[str]:
        """
        Generate completion from LLM.
        
        Args:
            request: Completion request with messages and parameters
            
        Returns:
            CompletionResponse for non-streaming, or AsyncIterator[str] for streaming
            
        Raises:
            ProviderError: If provider fails to generate completion
            ValidationError: If request is invalid
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is healthy and available.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        pass
    
    @abstractmethod
    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        """
        Calculate cost for completion in USD.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name
            
        Returns:
            Cost in USD
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of models supported by this provider.
        
        Returns:
            List of model names
        """
        pass

# Concrete implementation
class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""
    
    # Cost per 1K tokens (updated regularly)
    COST_PER_1K_TOKENS = {
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    }
    
    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        """Initialize OpenAI provider."""
        super().__init__(name, config)
        
        # Initialize OpenAI client
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=config.get("api_key"),
            organization=config.get("organization"),
            timeout=config.get("timeout", DEFAULT_TIMEOUT),
            max_retries=config.get("max_retries", MAX_RETRIES),
        )
    
    async def complete(
        self,
        request: CompletionRequest
    ) -> CompletionResponse | AsyncIterator[str]:
        """Generate completion using OpenAI API."""
        logger.info(
            "openai_completion_request",
            extra={
                "model": request.model,
                "message_count": len(request.messages),
                "stream": request.stream,
            }
        )
        
        try:
            start_time = datetime.utcnow()
            
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=[
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=request.stream,
            )
            
            if request.stream:
                # Return async generator for streaming
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                # Return complete response
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                return CompletionResponse(
                    text=response.choices[0].message.content,
                    model=request.model,
                    token_count=response.usage.total_tokens,
                    latency_ms=latency_ms,
                    cost_usd=self.calculate_cost(
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens,
                        request.model,
                    ),
                )
                
        except Exception as e:
            logger.error(
                "openai_completion_failed",
                extra={"error": str(e), "model": request.model},
                exc_info=True,
            )
            raise ProviderError(f"OpenAI completion failed: {e}") from e
    
    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
    
    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        """Calculate OpenAI API cost."""
        if model not in self.COST_PER_1K_TOKENS:
            logger.warning(f"Unknown model for cost calculation: {model}")
            return 0.0
        
        pricing = self.COST_PER_1K_TOKENS[model]
        return (
            input_tokens / 1000 * pricing["input"] +
            output_tokens / 1000 * pricing["output"]
        )
    
    def get_supported_models(self) -> List[str]:
        """Get OpenAI supported models."""
        return list(self.COST_PER_1K_TOKENS.keys())

# Custom exceptions
class ProviderError(Exception):
    """Base exception for provider errors."""
    pass

class ProviderUnavailableError(ProviderError):
    """Provider is temporarily unavailable."""
    pass

class ProviderRateLimitError(ProviderError):
    """Provider rate limit exceeded."""
    pass
```

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| **Module** | lowercase_with_underscores | `llm_router.py` |
| **Class** | PascalCase | `LLMProvider` |
| **Function** | lowercase_with_underscores | `calculate_cost()` |
| **Variable** | lowercase_with_underscores | `token_count` |
| **Constant** | UPPER_CASE_WITH_UNDERSCORES | `MAX_RETRIES` |
| **Private** | _leading_underscore | `_internal_method()` |
| **Type Variable** | Single capital letter or PascalCase | `T` or `ModelType` |

### Docstring Style (Google Format)

```python
def complex_function(
    param1: str,
    param2: int,
    param3: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    One-line summary of what the function does.
    
    Longer description with more details about the function's purpose,
    behavior, and any important implementation notes.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        param3: Optional description. Defaults to None.
    
    Returns:
        Dictionary containing:
            - key1: Description of key1
            - key2: Description of key2
    
    Raises:
        ValueError: If param2 is negative
        TypeError: If param1 is not a string
    
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["key1"])
        'value1'
    """
    pass
```

---

## 🔧 Database Schema Reference

### Complete Database Models

```python
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVector
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

# Base Model (inherited by all models)
class BaseModel:
    """Base model with common fields."""
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)

# 1. Organization Model
class Organization(Base, BaseModel):
    __tablename__ = "organizations"
    
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="free")  # free, pro, enterprise
    billing_email = Column(String(255))
    max_users = Column(Integer, default=5)
    max_documents = Column(Integer, default=100)
    settings = Column(JSONB, default={})
    
    # Relationships
    users = relationship("User", back_populates="organization")
    documents = relationship("Document", back_populates="organization")

# 2. User Model
class User(Base, BaseModel):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="viewer")  # viewer, editor, admin
    is_active = Column(Boolean, default=True)
    preferences = Column(JSONB, default={})
    last_login_at = Column(DateTime)
    
    # Foreign Keys
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    documents = relationship("Document", back_populates="user")
    chats = relationship("Chat", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")

# 3. Document Model
class Document(Base, BaseModel):
    __tablename__ = "documents"
    
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    mime_type = Column(String(100))
    file_size = Column(Integer)  # bytes
    status = Column(String(50), default="pending")  # pending, indexing, ready, failed
    error_message = Column(Text)
    indexed_at = Column(DateTime)
    metadata = Column(JSONB, default={})
    
    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="documents")
    organization = relationship("Organization", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="document")

# 4. Chunk Model (with Full-Text Search)
class Chunk(Base, BaseModel):
    __tablename__ = "document_chunks"
    
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    
    # Full-text search vector
    tsv = Column(TSVector, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    __table_args__ = (
        Index('ix_chunk_tsv', 'tsv', postgresql_using='gin'),
        Index('ix_chunk_document_index', 'document_id', 'chunk_index'),
    )

# 5. Chat Model
class Chat(Base, BaseModel):
    __tablename__ = "chats"
    
    title = Column(String(500))
    model = Column(String(100))  # gpt-4, claude-3, etc.
    total_messages = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

# 6. Message Model
class Message(Base, BaseModel):
    __tablename__ = "messages"
    
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False)
    role = Column(String(20), nullable=False)  # system, user, assistant
    content = Column(Text, nullable=False)
    token_count = Column(Integer)
    cost = Column(Float)
    latency_ms = Column(Float)
    metadata = Column(JSONB, default={})
    
    # Relationships
    chat = relationship("Chat", back_populates="messages")

# 7. Task Model (Background Jobs)
class Task(Base, BaseModel):
    __tablename__ = "tasks"
    
    task_type = Column(String(50), nullable=False)  # ingestion, export, etc.
    status = Column(String(50), default="queued")  # queued, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    celery_task_id = Column(String(255))
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Foreign Keys
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    
    # Relationships
    document = relationship("Document", back_populates="tasks")

# 8. AuditLog Model
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    organization_id = Column(UUID(as_uuid=True), index=True)
    action = Column(String(100), nullable=False)  # created, updated, deleted, accessed
    resource_type = Column(String(50), nullable=False)  # document, user, chat, etc.
    resource_id = Column(UUID(as_uuid=True))
    changes = Column(JSONB)  # Before/after values
    ip_address = Column(String(45))
    user_agent = Column(Text)

# 9. SemanticCache Model
class SemanticCache(Base):
    __tablename__ = "semantic_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_hash = Column(String(64), unique=True, nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    query_embedding = Column(JSONB, nullable=False)  # Store as JSON array
    response = Column(Text, nullable=False)
    hit_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    ttl_seconds = Column(Integer, default=3600)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_cache_last_used', 'last_used_at'),
    )

# 10. ApiKey Model
class ApiKey(Base, BaseModel):
    __tablename__ = "api_keys"
    
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    scopes = Column(JSONB, default=["read"])  # read, write, admin
    rate_limit = Column(Integer, default=100)  # requests per hour
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
```

---

## 🔌 Plugin Interface Specifications

### 8 Core Plugin Interfaces

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from pydantic import BaseModel
from enum import Enum

# 1. LLMProvider Interface (already shown above)

# 2. VectorDB Interface
class VectorDBProvider(ABC):
    """Base interface for vector database providers."""
    
    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance_metric: str = "cosine"
    ) -> bool:
        """Create a new collection."""
        pass
    
    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Insert or update vectors."""
        pass
    
    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        ids: List[str]
    ) -> bool:
        """Delete vectors by IDs."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check database health."""
        pass

# 3. EmbeddingModel Interface
class EmbeddingProvider(ABC):
    """Base interface for embedding model providers."""
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        pass
    
    @abstractmethod
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """Generate embeddings for batch of texts."""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check model health."""
        pass

# 4. DocumentParser Interface
class DocumentParser(ABC):
    """Base interface for document parsing."""
    
    @abstractmethod
    async def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse document and extract content.
        
        Returns:
            Dictionary containing:
                - text: Extracted text content
                - metadata: Document metadata
                - pages: List of page contents (if applicable)
        """
        pass
    
    @abstractmethod
    def supports_mime_type(self, mime_type: str) -> bool:
        """Check if parser supports mime type."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check parser health."""
        pass

# 5. Authenticator Interface
class AuthProvider(ABC):
    """Base interface for authentication providers."""
    
    @abstractmethod
    async def authenticate(
        self,
        credentials: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate user and return user info.
        
        Returns:
            User info dictionary or None if authentication fails
        """
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate authentication token."""
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Optional[str]:
        """Refresh authentication token."""
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """Revoke authentication token."""
        pass

# 6. RateLimiter Interface
class RateLimiter(ABC):
    """Base interface for rate limiting."""
    
    @abstractmethod
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> bool:
        """
        Check if request is within rate limit.
        
        Returns:
            True if within limit, False if exceeded
        """
        pass
    
    @abstractmethod
    async def get_remaining(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> int:
        """Get remaining requests in window."""
        pass
    
    @abstractmethod
    async def reset(self, key: str) -> bool:
        """Reset rate limit for key."""
        pass

# 7. Cache Interface
class CacheProvider(ABC):
    """Base interface for caching."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def clear(self, pattern: Optional[str] = None) -> bool:
        """Clear cache (optionally by pattern)."""
        pass

# 8. Notifier Interface
class NotificationProvider(ABC):
    """Base interface for notifications."""
    
    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send notification."""
        pass
    
    @abstractmethod
    async def send_batch(
        self,
        recipients: List[str],
        subject: str,
        message: str
    ) -> Dict[str, bool]:
        """Send notification to multiple recipients."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check notifier health."""
        pass
```

---

## 📝 Configuration File Templates

### config/base.yaml (Complete Template)

```yaml
# Base configuration (shared across all environments)
app:
  name: Knowledge Foundry
  version: 2.0.0
  environment: development
  debug: false
  hot_reload: false

database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
  name: ${DB_NAME:knowledge_foundry}
  user: ${DB_USER:postgres}
  password: ${DB_PASSWORD}
  pool_size: ${DB_POOL_SIZE:20}
  max_overflow: ${DB_MAX_OVERFLOW:10}
  pool_pre_ping: true
  ssl_mode: ${DB_SSL_MODE:prefer}
  echo: false

vector_db:
  provider: qdrant
  host: ${QDRANT_HOST:localhost}
  port: ${QDRANT_PORT:6333}
  collection: documents
  vector_size: 384
  distance_metric: cosine
  prefer_grpc: true

redis:
  host: ${REDIS_HOST:localhost}
  port: ${REDIS_PORT:6379}
  db: ${REDIS_DB:0}
  password: ${REDIS_PASSWORD}
  max_connections: ${REDIS_MAX_CONNECTIONS:50}

celery:
  broker_url: ${CELERY_BROKER_URL:redis://localhost:6379/0}
  result_backend: ${CELERY_RESULT_BACKEND:redis://localhost:6379/1}
  task_serializer: json
  accept_content: [json]
  result_serializer: json
  timezone: UTC
  enable_utc: true

auth:
  jwt_secret_key: ${JWT_SECRET_KEY}
  jwt_algorithm: HS256
  access_token_expire_minutes: 60
  refresh_token_expire_days: 30
  password_min_length: 12
  require_special_chars: true
  require_numbers: true
  require_uppercase: true

rate_limiting:
  enabled: true
  storage: redis
  default_limit: "100/hour"
  role_limits:
    viewer: "100/hour"
    editor: "500/hour"
    admin: "2000/hour"
  organization_limit: "10000/hour"
  ip_limit: "1000/hour"

caching:
  enabled: true
  default_ttl: 3600
  semantic_cache_enabled: true
  semantic_similarity_threshold: 0.95

observability:
  logging:
    level: INFO
    format: json
    output: stdout
  tracing:
    enabled: true
    provider: langfuse
    langfuse_public_key: ${LANGFUSE_PUBLIC_KEY}
    langfuse_secret_key: ${LANGFUSE_SECRET_KEY}
    langfuse_host: ${LANGFUSE_HOST:http://localhost:3000}
    sample_rate: 1.0
  metrics:
    enabled: true
    provider: prometheus
    port: 9090

plugins:
  llm_providers:
    - name: openai
      plugin: plugins.llm.openai:OpenAIProvider
      enabled: true
      config:
        api_key: ${OPENAI_API_KEY}
        organization: ${OPENAI_ORG_ID}
        models: [gpt-4-turbo, gpt-3.5-turbo]
        timeout: 60
        max_retries: 3
      routing:
        priority: 1
        models: ["gpt-*"]
    
    - name: anthropic
      plugin: plugins.llm.anthropic:AnthropicProvider
      enabled: true
      config:
        api_key: ${ANTHROPIC_API_KEY}
        models: [claude-3-opus, claude-3-sonnet]
        timeout: 60
      routing:
        priority: 2
        models: ["claude-*"]
    
    - name: ollama
      plugin: plugins.llm.ollama:OllamaProvider
      enabled: false
      config:
        host: http://localhost:11434
        models: [llama-3-8b, mistral-7b]
      routing:
        priority: 3
        models: ["llama-*", "mistral-*"]
        fallback_for: [openai, anthropic]

  vector_databases:
    primary:
      plugin: plugins.vector_db.qdrant:QdrantProvider
      config:
        host: ${QDRANT_HOST:localhost}
        port: ${QDRANT_PORT:6333}
        collection: documents
        distance_metric: cosine
    
    fallback:
      plugin: plugins.vector_db.chroma:ChromaProvider
      config:
        persist_directory: ./chroma_db
        collection: documents

  embedding_models:
    default:
      plugin: plugins.embedding.sentence_transformers:SentenceTransformersProvider
      config:
        model_name: sentence-transformers/all-MiniLM-L6-v2
        device: cuda  # cuda or cpu
        batch_size: 32

  document_parsers:
    - plugin: plugins.parser.unstructured:UnstructuredParser
      mime_types: [application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document]
    - plugin: plugins.parser.text:TextParser
      mime_types: [text/plain, text/markdown]

  authentication:
    jwt:
      plugin: plugins.auth.jwt:JWTAuthProvider
      enabled: true
    oauth2:
      plugin: plugins.auth.oauth2:OAuth2Provider
      enabled: false
      config:
        google:
          client_id: ${GOOGLE_CLIENT_ID}
          client_secret: ${GOOGLE_CLIENT_SECRET}

  notifiers:
    email:
      plugin: plugins.notifier.email:EmailNotifier
      enabled: true
      config:
        smtp_host: ${SMTP_HOST}
        smtp_port: ${SMTP_PORT:587}
        smtp_user: ${SMTP_USER}
        smtp_password: ${SMTP_PASSWORD}
        from_email: ${FROM_EMAIL}
    slack:
      plugin: plugins.notifier.slack:SlackNotifier
      enabled: false
      config:
        webhook_url: ${SLACK_WEBHOOK_URL}

feature_flags:
  hybrid_search: true
  semantic_cache: true
  llm_streaming: true
  multi_model_routing: false
  auto_reranking: true
  voice_input: false

ingestion:
  chunk_size: 512
  chunk_overlap: 50
  min_chunk_size: 100
  max_chunk_size: 2000
  supported_mime_types:
    - application/pdf
    - application/vnd.openxmlformats-officedocument.wordprocessingml.document
    - text/plain
    - text/markdown
  max_file_size_mb: 50

retrieval:
  default_k: 10
  max_k: 50
  reranking_enabled: true
  hybrid_search_weight: 0.7  # 0.7 vector + 0.3 full-text
```

---

## 🧪 Testing Standards

### Test Structure

```python
# tests/unit/test_llm_router.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.router import LLMRouter
from core.interfaces import CompletionRequest, ChatMessage

class TestLLMRouter:
    """Test suite for LLM router."""
    
    @pytest.fixture
    def router(self):
        """Create router instance for testing."""
        config = {
            "providers": [
                {"name": "openai", "enabled": True},
                {"name": "anthropic", "enabled": True},
            ]
        }
        return LLMRouter(config)
    
    @pytest.fixture
    def completion_request(self):
        """Create sample completion request."""
        return CompletionRequest(
            messages=[
                ChatMessage(role="user", content="Hello, world!")
            ],
            model="gpt-4-turbo",
            temperature=0.7,
        )
    
    @pytest.mark.asyncio
    async def test_route_success(self, router, completion_request):
        """Test successful routing to provider."""
        response = await router.route(completion_request)
        
        assert response is not None
        assert response.text != ""
        assert response.token_count > 0
        assert response.cost_usd >= 0
    
    @pytest.mark.asyncio
    async def test_route_with_failover(self, router, completion_request):
        """Test automatic failover when primary provider fails."""
        # Mock first provider to fail
        with patch.object(router.providers["openai"], "complete", side_effect=Exception("Provider down")):
            response = await router.route(completion_request)
            
            # Should fallback to anthropic
            assert response is not None
            assert response.model.startswith("claude")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, router, completion_request):
        """Test circuit breaker opens after threshold failures."""
        # Simulate 5 consecutive failures
        for _ in range(5):
            with pytest.raises(Exception):
                await router.route(completion_request)
        
        # Circuit should be open
        assert router.circuit_breakers["openai"].is_open()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, router, completion_request):
        """Test rate limiting enforcement."""
        # Make 101 requests (limit is 100/hour)
        for i in range(101):
            if i < 100:
                response = await router.route(completion_request)
                assert response is not None
            else:
                with pytest.raises(RateLimitError):
                    await router.route(completion_request)
    
    def test_cost_calculation(self, router):
        """Test cost calculation accuracy."""
        cost = router.calculate_cost(
            provider="openai",
            model="gpt-4-turbo",
            input_tokens=1000,
            output_tokens=500,
        )
        
        expected = (1000 / 1000 * 0.01) + (500 / 1000 * 0.03)
        assert abs(cost - expected) < 0.001
```

### Coverage Requirements

- **Unit tests**: 95%+ coverage
- **Integration tests**: Critical paths covered
- **Load tests**: Performance validation
- **Security tests**: OWASP Top 10 coverage

---

## 🚨 Error Handling Patterns

```python
# Custom exception hierarchy
class KnowledgeFoundryError(Exception):
    """Base exception for all Knowledge Foundry errors."""
    pass

class ConfigurationError(KnowledgeFoundryError):
    """Configuration is invalid or missing."""
    pass

class ProviderError(KnowledgeFoundryError):
    """Provider operation failed."""
    pass

class DatabaseError(KnowledgeFoundryError):
    """Database operation failed."""
    pass

class AuthenticationError(KnowledgeFoundryError):
    """Authentication failed."""
    pass

class AuthorizationError(KnowledgeFoundryError):
    """User not authorized for operation."""
    pass

class RateLimitError(KnowledgeFoundryError):
    """Rate limit exceeded."""
    pass

class ValidationError(KnowledgeFoundryError):
    """Input validation failed."""
    pass

# Error handling pattern
async def operation_with_error_handling():
    """Example of proper error handling."""
    try:
        result = await risky_operation()
        return result
        
    except ProviderError as e:
        logger.error("provider_error", error=str(e), exc_info=True)
        # Attempt retry or fallback
        return await fallback_operation()
        
    except DatabaseError as e:
        logger.error("database_error", error=str(e), exc_info=True)
        # Database errors are critical
        raise
        
    except Exception as e:
        logger.error("unexpected_error", error=str(e), exc_info=True)
        # Log and re-raise unexpected errors
        raise KnowledgeFoundryError(f"Unexpected error: {e}") from e
```

---

## 📊 Observability Patterns

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Log with structured context
logger.info(
    "llm_completion_success",
    provider="openai",
    model="gpt-4-turbo",
    tokens=1500,
    latency_ms=450.5,
    cost_usd=0.045,
    user_id=str(user_id),
)
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['provider', 'model', 'status']
)

llm_latency_seconds = Histogram(
    'llm_latency_seconds',
    'LLM request latency',
    ['provider', 'model']
)

active_connections = Gauge(
    'active_connections',
    'Currently active WebSocket connections'
)

# Use metrics
llm_requests_total.labels(provider='openai', model='gpt-4', status='success').inc()
llm_latency_seconds.labels(provider='openai', model='gpt-4').observe(0.45)
active_connections.inc()
```

### LangFuse Tracing

```python
from langfuse import Langfuse

langfuse = Langfuse()

# Trace LLM call
@langfuse.observe()
async def process_query(query: str, user_id: str):
    trace = langfuse.trace(name="rag_query", user_id=user_id)
    
    # Retrieval span
    with trace.span(name="retrieval") as span:
        chunks = await retrieve_chunks(query)
        span.end(output={"chunks_found": len(chunks)})
    
    # Generation span
    with trace.span(name="generation") as span:
        response = await generate_response(query, chunks)
        span.end(
            output=response.text,
            metadata={
                "tokens": response.token_count,
                "cost": response.cost_usd,
            }
        )
    
    return response
```

---

## 🎯 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Latency (p95)** | < 500ms | Prometheus histogram |
| **API Latency (p99)** | < 1s | Prometheus histogram |
| **Vector Search (p95)** | < 100ms | Qdrant metrics |
| **Full-Text Search (p95)** | < 200ms | PostgreSQL query time |
| **Throughput** | > 500 RPS | Load testing |
| **WebSocket Connections** | > 1000 concurrent | Stress testing |
| **Memory Usage** | < 2GB per worker | Container metrics |
| **CPU Usage** | < 70% average | Container metrics |
| **Database Connections** | < 80% pool | SQLAlchemy metrics |
| **Cache Hit Rate** | > 70% | Redis metrics |

---

## 🔐 Security Checklist

- [ ] All inputs validated with Pydantic models
- [ ] SQL injection prevented (ORM parameterized queries)
- [ ] XSS prevention (output escaping)
- [ ] CSRF protection (SameSite cookies + tokens)
- [ ] Rate limiting on all endpoints
- [ ] JWT tokens with expiration
- [ ] Passwords hashed with bcrypt (cost factor 12)
- [ ] API keys hashed before storage
- [ ] Secrets in environment variables (never hardcoded)
- [ ] Multi-tenant data isolation enforced
- [ ] Audit logging for all sensitive operations
- [ ] HTTPS/TLS in production
- [ ] CORS configured correctly
- [ ] Prompt injection detection
- [ ] File upload validation (mime type, size)

---

**END OF IMPLEMENTATION REFERENCE**

This document should be included in the context window for ALL development tasks. It serves as the single source of truth for:

1. Architecture patterns
2. Code style standards
3. Plugin interfaces
4. Database schema
5. Configuration structure
6. Testing requirements
7. Error handling
8. Observability patterns
9. Performance targets
10. Security requirements

**Usage**: Reference this document when generating ANY code for Knowledge Foundry.
