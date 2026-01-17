# ISMS Document Index

## ProSaaS / AgentLocator - Information Security Management System

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Last Updated**         | 2026-01-17                          |

---

## 1. ISMS Overview

This document provides an index to all Information Security Management System (ISMS) documentation for ProSaaS/AgentLocator, implementing ISO/IEC 27001:2022 requirements.

## 2. Document Index

### 2.1 Core Policy Documents

| Doc ID | Document | Description | Review Cycle |
|--------|----------|-------------|--------------|
| POL-ISMS-001 | [SECURITY_POLICY.md](SECURITY_POLICY.md) | Master security policy | Annual |
| POL-ISMS-002 | [ISMS_SCOPE.md](ISMS_SCOPE.md) | ISMS scope and boundaries | Annual |
| POL-ISMS-003 | [RISK_ASSESSMENT.md](RISK_ASSESSMENT.md) | Risk assessment framework | Annual |
| POL-ISMS-004 | [STATEMENT_OF_APPLICABILITY.md](STATEMENT_OF_APPLICABILITY.md) | ISO 27001 Annex A mapping | Annual |

### 2.2 Operational Policies

| Doc ID | Document | Description | Review Cycle |
|--------|----------|-------------|--------------|
| POL-ISMS-005 | [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) | Incident response procedures | Annual |
| POL-ISMS-006 | [ACCESS_CONTROL_POLICY.md](ACCESS_CONTROL_POLICY.md) | Access control and RBAC | Quarterly |
| POL-ISMS-007 | [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md) | Data classification scheme | Annual |
| POL-ISMS-008 | [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) | Backup and DR procedures | Annual |
| POL-ISMS-009 | [SUPPLIER_SECURITY.md](SUPPLIER_SECURITY.md) | Third-party risk management | Annual |
| POL-ISMS-010 | [CICD_SECURITY.md](CICD_SECURITY.md) | CI/CD pipeline security | Annual |

## 3. ISO 27001:2022 Clause Mapping

### 3.1 Management Requirements (Clauses 4-10)

| Clause | Requirement | Document |
|--------|-------------|----------|
| 4 | Context of the organization | ISMS_SCOPE.md |
| 5 | Leadership | SECURITY_POLICY.md |
| 6 | Planning | RISK_ASSESSMENT.md |
| 7 | Support | SECURITY_POLICY.md |
| 8 | Operation | All operational policies |
| 9 | Performance evaluation | Management review process |
| 10 | Improvement | Incident lessons learned |

### 3.2 Annex A Control Mapping

See [STATEMENT_OF_APPLICABILITY.md](STATEMENT_OF_APPLICABILITY.md) for complete mapping of all 93 Annex A controls.

## 4. Quick Reference

### 4.1 For Auditors

Start with:
1. [ISMS_SCOPE.md](ISMS_SCOPE.md) - Understand scope
2. [STATEMENT_OF_APPLICABILITY.md](STATEMENT_OF_APPLICABILITY.md) - Control mapping
3. [RISK_ASSESSMENT.md](RISK_ASSESSMENT.md) - Risk treatment

### 4.2 For Incident Response

1. [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) - Response procedures
2. [SECURITY_POLICY.md](SECURITY_POLICY.md) - Contact information
3. Security events logged in `security_events` database table

### 4.3 For Developers

1. [ACCESS_CONTROL_POLICY.md](ACCESS_CONTROL_POLICY.md) - RBAC implementation
2. [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md) - Data handling
3. [CICD_SECURITY.md](CICD_SECURITY.md) - Secure development

### 4.4 For New Employees

1. [SECURITY_POLICY.md](SECURITY_POLICY.md) - Security overview
2. [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md) - Data handling
3. [ACCESS_CONTROL_POLICY.md](ACCESS_CONTROL_POLICY.md) - Access rules

## 5. Code Evidence References

### 5.1 Authentication & Authorization

| Component | File | Description |
|-----------|------|-------------|
| Authentication | `/server/auth.py` | `require_auth` decorator |
| Authorization | `/server/authz.py` | `roles_required` decorator |
| Audit logging | `/server/security_audit.py` | `AuditLogger` class |
| Password policy | `/server/security_audit.py` | `password_strength_check()` |

### 5.2 Security Controls

| Control | File | Description |
|---------|------|-------------|
| Webhook signing | `/server/twilio_security.py` | `require_twilio_signature` |
| Session security | `/server/security_audit.py` | `SessionSecurity` class |
| Tenant isolation | `/server/auth.py` | `get_current_tenant()` |
| Rate limiting | `/server/rate_limiter.py` | Request rate limiting |

### 5.3 Data Models

| Model | File | Description |
|-------|------|-------------|
| Security events | `/server/models_sql.py` | `SecurityEvent` model |
| Users | `/server/models_sql.py` | `User` model with roles |
| Business | `/server/models_sql.py` | `Business` multi-tenant |

## 6. Review Schedule

| Document | Owner | Review Frequency | Next Review |
|----------|-------|------------------|-------------|
| SECURITY_POLICY | ISMS Owner | Annual | 2027-01-17 |
| ISMS_SCOPE | ISMS Owner | Annual | 2027-01-17 |
| RISK_ASSESSMENT | ISMS Owner | Annual | 2027-01-17 |
| STATEMENT_OF_APPLICABILITY | ISMS Owner | Annual | 2027-01-17 |
| INCIDENT_RESPONSE | ISMS Owner | Annual | 2027-01-17 |
| ACCESS_CONTROL_POLICY | ISMS Owner | Quarterly | 2026-04-17 |
| DATA_CLASSIFICATION | ISMS Owner | Annual | 2027-01-17 |
| BACKUP_AND_RECOVERY | ISMS Owner | Annual | 2027-01-17 |
| SUPPLIER_SECURITY | ISMS Owner | Annual | 2027-01-17 |
| CICD_SECURITY | ISMS Owner | Annual | 2027-01-17 |

## 7. Contact Information

| Role | Responsibility |
|------|----------------|
| **ISMS Owner** | CTO / System Owner - Overall accountability |
| **Security Operations** | Security monitoring and response |
| **Incident Commander** | Major incident management |

## 8. Certification Status

| Standard | Status | Target |
|----------|--------|--------|
| ISO 27001:2022 | Implementing | Certification ready |
| GDPR | Compliant | Ongoing |
| PCI DSS | Not applicable | Tokenization only |

---

## 9. Important Notes

### 9.1 Scope Limitation

> **The ISMS scope explicitly excludes storage or processing of raw payment card data (PAN, CVV, expiry).** All payment processing uses tokenization via certified third-party providers.

### 9.2 Evidence Requirements

> **For every control, ensure at least one form of evidence exists** (log, screenshot, config, code reference).

### 9.3 Definition of Done

For ISO 27001 audit readiness:
- ✅ All Annex A controls mapped
- ✅ All data classified
- ✅ No secrets in code
- ✅ No cross-tenant access
- ✅ Webhooks signed
- ✅ Audit trail complete
- ✅ All documents current
- ✅ Ready for external audit

---

**Document Control**

| Version | Date       | Author      | Changes                |
|---------|------------|-------------|------------------------|
| 1.0     | 2026-01-17 | System      | Initial document index |
