# Knowledge Foundry: AI Implementation Reference
## The Complete Guide for AI Agents

**Version**: 1.0  
**Purpose**: Single source of truth for AI agents during implementation  
**Usage**: Reference this document in every AI prompt for context  
**Last Updated**: February 8, 2026

---

## 🎯 Core Principles

### 1. Production-First Mindset
- Every generated artifact must be production-ready
- No TODOs, no placeholders, no "implement later"
- Include error handling, logging, metrics from day one
- Write code as if it deploys tomorrow

### 2. Type Safety is Non-Negotiable
```python
# ✅ CORRECT - Full type hints
async def create_document(
    user_id: UUID,
    file: UploadFile,
    organization_id: UUID,
    session: AsyncSession
) -> Document:
    """Create document with proper types."""
    pass

# ❌ WRONG - No type hints
async def create_document(user_id, file, organization_id, session):
    pass
```

### 3. Observability from the Start
Every function must include:
- Structured logging with context
- Prometheus metrics
- Error tracking
- Performance timing

```python
import structlog
from prometheus_client import Counter, Histogram
import time

logger = structlog.get_logger()
doc_created = Counter('documents_created_total', 'Documents created', ['organization'])
doc_creation_duration = Histogram('document_creation_seconds', 'Document creation time')

async def create_document(user_id: UUID, file: UploadFile) -> Document:
    start = time.time()
    log = logger.bind(user_id=str(user_id), filename=file.filename)
    
    try:
        log.info("document_creation_started")
        doc = await _process_document(file)
        doc_created.labels(organization=str(doc.organization_id)).inc()
        log.info("document_creation_completed", document_id=str(doc.id))
        return doc
    except Exception as e:
        log.error("document_creation_failed", error=str(e))
        raise
    finally:
        doc_creation_duration.observe(time.time() - start)
```

### 4. Security at Every Layer
- Validate ALL user input with Pydantic
- Use parameterized queries (SQLAlchemy ORM)
- Rate limit all endpoints
- Audit log sensitive operations
- Never log secrets or PII

---

## 📐 Architecture Patterns

### Repository Pattern (Mandatory for DB Access)

```python
from typing import Generic, TypeVar, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Base repository with common patterns."""
    
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model
    
    async def create(self, **kwargs) -> T:
        """Create with automatic session management."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # Get ID without committing
        await self.session.refresh(instance)
        return instance
    
    async def get_by_id(
        self, 
        id: UUID, 
        organization_id: Optional[UUID] = None
    ) -> Optional[T]:
        """Get by ID with optional org filter."""
        query = select(self.model).where(
            self.model.id == id,
            self.model.is_deleted == False
        )
        if organization_id:
            query = query.where(self.model.organization_id == organization_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_paginated(
        self,
        organization_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at"
    ) -> List[T]:
        """List with pagination."""
        query = select(self.model).where(self.model.is_deleted == False)
        if organization_id:
            query = query.where(self.model.organization_id == organization_id)
        query = query.order_by(getattr(self.model, order_by).desc())
        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def soft_delete(self, id: UUID) -> bool:
        """Soft delete pattern."""
        await self.session.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(is_deleted=True)
        )
        return True
```

### Plugin Interface Pattern

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel

class PluginConfig(BaseModel):
    """Base configuration for all plugins."""
    enabled: bool = True
    timeout_seconds: int = 30
    max_retries: int = 3
    circuit_breaker_threshold: int = 5

class PluginMetadata(BaseModel):
    """Plugin metadata."""
    name: str
    version: str
    author: str
    description: str
    dependencies: List[str] = []
    supported_models: List[str] = []

class BasePlugin(ABC):
    """Base class for all plugins."""
    
    def __init__(self, config: PluginConfig):
        self.config = config
        self.metadata = self.get_metadata()
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize plugin resources."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if plugin is healthy."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup plugin resources."""
        pass
```

### Circuit Breaker Pattern

```python
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failed, rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """Circuit breaker for external dependencies."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.state = CircuitState.CLOSED
        self.opened_at: Optional[datetime] = None
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if not self.opened_at:
            return False
        elapsed = datetime.utcnow() - self.opened_at
        return elapsed.total_seconds() >= self.timeout_seconds
