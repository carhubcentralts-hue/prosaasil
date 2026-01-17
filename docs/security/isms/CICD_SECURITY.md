# CI/CD Security Requirements

## ProSaaS / AgentLocator - Secure Development Pipeline

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-010                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This document establishes security requirements for the CI/CD pipeline in accordance with ISO/IEC 27001:2022 (A.14 System Acquisition, Development and Maintenance).

## 2. Scope

This policy applies to:
- All code repositories
- Build and deployment pipelines
- Container images
- Infrastructure as code
- Third-party dependencies

## 3. Security Gates

### 3.1 Pre-Merge Security Checks

| Check | Tool | Blocking | Description |
|-------|------|:--------:|-------------|
| Secret detection | gitleaks | ✅ Yes | Detect hardcoded secrets |
| Dependency scan | pip-audit / npm audit | ✅ Yes | Vulnerable dependencies |
| Container scan | Trivy | ⚠️ Warning | Container vulnerabilities |
| Code quality | Linters | ⚠️ Warning | Code quality issues |
| Unit tests | pytest / jest | ✅ Yes | Functional correctness |

### 3.2 Gate Criteria

**BLOCKING (Must Pass):**
- No HIGH/CRITICAL secrets detected
- No HIGH/CRITICAL dependency vulnerabilities
- All unit tests pass
- Syntax validation passes

**WARNING (Review Required):**
- Medium severity vulnerabilities
- Code quality issues
- Container image warnings

## 4. Secret Detection

### 4.1 gitleaks Configuration

Recommended `.gitleaks.toml` configuration:

```toml
# ProSaaS gitleaks configuration
title = "ProSaaS Secret Scanning"

[extend]
# Use default rules
useDefault = true

[allowlist]
description = "Global allowlist"
paths = [
    '''(.*)?test(.*)?''',
    '''docs/security/''',
]

[[rules]]
description = "API Key Detection"
regex = '''(?i)(api[_-]?key|apikey|api_secret)\s*[=:]\s*['"]?[\w-]{20,}['"]?'''
tags = ["key", "API"]
```

### 4.2 Secret Types to Detect

| Secret Type | Pattern | Severity |
|-------------|---------|----------|
| AWS credentials | `AKIA...` | Critical |
| Private keys | `-----BEGIN.*PRIVATE KEY` | Critical |
| API keys | `api_key=...` | High |
| Database passwords | `password=...` | Critical |
| JWT secrets | `jwt_secret=...` | Critical |
| Twilio tokens | `twilio_auth_token` | Critical |
| OpenAI keys | `sk-...` | Critical |

### 4.3 False Positive Handling

```yaml
# In .gitleaks.toml allowlist
[[allowlist.commits]]
description = "Known false positive"
regexes = [
    '''example_key_for_documentation''',
]
```

## 5. Dependency Security

### 5.1 Python Dependencies

```bash
# Check for vulnerabilities
pip-audit --requirement requirements.txt

# Update vulnerable packages
pip install --upgrade package_name
```

### 5.2 JavaScript Dependencies

```bash
# Check for vulnerabilities
npm audit

# Fix automatically (when safe)
npm audit fix

# Review breaking changes
npm audit fix --dry-run
```

### 5.3 Dependency Update Policy

| Severity | Action | Timeframe |
|----------|--------|-----------|
| Critical | Immediate update | 24 hours |
| High | Prioritized update | 7 days |
| Medium | Planned update | 30 days |
| Low | Next release | 90 days |

## 6. Container Security

### 6.1 Base Image Policy

| Requirement | Implementation |
|-------------|----------------|
| Official images | Use official base images only |
| Minimal images | Prefer alpine/slim variants |
| Pinned versions | Use specific version tags (not `latest`) |
| Regular updates | Update base images monthly |

### 6.2 Container Scanning

```bash
# Scan with Trivy
trivy image prosaas:latest

# Severity filtering
trivy image --severity HIGH,CRITICAL prosaas:latest
```

### 6.3 Dockerfile Best Practices

