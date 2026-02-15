# Knowledge Foundry — Deployment Runbook

## Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| Docker + Compose | 24+ / v2 | Container orchestration |
| Python | 3.12+ | Backend API |
| Node.js | 20+ | Frontend |
| kubectl | 1.28+ | Kubernetes deployment |
| k6 | 0.50+ | Load testing |

### Required Environment Variables

```bash
# .env (root of project)
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET_KEY=<random-256-bit-hex>   # openssl rand -hex 32
DATABASE_URL=postgresql+asyncpg://kf_user:kf_dev_password@localhost:5432/knowledge_foundry
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=kf_dev_password
```

---

## 1. Local Development

```bash
# Start infrastructure services
docker compose up -d qdrant redis postgres neo4j

# Backend
pip install -e ".[dev]"
uvicorn src.api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# All tests
python -m pytest tests/ -v
cd frontend && npx playwright test
```

---

## 2. Docker Compose (Staging)

```bash
# Start everything (8 services)
docker compose up -d --build

# Verify health
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/ready | jq .
curl -s http://localhost:8000/compliance/health | jq .

# Access UIs
# API:        http://localhost:8000/docs
# Frontend:   http://localhost:3000
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3001 (admin / kf_admin)
# Neo4j:      http://localhost:7474
# Qdrant:     http://localhost:6333/dashboard
```

---

## 3. Kubernetes (Production)

### Deploy Sequence

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create secrets
kubectl -n knowledge-foundry create secret generic kf-secrets \
  --from-literal=database-url='<PROD_DB_URL>' \
  --from-literal=jwt-secret='<JWT_SECRET>' \
  --from-literal=anthropic-api-key='<API_KEY>'

# 3. Deploy application
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml

# 4. Verify deployment
kubectl -n knowledge-foundry get pods
kubectl -n knowledge-foundry get hpa
kubectl -n knowledge-foundry logs -l app=kf-api --tail=50
```

### HPA Configuration

| Parameter | Value |
|-----------|-------|
| Min replicas | 3 |
| Max replicas | 20 |
| CPU target | 70% |
| Memory target | 80% |
| Scale-up window | 60s |
| Scale-down window | 300s |

---

## 4. CI/CD Pipeline

The GitHub Actions pipeline runs 7 jobs:

```
lint → test → ragas ─┐
         ↓           │
      security ──────┤
         ↓           │
      frontend ──────┤
                     ↓
                  docker → staging
```

**Quality gates (auto-fail deploy):**
- Unit test coverage < 85%
- RAGAS golden dataset validation fails
- Bandit finds high-severity issues
- Frontend build or E2E tests fail

---

## 5. Load Testing

```bash
# Run k6 load test (500 VU peak)
k6 run tests/load/load_test.js

# With custom API URL
k6 run -e API_URL=https://api.example.com tests/load/load_test.js
```

**Pass thresholds:**
- p95 latency < 500ms
- p99 latency < 1000ms
- Error rate < 1%

---

## 6. Rollback Procedure

### Automated Triggers
| Metric | Threshold | Action |
|--------|-----------|--------|
| Error rate | > 5% | Auto-rollback |
| p95 latency | > 1s | Auto-rollback |
| RAGAS score | < 0.90 | Block deploy |

### Manual Rollback

```bash
# Kubernetes
kubectl -n knowledge-foundry rollout undo deployment/kf-api
kubectl -n knowledge-foundry rollout status deployment/kf-api

# Docker Compose
docker compose down
git checkout <last-known-good-tag>
docker compose up -d --build
```

---

## 7. Disaster Recovery

| Parameter | Target |
|-----------|--------|
| RTO (Recovery Time) | 4 hours |
| RPO (Recovery Point) | 24 hours |
| Backup schedule | Daily |
| Restore drills | Monthly |

### Backup Commands

```bash
# PostgreSQL
pg_dump -U kf_user knowledge_foundry > backup_$(date +%Y%m%d).sql

# Qdrant
curl -X POST http://localhost:6333/collections/backup

# Neo4j
neo4j-admin database dump --to-path=/backups neo4j
```

---

## 8. Monitoring Access

| Service | URL | Credentials |
|---------|-----|-------------|
| API Health | `/health` | — |
| API Ready | `/ready` | — |
| Compliance | `/compliance/health` | — |
| Prometheus | `localhost:9090` | — |
| Grafana | `localhost:3001` | admin / kf_admin |

### Alert Rules

7 Prometheus alert rules fire on:
- p95 > 500ms, p99 > 1s
- Error rate > 1% (warn), > 5% (critical)
- Average cost > $0.10/query
- Cache hit rate < 50%
- API down for 30s
