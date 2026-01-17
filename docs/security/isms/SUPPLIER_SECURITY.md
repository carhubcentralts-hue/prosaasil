# Supplier Security Policy

## ProSaaS / AgentLocator - Third-Party and Vendor Risk Management

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-009                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This policy establishes requirements for managing security risks from third-party suppliers and service providers in accordance with ISO/IEC 27001:2022 (A.15 Supplier Relationships).

## 2. Scope

This policy applies to all third-party relationships where:
- Customer data is shared or processed
- System access is provided
- Services are integrated with ProSaaS/AgentLocator
- Business-critical functions are outsourced

## 3. Third-Party Risk Categories

### 3.1 Risk Classification

| Risk Level | Criteria | Examples |
|------------|----------|----------|
| **Critical** | Processes PII, system access | Twilio, OpenAI |
| **High** | Access to confidential data | Payment providers |
| **Medium** | Limited data access | Analytics tools |
| **Low** | No data access | Office supplies |

### 3.2 Current Suppliers

| Supplier | Service | Risk Level | Data Processed |
|----------|---------|------------|----------------|
| **Twilio** | Voice/SMS/WhatsApp | Critical | Phone numbers, call audio |
| **OpenAI** | AI/LLM processing | Critical | Conversation content |
| **WhatsApp/Meta** | Messaging | Critical | Phone numbers, messages |
| **Cloud Hosting** | Infrastructure | Critical | All application data |
| **Payment Provider** | Payment processing | High | Tokens only (no card data) |

## 4. Supplier Security Requirements

### 4.1 Mandatory Requirements

All suppliers processing ProSaaS/AgentLocator data must:

| Requirement | Description |
|-------------|-------------|
| Security certification | ISO 27001, SOC 2, or equivalent |
| Data encryption | TLS 1.2+ in transit, encryption at rest |
| Access controls | RBAC, MFA for admin access |
| Incident notification | 24-hour breach notification |
| Data Processing Agreement | GDPR-compliant DPA |
| Audit rights | Right to audit or review SOC reports |

### 4.2 Contractual Requirements

Every supplier agreement must include:

| Clause | Description |
|--------|-------------|
| Confidentiality | NDA or confidentiality clause |
| Data processing terms | Purpose limitation, data minimization |
| Security standards | Minimum security requirements |
| Subcontractor controls | Approval for subcontracting |
| Termination assistance | Data return/deletion upon termination |
| Liability and indemnity | Security breach liability |

## 5. Supplier Risk Assessment

### 5.1 Assessment Process

```
1. Initial Questionnaire
   └── Security practices
   └── Certifications
   └── Data handling

2. Document Review
   └── SOC 2 reports
   └── ISO 27001 certificate
   └── Penetration test results

3. Risk Evaluation
   └── Inherent risk assessment
   └── Control effectiveness
   └── Residual risk calculation

4. Decision
   └── Approve
   └── Approve with conditions
   └── Reject
```

### 5.2 Risk Assessment Template

| Assessment Area | Questions |
|-----------------|-----------|
| Security governance | Do you have a formal security program? |
| Access control | How is access to customer data controlled? |
| Encryption | What encryption is used for data at rest/transit? |
| Incident response | What is your breach notification timeframe? |
| Business continuity | What is your RPO/RTO? |
| Compliance | What security certifications do you hold? |

## 6. Supplier Security Profiles

### 6.1 Twilio

| Attribute | Value |
|-----------|-------|
| **Service** | Voice calls, SMS, WhatsApp Cloud API |
| **Data processed** | Phone numbers, call audio, metadata |
| **Risk level** | Critical |
| **Certifications** | ISO 27001, SOC 2 Type II, GDPR compliant |
| **Data location** | US/EU (configurable) |
| **Encryption** | TLS 1.2+, AES-256 at rest |
| **DPA status** | ✅ In place |
| **SLA** | 99.95% uptime |

**Security Controls:**
- Webhook signature validation implemented
- TLS-only connections
- Secure credential storage
- Audit logging of all API calls

**Code Reference:**
```python
# /server/twilio_security.py
def require_twilio_signature(f):
    """Validate Twilio webhook signatures."""
```

### 6.2 OpenAI

| Attribute | Value |
|-----------|-------|
| **Service** | AI/LLM processing (GPT-4) |
| **Data processed** | Conversation content, prompts |
| **Risk level** | Critical |
| **Certifications** | SOC 2 Type II |
| **Data retention** | 30 days (API, can opt out) |
| **Encryption** | TLS 1.2+, encrypted at rest |
| **DPA status** | ✅ Standard terms include DPA |
| **SLA** | Best effort |

**Security Controls:**
- API key rotation capability
- Rate limiting
- Content filtering
- No training on API data (with opt-out)

