# Knowledge Foundry — Retrieval & Agentic RAG Engine Spec

## Overview

The retrieval engine supports both simple retrieval (single KB, top-K) and agentic retrieval (multi-hop, multi-KB, query rewriting, tool-like behavior). Retrieval is a reusable service callable by any agent or application through a single endpoint.

---

## External API Surface

### Basic Retrieval

```
POST /api/v1/retrieve/basic
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `kb_id` | UUID | required | Knowledge base to search |
| `query` | string | required | Search query |
| `tenant_id` | string | required | Tenant for data isolation |
| `top_k` | int | 10 | Number of results (1-100) |
| `mode` | enum | `vector` | `keyword` / `vector` / `hybrid` |
| `filters` | object | `{}` | Metadata filters |
| `similarity_threshold` | float | 0.65 | Minimum similarity score (0-1) |

**Response:**
```json
{
  "request_id": "uuid",
  "answer": "",
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "text": "...",
      "score": 0.92,
      "metadata": {}
    }
  ],
  "steps": [{"step_number": 1, "action": "retrieve", ...}],
  "total_tokens_used": 0,
  "total_latency_ms": 42,
  "truncated": false
}
```

### Agentic Retrieval

```
POST /api/v1/retrieve/agentic
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Natural language question |
| `tenant_id` | string | required | Tenant for data isolation |
| `kb_ids` | UUID[] | `[]` | Knowledge bases to search (empty = all) |
| `max_steps` | int | 5 | Max retrieval iterations (1-20) |
| `reasoning_effort` | enum | `medium` | `low` / `medium` / `high` |
| `top_k_per_step` | int | 5 | Results per sub-query (1-50) |
| `token_budget` | int | 8000 | Max tokens for context (100-100000) |
| `max_latency_ms` | int | 30000 | Latency budget in ms (1000-120000) |
| `mode` | enum | `hybrid` | `keyword` / `vector` / `hybrid` |
| `filters` | object | `{}` | Metadata filters |

**Response** includes structured steps showing the full reasoning chain.

---

## Internal Flow: Agentic Retrieval

### Sequence Diagram

```
Client              API Gateway         Agentic Engine        LLM           Vector Store
  │                     │                    │                  │                │
  │  POST /retrieve/    │                    │                  │                │
  │  agentic            │                    │                  │                │
  │────────────────────►│                    │                  │                │
  │                     │  agentic_retrieve()│                  │                │
  │                     │───────────────────►│                  │                │
  │                     │                    │                  │                │
  │                     │                    │ Step 1: DECOMPOSE                 │
  │                     │                    │─────────────────►│                │
  │                     │                    │  "Break into     │                │
  │                     │                    │   sub-queries"   │                │
  │                     │                    │◄─────────────────│                │
  │                     │                    │  [sq1, sq2, sq3] │                │
  │                     │                    │                  │                │
  │                     │                    │ Step 2: RETRIEVE (sq1)            │
  │                     │                    │  embed_query()   │                │
  │                     │                    │─────────────────────────────────►│
  │                     │                    │  search()        │                │
  │                     │                    │◄─────────────────────────────────│
  │                     │                    │  [results]       │                │
  │                     │                    │                  │                │
  │                     │                    │ Step 3: RETRIEVE (sq2)            │
  │                     │                    │─────────────────────────────────►│
  │                     │                    │◄─────────────────────────────────│
  │                     │                    │                  │                │
  │                     │                    │ ... (budget/latency check) ...    │
  │                     │                    │                  │                │
  │                     │                    │ Step N: SYNTHESIZE                │
  │                     │                    │─────────────────►│                │
  │                     │                    │  "Synthesize     │                │
  │                     │                    │   answer from    │                │
  │                     │                    │   all context"   │                │
  │                     │                    │◄─────────────────│                │
  │                     │                    │  final_answer    │                │
  │                     │                    │                  │                │
  │                     │◄───────────────────│                  │                │
  │◄────────────────────│  RetrievalResponse │                  │                │
  │  {answer, results,  │                    │                  │                │
  │   steps, metrics}   │                    │                  │                │
```

### Processing Steps

1. **Query Understanding & Decomposition**
   - Input query analyzed for complexity
   - `LOW` effort: single pass (no decomposition)
   - `MEDIUM`/`HIGH` effort: LLM decomposes into 2-4 focused sub-queries
   - Each sub-query tagged with target KB if multi-KB

2. **Planning & Sub-Query Generation**
   - Sub-queries routed to appropriate KBs
   - Retrieval order determined (independent sub-queries can run in parallel)
   - Token budget allocated across sub-queries

3. **Iterative Retrieval**
   - Each sub-query: embed → vector search → collect results
   - After each step: check token budget and latency constraints
   - If budget exceeded: stop early, mark response as `truncated`
   - Results accumulated across steps

4. **Synthesis**
   - All gathered context assembled (respecting token budget at 70% for context)
   - LLM synthesizes final answer with source citations
   - Answer includes `[Source N]` markers for traceability

---

## Context Limits & Latency Constraints

| Constraint | Default | Range | Enforcement |
|-----------|---------|-------|-------------|
| **Token budget** | 8,000 | 100-100,000 | Checked after each retrieval step; context truncated at 70% of budget |
| **Latency budget** | 30s | 1s-120s | Wall-clock check before each step; early termination if exceeded |
| **Max steps** | 5 | 1-20 | Hard cap on retrieval iterations |
| **Top-K per step** | 5 | 1-50 | Limits results per sub-query |

**Enforcement strategy:**
- Pre-step check: elapsed time < `max_latency_ms` and tokens used < `token_budget`
- Context assembly: only include chunks until 70% of token budget consumed
- LLM synthesis: `max_tokens` capped at 50% of remaining budget
- Response marked `truncated: true` if any limit was hit

---

## Observability

### Structured Logging

Every retrieval request emits structured log entries:

```json
{
  "event": "agentic_retrieval_completed",
  "request_id": "uuid",
  "steps": 4,
  "sub_queries": 3,
  "total_results": 12,
  "total_tokens": 3500,
  "total_latency_ms": 2340,
  "truncated": false,
  "reasoning_effort": "medium"
}
```

### Metrics (Prometheus)

| Metric | Type | Labels |
|--------|------|--------|
| `kf_retrieval_requests_total` | counter | `mode` (basic/agentic), `status` |
| `kf_retrieval_latency_seconds` | histogram | `mode`, `reasoning_effort` |
| `kf_retrieval_tokens_used` | histogram | `mode` |
| `kf_retrieval_steps_total` | histogram | — |
| `kf_retrieval_results_total` | histogram | `mode` |
| `kf_retrieval_truncated_total` | counter | `reason` (budget/latency) |

### Traces

Each agentic retrieval creates a span tree:
```
[agentic_retrieve]
  ├── [decompose_query] — LLM call
  ├── [retrieve_subquery_1] — embed + search
  ├── [retrieve_subquery_2] — embed + search
  ├── [retrieve_subquery_3] — embed + search
  └── [synthesize] — LLM call
```

Each span captures: input/output, latency, token count, result count.

---

## Implementation Status

- [x] `AgenticRetrievalEngine` class (`src/retrieval/agentic.py`)
- [x] Basic retrieval endpoint (`POST /api/v1/retrieve/basic`)
- [x] Agentic retrieval endpoint (`POST /api/v1/retrieve/agentic`)
- [x] Query decomposition via LLM
- [x] Token budget and latency enforcement
- [x] Structured step artifacts for observability
- [x] Unit tests