```

---

## 🔧 Code Generation Standards

### Function Documentation Template

```python
async def process_document(
    document_id: UUID,
    chunking_strategy: str = "recursive",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    organization_id: Optional[UUID] = None
) -> List[DocumentChunk]:
    """
    Process document into chunks for embedding.
    
    This function handles the complete document processing pipeline:
    1. Load document from storage
    2. Extract text based on file type
    3. Split into chunks using specified strategy
    4. Generate embeddings for each chunk
    5. Store chunks in vector database
    
    Args:
        document_id: UUID of document to process
        chunking_strategy: Strategy to use ('recursive', 'semantic', 'fixed')
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Overlap tokens between chunks
        organization_id: Optional organization filter for multi-tenancy
    
    Returns:
        List of created DocumentChunk objects with embeddings
    
    Raises:
        DocumentNotFoundError: Document doesn't exist or is deleted
        ProcessingError: Error during text extraction or chunking
        EmbeddingError: Error generating embeddings
        VectorDBError: Error storing in vector database
    
    Example:
        ```python
        chunks = await process_document(
            document_id=doc.id,
            chunking_strategy="semantic",
            chunk_size=500,
            organization_id=org.id
        )
        logger.info(f"Created {len(chunks)} chunks")
        ```
    
    Performance:
        - Typical: 2-5 seconds for 10-page PDF
        - Uses async I/O for embedding API calls
        - Batches embedding requests (up to 100 chunks)
    
    Metrics:
        - document_processing_duration_seconds
        - document_chunks_created_total
        - embedding_api_calls_total
    """
    log = logger.bind(
        document_id=str(document_id),
        strategy=chunking_strategy
    )
    
    start = time.time()
    try:
        # Implementation here
        pass
    finally:
        duration = time.time() - start
        log.info("document_processed", duration=duration)
```

### Error Handling Pattern

```python
from typing import Optional
import traceback

