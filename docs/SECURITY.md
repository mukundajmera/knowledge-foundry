# Security Guide

Security architecture and best practices for Knowledge Foundry.

## Security Layers

### 1. Input Sanitization

**Protections:**
- SQL injection detection
- XSS pattern blocking  
- Prompt injection defense
- Path traversal prevention

**Implementation:** `src/security/input_sanitizer.py`

```python
from src.security.input_sanitizer import InputSanitizer

sanitizer = InputSanitizer()
clean_input = sanitizer.sanitize(user_input)
```

### 2. Output Filtering

**Protections:**
- PII redaction (emails, SSNs, credit cards)
- Sensitive data detection
- Custom pattern filtering

**Implementation:** `src/security/output_filter.py`

### 3. Authentication

**JWT-based authentication:**

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=user&password=pass"

# Use token
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/protected
```

**Configuration:**
```bash
JWT_SECRET_KEY=<strong-random-key>  # Generate: openssl rand -base64 32
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480
```

### 4. Rate Limiting

**Per-user limits:**
- 100 requests / minute (authenticated)
- 10 requests / minute (anonymous)

**Override in code:**
```python
@app.get("/endpoint")
@rate_limit(limit=50, window=60)
async def endpoint():
    ...
```

### 5. Audit Trail

**Immutable logs for compliance:**
```python
from src.security.audit import AuditLogger

audit = AuditLogger()
await audit.log_event(
    event_type="query_executed",
    user_id=user.id,
    details={"query": query_text}
)
```

## OWASP Top 10 (2026)

| Risk | Mitigation |
|------|-----------|
| Injection | Input sanitization, parameterized queries |
| Broken Auth | JWT with proper expiry, strong secrets |
| Sensitive Data | Encryption at rest/transit, output filtering |
| XXE | Disabled XML parsing, JSON only |
| Broken Access Control | RBAC, permission checks on every endpoint |
| Security Misconfiguration | Secure defaults, automated checks |
| XSS | Input sanitization, CSP headers |
| Insecure Deserialization | JSON-only, no pickle |
| Using Components with Known Vulnerabilities | Dependency scanning (Snyk) |
| Insufficient Logging | Comprehensive audit trail |

## EU AI Act Compliance

**Automated checks:**
- Risk assessment logging
- Human oversight controls
- Technical documentation generation
- Transparency requirements

**Implementation:** `src/compliance/`

## Secrets Management

**Never commit secrets to git!**

```bash
# Use .env for local
cp .env.example .env
# Add to .gitignore

# Use secrets manager in production
# Kubernetes secrets:
kubectl create secret generic kf-secrets \
  --from-literal=anthropic-api-key=$ANTHROPIC_API_KEY \
  --from-literal=jwt-secret=$JWT_SECRET
```

## Network Security

### Production Checklist
- [ ] Enable HTTPS (TLS 1.3)
- [ ] Configure CORS properly
- [ ] Use private networks for databases
- [ ] Enable firewall rules
- [ ] Use VPC/security groups
- [ ] Implement DDoS protection

### Docker Security
```yaml
# Use non-root user
user: "1000:1000"

# Read-only filesystem
read_only: true

# Drop capabilities
cap_drop:
  - ALL
```

## Vulnerability Scanning

```bash
# Python dependencies
pip-audit

# Docker images
docker scan knowledge-foundry:latest

# SAST
bandit -r src/

# Adversarial testing
garak --scan
```

## Security Monitoring

**Metrics to track:**
- Failed auth attempts
- Rate limit violations
- Suspicious input patterns
- Unusual query patterns

**Grafana alerts configured for:**
- > 10 failed logins / minute
- > 100 rate limit hits / minute
- Detected injection attempts

## Incident Response

1. **Detect**: Monitoring alerts
2. **Contain**: Disable affected services
3. **Investigate**: Check audit logs
4. **Remediate**: Apply fixes
5. **Report**: Document incident

## Best Practices

1. **Principle of Least Privilege**: Grant minimum necessary permissions
2. **Defense in Depth**: Multiple security layers
3. **Fail Securely**: Default to deny
4. **Update Dependencies**: Regular security patches
5. **Security by Design**: Security from day one, not bolted on

## Security Contacts

Report vulnerabilities: security@knowledge-foundry.io

**Please do not open public issues for security vulnerabilities.**
