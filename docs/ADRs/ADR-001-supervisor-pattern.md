# ADR-001: Supervisor Pattern for Multi-Agent Orchestration

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, CTO  

---

## Context

Knowledge Foundry requires multi-agent orchestration to handle diverse enterprise queries spanning knowledge retrieval, code generation, analysis, and compliance validation. We need a pattern that is debuggable, scalable, and production-proven.

Four candidate patterns were evaluated:
1. **Supervisor (Router)** – Central agent delegates to specialists
2. **Sequential** – Linear workflow chain
3. **Hierarchical** – Manager → Leads → Workers 
4. **Utility-Aware Negotiation** – Decentralized bidding

## Decision

**Adopt the Supervisor (Router) Pattern as the primary orchestration model**, implemented via LangGraph with state checkpoints.

- A Supervisor Agent classifies intent (Haiku, <100ms), routes to specialist agents in parallel, and synthesizes outputs.
- Safety Agent validates all outputs before delivery.
- Hierarchical Pattern available as secondary for large-context analysis (>50 docs).

## Rationale

| Criterion | Supervisor | Sequential | Hierarchical | Utility-Aware |
|-----------|:---:|:---:|:---:|:---:|
| Debuggability | ✅ High | ✅ High | ⚠️ Medium | ❌ Low |
| Parallel execution | ✅ | ❌ | ✅ | ✅ |
| Production maturity | ✅ | ✅ | ⚠️ | ❌ |
| Failure isolation | ✅ | ❌ (cascading) | ✅ | ⚠️ |
| Complexity | Low | Low | Medium | High |

- **Supervisor** provides centralized control for tracing, logging, and cost attribution — critical for EU AI Act compliance.
- **Sequential** too rigid for multi-domain queries.
- **Utility-Aware** too complex for MVP; planned for Phase 3.

## Consequences

**Benefits:**
- Clear audit trail (Supervisor logs every routing decision)
- Easy performance optimization (optimize per-agent independently)
- Natural fit for tiered intelligence routing

**Costs:**
- Supervisor is a single point of failure (mitigated by circuit breakers and LangGraph checkpointing)
- Additional latency from routing step (~50-100ms, acceptable)

**Risks:**
- Supervisor misrouting (mitigated by Haiku classifier accuracy tracking + escalation fallbacks)

## Alternatives Considered

- **LiteLLM's built-in routing** — Rejected: fails at 300 RPS (see ADR-007)
- **AutoGen framework** — Rejected: less mature checkpointing, heavier dependency