class KnowledgeFoundryError(Exception):
    """Base exception for all custom errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class DocumentNotFoundError(KnowledgeFoundryError):
    """Document not found or access denied."""
    
    def __init__(self, document_id: UUID):
        super().__init__(
            message=f"Document {document_id} not found",
            error_code="DOCUMENT_NOT_FOUND",
            details={"document_id": str(document_id)}
        )

class ProcessingError(KnowledgeFoundryError):
    """Error during document processing."""
    
    def __init__(self, document_id: UUID, stage: str, original_error: Exception):
        super().__init__(
            message=f"Processing failed at stage: {stage}",
            error_code="PROCESSING_FAILED",
            details={
                "document_id": str(document_id),
                "stage": stage,
                "original_error": str(original_error),
                "traceback": traceback.format_exc()
            }
        )

# Usage in functions
async def process_document(document_id: UUID) -> List[DocumentChunk]:
    try:
        doc = await doc_repo.get_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(document_id)
        
        try:
            chunks = await chunker.split(doc.content)
        except Exception as e:
            raise ProcessingError(document_id, "chunking", e)
        
        return chunks
    
    except KnowledgeFoundryError:
        raise  # Re-raise custom errors as-is
    except Exception as e:
        logger.error("unexpected_error", error=str(e), traceback=traceback.format_exc())
        raise ProcessingError(document_id, "unknown", e)
```

### Pydantic Models Pattern

```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class DocumentCreate(BaseModel):
    """Request model for document creation."""
    
    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0, le=100_000_000)  # Max 100MB
    mime_type: str = Field(..., regex=r'^[\w-]+/[\w-]+$')
    organization_id: UUID
    
    @validator('mime_type')
    def validate_mime_type(cls, v):
        """Validate supported MIME types."""
        allowed = [
            'application/pdf',
            'text/plain',
            'text/markdown',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        if v not in allowed:
            raise ValueError(f'Unsupported MIME type: {v}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "filename": "research_paper.pdf",
                "file_size": 2500000,
                "mime_type": "application/pdf",
                "organization_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }

class DocumentResponse(BaseModel):
    """Response model for document."""
    
    id: UUID
    filename: str
    file_size: int
    mime_type: str
    status: str
    chunk_count: int = 0
    created_at: datetime
    
    class Config:
        orm_mode = True  # Allow from SQLAlchemy models
```

---

## 🧪 Testing Standards

### Test Structure Template

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

class TestDocumentAPI:
    """Test document API endpoints."""
    
    @pytest.fixture
    async def test_organization(self, db: AsyncSession):
        """Create test organization."""
        org = Organization(
            id=uuid4(),
            name="Test Org",
            plan="enterprise"
        )
        db.add(org)
        await db.commit()
        return org
    
    @pytest.fixture
    async def test_user(self, db: AsyncSession, test_organization):
        """Create test user."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            organization_id=test_organization.id,
            role="editor"
        )
        db.add(user)
        await db.commit()
        return user
    
    @pytest.mark.asyncio
    async def test_create_document_success(
        self,
        client: AsyncClient,
        test_user,
        test_organization
    ):
        """Test successful document creation."""
        # Arrange
        files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
        headers = {"Authorization": f"Bearer {test_user.api_key}"}
        
        # Act
        response = await client.post(
            "/api/v1/documents",
            files=files,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["status"] == "pending"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_create_document_invalid_mime_type(
        self,
        client: AsyncClient,
        test_user
    ):
        """Test document creation with invalid MIME type."""
        # Arrange
        files = {"file": ("test.exe", b"EXE content", "application/x-msdownload")}
        headers = {"Authorization": f"Bearer {test_user.api_key}"}
        
        # Act
        response = await client.post(
            "/api/v1/documents",
            files=files,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 400
        assert "Unsupported MIME type" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_document_unauthorized(self, client: AsyncClient):
        """Test document creation without auth."""
        files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
        response = await client.post("/api/v1/documents", files=files)
        assert response.status_code == 401
```

### Integration Test Pattern

```python
@pytest.mark.integration
class TestDocumentProcessingPipeline:
    """Integration test for complete document processing."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_document_processing(
        self,
        db: AsyncSession,
        vector_db_client,
        embedding_service,
        test_organization
    ):
        """Test complete pipeline from upload to searchable chunks."""
        # 1. Upload document
        doc = await create_document(
            filename="test.pdf",
            content=b"Test content about AI",
            organization_id=test_organization.id
        )
        assert doc.status == "pending"
        
        # 2. Process document
        chunks = await process_document(doc.id)
        assert len(chunks) > 0
        assert all(c.embedding is not None for c in chunks)
        
        # 3. Verify chunks in vector DB
        results = await vector_db_client.search(
            query="AI",
            collection=f"org_{test_organization.id}",
            limit=5
        )
        assert len(results) > 0
        assert results[0].document_id == doc.id
        
        # 4. Verify document status updated
        await db.refresh(doc)
        assert doc.status == "completed"
        assert doc.chunk_count == len(chunks)
```

---

## 🔐 Security Patterns

### Input Validation

```python
from pydantic import BaseModel, validator, Field
import re

class ChatRequest(BaseModel):
    """Validated chat request."""
    
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[UUID] = None
    model: str = Field(default="gpt-4-turbo")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    @validator('message')
    def validate_message(cls, v):
        """Sanitize message content."""
        # Remove potential prompt injections
        forbidden_patterns = [
            r'ignore previous instructions',
            r'system:',
            r'<\|im_start\|>',
        ]
        for pattern in forbidden_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Message contains forbidden pattern')
        
        # Remove excessive whitespace
        v = re.sub(r'\s+', ' ', v).strip()
        return v
    
    @validator('model')
    def validate_model(cls, v):
        """Ensure model is in whitelist."""
        allowed = ['gpt-4-turbo', 'claude-3-opus', 'llama-3-70b']
        if v not in allowed:
            raise ValueError(f'Model {v} not allowed')
        return v
```

### Rate Limiting

```python
from fastapi import HTTPException, Request
from redis.asyncio import Redis
import time

class RateLimiter:
    """Token bucket rate limiter using Redis."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> bool:
        """Check if request is within rate limit."""
        now = int(time.time())
        window_start = now - window_seconds
        
        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
        pipe.zadd(key, {str(now): now})  # Add current request
        pipe.zcard(key)  # Count requests in window
        pipe.expire(key, window_seconds)  # Set expiry
        
        _, _, count, _ = await pipe.execute()
        return count <= max_requests

async def rate_limit_dependency(
    request: Request,
    user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """FastAPI dependency for rate limiting."""
    limits = {
        "viewer": (100, 3600),   # 100 req/hour
        "editor": (500, 3600),   # 500 req/hour
        "admin": (2000, 3600),   # 2000 req/hour
    }
    
    max_req, window = limits[user.role]
    key = f"rate_limit:user:{user.id}"
    
    if not await rate_limiter.check_rate_limit(key, max_req, window):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window)}
        )
