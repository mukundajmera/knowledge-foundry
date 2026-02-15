# ADR-005: OWASP 2026 Security Stack

**Status:** Accepted  
**Date:** February 14, 2026  
**Deciders:** Principal AI Architect, Security Lead  

---

## Context

LLM-powered systems face unique attack vectors including prompt injection, data exfiltration, jailbreaking, and tool misuse. The OWASP 2026 guidelines provide a defensive checklist for securing AI applications in production.

## Decision

**Implement a four-layer defense-in-depth security architecture** aligned with OWASP 2026 best practices:

### Layer 1: Input Validation
- Pydantic validation (type, length, format)
- Regex patterns for injection detection (`ignore instructions`, `system:`, `<|im_start|>`)
- Fuzzy matching for obfuscated attacks
- Rate limiting via Redis token bucket (per-user, per-tenant, per-endpoint)

### Layer 2: Orchestration Security
- XML delimiters (`<system>`, `<user>`, `<context>`, `<tool_output>`) to separate trusted/untrusted content
- Spotlighting: provenance markers on every input segment
- Least privilege per agent (Researcher: read-only DB; Coder: no deploy; Safety: can block)

### Layer 3: Tool/Plugin Security
- Explicit permission model (user consent for dangerous actions)
- Safety Agent validates all high-risk tool calls before execution
- Dry-run mode for destructive operations
- Sandboxed execution for plugins

### Layer 4: Output Validation
- System prompt leak detection (regex + Garak scanner)
- PII scanning (regex + NER model)
- Citation/source attribution required for all claims
- Confidence threshold enforcement (refuse when <0.5)

### Continuous Security
- Garak + NeMo Guardrails in CI/CD (every commit)
- Monthly automated multi-persona red teaming (adversarial, benign failure, edge cases)
- Quarterly manual penetration testing
- Incident response: detect <5min → contain <15min → remediate <4h → postmortem <48h

## Rationale

- Defense-in-depth prevents single-point security failures
- OWASP 2026 alignment provides industry-standard baseline
- Automated scanning in CI/CD catches vulnerabilities before production

## Consequences

**Benefits:** Comprehensive security posture, automated vulnerability detection, regulatory compliance  
**Costs:** CI/CD pipeline adds ~2 minutes per commit; Security Agent adds ~50ms latency per query  
**Risks:** False positives blocking legitimate queries → mitigated by tuned thresholds + user feedback loop
