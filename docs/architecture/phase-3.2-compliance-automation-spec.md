# Phase 3.2 – Compliance Automation & EU AI Act Readiness
## Knowledge Foundry: Continuous Regulatory Compliance Through Code

**Version**: 1.0 | **Date**: February 14, 2026 | **Status**: 📋 IMPLEMENTATION SPEC  
**Depends on**: Phase 1.5 (Observability), Phase 1.6 (EU AI Act), Phase 3.1 (Security Architecture)

---

## 1. COMPLIANCE-AS-CODE ARCHITECTURE

### 1.1 Automated Compliance Checks

**Pre-Deployment Compliance Gate (CI/CD):**

```yaml
# .compliance/checks.yaml
compliance_checks:
  eu_ai_act:
    - check: technical_documentation_exists
      required: true
      failure_action: block_deployment

    - check: automatic_logging_enabled
      required: true
      validation: |
        - Verify 100% of AI decisions logged
        - Verify logs include: input, output, model, timestamp, trace_id
        - Verify retention policy: 7 years

    - check: ragas_evaluation_passed
      required: true
      thresholds:
        faithfulness: 0.95
        context_precision: 0.90
      failure_action: block_deployment

    - check: human_oversight_workflow_configured
      required: true
      validation: |
        - HITL triggers defined
        - Designated reviewers assigned
        - Override mechanism functional

    - check: risk_assessment_current
      required: true
      validation: |
        - Risk register updated <90 days ago
        - All P0/P1 risks have mitigations

    - check: post_market_monitoring_active
      required: true
      validation: |
        - Metrics collection operational
        - Monthly report generation automated
```

**Continuous Compliance Monitoring:**

```python
class ComplianceMonitor:
    """Runs every hour — alerts on any compliance drift."""
    
    def run_hourly_checks(self):
        checks = [
            self.verify_logging_coverage(),
            self.verify_hitl_sla(),
            self.verify_cost_within_budget(),
            self.check_for_security_incidents(),
        ]
        
        results = execute_checks(checks)
        
        if any(r.failed for r in results):
            alert_compliance_team(results)
            if any(r.severity == "CRITICAL" for r in results):
                trigger_emergency_response()
    
    def verify_logging_coverage(self) -> CheckResult:
        log_coverage = query_metric("log_coverage_percentage")
        if log_coverage < 99.9:
            return CheckResult(
                passed=False, severity="HIGH",
                message=f"Log coverage {log_coverage}% < 99.9% requirement"
            )
        return CheckResult(passed=True)
    
    def verify_hitl_sla(self) -> CheckResult:
        pending = query_hitl_queue()
        overdue = [r for r in pending if r.age_hours > 4]
        if overdue:
            return CheckResult(
                passed=False, severity="MEDIUM",
                message=f"{len(overdue)} HITL reviews overdue (SLA: 4h)"
            )
        return CheckResult(passed=True)
```

---

### 1.2 Automated Technical Documentation Generation

**MLOps Integration (MLflow):**

```python
def deploy_model_with_compliance_docs(model_artifact, metadata):
    with mlflow.start_run():
        # Log model + params + metrics
        mlflow.sklearn.log_model(model_artifact, "model")
        mlflow.log_params({
            "model_type": metadata["type"],
            "training_data_version": metadata["data_version"],
            "hyperparameters": metadata["hyperparameters"],
        })
        mlflow.log_metrics({
            "ragas_faithfulness": metadata["ragas_scores"]["faithfulness"],
            "ragas_precision": metadata["ragas_scores"]["context_precision"],
            "accuracy": metadata["accuracy"],
        })
        
        # Log training data provenance
        mlflow.log_artifact("data/training_manifest.json", "data_provenance")
        
        # Auto-generate technical documentation
        tech_docs = generate_technical_documentation(
            model=model_artifact,
            metadata=metadata,
            training_logs=mlflow.get_run(mlflow.active_run().info.run_id),
        )
        mlflow.log_artifact(tech_docs, "compliance/technical_documentation.pdf")
        
        # EU AI Act: Declaration of Conformity
        conformity = generate_conformity_declaration(
            model_info=metadata,
            compliance_checks=run_compliance_checks(),
            responsible_person="CTO Name",
            organization="Knowledge Foundry Inc.",
        )
        mlflow.log_artifact(conformity, "compliance/eu_declaration_of_conformity.pdf")
```