```

### Audit Logging

```python
from contextvars import ContextVar
import structlog

# Context for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')

async def create_audit_log(
    action: str,
    resource_type: str,
    resource_id: UUID,
    changes: Dict[str, Any],
    db: AsyncSession
):
    """Create audit log entry."""
    audit = AuditLog(
        id=uuid4(),
        request_id=request_id_var.get(),
        user_id=UUID(user_id_var.get()),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=changes,
        timestamp=datetime.utcnow(),
        ip_address=request_ip_var.get()
    )
    db.add(audit)
    await db.flush()
    
    logger.info(
        "audit_log_created",
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id)
    )

# Usage in endpoints
@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    doc = await doc_repo.get_by_id(document_id, user.organization_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    # Audit log before deletion
    await create_audit_log(
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        changes={"filename": doc.filename, "deleted_by": str(user.id)},
        db=db
    )
    
    await doc_repo.soft_delete(document_id)
    return {"message": "Document deleted"}
```

---

## 📊 Configuration Reference

### Complete Configuration Schema

```yaml
# config/base.yaml
app:
  name: "Knowledge Foundry"
  version: "2.0.0"
  environment: "production"  # dev, staging, production
  debug: false
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

database:
  host: "${DB_HOST:localhost}"
  port: "${DB_PORT:5432}"
  name: "${DB_NAME:knowledge_foundry}"
  user: "${DB_USER:postgres}"
  password: "${DB_PASSWORD}"
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
  pool_recycle: 3600
  echo: false
  ssl_mode: "prefer"  # disable, prefer, require

redis:
  host: "${REDIS_HOST:localhost}"
  port: "${REDIS_PORT:6379}"
  db: 0
  password: "${REDIS_PASSWORD:}"
  ssl: false
  max_connections: 50

vector_db:
  provider: "qdrant"  # qdrant, chroma, pinecone
  host: "${QDRANT_HOST:localhost}"
  port: "${QDRANT_PORT:6333}"
  api_key: "${QDRANT_API_KEY:}"
  collection_prefix: "kf"
  distance_metric: "cosine"  # cosine, euclidean, dot
  vector_size: 1536

llm:
  default_provider: "openai"
  default_model: "gpt-4-turbo"
  timeout_seconds: 60
  max_retries: 3
  
  providers:
    openai:
      enabled: true
      api_key: "${OPENAI_API_KEY}"
      base_url: "https://api.openai.com/v1"
      models:
        - gpt-4-turbo
        - gpt-3.5-turbo
      rate_limit: 100  # requests per minute
    
    anthropic:
      enabled: true
      api_key: "${ANTHROPIC_API_KEY}"
      models:
        - claude-3-opus-20240229
        - claude-3-sonnet-20240229
      rate_limit: 50
    
    ollama:
      enabled: true
      host: "http://ollama:11434"
      models:
        - llama-3-8b
        - mistral-7b
      gpu_enabled: true

embedding:
  provider: "openai"  # openai, sentence_transformers, cohere
  model: "text-embedding-3-small"
  dimensions: 1536
  batch_size: 100

document_processing:
  allowed_mime_types:
    - application/pdf
    - text/plain
    - text/markdown
    - application/vnd.openxmlformats-officedocument.wordprocessingml.document
  max_file_size: 104857600  # 100MB in bytes
  
  chunking:
    strategy: "recursive"  # recursive, semantic, fixed
    chunk_size: 1000
    chunk_overlap: 200
    separators: ["\n\n", "\n", ". ", " ", ""]
  
  parsers:
    unstructured:
      enabled: true
      strategy: "fast"  # fast, hi_res, ocr_only
    
    docling:
      enabled: true
      ocr_enabled: false

authentication:
  jwt_secret: "${JWT_SECRET}"
  jwt_algorithm: "HS256"
  access_token_expire_minutes: 60
  refresh_token_expire_days: 30
  
  oauth2:
    google:
      enabled: false
      client_id: "${GOOGLE_CLIENT_ID:}"
      client_secret: "${GOOGLE_CLIENT_SECRET:}"

rate_limiting:
  enabled: true
  storage: "redis"  # redis, memory
  
  limits:
    viewer:
      requests_per_hour: 100
      burst: 10
    editor:
      requests_per_hour: 500
      burst: 20
    admin:
      requests_per_hour: 2000
      burst: 50

caching:
  semantic_cache:
    enabled: true
    similarity_threshold: 0.95
    ttl_seconds: 3600
  
  exact_cache:
    enabled: true
    ttl_seconds: 1800

observability:
  prometheus:
    enabled: true
    port: 9090
  
  langfuse:
    enabled: true
    public_key: "${LANGFUSE_PUBLIC_KEY}"
    secret_key: "${LANGFUSE_SECRET_KEY}"
    host: "${LANGFUSE_HOST:https://cloud.langfuse.com}"
  
  logging:
    format: "json"  # json, text
    level: "INFO"
    structured: true

storage:
  provider: "s3"  # s3, minio, local
  bucket: "knowledge-foundry-documents"
  region: "us-east-1"
  endpoint: "${S3_ENDPOINT:}"
  access_key: "${S3_ACCESS_KEY}"
  secret_key: "${S3_SECRET_KEY}"
```

---

## 🚀 Prompt Usage Guidelines

### When to Use Each Prompt

| Phase | Prompt | When to Use | Expected Output |
|-------|--------|-------------|-----------------|
| 0 | Strategic Analysis | Before any code | Technology validation, ADRs, risk analysis |
| 0 | Plugin Architecture | After analysis approved | Complete plugin system interfaces |
| 0 | Configuration Design | After plugin design | Configuration schema and loader |
| 1 | LLM Router | Start of implementation | Production LLM routing system |
| 1 | Database Layer | After router | Complete DB models and repositories |
| 1 | Document Pipeline | After database | Document processing system |

### Prompt Context Template

Use this template when invoking AI:

```markdown
# CONTEXT
Project: Knowledge Foundry - Enterprise RAG Platform
Phase: [Phase Number and Name]
Reference Document: AI-Implementation-Reference.md (this document)

# PREVIOUS DECISIONS
[List relevant ADRs and architectural decisions from previous phases]

# CURRENT TASK
[Specific task from the prompt]

# CONSTRAINTS
- Must follow patterns in AI-Implementation-Reference.md
- Must include full type hints (mypy strict)
- Must include structured logging
- Must include Prometheus metrics
- Must achieve 95%+ test coverage
- Must handle all error cases
- Production-ready code only (no TODOs)

# OUTPUT REQUIREMENTS
[List specific files and deliverables expected]
```

---

## 🎯 Quality Checklist

Before considering any component complete:

### Code Quality
- [ ] Full type hints (passes `mypy --strict`)
- [ ] Google-style docstrings for all functions/classes
- [ ] Structured logging with context
- [ ] Prometheus metrics for key operations
- [ ] Comprehensive error handling
- [ ] Input validation with Pydantic
- [ ] Proper async/await usage
- [ ] No hardcoded values (use config)

### Testing
- [ ] Unit tests for business logic
- [ ] Integration tests for API endpoints
- [ ] Test edge cases and error conditions
- [ ] 95%+ code coverage
- [ ] Load tests for performance-critical paths
- [ ] Security tests (SQL injection, XSS, etc.)

### Security
- [ ] All user input validated
- [ ] SQL injection prevention (ORM/parameterized)
- [ ] XSS prevention (output escaping)
- [ ] Rate limiting implemented
- [ ] Audit logging for sensitive operations
- [ ] No secrets in code (use env vars)
- [ ] HTTPS enforcement in production

### Performance
- [ ] Database queries optimized (indexes, N+1 prevention)
- [ ] Async I/O for external calls
- [ ] Connection pooling configured
- [ ] Caching where appropriate
- [ ] Pagination for large result sets
- [ ] p95 latency < target SLA

### Observability
- [ ] Structured logging throughout
- [ ] Prometheus metrics exported
- [ ] Error tracking integrated
- [ ] Health check endpoint
- [ ] Ready check endpoint
- [ ] LangFuse tracing for LLM calls

### Documentation
- [ ] README with setup instructions
- [ ] API documentation (OpenAPI)
- [ ] Architecture diagrams updated
- [ ] Configuration documented
- [ ] Deployment guide updated

---

## 📝 Example: Complete Feature Implementation

Here's how to implement a complete feature following all patterns:

```python
# File: api/v1/chat.py
"""
Chat API endpoints.

Implements real-time chat with RAG using:
- LLM routing with fallback
- Semantic search over documents
- Streaming responses
- Rate limiting
- Audit logging
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncIterator
import structlog

from core.auth import get_current_user
from core.dependencies import get_db, get_llm_router, get_vector_db
from models.user import User
from models.chat import Chat, Message
from schemas.chat import ChatRequest, ChatResponse, MessageCreate
from repositories.chat_repository import ChatRepository
from services.rag_service import RAGService
from core.metrics import (
    chat_requests_total,
    chat_duration_seconds,
    chat_tokens_total
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

@router.post("/", response_model=ChatResponse)
async def create_chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_router = Depends(get_llm_router),
    vector_db = Depends(get_vector_db)
):
    """
    Create new chat and get first response.
    
    This endpoint:
    1. Validates request (Pydantic)
    2. Checks rate limits
    3. Performs semantic search over user's documents
    4. Generates LLM response with RAG
    5. Stores chat and message
    6. Returns response with metadata
    
    Args:
        request: ChatRequest with message and optional config
        user: Authenticated user from JWT
        db: Database session
        llm_router: LLM routing service
        vector_db: Vector database client
    
    Returns:
        ChatResponse with answer, sources, and metadata
    
    Raises:
        HTTPException 400: Invalid request
        HTTPException 429: Rate limit exceeded
        HTTPException 500: Internal error
    
    Performance:
        - Typical: 2-4 seconds for GPT-4 response
        - Includes: vector search (200ms) + LLM call (1.5-3s)
    """
    log = logger.bind(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        model=request.model
    )
    
    start = time.time()
    chat_requests_total.labels(
        user_role=user.role,
        model=request.model
    ).inc()
    
    try:
        log.info("chat_request_started")
        
        # Create chat record
        chat_repo = ChatRepository(db)
        chat = await chat_repo.create(
            user_id=user.id,
            organization_id=user.organization_id,
            title=request.message[:100],
            model=request.model
        )
        
        # Perform RAG
        rag_service = RAGService(llm_router, vector_db, db)
        result = await rag_service.generate_response(
            query=request.message,
            organization_id=user.organization_id,
            model=request.model,
            temperature=request.temperature
        )
        
        # Store message
        message = await chat_repo.add_message(
            chat_id=chat.id,
            role="assistant",
            content=result.answer,
            token_count=result.token_count,
            cost=result.cost,
            latency_ms=int((time.time() - start) * 1000)
        )
        
        # Update chat stats
        await chat_repo.update_stats(
            chat_id=chat.id,
            total_tokens=result.token_count,
            total_cost=result.cost
        )
        
        # Audit log
        await create_audit_log(
            action="chat.create",
            resource_type="chat",
            resource_id=chat.id,
            changes={
                "model": request.model,
                "message_length": len(request.message)
            },
            db=db
        )
        
        # Metrics
        duration = time.time() - start
        chat_duration_seconds.observe(duration)
        chat_tokens_total.labels(model=request.model).inc(result.token_count)
        
        log.info(
            "chat_request_completed",
            chat_id=str(chat.id),
            duration=duration,
            tokens=result.token_count,
            sources=len(result.sources)
        )
        
        return ChatResponse(
            chat_id=chat.id,
            message_id=message.id,
            answer=result.answer,
            sources=result.sources,
            model=request.model,
            token_count=result.token_count,
            cost=result.cost,
            latency_ms=int(duration * 1000)
        )
    
    except RateLimitError as e:
        log.warning("rate_limit_exceeded", error=str(e))
        raise HTTPException(429, "Rate limit exceeded")
    
    except VectorDBError as e:
        log.error("vector_db_error", error=str(e))
        raise HTTPException(500, "Search service unavailable")
    
    except LLMProviderError as e:
        log.error("llm_provider_error", error=str(e), provider=e.provider)
        raise HTTPException(500, f"AI service error: {e.message}")
    
    except Exception as e:
        log.error(
            "unexpected_error",
            error=str(e),
            traceback=traceback.format_exc()
        )
        raise HTTPException(500, "Internal server error")

@router.post("/{chat_id}/messages", response_model=ChatResponse)
async def add_message(
    chat_id: UUID,
    request: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_router = Depends(get_llm_router),
    vector_db = Depends(get_vector_db)
):
    """Add message to existing chat."""
    # Similar pattern to create_chat
    # Load chat history for context
    # Perform RAG with conversation history
    # Store new message
    pass

@router.get("/{chat_id}/stream")
async def stream_response(
    chat_id: UUID,
    message: str,
    user: User = Depends(get_current_user),
    llm_router = Depends(get_llm_router)
):
    """
    Stream LLM response in real-time.
    
    Returns:
        StreamingResponse with Server-Sent Events
    """
    async def generate() -> AsyncIterator[str]:
        """Generate SSE stream."""
        async for chunk in llm_router.stream(message):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# File: tests/api/test_chat.py
"""Tests for chat API."""

import pytest
from httpx import AsyncClient
from uuid import uuid4

class TestChatAPI:
    """Test chat endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_chat_success(
        self,
        client: AsyncClient,
        test_user,
        mock_llm_router,
        mock_vector_db
    ):
        """Test successful chat creation."""
        # Arrange
        headers = {"Authorization": f"Bearer {test_user.token}"}
        payload = {
            "message": "What is RAG?",
            "model": "gpt-4-turbo"
        }
        
        # Mock LLM response
        mock_llm_router.route.return_value = {
            "answer": "RAG stands for Retrieval Augmented Generation...",
            "token_count": 150,
            "cost": 0.0045
        }
        
        # Mock vector search
        mock_vector_db.search.return_value = [
            {"content": "RAG is...", "score": 0.92}
        ]
        
        # Act
        response = await client.post(
            "/api/v1/chat",
            json=payload,
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "chat_id" in data
        assert "answer" in data
        assert data["model"] == "gpt-4-turbo"
        assert data["token_count"] == 150
        assert len(data["sources"]) > 0
    
    @pytest.mark.asyncio
    async def test_create_chat_rate_limited(
        self,
        client: AsyncClient,
        test_user
    ):
        """Test rate limiting."""
        headers = {"Authorization": f"Bearer {test_user.token}"}
        payload = {"message": "Test", "model": "gpt-4-turbo"}
        
        # Make requests until rate limited
        for _ in range(test_user.rate_limit + 1):
            response = await client.post(
                "/api/v1/chat",
                json=payload,
                headers=headers
            )
        
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
```

---

## 🎓 Best Practices Summary

1. **Always use type hints** - Enables better IDE support and catches errors early
2. **Structured logging** - Makes debugging in production possible
3. **Metrics everywhere** - You can't improve what you don't measure
4. **Error handling** - Plan for failure, implement graceful degradation
5. **Testing** - Write tests as you code, not after
6. **Security first** - Validate input, rate limit, audit log
7. **Configuration-driven** - No hardcoded values, use env vars
8. **Documentation** - Code explains how, comments explain why
9. **Async by default** - Use async/await for all I/O operations
10. **Repository pattern** - Abstract database access, enable testing

---

**This document is your single source of truth. Reference it in every AI prompt. Update it as patterns evolve.**