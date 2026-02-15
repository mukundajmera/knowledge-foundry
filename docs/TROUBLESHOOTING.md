# Troubleshooting Guide

Common issues and solutions for Knowledge Foundry.

## Docker & Infrastructure

### Docker Daemon Not Running

**Symptom:**
```
✗ Docker daemon is not running. Please start Docker Desktop.
```

**Solution:**
1. Start Docker Desktop
2. Wait for it to fully initialize (green status)
3. Run `./kf.sh start` again

### Port Already in Use

**Symptom:**
```
Error: bind: address already in use
```

**Solution:**
```bash
# Find what's using the port
lsof -i :8000  # Replace 8000 with your port

# Kill the process
kill -9 <PID>

# Or change the port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 on host instead
```

### Health Check Timeout

**Symptom:**
```
⚠ postgres health check timed out after 60s
```

**Solution:**
```bash
# Check logs
./kf.sh logs postgres

# Common fixes:
# 1. Wait longer (services may be slow to start)
# 2. Increase resources in Docker Desktop
# 3. Restart Docker Desktop
# 4. Clean and restart
./kf.sh clean && ./kf.sh start
```

### Out of Disk Space

**Symptom:**
```
Error: no space left on device
```

**Solution:**
```bash
# Clean Docker system
docker system prune -a --volumes

# Clean Knowledge Foundry volumes specifically
./kf.sh clean
```

## API Errors

### Authentication Failed

**Symptom:**
```json
{
  "detail": "Could not validate credentials"
}
```

**Solution:**
1. Check JWT_SECRET_KEY in `.env`
2. Regenerate token
3. Verify token expiry (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)

### Rate Limited

**Symptom:**
```json
{
  "detail": "Rate limit exceeded"
}
```

**Solution:**
1. Wait for rate limit window to reset
2. Adjust rate limits in `src/api/middleware/rate_limit.py`
3. Use authentication for higher limits

### LLM Provider Error

**Symptom:**
```json
{
  "detail": "Anthropic rate limit exceeded"
}
```

**Solution:**
1. Check API key validity
2. Verify account limits
3. Wait and retry (uses exponential backoff)
4. Switch to different provider: `provider="ollama"` (local, no limits)

## LLM Routing Issues

### Always Using Opus (Expensive)

**Symptom:**
High costs, all requests going to Opus tier.

**Solution:**
```bash
# Check router complexity classification
# Add these logs to src/llm/router.py temporarily:

log.info(f"Complexity score: {score}, Tier: {tier}")

# Adjust thresholds in router.py:
# OPUS_THRESHOLD = 0.9  # Default 0.8, increase to use Opus less
# SONNET_THRESHOLD = 0.6  # Default 0.4, increase to use Sonnet less
```

### Circuit Breaker Always Open

**Symptom:**
```
CircuitBreakerOpenError: Circuit breaker open for opus
```

**Solution:**
```bash
# Check recent errors
./kf.sh logs api | grep "Circuit"

# Reset circuit breaker (restart)
./kf.sh restart

# Adjust thresholds in router.py:
# failure_threshold = 10  # Default 5, increase tolerance
```

## RAG (Retrieval) Issues

### No Results Found

**Symptom:**
Empty context, no relevant documents retrieved.

**Solution:**
1. **Check if documents are indexed:**
   ```bash
   curl http://localhost:8000/api/v1/documents/count
   ```

2. **Lower similarity threshold:**
   ```python
   # In src/retrieval/rag_pipeline.py
   similarity_threshold = 0.6  # Default 0.7, lower to retrieve more
   ```

3. **Increase top_k:**
   ```python
   top_k = 10  # Default 5
   ```

4. **Check embeddings service:**
   ```bash
   ./kf.sh logs api | grep "embedding"
   ```

### Qdrant Connection Failed

**Symptom:**
```
QdrantConnectionError: Could not connect to Qdrant
```

**Solution:**
```bash
# Check Qdrant is running
./kf.sh status

# Check logs
./kf.sh logs qdrant

# Verify connection
curl http://localhost:6333/healthz

# Restart Qdrant
docker compose restart qdrant
```

### Neo4j Connection Failed

**Symptom:**
```
ServiceUnavailable: Could not connect to Neo4j
```

**Solution:**
```bash
# Check Neo4j status
./kf.sh status

# Check browser UI
open http://localhost:7474

# Verify credentials in .env
NEO4J_USER=neo4j
NEO4J_PASSWORD=kf_dev_password

# Restart Neo4j
docker compose restart neo4j
```

## Agent Issues

### Supervisor Timeout

**Symptom:**
```
AgentError: Supervisor timed out after 300s
```