**Auto-Generated Documentation (11 Sections):**

```
┌─────────────────────────────────────────────────────────────┐
│  Technical Documentation – Knowledge Foundry AI System      │
│  Generated: 2026-02-08 | Version: 1.2.3                    │
├─────────────────────────────────────────────────────────────┤
│  1. System Description                                      │
│     Purpose, use cases, risk classification (Art. 6)        │
│  2. System Architecture                                     │
│     LLM Router, Vector DB, Graph DB, Multi-Agent            │
│  3. Models Used                                             │
│     Opus 4, Sonnet 3.5, Haiku 3 — provider, version        │
│  4. Training Data / Retrieval Corpus                        │
│     Sources, volume, quality, bias assessment, lineage      │
│  5. Performance Metrics                                     │
│     RAGAS scores, latency p95 (Golden Dataset eval)         │
│  6. Risk Management                                         │
│     Key risks, mitigations, residual risk                   │
│  7. Human Oversight                                         │
│     HITL triggers, roles, override authority, SLA           │
│  8. Logging & Traceability                                  │
│     100% coverage, 7yr retention, S3 WORM                   │
│  9. Post-Market Monitoring                                  │
│     Data collection, analysis cadence, reporting            │
│  10. Version History                                        │
│      Changes, dates, approvers                              │
│  11. Conformity Declaration                                 │
│      EU AI Act Declaration of Conformity (signed)           │
└─────────────────────────────────────────────────────────────┘
```

---

### 1.3 Change Management & Audit Trail

**Configuration Change Record:**

```json
{
  "change_id": "UUID",
  "timestamp": "2026-02-08T03:00:00Z",
  "changed_by": "user_id or system",
  "change_type": "configuration_update",
  "category": "models",
  "field_changed": "models.workhorse.temperature",
  "old_value": 0.3,
  "new_value": 0.2,
  "rationale": "Reduce variability in code generation",
  "risk_assessment": "LOW",
  "approved_by": "tech_lead_user_id",
  "approval_timestamp": "2026-02-08T02:55:00Z"
}
```

**Immutable Audit Log (Blockchain-style):**
- Each change hashed (SHA-256) and chained to previous record
- Impossible to tamper with historical records
- Cryptographically verifiable integrity
- Stored in S3 WORM (Write Once Read Many) — 7yr retention

---

## 2. POST-MARKET MONITORING AUTOMATION

### 2.1 Data Collection Pipeline

```python
class PostMarketMonitor:
    """Collects daily metrics across 5 categories for compliance reporting."""
    
    def collect_daily_metrics(self, date: date) -> Dict:
        metrics = {
            "usage": {
                "total_queries": query_count(date),
                "unique_users": unique_user_count(date),
                "queries_by_use_case": query_breakdown(date),
            },
            "performance": {
                "ragas_scores": {
                    "faithfulness": avg_ragas_metric(date, "faithfulness"),
                    "precision": avg_ragas_metric(date, "context_precision"),
                    "recall": avg_ragas_metric(date, "context_recall"),
                },
                "latency_p95": latency_percentile(date, 0.95),
                "error_rate": error_rate(date),
            },
            "safety": {
                "injection_attempts": count_security_events(date, "injection"),
                "harmful_content_blocked": count_security_events(date, "harmful"),
                "pii_redactions": count_security_events(date, "pii"),
            },
            "user_satisfaction": {
                "thumbs_up_rate": satisfaction_rate(date),
                "flags": count_user_flags(date),
                "escalations_to_human": hitl_count(date),
            },
            "compliance": {
                "log_coverage": logging_coverage(date),
                "hitl_sla_compliance": hitl_sla_adherence(date),
                "incidents": serious_incident_count(date),
            },
        }
        
        store_metrics(date, metrics)
        
        if detect_anomaly(metrics):
            alert_governance_team(metrics, date)
        
        return metrics
```

### 2.2 Monthly Compliance Report (Auto-Generated)

