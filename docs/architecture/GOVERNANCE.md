# Knowledge Foundry — Safety, Evaluation & Governance Design

## Overview

This document describes the safety, evaluation, and governance layer for Knowledge Foundry. The goal is to make it easy for teams to attach safety policies and evaluation suites to knowledge bases and clients, covering hallucination control, toxicity, bias, and data exfiltration detection.

---

## Conceptual Design

### Core Principles

1. **Declarative policies**: Safety rules are defined as data, not code
2. **Composable attachment**: Policies and eval suites attach to KBs, ClientApps, or both
3. **Dual evaluation**: Pre-deployment (offline) and continuous (online) evaluation
4. **Graduated enforcement**: Block → Flag → Transform → Log-only actions
5. **Full auditability**: Every violation and eval result is logged for governance

---

## Data Model

### Entity Relationships

```
┌─────────────────────┐          ┌──────────────────┐
│   KnowledgeBase     │◄────────►│   SafetyPolicy   │
│                     │  attach   │                  │
└─────────────────────┘          │  - rules[]       │
         ▲                        │  - blocked_cats  │
         │                        │  - default_action│
    used by                       │  - require_      │
         │                        │    grounding     │
┌─────────────────────┐          └──────────────────┘
│    ClientApp        │◄────────►│   SafetyPolicy   │
│                     │  attach   └──────────────────┘
└─────────────────────┘
         │                        ┌──────────────────┐
         └───────────────────────►│   EvalSuite      │
                     attach       │                  │
                                  │  - probes[]      │
                                  │  - metrics       │
                                  │  - schedule      │
                                  │  - sample_rate   │
                                  └──────────────────┘
                                          │
                                     executes
                                          │
                                          ▼
                                  ┌──────────────────┐
                                  │    EvalRun       │
                                  │                  │
                                  │  - probe_results │
                                  │  - aggregate_    │
                                  │    scores        │
                                  │  - passed/failed │
                                  └──────────────────┘
```

### SafetyPolicy

| Field | Type | Description |
|-------|------|-------------|
| `policy_id` | UUID | Unique identifier |
| `name` | string | Human-readable name |
| `knowledge_base_id` | UUID? | Attached KB (null = global) |
| `client_id` | UUID? | Attached client (null = global) |
| `rules` | SafetyRule[] | Individual safety rules |
| `blocked_categories` | BlockedCategory[] | Categories to block |
| `default_action` | enum | `block` / `flag` / `transform` / `log_only` |
| `require_grounding` | bool | Require responses to be grounded in context |
| `add_disclaimers` | bool | Add safety disclaimers to responses |
| `enabled` | bool | Whether policy is active |

### SafetyRule

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | UUID | Unique identifier |
| `name` | string | Rule name |
| `category` | BlockedCategory | `hallucination` / `toxicity` / `bias` / `pii_leak` / `data_exfiltration` / `prompt_injection` / `off_topic` / `harmful_content` |
| `action` | SafetyAction | Action when triggered |
| `threshold` | float | Confidence threshold (0-1) |
| `enabled` | bool | Whether rule is active |

### EvalSuite

| Field | Type | Description |
|-------|------|-------------|
| `suite_id` | UUID | Unique identifier |
| `name` | string | Suite name |
| `knowledge_base_id` | UUID? | Attached KB |
| `client_id` | UUID? | Attached client |
| `probes` | EvalProbe[] | Test cases |
| `metrics` | EvalMetricType[] | Metrics to compute |
| `schedule` | enum | `on_demand` / `pre_deployment` / `continuous` / `scheduled` |
| `sample_rate` | float | Traffic sampling rate for continuous eval |

### EvalProbe

| Field | Type | Description |
|-------|------|-------------|
| `probe_id` | UUID | Unique identifier |
| `name` | string | Probe name |
| `input_query` | string | Test query |
| `expected_output` | string? | Expected answer (for faithfulness scoring) |
| `metric_type` | enum | Primary metric to evaluate |
| `threshold` | float | Minimum acceptable score |

### EvalRun

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | UUID | Unique identifier |
| `suite_id` | UUID | Parent evaluation suite |
| `status` | enum | `pending` / `running` / `completed` / `failed` |
| `probe_results` | EvalProbeResult[] | Per-probe results |
| `aggregate_scores` | dict | Average scores per metric |
| `passed` | bool | Overall pass/fail |
| `total_probes` | int | Total probes executed |
| `passed_probes` | int | Number that passed |
| `failed_probes` | int | Number that failed |

---

## Request-Time Behavior

When a retrieval request arrives, the safety engine evaluates it against all applicable policies:

### Request Flow

