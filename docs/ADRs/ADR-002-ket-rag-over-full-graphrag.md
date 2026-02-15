# ADR-002: KET-RAG over Full GraphRAG

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, Tech Lead  

---

## Context

Knowledge Foundry requires multi-hop reasoning for complex enterprise queries (e.g., regulatory impact analysis across supply chains). Four retrieval architectures were evaluated based on 2026 enterprise AI research.

## Decision

**Adopt KET-RAG (Knowledge-Enhanced Triple RAG) with skeleton graph as the primary retrieval architecture.** Use VectorCypher (full graph) as a fallback for critical domains requiring >90% multi-hop accuracy.

- **20% central documents** → full graph entities + relationships (Neo4j)
- **80% peripheral content** → vector-only with metadata (Qdrant)
- Central documents identified via PageRank + manual curation for regulatory docs

## Rationale

| Factor | Plain Vector | Full GraphRAG | VectorCypher | **KET-RAG** |
|--------|:---:|:---:|:---:|:---:|
| Indexing cost (5GB) | $500 | **$33,000** | $5,000 | **$3,300** |
| Multi-hop accuracy | 40-60% | 85-95% | 80-90% | **75-85%** |
| Operational complexity | Low | Very High | High | **Medium-High** |
| Query latency (p95) | <100ms | <800ms | <400ms | **<300ms** |

- KET-RAG achieves **10x cost reduction** vs. full GraphRAG while retaining meaningful multi-hop capabilities.
- For the MVP, 75-85% multi-hop accuracy is acceptable; critical domains that need >90% can be selectively upgraded to VectorCypher.
- Full GraphRAG's $33K indexing cost is prohibitive for initial deployment.

## Consequences

**Benefits:**
- $29,700 savings on initial indexing vs. full GraphRAG
- Lower maintenance burden (smaller graph, fewer entities)
- Good enough accuracy for 80% of enterprise queries

**Costs:**
- Reduced accuracy on complex multi-hop queries (75-85% vs. 85-95%)
- Need to maintain skeleton selection logic (PageRank pipeline)

**Risks:**
- **RISK-001:** KET-RAG accuracy may be insufficient for regulated domains → Mitigation: increase skeleton coverage from 20% → 40% (+$10K), or selectively upgrade to VectorCypher

## Alternatives Considered

- **Full GraphRAG** — Rejected: $33K indexing cost, excessive for MVP
- **Plain Vector RAG only** — Rejected: 40-60% multi-hop accuracy unacceptable for enterprise use
- **Long Context (full document)** — Rejected: 20-24x more expensive than RAG at scale
