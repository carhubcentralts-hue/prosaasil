# Data Classification Policy

## ProSaaS / AgentLocator - Information Classification Scheme

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-007                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This policy establishes the data classification scheme for ProSaaS/AgentLocator in accordance with ISO/IEC 27001:2022 (A.8 Asset Management) to ensure appropriate protection of information assets.

## 2. Scope

This policy applies to all information processed, stored, or transmitted by ProSaaS/AgentLocator systems, including:
- Customer data
- System configuration
- Call recordings and transcripts
- Business intelligence data
- Logs and audit trails

## 3. Classification Levels

### 3.1 Four-Tier Classification Scheme

| Level | Label | Description | Examples |
|-------|-------|-------------|----------|
| **1** | Public | Information approved for public release | Marketing materials, public docs |
| **2** | Internal | Internal use only, low sensitivity | Internal procedures, meeting notes |
| **3** | Confidential | Business-sensitive, restricted access | Customer lists, financial data |
| **4** | Restricted | Highly sensitive, strict access | PII, call recordings, credentials |

### 3.2 Classification Details

#### Level 1: Public

| Aspect | Requirement |
|--------|-------------|
| **Access** | Open to anyone |
| **Storage** | No special requirements |
| **Transmission** | No restrictions |
| **Disposal** | Standard deletion |
| **Labeling** | Optional |

**Examples:**
- Public website content
- Published documentation
- Open-source code

#### Level 2: Internal

| Aspect | Requirement |
|--------|-------------|
| **Access** | Employees and authorized contractors |
| **Storage** | Company systems only |
| **Transmission** | Internal networks preferred |
| **Disposal** | Standard deletion |
| **Labeling** | "Internal" header |

**Examples:**
- Internal procedures
- Training materials
- Non-sensitive business data

#### Level 3: Confidential

| Aspect | Requirement |
|--------|-------------|
| **Access** | Need-to-know basis |
| **Storage** | Encrypted at rest |
| **Transmission** | TLS required |
| **Disposal** | Secure deletion |
| **Labeling** | "Confidential" header |

**Examples:**
- Business plans
- Customer lists (without PII)
- Financial projections
- System architecture

#### Level 4: Restricted (PII, Financial)

| Aspect | Requirement |
|--------|-------------|
| **Access** | Explicit authorization required |
| **Storage** | Encrypted at rest (AES-256/Fernet) |
| **Transmission** | TLS 1.2+ only |
| **Disposal** | Cryptographic erasure |
| **Labeling** | "Restricted" header |

**Examples:**
- Personal Identifiable Information (PII)
- Call recordings
- Transcripts with customer data
- Authentication credentials
- API keys and secrets

## 4. Data Categories

### 4.1 Personal Identifiable Information (PII)

| Data Element | Classification | Handling |
|--------------|----------------|----------|
| Full name | Restricted | Encrypted, logged access |
| Phone number | Restricted | Encrypted, masked in logs |
| Email address | Restricted | Encrypted |
| ID numbers | Restricted | Encrypted, no logs |
| Address | Restricted | Encrypted |

### 4.2 Financial Data

| Data Element | Classification | Handling |
|--------------|----------------|----------|
| Payment tokens | Restricted | Never logged, encrypted |
| Invoice amounts | Confidential | Access controlled |
| Transaction IDs | Confidential | Logged without amounts |

> **CRITICAL:** Raw credit card data (PAN, CVV, expiry) is NEVER stored. Only payment tokens from certified payment providers are stored.

### 4.3 Call Data

| Data Element | Classification | Handling |
|--------------|----------------|----------|
| Call recordings | Restricted | Encrypted storage, time-limited retention |
| Transcripts | Restricted | Encrypted, PII handling rules apply |
| Call metadata | Confidential | Access controlled |
| Call summaries | Confidential | PII removed or masked |

### 4.4 System Data

| Data Element | Classification | Handling |
|--------------|----------------|----------|
| Audit logs | Confidential | Encrypted, immutable storage |
| System logs | Internal | PII masked |
| Configuration | Confidential | Version controlled, encrypted secrets |
| API keys | Restricted | Secret management, never logged |

## 5. Data Handling Requirements

### 5.1 Encryption Requirements

| Data State | Requirement | Implementation |
|------------|-------------|----------------|
| At Rest | AES-256 or Fernet | Database encryption, file encryption |
| In Transit | TLS 1.2+ | HTTPS only, signed webhooks |
| In Processing | Memory protection | No sensitive data in debug output |

### 5.2 Masking Requirements

Sensitive data must be masked in logs:

| Data Type | Masking Rule | Example |
|-----------|--------------|---------|
| Phone number | Last 4 digits visible | `****5678` |
| Email | Domain visible | `***@domain.com` |
| Credit card | Never logged | `[REDACTED]` |
| API keys | First 4 chars only | `sk-4...***` |