**Data Flow:**
```
ProSaaS → OpenAI API → Response
        (TLS encrypted)
```

### 6.3 WhatsApp/Meta

| Attribute | Value |
|-----------|-------|
| **Service** | Business messaging |
| **Data processed** | Phone numbers, message content |
| **Risk level** | Critical |
| **Certifications** | ISO 27001, SOC 2 |
| **Data location** | Regional data centers |
| **Encryption** | End-to-end encryption |
| **DPA status** | ✅ Part of Meta Business Terms |
| **SLA** | 99.9% |

**Security Controls:**
- Webhook signature validation
- Message encryption
- Access token management
- Rate limiting compliance

### 6.4 Cloud Hosting Provider

| Attribute | Value |
|-----------|-------|
| **Service** | Infrastructure, compute, storage |
| **Data processed** | All application data |
| **Risk level** | Critical |
| **Certifications** | ISO 27001, SOC 2, PCI DSS |
| **Data location** | Configurable by region |
| **Encryption** | AES-256 at rest, TLS in transit |
| **DPA status** | ✅ In place |
| **SLA** | 99.99% |

**Security Controls:**
- Network isolation
- Firewall configuration
- Access logging
- Backup management

## 7. Ongoing Monitoring

### 7.1 Review Schedule

| Activity | Frequency | Responsible |
|----------|-----------|-------------|
| Supplier security review | Annual | ISMS Owner |
| Certification verification | Annual | Security Team |
| SLA monitoring | Monthly | Operations |
| Incident review | As needed | Security Team |

### 7.2 Monitoring Checklist

```
□ Review supplier security certifications
□ Review any security incidents reported
□ Verify DPA/contract compliance
□ Assess service performance against SLA
□ Review access and integration points
□ Update risk assessment if needed
```

### 7.3 Trigger-Based Reviews

Immediate review required when:
- Supplier reports security incident
- Supplier changes ownership
- Significant service changes
- New data sharing requirements
- Regulatory changes

## 8. Incident Management

### 8.1 Supplier Incident Notification

| Requirement | Timeframe |
|-------------|-----------|
| Initial notification | 24 hours |
| Preliminary assessment | 48 hours |
| Full incident report | 7 days |

### 8.2 Our Response

| Phase | Actions |
|-------|---------|
| Detection | Receive supplier notification |
| Assessment | Evaluate impact on our customers |
| Containment | Suspend integration if needed |
| Customer notification | Notify affected customers |
| Resolution | Work with supplier on remediation |
| Post-incident | Update risk assessment |

## 9. Exit Strategy

### 9.1 Termination Requirements

| Requirement | Description |
|-------------|-------------|
| Data return | All data returned in portable format |
| Data deletion | Confirmation of secure deletion |
| Transition period | Minimum 30 days notice |
| Access revocation | All access credentials revoked |
| Audit | Final security review |

### 9.2 Contingency Plans

| Supplier | Contingency |
|----------|-------------|
| Twilio | Alternative VoIP provider evaluation |
| OpenAI | Alternative LLM provider (Azure OpenAI, Anthropic) |
| WhatsApp | Alternative messaging (SMS fallback) |
| Cloud hosting | Multi-cloud architecture evaluation |

## 10. Record Keeping

### 10.1 Required Records

| Record | Retention |
|--------|-----------|
| Supplier contracts | Duration + 7 years |
| Risk assessments | 5 years |
| DPA/security addenda | Duration + 7 years |
| Audit reports | 3 years |
| Incident records | 5 years |

### 10.2 Evidence Repository

| Document Type | Location |
|---------------|----------|
| Contracts | Legal document repository |
| Certifications | Security documentation |
| Risk assessments | ISMS documentation |
| Incident reports | Incident management system |

## 11. Compliance

### 11.1 ISO 27001 Controls

| Control | Implementation |
|---------|----------------|
| A.15.1.1 | Information security policy for supplier relationships (this document) |
| A.15.1.2 | Addressing security in supplier agreements (contractual requirements) |
| A.15.1.3 | ICT supply chain (supplier risk assessment) |
| A.15.2.1 | Monitoring of supplier services (ongoing monitoring) |
| A.15.2.2 | Managing changes to supplier services (change review) |

### 11.2 GDPR Compliance

- All suppliers processing EU data have DPAs
- Data processing purposes are documented
- Subprocessor lists are maintained
- Cross-border transfer mechanisms in place

## 12. Review and Updates

This policy shall be reviewed:
- Annually as part of management review
- When new critical suppliers are engaged
- When supplier relationships significantly change
- Following supplier security incidents

---

**Document Control**

| Version | Date       | Author      | Changes                       |
|---------|------------|-------------|-------------------------------|
| 1.0     | 2026-01-17 | System      | Initial supplier security policy |
