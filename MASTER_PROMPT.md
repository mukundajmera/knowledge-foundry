# KNOWLEDGE FOUNDRY — MASTER BUILD PROMPT
## Session-Resilient Implementation Controller

> **HOW TO USE**: Copy this entire file into any LLM session. The AI will read the GLOBAL CONTEXT, check the PROGRESS TRACKER, and resume from exactly where you left off. After each session, update the PROGRESS TRACKER section below with what was completed.

---

## 1. GLOBAL SYSTEM CONTEXT (always prepend)

You are building **Knowledge Foundry** — an enterprise AI knowledge management platform.

**Tech Stack:**
- **LLMs**: Anthropic Claude (Opus 4 / Sonnet 3.5 / Haiku 3) via tiered intelligence router
- **Vector DB**: Qdrant (HNSW, hybrid search)
- **Graph DB**: Neo4j (KET-RAG, entity-relationship traversal)
- **Relational DB**: PostgreSQL (metadata, audit, analytics)
- **Cache**: Redis (3-level: response → embedding → retrieval)
- **Backend**: Python 3.12+, FastAPI, LangChain/LangGraph, async
- **Frontend**: Next.js 14+, TypeScript, React
- **Orchestration**: Multi-agent supervisor pattern (LangGraph)
- **MLOps**: MLflow, DVC, GitHub Actions CI/CD
- **Observability**: Langfuse, Arize Phoenix, Prometheus/Grafana
- **Infra**: Kubernetes (HPA 3-20 pods), NGINX, CloudFront CDN
- **Compliance**: EU AI Act (Art. 6 High-Risk), OWASP 2026
- **Testing**: Pytest, RAGAS, Garak, k6, Playwright

**Architecture Pattern:**
```
User → API Gateway → LLM Router → Agent Supervisor
                                       ├── Researcher Agent → Hybrid RAG (Qdrant + Neo4j)
                                       ├── Risk Agent
                                       ├── Compliance Agent
                                       ├── Coder Agent
                                       ├── Growth Agent
                                       └── Safety Agent (guardrails)
```

**Quality Targets:**
| Metric | Target |
|--------|--------|
| RAGAS Faithfulness | >0.95 |
| Context Precision | >0.90 |
| Latency p95 | <500ms |
| Throughput | 500 QPS |
| Cost/Query | <$0.10 |
| Uptime | 99.9% |

**Project Root**: `/Users/mukundajmera/pocs/Knowledge Foundry/`
**Spec Docs**: `docs/architecture/phase-*.md` (11 files, all complete)

---

## 2. ARCHITECTURE SPECS SUMMARY (read full specs from `docs/architecture/` if details needed)

### Phase 1 — Core Platform
- Tiered LLM Router: complexity classifier → Haiku (simple) / Sonnet (standard) / Opus (complex)
- Hybrid VectorCypher RAG: vector similarity (Qdrant) + graph traversal (Neo4j) fusion
- Multi-tenant isolation: tenant_id on all queries, row-level security
- Observability: Langfuse tracing, Prometheus metrics, structured JSON logging

### Phase 2 — Multi-Agent & Plugins
- Supervisor pattern (LangGraph): routes to specialist agents, merges results
- 6 agents: Researcher, Coder, Risk, Growth, Safety, Compliance
- Plugin system: BasePlugin interface, manifest.yaml, sandboxed execution
- Agent communication: shared state + message bus

### Phase 3 — Security & Compliance
- OWASP 2026: input sanitization, output filtering, rate limiting, RBAC
- EU AI Act: auto tech docs (MLflow), immutable audit trail (SHA-256 hash chain), HITL triggers
- Compliance-as-code: YAML CI/CD gates, hourly monitoring, 15-day incident protocol

### Phase 4 — Testing
- Pyramid: 80% unit / 15% integration / 5% E2E
- RAGAS golden dataset (500 queries), Garak adversarial, k6 load (500 QPS sustained)
- Quality gates: no deploy if RAGAS below thresholds

