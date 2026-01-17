# Incident Response Policy

## ProSaaS / AgentLocator - Information Security Incident Response

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-005                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This document establishes the procedures for identifying, responding to, and recovering from information security incidents in accordance with ISO/IEC 27001:2022 requirements.

## 2. Scope

This policy applies to all security incidents affecting:
- ProSaaS/AgentLocator systems and data
- Customer data and privacy
- System availability and integrity
- Third-party service integrations

## 3. Definitions

| Term | Definition |
|------|------------|
| **Security Event** | An occurrence indicating a possible breach of security policy |
| **Security Incident** | A confirmed security event with potential to cause harm |
| **Data Breach** | Unauthorized access to or disclosure of personal data |
| **Severity Level** | Classification of incident impact (Critical/High/Medium/Low) |

## 4. Severity Levels

| Level | Description | Example | Response Time |
|-------|-------------|---------|---------------|
| **Critical** | Major data breach, complete service outage | Customer data exposed | < 1 hour |
| **High** | Significant security violation, partial outage | Unauthorized admin access | < 4 hours |
| **Medium** | Limited impact, isolated incident | Single user compromise | < 24 hours |
| **Low** | Minimal impact, policy violation | Failed login attempts | < 72 hours |

## 5. Incident Response Team

### 5.1 Team Structure

| Role | Responsibilities |
|------|------------------|
| **Incident Commander** | Overall incident management, communications |
| **Technical Lead** | Technical investigation and remediation |
| **Operations** | System monitoring, log analysis |
| **Communications** | Customer and stakeholder communications |
| **Legal/Compliance** | Regulatory notification, legal matters |

### 5.2 Contact Information

| Role | Primary Contact | Backup Contact |
|------|-----------------|----------------|
| Incident Commander | ISMS Owner/CTO | Management |
| Technical Lead | Senior Engineer | Engineering Team |
| Operations | On-call Engineer | DevOps Team |

## 6. Incident Response Phases

### 6.1 Phase 1: Detection and Identification

**Objectives:**
- Detect security events through monitoring
- Determine if event is a security incident
- Classify incident severity

**Activities:**
1. Monitor security logs and alerts
2. Receive and analyze incident reports
3. Verify the incident is genuine
4. Classify severity level
5. Log incident in security events table

**Code Reference:**
```python
# /server/security_audit.py
audit_logger.log_action(
    action_type='SECURITY_EVENT',
    resource='system',
    details={
        'event_type': 'detected_incident',
        'severity': 'HIGH',
        'description': 'Incident description'
    }
)
```

### 6.2 Phase 2: Containment

**Objectives:**
- Limit incident impact
- Prevent further damage
- Preserve evidence

**Short-term Containment:**
1. Isolate affected systems
2. Block malicious IP addresses
3. Disable compromised accounts
4. Revoke compromised tokens/sessions

**Long-term Containment:**
1. Apply temporary fixes
2. Implement additional monitoring
3. Prepare for eradication

### 6.3 Phase 3: Eradication

**Objectives:**
- Remove threat from environment
- Identify and address root cause

**Activities:**
1. Remove malware/unauthorized access
2. Patch vulnerabilities
3. Reset compromised credentials
4. Review and harden configurations

### 6.4 Phase 4: Recovery

**Objectives:**
- Restore normal operations
- Verify system integrity
- Monitor for recurrence

**Activities:**
1. Restore from clean backups if needed
2. Verify system functionality
3. Monitor for re-infection
4. Gradually restore access
5. Document all recovery actions

### 6.5 Phase 5: Lessons Learned

**Objectives:**
- Document incident timeline
- Identify improvements
- Update policies and procedures

**Activities:**
1. Conduct post-incident review
2. Document lessons learned
3. Update security controls
4. Train staff on findings
5. Update incident response procedures

## 7. Incident Response Procedures

### 7.1 Initial Response Checklist

```
□ Confirm incident is real (not false positive)
□ Classify severity level
□ Notify Incident Commander
□ Log incident in security events
□ Begin documentation
□ Preserve evidence (logs, screenshots)
□ Initiate containment measures
□ Assess scope and impact
```

### 7.2 Data Breach Response

**Immediate Actions (Within 1 Hour):**
1. Contain the breach
2. Notify Incident Commander
3. Preserve all evidence
4. Document known facts

**Within 24 Hours:**
1. Assess scope of data exposure
2. Identify affected individuals
3. Determine notification requirements
4. Prepare customer communications

**Within 72 Hours (GDPR Requirement):**
1. Notify supervisory authority (if required)
2. Notify affected individuals (if required)
3. Document all actions taken