```dockerfile
# Use specific version
FROM python:3.11-slim-bookworm

# Don't run as root
RUN useradd -r -s /bin/false appuser
USER appuser

# Copy only necessary files
COPY --chown=appuser:appuser . /app

# Use multi-stage builds
FROM builder AS runtime
COPY --from=builder /app /app
```

## 7. Code Review Security

### 7.1 Security Review Checklist

```
□ No hardcoded credentials
□ Input validation on all user inputs
□ SQL queries use parameterized queries
□ No sensitive data in logs
□ Proper authentication on new endpoints
□ Authorization checks for data access
□ Error messages don't leak information
□ Dependencies from trusted sources
```

### 7.2 High-Risk Changes

Changes requiring security-focused review:
- Authentication/authorization logic
- Cryptographic operations
- User input handling
- Database queries
- API endpoint additions
- File upload handling
- External service integrations

## 8. Build Security

### 8.1 Build Environment

| Requirement | Implementation |
|-------------|----------------|
| Isolated builds | Containerized build environment |
| No network access | Build-time network isolation |
| Clean environment | Fresh container per build |
| Artifact signing | Sign build outputs |

### 8.2 Artifact Security

| Artifact | Security Measure |
|----------|------------------|
| Container images | Signed with registry |
| Build outputs | Checksum verification |
| Configuration | Encrypted at rest |

## 9. Deployment Security

### 9.1 Deployment Checklist

```
□ All security scans passed
□ Code review approved
□ Tests passed
□ Configuration verified
□ Secrets in secret manager
□ Rollback plan ready
□ Monitoring alerts configured
```

### 9.2 Environment Separation

| Environment | Access | Purpose |
|-------------|--------|---------|
| Development | Developers | Feature development |
| Staging | Dev + QA | Pre-production testing |
| Production | Limited | Customer-facing |

### 9.3 Secret Management

| Practice | Implementation |
|----------|----------------|
| No secrets in code | Environment variables only |
| Secret rotation | Quarterly or on compromise |
| Least privilege | Per-environment secrets |
| Audit logging | Log secret access |

## 10. Monitoring and Alerting

### 10.1 Security Alerts

| Alert | Trigger | Response |
|-------|---------|----------|
| Build failure | Security scan failure | Review and fix |
| Dependency alert | New vulnerability | Assess and update |
| Deploy failure | Health check failure | Rollback |

### 10.2 Metrics

| Metric | Target |
|--------|--------|
| Secret scan pass rate | 100% |
| Dependency vulnerabilities (critical) | 0 |
| Build scan pass rate | >95% |
| Mean time to fix critical | <24 hours |

## 11. GitHub Actions Security

### 11.1 Workflow Security

```yaml
# Example secure workflow
name: Security Scan

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  security:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Run pip-audit
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt
      
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'HIGH,CRITICAL'
```

### 11.2 Workflow Permissions

| Permission | Setting |
|------------|---------|
| Default permissions | Read-only |
| Secret access | Limited to needed jobs |
| External actions | Pinned to SHA |

## 12. Compliance

### 12.1 ISO 27001 Controls

| Control | Implementation |
|---------|----------------|
| A.14.2.1 | Secure development policy (this document) |
| A.14.2.2 | System change control (Git, PR reviews) |
| A.14.2.3 | Technical review (code review) |
| A.14.2.5 | Secure engineering (security scans) |
| A.14.2.6 | Secure development environment (isolated) |
| A.14.2.7 | Outsourced development (N/A) |
| A.14.2.8 | System security testing (automated scans) |
| A.14.2.9 | System acceptance testing (pre-deploy checks) |

## 13. Review and Updates

This policy shall be reviewed:
- Annually as part of management review
- When CI/CD tooling changes
- When new security tools become available
- After security incidents related to development

---

**Document Control**

| Version | Date       | Author      | Changes                     |
|---------|------------|-------------|-----------------------------|
| 1.0     | 2026-01-17 | System      | Initial CI/CD security policy |
