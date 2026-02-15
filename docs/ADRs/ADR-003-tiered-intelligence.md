# ADR-003: Tiered Intelligence (Opus/Sonnet/Haiku)

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, Engineering Manager  

---

## Context

Running all queries through a single high-capability model (Opus at $15/1M tokens) is cost-prohibitive at scale. With 1000 users generating ~100K queries/month, an all-Opus architecture would cost ~$24K/month in LLM costs alone, exceeding the $30K total budget.

## Decision

**Implement three-tier model routing (Opus/Sonnet/Haiku) with a custom complexity-based router**, targeting <$0.10 per query and 60% cost savings vs. all-Opus.

| Tier | Model | Cost/1M Tokens | Query Share | Use Cases |
|------|-------|---------------|:-----------:|-----------|
| Strategist | Claude Opus | $15.00 | 10% | Architecture, complex reasoning, security analysis |
| Workhorse | Claude Sonnet | $3.00 | 70% | Standard RAG, coding, documentation |
| Sprinter | Claude Haiku | $0.25 | 20% | Classification, extraction, formatting |

## Rationale

- **Blended cost:** ~$0.09/query (vs. $0.24/query all-Opus) → **60% savings**
- **Quality preservation:** Each tier has minimum quality thresholds with confidence-based escalation
- **Latency improvement:** Haiku at <100ms for classification, improving routing speed
- Most enterprise queries (70%) are standard knowledge retrieval that Sonnet handles well

**Escalation Safety Net:**
- Haiku → Sonnet if confidence <0.7
- Sonnet → Opus if confidence <0.6
- Opus → Human if confidence <0.5

## Consequences

**Benefits:** 60% cost reduction, improved latency for simple queries, quality maintained via escalation  
**Costs:** Routing overhead (~50ms), classifier maintenance (monthly retraining)  
**Risks:** Misclassification causing quality drops → mitigated by confidence-based auto-escalation

## Alternatives Considered

- **All-Opus** — Rejected: $24K/month LLM costs alone, exceeds budget
- **Two-tier (Opus + Haiku)** — Rejected: gap too large, Sonnet fills critical middle ground
- **LiteLLM auto-routing** — Rejected: see ADR-007
