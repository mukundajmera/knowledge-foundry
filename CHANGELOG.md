# Changelog

All notable changes to Knowledge Foundry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Oracle Code Assist LLM provider support
- LM Studio local LLM provider support
- Ollama local LLM provider support
- Multi-provider registry in LLM router
- DevOps management script (`kf.sh`) with 11 commands
- Comprehensive documentation suite (13 new docs)

### Changed
- README overhauled with architecture diagram and complete feature list
- LLM router now supports provider selection via `provider` parameter

### Fixed
- Code sandbox tests when Docker SDK not installed locally

## [1.0.0] - 2026-02-14

### Added
- **Core Platform**
  - FastAPI backend with async support
  - Multi-agent orchestration (Supervisor, Researcher, Writer, Reviewer, Coder)
  - Tiered LLM routing (Opus/Sonnet/Haiku) based on complexity
  - Advanced RAG with vector + graph search
  - Plugin system (WebSearch, CodeSandbox, Database, Communication)

- **LLM Integration**
  - Anthropic Claude support (Opus, Sonnet, Haiku)
  - OpenAI embeddings (text-embedding-3-large)
  - Circuit breaker pattern for resilience
  - Cost tracking per request
  - Tier escalation on low confidence

- **Data Layer**
  - Qdrant vector database integration
  - Neo4j knowledge graph with KET-RAG
  - PostgreSQL for structured data
  - Redis caching layer
  - Semantic chunking with overlap

- **Security & Compliance**
  - Input sanitization (SQL injection, XSS, prompt injection)
  - Output filtering (PII redaction, sensitive data detection)
  - Immutable audit trails
  - EU AI Act compliance framework
  - JWT authentication
  - Rate limiting

- **Observability**
  - Langfuse end-to-end tracing
  - Arize Phoenix semantic drift detection
  - Prometheus metrics
  - Grafana dashboards
  - Health checks for all services

- **Quality Assurance**
  - RAGAS evaluation framework
  - 576 unit + integration tests
  - 95%+ test coverage
  - Load testing with k6
  - Automated quality gates

- **Infrastructure**
  - Docker Compose for local development
  - Kubernetes Helm charts for production
  - GitHub Actions CI/CD
  - Automated migrations (Alembic)

- **Frontend**
  - Next.js 15 responsive UI
  - Real-time query interface
  - Markdown rendering
  - Dark mode support
  - Playwright E2E tests

- **Documentation**
  - 20 detailed architecture specs
  - 7 Architecture Decision Records (ADRs)
  - API documentation
  - Deployment guide
  - User guide

### Performance
- P95 latency: < 500ms (Haiku), < 2s (Sonnet), < 5s (Opus)
- Throughput: 120+ req/s
- RAGAS score: 0.85 (target: > 0.8)
- Faithfulness: 0.95 (target: > 0.95)

---

## Version History

- **1.0.0** (2026-02-14): Initial production release
- **Unreleased**: Ongoing development

[unreleased]: https://github.com/your-org/knowledge-foundry/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/knowledge-foundry/releases/tag/v1.0.0