**Code Reference:**
```python
# Example log masking implementation
def mask_phone(phone):
    if phone and len(phone) > 4:
        return '*' * (len(phone) - 4) + phone[-4:]
    return '[MASKED]'
```

### 5.3 Access Logging

All access to Restricted data must be logged:

| Log Element | Required |
|-------------|----------|
| Timestamp | ✅ Yes |
| User ID | ✅ Yes |
| Data accessed | ✅ Yes |
| Access type (read/write) | ✅ Yes |
| IP address | ✅ Yes |
| Result (success/fail) | ✅ Yes |

## 6. Retention Policy

### 6.1 Retention Periods

| Data Type | Retention | Justification |
|-----------|-----------|---------------|
| Call recordings | 90 days | Business requirement |
| Call transcripts | 90 days | Business requirement |
| Audit logs | 1 year | Compliance requirement |
| System logs | 30 days | Operational requirement |
| Customer data | Duration of contract + 30 days | Legal requirement |
| Backup data | 30 days rolling | Disaster recovery |

### 6.2 Disposal Procedures

| Classification | Disposal Method |
|----------------|-----------------|
| Public | Standard deletion |
| Internal | Standard deletion |
| Confidential | Secure deletion (file shredding) |
| Restricted | Cryptographic erasure |

## 7. Multi-Tenant Data Isolation

### 7.1 Tenant Isolation Requirements

| Requirement | Implementation |
|-------------|----------------|
| Data segregation | `business_id` on all tables |
| Query filtering | Automatic tenant context |
| Cross-tenant prevention | Authorization checks |
| Admin access | Audit logged |

**Code Reference:**
```python
# /server/auth.py - Tenant isolation
def get_current_tenant():
    """Ensure all queries are scoped to current tenant."""
    if hasattr(g, 'tenant') and g.tenant is not None:
        tenant_id = g.tenant.id
        return int(tenant_id)
    # ... tenant resolution logic
```

### 7.2 Data Access Flow

```
User Request → Authentication → Authorization (RBAC) → Tenant Context
     ↓
Database Query (WHERE business_id = :tenant_id)
     ↓
Response (tenant-scoped data only)
```

## 8. Third-Party Data Sharing

### 8.1 Data Sharing Requirements

| Before Sharing | Required |
|----------------|----------|
| Data Processing Agreement | ✅ Yes |
| Security assessment | ✅ Yes |
| Business justification | ✅ Yes |
| Customer consent (if applicable) | ✅ Yes |

### 8.2 Third-Party Data Flows

| Service | Data Shared | Classification | Controls |
|---------|-------------|----------------|----------|
| Twilio | Phone numbers, call audio | Restricted | DPA, encryption |
| OpenAI | Conversation text | Confidential | DPA, no persistent storage |
| WhatsApp | Phone numbers, messages | Restricted | DPA, encryption |

## 9. Data Subject Rights

### 9.1 GDPR Rights Support

| Right | Implementation |
|-------|----------------|
| Right to Access | Data export functionality |
| Right to Rectification | Data update API |
| Right to Erasure | Data deletion with verification |
| Right to Portability | JSON/CSV export |
| Right to Object | Processing opt-out mechanism |

### 9.2 Data Request Process

1. Verify requester identity
2. Document request
3. Process within 30 days
4. Provide data in portable format
5. Log completion

## 10. Labeling Requirements

### 10.1 Document Labels

All documents must include classification in header:

```markdown
| **Classification** | [Public/Internal/Confidential/Restricted] |
```

### 10.2 System Labels

| Location | Labeling Method |
|----------|-----------------|
| Database columns | Comments in schema |
| API responses | No sensitive data by default |
| Logs | Masking applied automatically |
| UI | Restricted data marked |

## 11. Training and Awareness

### 11.1 Training Requirements

| Role | Training Frequency |
|------|-------------------|
| All staff | Annual data handling training |
| Developers | Security coding practices |
| Administrators | Privileged data handling |
| New hires | Onboarding security training |

### 11.2 Awareness Topics

- Data classification levels
- Handling requirements per level
- Reporting suspected violations
- Data breach procedures

## 12. Compliance

### 12.1 Violations

Non-compliance with this policy may result in:
- Disciplinary action
- Access revocation
- Legal consequences

### 12.2 Reporting

Report data handling concerns to:
- ISMS Owner
- Direct manager
- Security team

## 13. Review and Updates

This policy shall be reviewed:
- Annually as part of management review
- When new data types are introduced
- When regulations change
- Following data incidents

---

**Document Control**

| Version | Date       | Author      | Changes                          |
|---------|------------|-------------|----------------------------------|
| 1.0     | 2026-01-17 | System      | Initial data classification policy |