**Solution:**
1. **Adjust timeout:**
   ```python
   # In src/agents/supervisor.py
   timeout_seconds = 600  # Increase from 300
   ```

2. **Simplify query:**
   - Complex multi-step queries may timeout
   - Break into smaller queries

3. **Check agent logs:**
   ```bash
   ./kf.sh logs api | grep "Agent"
   ```

### Code Sandbox Plugin Fails

**Symptom:**
```
PluginError: Docker not available for sandbox
```

**Solution:**
1. **Docker is required for sandbox:**
   ```bash
   # Verify Docker is running
   docker ps
   ```

2. **Docker socket mounted:**
   ```yaml
   # In docker-compose.yml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
   ```

3. **Disable sandbox if not needed:**
   ```python
   # Don't use Coder agent / code execution
   use_supervisor = False
   ```

## Performance Issues

### Slow Response Times

**Symptom:**
API responses taking > 10s.

**Solution:**
1. **Check which tier is being used:**
   - Opus: Expect 3-5s
   - Sonnet: Expect 1-2s
   - Haiku: Expect 200-500ms

2. **Enable caching:**
   ```bash
   # Verify Redis is running
   ./kf.sh status | grep redis
   ```

3. **Check database performance:**
   ```bash
   ./kf.sh logs postgres | grep "slow query"
   ```

4. **Profile with Grafana:**
   - Open http://localhost:3001
   - Check "API Latency" dashboard

### High Memory Usage

**Symptom:**
API container using > 4GB RAM.

**Solution:**
1. **Increase Docker resources:**
   - Docker Desktop → Settings → Resources
   - Increase Memory to 8GB+

2. **Reduce batch sizes:**
   ```python
   # In src/retrieval/chunking.py
   batch_size = 10  # Default 32
   ```

3. **Disable features:**
   ```python
   # Disable graph search if not needed
   use_graph_search = False
   ```

## Database Issues

### PostgreSQL Migrations Failed

**Symptom:**
```
alembic.util.exc.CommandError: Can't locate revision
```

**Solution:**
```bash
# Reset migrations (⚠ destroys data)
./kf.sh shell api
alembic downgrade base
alembic upgrade head

# Or clean slate:
./kf.sh clean
./kf.sh start
./kf.sh db-migrate
```

### Redis Memory Full

**Symptom:**
```
RedisError: OOM command not allowed when used memory > 'maxmemory'
```

**Solution:**
```bash
# Increase maxmemory in docker-compose.yml
command: redis-server --maxmemory 512mb  # Increase from 256mb

# Or clear cache
docker compose exec redis redis-cli FLUSHALL
```

## Testing Issues

### Tests Fail Locally

**Symptom:**
```
ModuleNotFoundError: No module named 'src'
```

**Solution:**
```bash
# Install in editable mode
pip install -e ".[dev]"

# Verify import
python -c "import src; print(src.__file__)"
```

### Docker Tests Fail

**Symptom:**
```
ConnectionError: [Errno 111] Connection refused
```

**Solution:**
```bash
# Ensure test uses correct URLs
# In tests, use localhost:
QDRANT_HOST=localhost  # Not 'qdrant'

# Or run tests inside Docker
docker compose exec api pytest tests/
```

## Frontend Issues

### Frontend Won't Start

**Symptom:**
```
Error: Cannot find module 'next'
```

**Solution:**
```bash
cd frontend
npm install  # Reinstall dependencies
npm run dev
```

### API Connection Refused

**Symptom:**
Frontend shows "Network Error".

**Solution:**
1. **Check API is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check CORS settings:**
   ```python
   # In src/api/main.py
   allow_origins=["http://localhost:3000"]
   ```

3. **Check frontend env:**
   ```bash
   # In frontend/.env.local
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

## Getting Help

### Enable Debug Logging

```bash
# In .env
APP_LOG_LEVEL=DEBUG

# Restart
./kf.sh restart

# View logs
./kf.sh logs api
```

### Check All Logs

```bash
# All services
./kf.sh logs

# Specific service
./kf.sh logs api
./kf.sh logs postgres
./kf.sh logs qdrant
```

### Verify Configuration

```bash
# Print effective config
./kf.sh shell api
python -c "from src.core.config import get_settings; import json; print(json.dumps(get_settings().dict(), indent=2))"
```

### Report an Issue

When reporting issues, include:

1. **Error message** (full stack trace)
2. **Steps to reproduce**
3. **Environment:**
   ```bash
   ./kf.sh status
   python --version
   docker --version
   ```
4. **Logs:**
   ```bash
   ./kf.sh logs > logs.txt
   ```

Submit to: https://github.com/your-org/knowledge-foundry/issues

## See Also

- [Configuration Reference](CONFIGURATION.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Developer Guide](DEVELOPER_GUIDE.md)
