# Phase 5.1 – Performance Optimization Strategy
## Knowledge Foundry: Latency, Throughput & Cost Optimization

**Version**: 1.0 | **Date**: February 14, 2026 | **Status**: 📋 IMPLEMENTATION SPEC  
**Depends on**: Phase 1 (Core Platform), Phase 2 (Multi-Agent), Phase 4.1 (Testing — load benchmarks)

---

## 1. PERFORMANCE TARGETS

### 1.1 Latency Targets

| Query Type | p50 | p95 | p99 |
|------------|:---:|:---:|:---:|
| Simple (Vector only) | <100ms | <200ms | <500ms |
| Complex (Hybrid VectorCypher) | <200ms | <500ms | <1000ms |
| Multi-Agent (3+ agents) | <500ms | <1500ms | <3000ms |
| Batch/Async | N/A | <10s | <30s |

### 1.2 Throughput Targets

| Metric | Target |
|--------|:------:|
| Sustained QPS | 500 |
| Burst QPS (1 min) | 1000 |
| Per-User QPS | 10 (rate limit) |

### 1.3 Cost Targets

| Metric | Target |
|--------|:------:|
| Cost per Query (avg) | <$0.10 |
| Monthly Infrastructure (1K users) | <$30,000 |
| Monthly LLM API (1K users, 100K queries) | <$10,000 |

---

## 2. OPTIMIZATION LEVERS

### 2.1 Multi-Level Caching Strategy

```
┌───────────────────────────────────┐
│  Level 1: Response Cache (Hot)    │  Redis, 5-15 min TTL
│  Full responses for identical     │  Hit rate target: >40%
│  queries per tenant               │
├───────────────────────────────────┤
│  Level 2: Embedding Cache (Warm)  │  Persistent, no TTL
│  Query embeddings (deterministic) │  Eliminates redundant API calls
├───────────────────────────────────┤
│  Level 3: Retrieval Cache (Warm)  │  Redis, event-based invalidation
│  Vector search results for        │  Invalidates on document update
│  common queries                   │
└───────────────────────────────────┘
```

**Level 1 — Response Cache:**

```python
class ResponseCache:
    def get_cached_response(self, query_hash: str, tenant_id: str) -> Optional[Dict]:
        cache_key = f"{tenant_id}:{query_hash}"
        cached = redis.get(cache_key)
        if cached:
            cached["hit"] = True
            return cached
        return None

    def cache_response(self, query_hash: str, tenant_id: str, response: Dict, ttl: int = 300):
        redis.setex(f"{tenant_id}:{query_hash}", ttl, json.dumps(response))
```

**Level 2 — Embedding Cache:**

```python
class EmbeddingCache:
    def get_embedding(self, text: str) -> List[float]:
        cache_key = hashlib.sha256(text.encode()).hexdigest()
        cached = persistent_cache.get(cache_key)
        if cached:
            return cached
        embedding = generate_embedding(text)
        persistent_cache.set(cache_key, embedding)   # No TTL — deterministic
        return embedding
```

**Level 3 — Retrieval Cache:**

```python
class RetrievalCache:
    def get_cached_results(self, query_embedding, top_k: int, filters: Dict):
        cache_key = f"retrieval:{hash(query_embedding)}:{top_k}:{hash(filters)}"
        return redis.get(cache_key)
```

**Cache Invalidation Strategy:**
- **Time-based**: 5-15 min TTL (configurable per tenant)
- **Event-based**: Invalidate on document update
- **Manual**: Admin flush via API

---

### 2.2 Query Optimization

**Vector Search — Qdrant HNSW Tuning:**

```yaml
hnsw_config:
  m: 16                  # Connections per node
  ef_construct: 100      # Build-time search quality
  ef: 64                 # Query-time search quality (tunable)
  # ef=32  → 2x faster, ~2% recall drop
  # ef=128 → 2x slower, ~1% recall gain
```

**Adaptive top_k:**

```python
def determine_optimal_top_k(query_complexity: str) -> int:
    return {"simple": 5, "medium": 10, "complex": 20}[query_complexity]
```

**Graph Traversal — Breadth Limiting:**

