# ADR-006: RAGAS as Quality Gate

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, QA Lead  

---

## Context

LLM outputs are non-deterministic and require automated evaluation to prevent quality regressions. Traditional unit tests are insufficient for RAG systems — we need metrics that evaluate retrieval quality, answer faithfulness, and end-to-end relevancy.

## Decision

**Adopt RAGAS (Retrieval Augmented Generation Assessment) as the primary quality gate**, supplemented by DeepEval for unit testing and Arize Phoenix for production monitoring.

### Quality Gate Thresholds

| Metric | Target | Blocking Level | Measurement |
|--------|:------:|:--------------:|-------------|
| Context Precision | >0.9 | Pre-deploy | Proportion of relevant chunks in top-k |
| Context Recall | >0.85 | Weekly golden dataset | Proportion of relevant info retrieved |
| Faithfulness | >0.95 | Pre-deploy | Claims supported by retrieval context |
| Answer Relevancy | >0.9 | Pre-deploy | Response addresses the question |

### Evaluation Pipeline

1. **Pre-commit:** RAGAS regression test against golden dataset (200 queries)
2. **Pre-deploy:** Full RAGAS evaluation; deployment blocked if any metric below threshold
3. **Production (10% sampled):** Real-time RAGAS scoring with alerting on degradation
4. **Weekly:** Full golden dataset evaluation with trend analysis

### Golden Dataset

- 200 queries across 5 complexity tiers
- Annotated ground truth (correct answer + source documents)
- Version-controlled in `tests/evaluation/golden_dataset/`
- Refreshed quarterly by domain experts

## Rationale

- RAGAS provides the most comprehensive RAG-specific evaluation framework
- Component-level metrics (precision, recall, faithfulness) enable targeted debugging
- Automated evaluation enables continuous deployment without manual review of every change
- Industry benchmark for High Performer organizations

## Consequences

**Benefits:** Automated quality assurance, regression detection, production monitoring  
**Costs:** Golden dataset creation (~40 hours initial), evaluation pipeline adds ~5 minutes to CI/CD  
**Risks:** RAGAS metrics may not capture domain-specific quality requirements → mitigated by custom evaluation extensions