### Phase 5 — Performance
- 3-level cache (Redis): response (5-15min TTL) → embedding (persistent) → retrieval (event-invalidated)
- Adaptive HNSW ef, dynamic top_k, graph breadth limiting
- Tiered intelligence: Haiku 50%, Sonnet 45%, Opus 5% → $0.06/query avg
- Batch processing, parallel agent execution (asyncio.gather)

### Phase 6 — MLOps
- CI/CD: test → eval → compliance → staging → load test → prod (blue-green)
- Automated rollback: error >5%, p95 >1s, or RAGAS <0.90
- DR: RTO 4h, RPO 24h, daily backups, monthly restore drills

### Phase 7 — UI/UX
- Chat-based with streaming, inline citations, progressive disclosure
- Advanced: file upload, multi-agent visualization, collaboration (share/annotate)
- Mobile-optimized, WCAG 2.1 AA, keyboard shortcuts

### Phase 8 — Continuous Improvement
- 13 KPIs, weekly automated analysis, 5-cohort user segmentation
- A/B testing (YAML config, t-test + Cohen's d, guardrails)
- Self-healing: auto-scale on latency, Opus-shift on quality drop, Haiku-shift on cost spike

---

## 3. PROJECT STRUCTURE (target)

```
Knowledge Foundry/
├── src/
│   ├── core/
│   │   ├── config.py              # Settings, env vars, multi-tenant config
│   │   ├── interfaces.py          # Abstract base classes (all contracts)
│   │   ├── exceptions.py          # Custom exceptions
│   │   └── dependencies.py        # ServiceContainer (DI wiring)
│   ├── llm/
│   │   ├── router.py              # Tiered intelligence router + complexity classifier
│   │   └── providers.py           # Anthropic client wrapper
│   ├── retrieval/
│   │   ├── vector_store.py        # Qdrant client
│   │   ├── hybrid_rag.py          # VectorCypher fusion (3 strategies)
│   │   ├── embeddings.py          # Embedding generation
│   │   └── chunking.py            # Semantic chunking
│   ├── graph/
│   │   ├── graph_store.py         # Neo4j client
│   │   ├── extraction.py          # Entity/relationship extraction
│   │   └── schemas.py             # Graph data models
│   ├── agents/
│   │   ├── supervisor.py          # Supervisor orchestrator
│   │   ├── researcher.py          # Research agent
│   │   ├── coder.py               # Code agent
│   │   ├── reviewer.py            # Review agent
│   │   ├── risk.py                # Risk agent
│   │   ├── compliance.py          # Compliance agent
│   │   ├── growth.py              # Growth agent
│   │   ├── safety.py              # Safety / guardrails agent
│   │   ├── state.py               # OrchestratorState (shared state)
│   │   └── graph_builder.py       # LangGraph orchestrator builder
│   ├── security/
│   │   ├── input_sanitizer.py     # Sanitization, injection detection, entropy
│   │   └── output_filter.py       # PII redaction, harmful content, leak detection
│   ├── observability/
│   │   ├── tracing.py             # Langfuse integration
│   │   └── metrics.py             # Prometheus metrics
│   ├── compliance/
│   │   └── audit.py               # Immutable hash-chained audit trail (EU AI Act Art. 12)
│   ├── cache/
│   │   ├── response_cache.py      # L1 response cache + L3 retrieval cache
│   │   └── embedding_cache.py     # L2 embedding cache
│   ├── improvement/
│   │   ├── metrics_collector.py   # 13 KPI collection
│   │   ├── weekly_analyzer.py     # Automated weekly analysis + recommendations
│   │   ├── ab_testing.py          # A/B test framework (t-test, Cohen's d)
│   │   ├── feedback_processor.py  # User feedback processing + sentiment
│   │   └── self_healing.py        # Auto-scale, model shifting, circuit breakers
│   ├── mlops/
│   │   ├── drift_monitor.py       # KL divergence + PSI drift detection
│   │   ├── deployment_monitor.py  # Auto-rollback + feature flags
│   │   ├── golden_dataset_manager.py # Production → golden dataset expansion
│   │   └── anomaly_detector.py    # Z-score anomaly detection
│   └── api/
│       ├── main.py                # FastAPI app
│       ├── routes/
│       │   ├── query.py           # POST /v1/query
│       │   ├── orchestrator.py    # POST /v1/orchestrate
│       │   ├── feedback.py        # POST /v1/feedback
│       │   ├── documents.py       # Document CRUD
│       │   ├── graph_routes.py    # Graph query endpoints
│       │   ├── health.py          # GET /health, /ready
│       │   └── compliance_health.py # GET /compliance/health
│       └── middleware/
│           ├── auth.py            # JWT + RBAC + tenant isolation
│           ├── rate_limit.py      # Per-user/tenant rate limiting
│           └── telemetry.py       # Request tracing + Prometheus
├── frontend/                      # Next.js 14 app
│   ├── app/                       # layout.tsx, page.tsx, globals.css
│   ├── components/                # ErrorBanner, FileUpload, MessageBubble, QueryInput, Sidebar, KeyboardShortcuts, RoutingTrace, ThemeToggle, DocumentManager
│   ├── hooks/                     # useChat.ts, useConversations.ts
│   ├── lib/                       # api.ts, types.ts
│   └── e2e/                       # Playwright: chat, sidebar, file-upload, accessibility
├── tests/
│   ├── unit/                      # 34 test files, 490+ tests
│   ├── integration/               # test_production_pipeline.py (26 tests)
│   ├── evaluation/                # RAGAS golden dataset (20+ questions) + test_ragas.py
│   └── load/                      # k6 load_test.js
├── k8s/                           # api-deployment, api-service, hpa, ingress, namespace
├── infra/                         # prometheus.yml, alert_rules.yml, grafana-dashboard.json
├── docs/
│   ├── architecture/              # 20 spec documents (COMPLETE)
│   ├── ADRs/                      # 7 Architecture Decision Records
│   ├── DEPLOYMENT.md
│   └── deployment-runbook.md
├── .github/workflows/
│   ├── ci.yml                     # CI/CD: test, security, RAGAS, lint
│   └── deploy.yml                 # Deploy: test → evaluate → staging → load test → production
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml             # 8 services: qdrant, redis, postgres, neo4j, api, frontend, prometheus, grafana
└── MASTER_PROMPT.md               # THIS FILE
```

---

## 4. IMPLEMENTATION ORDER (build sequence)

> **Rule**: Each task produces working, tested code. Every session should end with runnable state.

### MILESTONE 1 — Walking Skeleton (Sessions 1-3)
```
1.1 [x] Project scaffolding (pyproject.toml, Docker, .env, config.py, interfaces.py)
1.2 [x] Anthropic LLM client wrapper (providers.py) + basic router (router.py)
1.3 [x] Qdrant vector store (vector_store.py) + embedding generation (embeddings.py)
1.4 [x] Semantic chunking (chunking.py) + document ingestion endpoint
1.5 [x] Basic RAG query pipeline (vector search → LLM → response)
1.6 [x] FastAPI app (main.py) with /v1/query and /health endpoints
1.7 [x] Unit tests for core modules
```

### MILESTONE 2 — Hybrid RAG + Agents (Sessions 4-6)
```
2.1 [x] Neo4j graph store (graph_store.py) + entity extraction
2.2 [x] Hybrid VectorCypher fusion (hybrid_rag.py)
2.3 [x] Tiered intelligence router with complexity classifier
2.4 [x] Supervisor agent (supervisor.py) + Researcher agent
2.5 [x] Safety agent (guardrails, input/output filtering)
2.6 [x] Additional agents (Risk, Compliance, Coder, Growth)
2.7 [x] Integration tests for multi-agent flows
```

### MILESTONE 3 — Security & Caching (Sessions 7-8)
```
3.1 [x] Auth (JWT + RBAC) + tenant isolation middleware
3.2 [x] Input sanitization + prompt injection detection
3.3 [x] Output filtering (PII redaction, harmful content)
3.4 [x] Rate limiting (per-user, per-tenant)
3.5 [x] 3-level Redis cache (response, embedding, retrieval)
3.6 [x] Observability (Langfuse tracing, Prometheus metrics)
3.7 [x] Security tests
```

### MILESTONE 4 — Frontend (Sessions 9-10)
```
4.1 [x] Next.js project scaffolding + design system
4.2 [x] Chat interface (streaming, citations, markdown)
4.3 [x] Sources panel + answer card + feedback (👍/👎)
4.4 [x] Advanced options (model select, deep search, file upload)
4.5 [x] Conversation history + workspace sidebar
4.6 [x] Mobile responsive + accessibility (WCAG 2.1 AA)
4.7 [x] E2E tests (Playwright)
```

### MILESTONE 5 — Production Readiness (Sessions 11-12)
```
5.1 [x] Docker Compose (all services)
5.2 [x] CI/CD pipeline (GitHub Actions)
5.3 [x] RAGAS evaluation suite + golden dataset
5.4 [x] Audit trail + compliance checks
5.5 [x] Kubernetes manifests + HPA + load balancer
5.6 [x] Load testing (k6, 500 QPS target)
5.7 [x] Documentation + deployment runbook
```

### MILESTONE 6 — MLOps Pipeline (Phase 6)
```
6.1 [x] Data drift monitor (KL divergence + PSI, severity levels)
6.2 [x] Deployment monitor (auto-rollback on error/latency/quality)
6.3 [x] Feature flag manager (tenant-scoped, rollout percentage)
6.4 [x] Golden dataset manager (production → golden expansion)
6.5 [x] Anomaly detector (z-score, multi-metric, sliding windows)
6.6 [x] Deploy pipeline (deploy.yml: 7-stage blue-green)
```

### MILESTONE 7 — UI/UX Enhancements (Phase 7)
```
7.1 [x] RoutingTrace component (agent routing visualization)
7.2 [x] Dark/light theme toggle (localStorage + OS preference)
7.3 [x] Document manager page (CRUD, search, sort, upload)
7.4 [x] View tabs (Chat ↔ Documents) in header
7.5 [x] Light theme CSS variables
```

### MILESTONE 8 — Continuous Improvement (Phase 8)
```
8.1 [x] Metrics collector (13 KPIs, sliding windows)
8.2 [x] Weekly analyzer (trend detection, recommendations)
8.3 [x] A/B testing framework (YAML config, t-test + Cohen's d, guardrails)
8.4 [x] Feedback processor (sentiment analysis, topic extraction)
8.5 [x] Self-healing system (auto-scale, model shifting, circuit breakers)
```

---

## 5. PROGRESS TRACKER

> **IMPORTANT**: Update this section at the END of every session. The next session reads this to know where to resume.

### Current State
- **Last Session Date**: 2026-02-14
- **Last Milestone**: Milestone 7 — UI/UX Enhancements ✅ COMPLETE
- **Last Task Completed**: `7.5 — Light theme CSS`
- **Next Task**: All milestones (M1–M8) complete.
- **Blockers**: None
- **Total Tests**: 532 tests — ALL PASSING, frontend build clean

### Session Log
<!-- Append one entry per session. Format:
| # | Date | Tasks Done | Files Created/Modified | Notes |
-->
| # | Date | Tasks Done | Files Created/Modified | Notes |
|---|------|-----------|----------------------|-------|
| 1 | 2026-02-14 | 1.1–1.7 (scaffold, LLM, retrieval, API, tests, DI) | 17 src + 7 test files | 92 tests pass. Walking skeleton complete. |
| 2 | 2026-02-14 | 2.1–2.7 (graph, hybrid RAG, agents, orchestrator) | graph/, agents/, hybrid_rag.py + tests | All agent nodes + LangGraph routing verified. |
| 3 | 2026-02-14 | 3.1–3.7 (auth, sanitizer, filter, cache, observability) | security/, cache/, observability/, compliance/ + tests | Full security pipeline with 19 integration tests. |
| 4 | 2026-02-14 | 4.1–4.7 (Next.js frontend, chat, sidebar, e2e) | frontend/ (14 source files + Playwright) | Chat UI with streaming, file upload, keyboard shortcuts. |
| 5 | 2026-02-14 | 5.1–5.7 (Docker, CI/CD, K8s, RAGAS, audit) | Dockerfile, docker-compose.yml, k8s/, infra/, .github/ | Full production stack: 8 Docker services, 5 K8s manifests, Grafana dashboards. |
| 6 | 2026-02-14 | Phase 8 (continuous improvement framework) | src/improvement/ (5 modules) + tests | Metrics collector, weekly analyzer, A/B testing, self-healing. |
| 7 | 2026-02-14 | Full audit: M2–M5, M8 verified complete | No changes needed | 415 unit + 26 integration tests pass. Zero gaps found. |
| 8 | 2026-02-14 | M6: MLOps pipeline (drift, deployment, golden dataset, anomaly) | src/mlops/ (4 modules), deploy.yml, 4 test files | 75 new tests, 532 total. Full MLOps pipeline operational. |
| 9 | 2026-02-14 | M7: UI/UX (routing trace, theme toggle, document manager) | 3 new components + CSS | Frontend build clean. All milestones complete. |
| 10 | 2026-02-15 | M2.2: Plugin System (Registry, Calculator, WebSearch) | src/plugins/, supervisor.py, graph_builder.py | Implemented dynamic plugin loading and integrated into Supervisor. Verified with integration tests. |
| 11 | 2026-02-15 | M2.3: Advanced Plugins (Code Sandbox) | src/plugins/sandbox.py, tests/unit/test_sandbox.py | Implemented secure Python code execution via Docker. Integrated into Supervisor. Verified with mocked Docker integration test. |
| 12 | 2026-02-15 | M2.4: Data & Communication Plugins (DB, Email, Slack) | src/plugins/database.py, src/plugins/communication.py | Implemented SQLite connector and Mock Email/Slack plugins. Verified integration. |

---

## 6. SESSION INSTRUCTIONS (for the AI)

When you receive this prompt:

1. **Read §5 PROGRESS TRACKER** to find where we left off
2. **Pick up the next uncompleted task** from §4 IMPLEMENTATION ORDER
3. **Read the relevant phase spec** from `docs/architecture/phase-*.md` for detailed requirements
4. **Implement with tests** — every module must have corresponding unit tests
5. **Follow conventions**:
   - Python: type hints, docstrings, async where applicable, Black formatting
   - All code must be production-quality, not scaffolding stubs
   - Handle errors with custom exceptions from `core/exceptions.py`
   - Use dependency injection via interfaces from `core/interfaces.py`
6. **At session end**: Tell the user to update §5 PROGRESS TRACKER with what was done

**Coding Rules:**
- Write **real, complete, working code** — not pseudocode or placeholders
- **Every file** gets unit tests in `tests/unit/test_<module>.py`
- Use `pyproject.toml` (not requirements.txt)
- Async FastAPI endpoints throughout
- All DB operations via repository pattern (interface → implementation)
- Environment variables via pydantic-settings `BaseSettings`
- Docker-first: every service must work in docker-compose

**When stuck**: Read the relevant `docs/architecture/phase-*.md` spec file for detailed design decisions, class diagrams, and pseudocode to follow.

---

## 7. QUICK REFERENCE — KEY INTERFACES

```python
# core/interfaces.py — All modules implement these contracts

class LLMProvider(ABC):
    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse: ...

class VectorStore(ABC):
    async def search(self, query_embedding: list[float], top_k: int, filters: dict) -> list[SearchResult]: ...
    async def upsert(self, documents: list[Document]) -> None: ...

class GraphStore(ABC):
    async def query(self, cypher: str, params: dict) -> list[dict]: ...
    async def add_entities(self, entities: list[Entity], relationships: list[Relationship]) -> None: ...

class Agent(ABC):
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult: ...

class Plugin(ABC):
    def manifest(self) -> PluginManifest: ...
    async def execute(self, action: str, params: dict) -> PluginResult: ...

class Cache(ABC):
    async def get(self, key: str) -> Optional[Any]: ...
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None: ...
    async def invalidate(self, pattern: str) -> None: ...
```

---

*Copy this entire file to start or resume building. Update §5 after each session. All architectural decisions are already made — just build.*
