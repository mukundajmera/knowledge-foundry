# API Documentation

REST API reference for Knowledge Foundry.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

```bash
# Get token
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded

username=user&password=pass

# Use token
Authorization: Bearer <token>
```

## Endpoints

### Query

**POST /api/v1/query**

Execute a query with optional supervisor orchestration.

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain quantum computing",
    "use_supervisor": true,
    "provider": "anthropic"
  }'
```

**Request:**
```json
{
  "query": "string (required)",
  "use_supervisor": "boolean (default: false)",
  "provider": "string (optional: anthropic|oracle|lmstudio|ollama)",
  "force_model": "string (optional: opus|sonnet|haiku)",
  "max_tokens": "integer (default: 4096)",
  "temperature": "number (default: 0.2)"
}
```

**Response:**
```json
{
  "text": "Generated response...",
  "model": "claude-sonnet-4-20250514",
  "tier": "sonnet",
  "input_tokens": 150,
  "output_tokens": 500,
  "latency_ms": 1234,
  "cost_usd": 0.0045,
  "sources": [...]
}
```

### Documents

**POST /api/v1/documents**

Upload a document for indexing.

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@document.pdf" \
  -F "metadata={\"source\":\"manual\"}"
```

**GET /api/v1/documents**

List all documents.

**GET /api/v1/documents/{id}**

Get document details.

**DELETE /api/v1/documents/{id}**

Delete a document.

### Health

**GET /health**

Health check endpoint.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "qdrant": "healthy",
    "redis": "healthy",
    "postgres": "healthy",
    "neo4j": "healthy"
  }
}
```

### Providers

**GET /api/v1/providers**

List available LLM providers.

```json
{
  "providers": ["anthropic", "oracle", "lmstudio", "ollama"],
  "default": "anthropic"
}
```

### Metrics

**GET /metrics**

Prometheus metrics endpoint.

## Interactive Docs

**Swagger UI:** http://localhost:8000/docs

**ReDoc:** http://localhost:8000/redoc

## Status Codes

- `200` - Success
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

## Rate Limits

**Authenticated:** 100 requests/minute

**Anonymous:** 10 requests/minute

Header: `X-RateLimit-Remaining`

## Examples

### Python
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/v1/query",
        json={"query": "What is RAG?", "use_supervisor": False}
    )
    print(response.json())
```

### JavaScript
```javascript
const response = await fetch('http://localhost:8000/api/v1/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query: 'What is RAG?'})
});
const data = await response.json();
```

### curl
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?"}'
```