### 7.3 Credential Compromise

**Immediate Actions:**
1. Revoke compromised credentials
2. Force password reset
3. Terminate active sessions
4. Review access logs

**Evidence Reference:**
```python
# /server/security_audit.py - Session rotation
SessionSecurity.rotate_session()
```

### 7.4 Service Outage

**Immediate Actions:**
1. Assess scope of outage
2. Notify affected customers
3. Activate disaster recovery if needed
4. Monitor restoration progress

## 8. Notification Requirements

### 8.1 Internal Notifications

| Severity | Notify | Timeframe |
|----------|--------|-----------|
| Critical | Management, All Team | Immediate |
| High | Management, Technical Team | Within 1 hour |
| Medium | Technical Team | Within 4 hours |
| Low | Security Team | Within 24 hours |

### 8.2 External Notifications

| Situation | Notify | Timeframe |
|-----------|--------|-----------|
| Data Breach (GDPR) | Supervisory Authority | Within 72 hours |
| Customer Data Breach | Affected Customers | Without undue delay |
| Third-party Incident | Affected Vendor | Immediate |

### 8.3 Authority Contacts

| Authority | Region | When to Contact |
|-----------|--------|-----------------|
| Data Protection Authority | Israel | Data breach affecting residents |
| EU DPA | EU | GDPR data breach |
| Law Enforcement | Any | Criminal activity |

## 9. Security Events Database

### 9.1 Database Schema

All security incidents must be logged in the security_events table:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier |
| `event_type` | Type of security event |
| `severity` | Critical/High/Medium/Low |
| `description` | Event description |
| `impact` | Business impact assessment |
| `response` | Actions taken |
| `lessons_learned` | Post-incident findings |
| `status` | Open/In Progress/Resolved |
| `created_at` | Event detection time |
| `resolved_at` | Resolution time |
| `reporter_id` | Who reported the event |
| `assigned_to` | Who is handling the event |

### 9.2 Event Categories

- Authentication failures
- Unauthorized access attempts
- Data access violations
- System vulnerabilities
- Third-party service issues
- Configuration changes
- Policy violations

## 10. Evidence Collection

### 10.1 Evidence Types

| Type | Collection Method | Retention |
|------|-------------------|-----------|
| System Logs | Automated logging | 90 days minimum |
| Audit Logs | `/logs/audit.log` | 1 year |
| Screenshots | Manual capture | As needed |
| Network Traffic | Packet capture | 30 days |
| Configuration | Backup/snapshot | Per backup policy |

### 10.2 Evidence Handling

1. **Preserve:** Secure original evidence
2. **Copy:** Create forensic copies
3. **Document:** Record chain of custody
4. **Store:** Secure storage with access controls
5. **Retain:** Follow retention policy

## 11. Communication Templates

### 11.1 Internal Incident Alert

```
SECURITY INCIDENT ALERT
-----------------------
Date/Time: [DateTime]
Severity: [Critical/High/Medium/Low]
Type: [Incident Type]
Description: [Brief description]
Impact: [Known impact]
Status: [Current status]
Actions: [Actions being taken]
Contact: [Incident Commander]
```

### 11.2 Customer Notification

```
Subject: Important Security Notice from ProSaaS

Dear [Customer],

We are writing to inform you of a security incident that may 
have affected your account.

What Happened: [Brief description]
What We've Done: [Remediation steps]
What You Should Do: [Customer actions]
Contact: [Support contact]

We sincerely apologize for any inconvenience.

[Signature]
```

## 12. Metrics and Reporting

### 12.1 Key Metrics

| Metric | Target |
|--------|--------|
| Mean Time to Detect (MTTD) | < 24 hours |
| Mean Time to Respond (MTTR) | Per severity SLA |
| Mean Time to Resolve | < 72 hours (Critical) |
| Incidents per Month | Trend monitoring |

### 12.2 Monthly Reporting

- Number of incidents by severity
- Response time compliance
- Root cause analysis summary
- Lessons learned summary
- Control improvements implemented

## 13. Review and Testing

### 13.1 Review Schedule

- **Quarterly:** Review incident logs and metrics
- **Annually:** Full incident response plan review
- **Post-incident:** Review after each significant incident

### 13.2 Testing

- Annual tabletop exercises
- Periodic response drills
- Post-exercise improvement implementation

---

**Document Control**

| Version | Date       | Author      | Changes                          |
|---------|------------|-------------|----------------------------------|
| 1.0     | 2026-01-17 | System      | Initial incident response policy |