```python
def generate_monthly_compliance_report(month: int, year: int) -> None:
    monthly_data = aggregate_metrics(month, year)
    
    report = ComplianceReport(
        period=f"{month}/{year}",
        generated_date=datetime.now(),
    )
    
    # 7 sections auto-populated from metrics
    report.add_section("Executive Summary", executive_summary(monthly_data))
    report.add_table("Performance", performance_table(monthly_data))
    report.add_section("Safety & Security", safety_summary(monthly_data))
    report.add_section("Human Oversight", hitl_summary(monthly_data))
    report.add_checklist("EU AI Act Compliance", compliance_checklist(monthly_data))
    report.add_table("Incidents", incident_table(monthly_data))
    report.add_section("Recommendations", generate_recommendations(monthly_data))
    
    # Export & distribute
    report.export_pdf(f"compliance_reports/{year}_{month:02d}_compliance_report.pdf")
    send_email(
        to=["ai_governance_officer@company.com", "cto@company.com", "legal@company.com"],
        subject=f"Monthly AI Compliance Report: {month}/{year}",
        attachment=report.pdf_path,
    )
```

**Report Sections:**

| Section | Content | Data Source |
|---------|---------|------------|
| Executive Summary | Uptime, query count, health status, serious incidents | Aggregated metrics |
| Performance | RAGAS scores vs targets, latency, error rate | RAGAS evaluator, APM |
| Safety & Security | Injection attempts blocked, harmful content, PII redactions | Safety Scanner logs |
| Human Oversight | HITL reviews, SLA compliance, override rate | HITL queue + audit log |
| EU AI Act Compliance | 5-point checklist (Tech docs, logging, HITL, monitoring, incidents) | Compliance checks |
| Incidents | Date, type, severity, status, resolution time | Incident tracker |
| Recommendations | AI-generated improvement suggestions | Anomaly detection |

---

### 2.3 Serious Incident Reporting Automation (Art. 73)

**15-Day Reporting Timeline:**

```
Day 0     Day 3      Day 7       Day 12     Day 14    Day 15
  │         │          │           │          │         │
  ▼         ▼          ▼           ▼          ▼         ▼
Detect   Investigate  RCA      Draft Report  Legal   SUBMIT
& Alert  & Contain   Complete   to Regulator Review  DEADLINE
```

```python
class SeriousIncidentHandler:
    def handle_incident(self, incident: Incident) -> None:
        if self.is_serious_incident(incident):
            self.initiate_serious_incident_protocol(incident)
    
    def is_serious_incident(self, incident: Incident) -> bool:
        """EU AI Act criteria for serious incidents."""
        criteria = [
            incident.caused_death_or_serious_harm,
            incident.disrupted_critical_infrastructure,
            incident.violated_eu_law,                    # discrimination, privacy
            incident.widespread_impact > 1000,           # >1000 users affected
        ]
        return any(criteria)
    
    def initiate_serious_incident_protocol(self, incident: Incident) -> None:
        record = create_incident_record(
            incident_id=generate_uuid(),
            detected_at=datetime.now(),
            type=incident.type,
            severity="SERIOUS",
            reporting_deadline=datetime.now() + timedelta(days=15),
        )
        
        # Day 0-3: Investigation & containment
        assign_to_team(record, team="incident_response")
        alert_stakeholders(["cto", "legal", "ai_governance_officer"])
        
        # Day 3-7: Root cause analysis
        schedule_task(record, "root_cause_analysis", due=days(7))
        
        # Day 7-12: Draft regulatory report
        schedule_task(record, "draft_regulatory_report", due=days(12))
        
        # Day 12-14: Legal review
        schedule_task(record, "legal_review_report", due=days(14))
        
        # Day 14: Submit to regulator
        schedule_task(record, "submit_to_regulator", due=days(14))
        
        # Day 15: Deadline safety net
        if not record.submitted_by_deadline:
            escalate_to_ceo(record, "REGULATORY DEADLINE MISSED")
    
    def generate_regulatory_report(self, record: IncidentRecord) -> Dict:
        return {
            "provider_info": {
                "name": "Knowledge Foundry Inc.",
                "contact": "legal@knowledge-foundry.com",
                "responsible_person": "CTO Name",
            },
            "ai_system_info": {
                "name": "Knowledge Foundry",
                "version": "1.2.3",
                "classification": "High-Risk AI System",
            },
            "incident_details": {
                "date": record.detected_at,
                "type": record.type,
                "affected_users": record.affected_user_count,
                "severity_assessment": record.severity_rationale,
            },
            "root_cause": record.root_cause_analysis,
            "immediate_actions_taken": record.containment_actions,
            "corrective_actions": record.remediation_plan,
            "timeline": record.timeline,
            "supporting_evidence": record.evidence_attachments,
        }
```

