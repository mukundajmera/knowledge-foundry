# Knowledge Foundry — Domain Model & Architecture

## Overview

Knowledge Foundry is a self-hosted, developer-focused unified knowledge and RAG layer for agents and applications. It provides reusable topic-centric knowledge bases, automatic ingestion/indexing/vectorization, hybrid search, and an agentic retrieval engine exposed via a single endpoint.

This document defines the core domain model, high-level architecture, ingestion lifecycle, and explicit v1 non-goals.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                   │
│   Agents / Apps / ClientApps ──► API Gateway (FastAPI)               │
│       ▲  (REST + streaming)                                           │
└───────┼──────────────────────────────────────────────────────────────┘
        │
┌───────┼──────────────────────────────────────────────────────────────┐
│       ▼         RETRIEVAL / RUNTIME LAYER                             │
│  ┌──────────┐  ┌──────────────────┐  ┌─────────────────┐            │
│  │  Basic    │  │ Agentic Retrieval│  │  Safety/Gov     │            │
│  │  Retrieve │  │ (multi-hop,      │  │  Engine         │            │
│  │  (top-K)  │  │  multi-KB)       │  │  (policies,     │            │
│  └──────────┘  └──────────────────┘  │   eval suites)  │            │
│                                       └─────────────────┘            │
└──────────────────────────────────────────────────────────────────────┘
        │
┌───────┼──────────────────────────────────────────────────────────────┐
│       ▼         INGESTION / INDEXING LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Connectors│─►│ Ingestion│─►│ Chunking │─►│ Embedding│            │
│  │ (file,   │  │ Workers  │  │ Engine   │  │ Service  │            │
│  │  git,    │  │ (jobs)   │  │          │  │          │            │
│  │  DB, API)│  └──────────┘  └──────────┘  └──────────┘            │
│  └──────────┘                                    │                    │
└──────────────────────────────────────────────────┼───────────────────┘
        │                                          │
┌───────┼──────────────────────────────────────────┼───────────────────┐
│       ▼         STORAGE LAYER                    ▼                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │PostgreSQL│  │  Qdrant  │  │  Neo4j   │  │  Redis   │            │
│  │(metadata,│  │ (vectors,│  │(knowledge│  │ (cache,  │            │
│  │ configs, │  │  chunks) │  │  graph)  │  │  embeds) │            │
│  │ policies)│  └──────────┘  └──────────┘  └──────────┘            │
│  └──────────┘                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### Services & Modules

| Module | Responsibility | Storage |
|--------|---------------|---------|
| **Connectors** | Pull data from external systems (file shares, Git, DBs, SaaS) | Config in PostgreSQL |
| **Ingestion Workers** | Orchestrate ingestion jobs: discover → fetch → chunk → embed → index | Job state in PostgreSQL |
| **Chunking Engine** | Segment documents into semantically meaningful chunks | — |
| **Embedding Service** | Generate vector embeddings for chunks and queries | Redis (cache) |
| **Indexing** | Maintain keyword + vector + hybrid search indices | Qdrant, PostgreSQL |
| **Metadata Store** | KB configs, source definitions, policies, client registrations | PostgreSQL |
| **Retrieval APIs** | Basic top-K and agentic multi-hop retrieval | — |
| **Safety/Governance** | Enforce safety policies, run evaluations, log violations | PostgreSQL |
| **Observability** | Structured logs, Prometheus metrics, distributed tracing | Prometheus, Grafana |

---

## Core Domain Entities

```
┌─────────────────────┐
│    KnowledgeBase     │──────── 1:N ──────── Source
│   (topic-centric    │                         │
│    aggregate)       │                    references
│                     │                         │
│  - kb_id            │                    Connector
│  - tenant_id        │                  (reusable config)
│  - name             │
│  - embedding_model  │──────── 1:N ──────── Index
│  - chunking_strategy│                  (vector/keyword/hybrid)
│  - tags             │
│                     │──────── 1:N ──────── Policy
└─────────────────────┘                  (access/safety/retention)
         │
    used by (N:M)
         │
    ClientApp
  (agent or app
   consuming KBs)

Source ────── 1:N ────── IngestionJob
                          (queued → running → completed)
```

### Entity Definitions

