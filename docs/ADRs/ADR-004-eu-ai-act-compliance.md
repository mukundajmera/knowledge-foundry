# ADR-004: EU AI Act Compliance Architecture

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, CTO, Legal Counsel  

---

## Context

The EU AI Act Phase 3 enforcement begins August 2026. Knowledge Foundry is classified as a **High-Risk AI System** when deployed for employment decisions, access to essential services, or regulatory compliance. Non-compliance carries penalties of up to **€15M or 3% of global turnover**.

## Decision

**Build compliance-as-code into the platform from Day 1**, with four mandatory controls:

### 1. Technical Documentation (Article 11)
- Auto-generated from MLflow experiment metadata on every model deployment
- Includes: model purpose, training data description, decision logic, bias test results, performance metrics
- Stored in Git (versioned) + S3 WORM (immutable archive)

### 2. Automatic Logging (Article 12)
- Every query logged: inputs, outputs, model version, agent chain, config snapshot, RAGAS scores, cost, latency
- Format: JSON Lines → S3 Object Lock (Compliance mode, WORM)
- Retention: 7 years
- Access: read-only IAM role for auditors

### 3. Human-in-the-Loop (Article 14)
- HITL gates for: confidence <0.5, PII detection, new model deployments, compliance violations
- Designated roles: AI Governance Officer, Domain Experts
- Override mechanisms with audit trail

### 4. Post-Market Monitoring
- Monthly: RAGAS trends, cost analysis, user complaints
- Quarterly: comprehensive bias audit, model performance review
- Annual: regulator report + immediate notification for serious incidents

## Rationale

- **Penalty avoidance:** €15M fine vs. ~$50K/year compliance cost → clear ROI
- **Competitive advantage:** Compliance readiness as enterprise selling point
- **Early adoption:** Building compliance in from Day 1 is 5x cheaper than retrofitting

## Consequences

**Benefits:** Regulatory compliance, enterprise trust, audit-ready from launch  
**Costs:** ~$50K/year (tooling: MLflow, S3 WORM, monitoring; personnel: part-time governance)  
**Risks:** Regulatory interpretation changes → mitigated by quarterly legal review

## Alternatives Considered

- **Post-hoc compliance bolting** — Rejected: 5x more expensive, risky timeline
- **Third-party compliance SaaS** — Rejected: vendor lock-in, less control over audit trails