---

## 3. COMPLIANCE DASHBOARD

### 3.1 Real-Time Compliance Cockpit

**Compliance Health Score (0-100):**

| Component | Points | Measurement |
|-----------|:------:|-------------|
| Technical Documentation Current | 20 | Doc version ≤ system version |
| Logging Coverage >99.9% | 20 | `log_coverage_percentage` metric |
| RAGAS > Thresholds | 15 | All 3 metrics above targets |
| HITL SLA Met | 15 | No overdue reviews (>4h) |
| No Serious Incidents | 10 | Zero in last 90 days |
| Risk Register Current | 10 | Updated <90 days ago |
| Security Posture (OWASP) | 10 | Last Garak scan clean |
| **Total** | **100** | |

**Health Score Display:**

| Score | Status | Indicator |
|:-----:|:------:|:---------:|
| 90-100 | Excellent | 🟢 Green |
| 70-89 | Good | 🟡 Yellow |
| <70 | Action Required | 🔴 Red |

### 3.2 Dashboard Panels

| Panel | Content | Alert |
|-------|---------|:-----:|
| **Health Score** | Gauge 0-100 | <70 → alert |
| **Logging Coverage** | Current % + 30-day trend | <99.9% → alert |
| **RAGAS Scores** | Faithfulness, Precision, Recall + trends | Below threshold → alert |
| **HITL Oversight** | Pending reviews, overdue, SLA %, avg time | Any overdue → alert |
| **Incidents** | Open count, serious (90d), avg resolution | Serious incident → page |
| **Upcoming Deadlines** | Risk review, external audit, cert renewal | <7 days → alert |

### 3.3 Regulatory Reporting Dashboard

**For Regulators/Auditors (read-only view):**

- System overview: classification, version, deployment date
- Historical performance metrics (RAGAS, latency, uptime)
- Safety metrics: security incidents, harmful content blocked
- Human oversight statistics: HITL reviews, override rates
- Incident log: all serious incidents with resolutions
- Export: generate compliance reports for specific time periods (PDF)

---

## 4. ACCEPTANCE CRITERIA

| # | Criterion | Test Method | Status |
|:-:|-----------|------------|:------:|
| 1 | Compliance checks run automatically in CI/CD | Deploy with missing check → verify blocked | ☐ |
| 2 | Deployment blocked if RAGAS < thresholds | Deploy with faithfulness=0.8 → verify rejected | ☐ |
| 3 | Deployment blocked if tech docs missing | Deploy without docs → verify blocked | ☐ |
| 4 | Technical documentation auto-generated on every deployment | Deploy and verify PDF output | ☐ |
| 5 | Conformity declaration generated with correct fields | Inspect generated PDF | ☐ |
| 6 | Change audit trail captures all config changes | Make 5 config changes → verify all logged | ☐ |
| 7 | Audit trail is immutable (hash chain verified) | Attempt to modify log → verify integrity check fails | ☐ |
| 8 | Daily metrics collected across 5 categories | Run collector → verify all fields populated | ☐ |
| 9 | Monthly compliance report generated without manual intervention | Trigger monthly report → verify 7 sections | ☐ |
| 10 | Anomaly detection alerts governance team | Inject anomalous metric → verify alert | ☐ |
| 11 | Serious incident protocol triggers on qualifying incidents | Simulate serious incident → verify 15-day timeline | ☐ |
| 12 | Regulatory report contains all required fields | Generate report → inspect against Art. 73 template | ☐ |
| 13 | CEO escalation if deadline missed | Simulate missed deadline → verify escalation | ☐ |
| 14 | Compliance dashboard shows real-time health score | Visual verification of gauge | ☐ |
| 15 | Health score correctly computed (7 components) | Set known values → verify score calculation | ☐ |
| 16 | Logging coverage alert fires at <99.9% | Reduce coverage → verify alert | ☐ |
| 17 | Regulatory dashboard provides read-only auditor access | Login as auditor → verify read-only | ☐ |
| 18 | Export generates PDF for arbitrary time periods | Export last 30-day report → verify PDF | ☐ |
| 19 | All EU AI Act requirements (Art. 9-15) automated where possible | Legal review of automation coverage | ☐ |
| 20 | Legal review confirms compliance readiness | Sign-off from legal | ☐ |