```cypher
-- BAD: Explodes exponentially
MATCH path = (start)-[*1..3]-(related)
RETURN path

-- GOOD: Limit breadth at each hop
MATCH (start)-[r1]-(hop1)
WITH start, hop1, r1 LIMIT 10
MATCH (hop1)-[r2]-(hop2)
WITH start, hop1, hop2, [r1, r2] as rels LIMIT 50
RETURN start, hop1, hop2, rels
```

**Graph — Relationship Confidence Filtering:**

```cypher
MATCH path = (start)-[r:DEPENDS_ON|AFFECTS*1..3]-(related)
WHERE all(rel in relationships(path) WHERE rel.confidence > 0.7)
RETURN path
```

---

### 2.3 Tiered Intelligence Optimization

| | Current | Optimized | Δ |
|---|:---:|:---:|:---:|
| **Opus** | 10% | 5% | ↓ 5% |
| **Sonnet** | 60% | 45% | ↓ 15% |
| **Haiku** | 30% | 50% | ↑ 20% |
| **Avg Cost/Query** | $0.09 | $0.06 | **-33%** |

**Strategy:**
- Improve Haiku routing accuracy (reduce false escalations)
- Use Haiku for all classification, extraction, formatting
- Escalate to Sonnet only if Haiku confidence < 0.7

---

### 2.4 Prompt Optimization

**Prompt Compression (20-30% token savings):**

```diff
- You are an AI assistant. Your task is to answer the user's question based
- on the provided context. Please make sure to cite your sources using the
- document IDs provided. If the information is not in the context, please
- say that you don't have that information. Do not make up information.
-
- Context:
- [10,000 tokens of context]
-
- Question: What is our security policy?
- Please provide your answer:

+ Answer using ONLY the context below. Cite sources [doc_id]. If not in
+ context, say "Not available."
+
+ Context:
+ [8,000 tokens - deduped, pruned]
+
+ Q: What is our security policy?
+ A:
```

**Context Deduplication:**

```python
def deduplicate_context(chunks: List[Chunk]) -> List[Chunk]:
    unique, seen = [], set()
    for chunk in chunks:
        h = hashlib.md5(chunk.text.encode()).hexdigest()
        if h not in seen:
            unique.append(chunk)
            seen.add(h)
    return unique
```

---

### 2.5 Batch Processing

```python
class BatchProcessor:
    batch_size = 10
    batch_timeout = 5     # seconds

    def process_batch(self):
        queries = [q.text for q in self.batch_queue]
        embeddings = generate_embeddings_batch(queries)       # 1 API call vs N
        results = parallel_vector_search(embeddings)
        answers = batch_llm_inference(queries, results)
        for query, answer in zip(self.batch_queue, answers):
            query.callback(answer)
```

**Use Cases**: Analytics queries, batch document processing, scheduled reports  
**Cost Savings**: 30-50% for batch workloads

---

### 2.6 Parallel Execution

```python
async def supervisor_parallel_delegation(sub_tasks):
    # Sequential: T1 + T2 + T3
    # Parallel:   max(T1, T2, T3)  → 2-3x speedup
    results = await asyncio.gather(
        researcher_agent(sub_tasks),
        risk_agent(sub_tasks),
        compliance_agent(sub_tasks),
    )
```

---

## 3. DATABASE OPTIMIZATION

### 3.1 PostgreSQL Tuning

**Connection Pooling:**

```python
engine = create_engine(
    "postgresql://...",
    pool_size=50,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

**Indexes:**

```sql
CREATE INDEX idx_documents_tenant_id ON documents(tenant_id);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE INDEX idx_queries_user_id_timestamp ON queries(user_id, timestamp DESC);
CREATE INDEX idx_documents_tenant_created ON documents(tenant_id, created_at DESC);
```

**Materialized Views (Analytics):**

```sql
CREATE MATERIALIZED VIEW daily_query_stats AS
SELECT DATE(timestamp) as date, tenant_id,
       COUNT(*) as query_count, AVG(latency_ms) as avg_latency,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency
FROM queries GROUP BY DATE(timestamp), tenant_id;

-- Refresh nightly
REFRESH MATERIALIZED VIEW daily_query_stats;
```

### 3.2 Qdrant Optimization

```yaml
storage:
  on_disk: true
  optimizers:
    indexing_threshold: 20000

performance:
  max_search_threads: 4
```

**Adaptive ef:**

```python
def get_search_ef(current_load: float) -> int:
    return 32 if current_load > 0.8 else 64