```
                                    ┌─────────────────┐
  Incoming Query ──────────────────►│  Safety Engine   │
                                    │                  │
                                    │  For each policy:│
                                    │   For each rule: │
                                    │    evaluate()    │
                                    │                  │
                                    │  Actions:        │
                                    │   BLOCK → 403    │
                                    │   FLAG → log +   │
                                    │          proceed │
                                    │   TRANSFORM →    │
                                    │     modify query │
                                    │   LOG_ONLY →     │
                                    │     proceed      │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
  Retrieval ◄──────────────────────│  Retrieve &      │
  Results                           │  Generate        │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
  Final Response ◄─────────────────│  Response Check  │
   (with disclaimers               │                  │
    if required)                    │  Check output    │
                                    │  for violations  │
                                    │                  │
                                    │  Add disclaimers │
                                    │  if policy says  │
                                    └─────────────────┘
```

### Action Effects

| Action | Request | Response |
|--------|---------|----------|
| **BLOCK** | Return 403 with reason | Suppress response, return safe fallback |
| **FLAG** | Log violation, proceed | Log violation, include warning in metadata |
| **TRANSFORM** | Rewrite query to remove unsafe content | Redact unsafe content from response |
| **LOG_ONLY** | Log for analytics, proceed normally | Log for analytics, deliver unchanged |

---

## Evaluation Flows

### Pre-Deployment (Offline)

```
Developer triggers eval ──► EvalEngine.run_suite()
                                 │
                                 ├── For each probe:
                                 │    1. Run query through retrieval
                                 │    2. Score output against expected
                                 │    3. Compute metrics (faithfulness,
                                 │       relevancy, groundedness)
                                 │
                                 └── Produce EvalRun
                                      - Per-probe results
                                      - Aggregate scores
                                      - Pass/fail verdict
```

**Use case**: Run before deploying new KB content or model changes. Gate deployment on eval passing.

### Continuous (Online)

```
Production Traffic ──► Sample at configured rate (e.g., 10%)
                            │
                            ├── Run sampled queries through eval
                            │   (asynchronously, non-blocking)
                            │
                            └── Log results to telemetry store
                                 │
                                 └── Feed into dashboards
                                     and governance reports
```

**Use case**: Monitor production quality over time. Detect drift, new failure modes.

---

## Telemetry Schema

### Safety Violation Record

```json
{
  "violation_id": "uuid",
  "policy_id": "uuid",
  "rule_id": "uuid",
  "category": "hallucination",
  "severity": "high",
  "action_taken": "block",
  "query": "...",
  "response_snippet": "...",
  "confidence": 0.92,
  "blocked": true,
  "knowledge_base_id": "uuid",
  "client_id": "uuid",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Evaluation Score Record

```json
{
  "run_id": "uuid",
  "suite_id": "uuid",
  "metric_type": "faithfulness",
  "score": 0.95,
  "passed": true,
  "probe_name": "test-hallucination-1",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Dashboard Metrics

| Metric | Description | Aggregation |
|--------|-------------|-------------|
| `violations_by_category` | Count of violations per category | Counter, by category |
| `violations_by_severity` | Count by severity level | Counter, by severity |
| `block_rate` | Percentage of blocked requests | Gauge |
| `eval_pass_rate` | Percentage of passing eval probes | Gauge, by suite |
| `avg_faithfulness_score` | Average faithfulness across probes | Gauge |
| `avg_relevancy_score` | Average relevancy across probes | Gauge |
| `near_miss_rate` | Violations with confidence near threshold | Gauge |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/governance/safety-policies` | POST | Create a safety policy |
| `/api/v1/governance/safety-policies` | GET | List all policies |
| `/api/v1/governance/safety-policies/{id}` | GET | Get policy details |
| `/api/v1/governance/safety-check` | POST | Check content against policies |
| `/api/v1/governance/violations` | GET | List recorded violations |
| `/api/v1/governance/eval-suites` | POST | Create an evaluation suite |
| `/api/v1/governance/eval-suites` | GET | List all eval suites |
| `/api/v1/governance/eval-suites/{id}` | GET | Get eval suite details |
| `/api/v1/governance/eval-runs` | GET | List eval runs |
| `/api/v1/governance/eval-runs/{id}` | GET | Get eval run details |

---

## Implementation Status

- [x] Safety policy model (`src/governance/models.py`)
- [x] Evaluation suite and run models (`src/governance/models.py`)
- [x] Safety enforcement engine (`src/governance/safety.py`)
- [x] Evaluation engine (`src/governance/evaluation.py`)
- [x] Governance API endpoints (`src/api/routes/governance.py`)
- [x] Violation telemetry logging
- [x] Unit tests
