# Knowledge Foundry — Deployment Runbook

## Quick Start

### Local Development

```bash
# Clone and setup Python
git clone <repo-url> && cd knowledge-foundry
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Start infrastructure
docker compose up -d qdrant redis postgres neo4j

# Run API
uvicorn src.api.main:app --reload --port 8000

# Start frontend
cd frontend && npm install && npm run dev
```

### Full Stack (Docker Compose)

```bash
# Build and start everything
docker compose up --build -d

# Verify
curl http://localhost:8000/health
open http://localhost:3000
open http://localhost:9090  # Prometheus
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant vector DB URL |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis cache URL |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | No | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Yes | — | Neo4j password |
| `JWT_SECRET_KEY` | Yes | — | JWT signing key (≥32 bytes) |
| `LOG_LEVEL` | No | `info` | Logging level |
| `ENVIRONMENT` | No | `development` | `development` / `production` |

---

## Kubernetes Deployment

```bash
# Create namespace and secrets
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic kf-secrets \
  --namespace=knowledge-foundry \
  --from-literal=database-url='postgresql+asyncpg://...' \
  --from-literal=jwt-secret='<32-byte-key>' \
  --from-literal=anthropic-api-key='<key>'

# Deploy
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml

# Verify
kubectl get pods -n knowledge-foundry
kubectl get hpa -n knowledge-foundry
```

---

## Testing

```bash
# Unit tests (256+ tests)
python -m pytest tests/unit/ -v --cov=src --cov-fail-under=85

# Evaluation tests (RAGAS metrics)
python -m pytest tests/evaluation/ -v

# Frontend E2E (18 tests)
cd frontend && npx playwright test

# Load testing (requires k6: brew install k6)
k6 run tests/load/load_test.js
```

---

## Monitoring

| Service | Port | URL |
|---------|------|-----|
| API | 8000 | `http://localhost:8000` |
| Frontend | 3000 | `http://localhost:3000` |
| Prometheus | 9090 | `http://localhost:9090` |
| Qdrant | 6333 | `http://localhost:6333/dashboard` |
| Neo4j | 7474 | `http://localhost:7474` |
| PostgreSQL | 5432 | — |
| Redis | 6379 | — |

### Key Metrics to Monitor

- **`kf_api_request_duration_seconds`** — p95 should be <500ms
- **`kf_api_request_total`** — Request throughput
- **`kf_llm_request_total`** — LLM API usage by model
- **`kf_security_events_total`** — Security event count
- **`kf_cache_hits_total`** / **`kf_cache_misses_total`** — Cache efficiency

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 503 on API | Pods not ready | `kubectl rollout status deploy/kf-api -n knowledge-foundry` |
| High latency | Cache cold | Wait for warm-up or increase cache TTL |
| 429 rate limit | Quota exceeded | Check tier limits, upgrade user tier |
| JWT decode error | Wrong secret | Verify `JWT_SECRET_KEY` matches across pods |
| Qdrant connection refused | Service not started | `docker compose up qdrant -d` |
| Neo4j auth failure | Wrong password | Check `NEO4J_AUTH` / `NEO4J_PASSWORD` |

---

## Production Checklist

- [ ] All secrets in K8s Secrets (not env vars or configmaps)
- [ ] TLS certificate configured via cert-manager
- [ ] HPA tested under load (3→20 pods)
- [ ] Backup schedule configured (PostgreSQL, Qdrant, Neo4j)
- [ ] Monitoring alerts configured in Prometheus/PagerDuty
- [ ] Rate limits tuned per tenant tier
- [ ] JWT secret is ≥32 bytes and rotated quarterly
- [ ] RAGAS evaluation passes quality gates
- [ ] Load test confirms p95 <500ms at 500 QPS
- [ ] EU AI Act audit trail enabled and immutable