```

### 3.3 Neo4j Optimization

**Indexes:**

```cypher
CREATE INDEX entity_id FOR (n:Entity) ON (n.id);
CREATE INDEX entity_tenant FOR (n:Entity) ON (n.tenant_id);
CREATE INDEX relationship_confidence FOR ()-[r:DEPENDS_ON]-() ON (r.confidence);
```

**Query Pattern:**

```cypher
MATCH (start:Entity {id: $start_id})-[:DEPENDS_ON|AFFECTS*1..3]-(related)
WHERE start.tenant_id = $tenant_id
RETURN related LIMIT 100
```

---

## 4. INFRASTRUCTURE SCALING

### 4.1 Horizontal Scaling (Kubernetes)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledge-foundry-api
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
  template:
    spec:
      containers:
      - name: api
        image: knowledge-foundry:latest
        resources:
          requests: { cpu: 1000m, memory: 2Gi }
          limits:   { cpu: 2000m, memory: 4Gi }
        env:
        - name: MAX_WORKERS
          value: "4"
```

**Auto-Scaling (HPA):**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: knowledge-foundry-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
  - type: Resource
    resource: { name: memory, target: { type: Utilization, averageUtilization: 80 } }
```

### 4.2 Load Balancing

```nginx
upstream api_servers {
    least_conn;
    server api-1:8000 weight=1;
    server api-2:8000 weight=1;
    server api-3:8000 weight=1;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    location /v1/query {
        proxy_pass http://api_servers;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

### 4.3 CDN for Static Assets

**CloudFront/Cloudflare**: UI assets, API docs, public content  
**Benefits**: Reduced origin load, lower latency (edge), DDoS protection

---

## 5. MONITORING & CONTINUOUS OPTIMIZATION

### 5.1 Performance Monitoring Dashboard

| Metric | Visual | Alert |
|--------|--------|:-----:|
| Latency (p50/p95/p99) | Real-time line chart | p95 >500ms for >5 min |
| Throughput (QPS) | Gauge + sparkline | — |
| Error rate (%) | Gauge | >1% for >5 min → PagerDuty |
| Cache hit rate (%) | Gauge | <30% → review TTL |
| Cost per query ($) | Gauge + target | >2x baseline → email finance |

### 5.2 Continuous Optimization Loop

```python
class PerformanceOptimizer:
    def run_weekly_optimization(self):
        bottlenecks = self.analyze_traces()
        recommendations = []

        if bottlenecks["vector_search"] > 200:
            recommendations.append("Reduce HNSW ef to 32")
        if bottlenecks["llm_latency"] > 1000:
            recommendations.append("Compress context, review prompt length")
        if cache_hit_rate < 0.3:
            recommendations.append("Increase cache TTL or identify patterns")

        for rec in recommendations:
            result = self.a_b_test_optimization(rec)
            if result.improves_performance and not result.degrades_quality:
                self.deploy_optimization(rec)

        self.send_weekly_report(recommendations)
```

---

## 6. ACCEPTANCE CRITERIA

| # | Criterion | Test Method | Status |
|:-:|-----------|------------|:------:|
| 1 | p95 <500ms for complex queries | Load test | ☐ |
| 2 | p95 <200ms for simple queries | Load test | ☐ |
| 3 | Sustained throughput 500 QPS | Load test | ☐ |
| 4 | Cache hit rate >40% | Production monitoring | ☐ |
| 5 | Cost per query <$0.10 | Cost tracking | ☐ |
| 6 | Tiered intelligence: Haiku ≥50% of queries | Routing metrics | ☐ |
| 7 | Prompt compression: 20%+ token savings | A/B test | ☐ |
| 8 | Auto-scaling: 3→20 pods under load test | K8s HPA verification | ☐ |
| 9 | Load balancer distributes traffic evenly | LB metrics | ☐ |
| 10 | All DB queries <50ms with proper indexes | Query profiling | ☐ |
| 11 | Batch processing: 30%+ cost savings | Cost comparison | ☐ |
| 12 | Parallel agent execution: 2x+ speedup | Timing benchmark | ☐ |
| 13 | Weekly optimization reviews automated | Process verification | ☐ |
| 14 | Context deduplication reduces tokens 20%+ | A/B test | ☐ |
