# ADR-007: Custom LLM Router over LiteLLM

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, Tech Lead  

---

## Context

Knowledge Foundry requires an LLM routing layer to implement tiered intelligence (Opus/Sonnet/Haiku), circuit breaking, rate limiting, cost tracking, and multi-provider fallback. LiteLLM is the most popular open-source option.

## Decision

**Build a custom FastAPI-based LLM Router** instead of using LiteLLM.

### Custom Router Components:
1. **Complexity Classifier** — Haiku-based task classification (<50ms)
2. **Tier Router** — Maps complexity score to model tier
3. **Circuit Breaker** — Per-provider failure isolation (5 failures → open for 60s)
4. **Rate Limiter** — Redis-based token bucket (per-user, per-tenant, per-endpoint)
5. **Cost Tracker** — Per-query cost logging to Langfuse
6. **Load Balancer** — Weighted round-robin across API keys
7. **Fallback Chain** — Automatic provider fallback on failure

## Rationale

| Factor | LiteLLM | Custom Router |
|--------|:-------:|:-------------:|
| Throughput (RPS) | **Fails at 300 RPS** | Target: 500+ RPS |
| Tiered intelligence | Basic routing | Full complexity-based routing |
| Circuit breaking | Basic | Configurable per-provider |
| Cost tracking | Generic | Integrated with Langfuse |
| EU AI Act logging | Manual | Built-in immutable logging |
| Customizability | Limited | Full control |
| Dependency risk | External project | Internal ownership |

- LiteLLM has been validated to **fail under load at 300 RPS** — below our 500 RPS target
- Custom router provides full control over routing logic, essential for tiered intelligence
- Deep integration with Langfuse for observability and EU AI Act compliance logging
- No external dependency risk for a critical infrastructure component

## Consequences

**Benefits:** Full control, higher throughput, deep observability, compliance integration  
**Costs:** ~2 weeks development, ongoing maintenance ownership  
**Risks:** Development effort and maintenance burden → mitigated by clear interface design and comprehensive tests

## Alternatives Considered

- **LiteLLM** — Rejected: performance ceiling at 300 RPS, limited customization
- **OpenRouter** — Rejected: SaaS dependency for critical path, data sovereignty concerns
- **Custom Nginx-based proxy** — Rejected: lacks LLM-specific features (complexity routing, token counting)