| Entity | Description | Key Fields |
|--------|-------------|------------|
| **KnowledgeBase** | Top-level aggregate grouping sources, indices, and policies | `kb_id`, `tenant_id`, `name`, `embedding_model`, `chunking_strategy`, `tags` |
| **Source** | A data source within a KB, bound to a Connector | `source_id`, `kb_id`, `connector_id`, `location`, `file_patterns`, `status` |
| **Connector** | Reusable config for pulling data from an external system | `connector_id`, `type` (file_share, git_repo, etc.), `config`, `credentials_ref` |
| **IngestionJob** | Tracks a single ingestion run for a Source | `job_id`, `source_id`, `status`, `documents_processed`, `chunks_created` |
| **Chunk** | A semantically meaningful segment of a document | `chunk_id`, `document_id`, `text`, `embedding`, `chunk_index` |
| **Index** | A search index (vector, keyword, or hybrid) for a KB | `index_id`, `kb_id`, `index_type`, `embedding_model`, `dimensions` |
| **Policy** | Rules governing a KB (access control, retention, safety) | `policy_id`, `kb_id`, `policy_type`, `rules`, `enabled` |
| **ClientApp** | An application/agent registered to consume KBs | `client_id`, `name`, `api_key_hash`, `allowed_kb_ids`, `rate_limits` |
| **Embedding** | Vector representation of a chunk (stored in Qdrant) | Managed by the vector store; linked via `chunk_id` |

---

## Ingestion Lifecycle: Git Repository Source

The following describes the end-to-end ingestion lifecycle when a user adds a Git repository as a source:

### 1. Source Registration
```
POST /api/v1/kb/{kb_id}/sources
{
  "name": "docs-repo",
  "connector_id": "<git-connector-id>",
  "location": "https://github.com/org/docs.git",
  "file_patterns": ["*.md", "*.rst", "*.txt"]
}
```
- Source is created with status `PENDING`
- Validated against the referenced Connector

### 2. Ingestion Trigger
```
POST /api/v1/kb/{kb_id}/sources/{source_id}/ingest
```
- Creates an `IngestionJob` with status `QUEUED`
- Job is picked up by an ingestion worker

### 3. Discovery & Fetch
- Worker clones/pulls the Git repository (shallow clone)
- Walks the file tree matching `file_patterns`
- Emits `document_discovered` events for each matched file
- Downloads file content into memory

### 4. Chunking
- Each document is passed through the Chunking Engine
- Uses the KB's configured `chunking_strategy` (default: semantic)
- Produces `Chunk` objects with `chunk_index`, `text_hash`, metadata
- Emits `chunk_created` events

### 5. Embedding Generation
- Chunks are batched and sent to the Embedding Service
- Embeddings are generated using the KB's configured `embedding_model`
- Results are cached in Redis for deduplication
- Emits `embedding_generated` events

### 6. Indexing
- Chunks + embeddings are upserted into the KB's Index (Qdrant)
- Keyword indices are updated (if hybrid mode)
- Knowledge graph entities are extracted and stored (Neo4j)

### 7. Completion
- `IngestionJob` status transitions to `COMPLETED`
- Source status updated to `ACTIVE`
- Statistics recorded: `documents_processed`, `chunks_created`, `embeddings_generated`

### Error Handling
- Individual document failures don't abort the job
- Job transitions to `PARTIAL` if some documents failed
- Error details captured in `IngestionJob.error_details`
- Full failure → `FAILED` status with `error_message`

---

## V1 Non-Goals

The following are explicitly out of scope for the initial version to keep the design focused:

| Non-Goal | Rationale |
|----------|-----------|
| **Full workflow engine** | Ingestion jobs use a simple state machine, not a general-purpose orchestrator (e.g., Temporal, Airflow) |
| **Web UI** | V1 is API-first; no admin dashboard or visual KB management |
| **Unlimited connector set** | V1 supports: file share, Git repo, S3, and database. Additional connectors added incrementally |
| **Real-time streaming ingestion** | Batch/pull-based ingestion only; no Kafka/event-stream connectors in v1 |
| **Multi-region deployment** | Single-region deployment; multi-region replication deferred |
| **Fine-grained RBAC** | V1 has tenant isolation and API key auth; role-based access control deferred |
| **Custom embedding model training** | V1 uses pre-trained embedding models; fine-tuning/custom training deferred |
| **Document versioning** | Re-ingestion replaces previous version; diff-based updates deferred |
| **Cross-tenant knowledge sharing** | Each tenant's KBs are fully isolated |
| **Plugin marketplace** | Plugins are code-level; no discovery/marketplace UI |

---

## Implementation Status

- [x] Domain entities defined (`src/core/domain.py`)
- [x] KB management API (`src/api/routes/knowledge_bases.py`)
- [x] In-memory stores for v1 (DB-backed storage deferred)
- [x] Unit tests for domain model and API
