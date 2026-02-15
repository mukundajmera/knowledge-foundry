# Configuration Reference

Complete reference for all Knowledge Foundry configuration options.

## Environment Variables

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `knowledge-foundry` | Application name |
| `APP_ENV` | `development` | Environment (`development`/`staging`/`production`) |
| `APP_DEBUG` | `true` | Debug mode |
| `APP_HOST` | `0.0.0.0` | Server bind host |
| `APP_PORT` | `8000` | Server bind port |
| `APP_LOG_LEVEL` | `INFO` | Log level (`DEBUG`/`INFO`/`WARN`/`ERROR`) |

### LLM Providers

#### Anthropic (Required)
```bash
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL_OPUS=claude-opus-4-20250514
ANTHROPIC_MODEL_SONNET=claude-sonnet-4-20250514
ANTHROPIC_MODEL_HAIKU=claude-3-5-haiku-20241022
ANTHROPIC_MAX_RETRIES=3
ANTHROPIC_TIMEOUT=60
```

#### OpenAI (For Embeddings)
```bash
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_MAX_RETRIES=3
OPENAI_TIMEOUT=60
```

#### Oracle Code Assist (Optional)
```bash
ORACLE_ENDPOINT=https://your-instance.oraclecloud.com/v1
ORACLE_API_KEY=your-key
ORACLE_MODEL=oracle-code-assist-v1
ORACLE_TIMEOUT=30
```

#### LM Studio (Optional - Local)
```bash
LMSTUDIO_HOST=localhost
LMSTUDIO_PORT=1234
LMSTUDIO_MODEL=          # Auto-detected
LMSTUDIO_TIMEOUT=60
```

#### Ollama (Optional - Local)
```bash
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3
OLLAMA_TIMEOUT=120
```

### LLM Routing

```bash
LLM_ALLOW_ESCALATION=true                # Enable tier escalation
LLM_ESCALATION_THRESHOLD=0.5             # Confidence threshold for escalation
```

### Vector Database (Qdrant)

```bash
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=knowledge_foundry
QDRANT_API_KEY=                          # Optional for cloud
```

### Cache (Redis)

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=                          # Optional
REDIS_TTL=3600                           # Cache TTL in seconds
```

### Database (PostgreSQL)

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_foundry
POSTGRES_USER=kf_user
POSTGRES_PASSWORD=kf_dev_password
```

### Graph Database (Neo4j)

```bash
NEO4J_HOST=localhost
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=kf_dev_password
```

### Security

```bash
JWT_SECRET_KEY=change-me-in-production    # REQUIRED: Change in production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480       # 8 hours
```

### Observability

#### Langfuse
```bash
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

#### Arize Phoenix
```bash
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

## Docker Compose Configuration

Edit `docker-compose.yml` to customize service settings:

### Resource Limits

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Port Mappings

```yaml
ports:
  - "8000:8000"  # Change left value to use different host port
```

### Environment Overrides

```yaml
environment:
  - LOG_LEVEL=debug
  - MAX_WORKERS=4
```

## Application Settings (src/core/config.py)

For advanced configuration, edit `src/core/config.py`:

### RAG Settings

```python
class RAGSettings(BaseSettings):
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    similarity_threshold: float = 0.7
    rerank_enabled: bool = True
```

### Agent Settings

```python
class AgentSettings(BaseSettings):
    max_iterations: int = 10
    timeout_seconds: int = 300
    enable_memory: bool = True
```

## Production Checklist

- [ ] Change `JWT_SECRET_KEY` to a secure random value
- [ ] Set `APP_ENV=production`
- [ ] Set `APP_DEBUG=false`
- [ ] Use strong database passwords
- [ ] Enable TLS/SSL
- [ ] Configure proper firewall rules
- [ ] Set up backup strategy
- [ ] Configure log rotation
- [ ] Enable rate limiting
- [ ] Set resource limits

## Example: Production .env

```bash
# Application
APP_ENV=production
APP_DEBUG=false
APP_LOG_LEVEL=INFO

# Security
JWT_SECRET_KEY=<generate-with-openssl-rand-base64-32>

# LLM
ANTHROPIC_API_KEY=<your-prod-key>

# Databases (use managed services)
QDRANT_HOST=qdrant-prod.example.com
QDRANT_API_KEY=<your-api-key>

REDIS_HOST=redis-prod.example.com
REDIS_PASSWORD=<strong-password>

POSTGRES_HOST=postgres-prod.example.com
POSTGRES_PASSWORD=<strong-password>

NEO4J_HOST=neo4j-prod.example.com
NEO4J_PASSWORD=<strong-password>

# Observability
LANGFUSE_PUBLIC_KEY=<your-key>
LANGFUSE_SECRET_KEY=<your-secret>
```

## See Also

- [Deployment Guide](DEPLOYMENT.md)
- [Security Guide](SECURITY.md)
- [Troubleshooting](TROUBLESHOOTING.md)
