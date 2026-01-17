# Statement of Applicability (SoA)

## ProSaaS / AgentLocator - ISO/IEC 27001:2022 Annex A Control Mapping

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-004                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This Statement of Applicability (SoA) documents the selection and implementation status of ISO/IEC 27001:2022 Annex A controls for ProSaaS/AgentLocator. Each control is mapped to specific system implementations with evidence references.

## 2. Control Selection Criteria

Controls are selected based on:
- Risk assessment results
- Legal and regulatory requirements
- Contractual obligations
- Business requirements

## 3. Annex A Control Implementation

### A.5 Organizational Controls

| Control | Title | Applicable | Implementation | Evidence |
|---------|-------|------------|----------------|----------|
| A.5.1 | Policies for information security | ✅ Yes | Security policy documented | `/docs/security/isms/SECURITY_POLICY.md` |
| A.5.2 | Information security roles | ✅ Yes | ISMS Owner defined, roles documented | `/docs/security/isms/ACCESS_CONTROL_POLICY.md` |
| A.5.3 | Segregation of duties | ✅ Yes | Role-based access control (RBAC) | `/server/authz.py` - `roles_required()` |
| A.5.4 | Management responsibilities | ✅ Yes | Management review process defined | Security Policy Section 6 |
| A.5.5 | Contact with authorities | ✅ Yes | Incident response includes authority contacts | `/docs/security/isms/INCIDENT_RESPONSE.md` |
| A.5.6 | Contact with special interest groups | ⚪ N/A | Not applicable for current scope | - |
| A.5.7 | Threat intelligence | ✅ Yes | Dependency scanning, vulnerability monitoring | CI/CD security scanning |
| A.5.8 | Information security in project management | ✅ Yes | Security review in development process | Code review requirements |
| A.5.9 | Inventory of information | ✅ Yes | Asset inventory maintained | Data classification document |
| A.5.10 | Acceptable use of information | ✅ Yes | Usage policies documented | Security Policy |
| A.5.11 | Return of assets | ✅ Yes | Offboarding procedures | Access Control Policy |
| A.5.12 | Classification of information | ✅ Yes | 4-tier classification scheme | `/docs/security/isms/DATA_CLASSIFICATION.md` |
| A.5.13 | Labelling of information | ✅ Yes | Document classification headers | All ISMS documents |
| A.5.14 | Information transfer | ✅ Yes | TLS for all transfers | `/server/twilio_security.py`, config |
| A.5.15 | Access control | ✅ Yes | RBAC with MFA for admin | `/server/authz.py` |
| A.5.16 | Identity management | ✅ Yes | User identity management | `/server/auth_api.py` |
| A.5.17 | Authentication information | ✅ Yes | Strong password policy | `/server/security_audit.py` - `password_strength_check()` |
| A.5.18 | Access rights | ✅ Yes | Role-based access rights | `/server/authz.py` |
| A.5.19 | Information security in supplier relationships | ✅ Yes | Vendor security documented | `/docs/security/isms/SUPPLIER_SECURITY.md` |
| A.5.20 | Addressing security in supplier agreements | ✅ Yes | DPA requirements documented | Supplier Security |
| A.5.21 | Managing information security in the ICT supply chain | ✅ Yes | Third-party service monitoring | Supplier Security |
| A.5.22 | Monitoring, review and change management of supplier services | ✅ Yes | Supplier review process | Supplier Security |
| A.5.23 | Information security for use of cloud services | ✅ Yes | Cloud security controls | Infrastructure documentation |
| A.5.24 | Information security incident management planning | ✅ Yes | Incident response documented | `/docs/security/isms/INCIDENT_RESPONSE.md` |
| A.5.25 | Assessment and decision on information security events | ✅ Yes | Security events table | `/server/security_audit.py` |
| A.5.26 | Response to information security incidents | ✅ Yes | Response procedures | Incident Response |
| A.5.27 | Learning from information security incidents | ✅ Yes | Lessons learned process | Incident Response |
| A.5.28 | Collection of evidence | ✅ Yes | Audit logging | `/server/security_audit.py` - `AuditLogger` |
| A.5.29 | Information security during disruption | ✅ Yes | Backup and recovery | `/docs/security/isms/BACKUP_AND_RECOVERY.md` |
| A.5.30 | ICT readiness for business continuity | ✅ Yes | Disaster recovery documented | Backup and Recovery |
| A.5.31 | Legal, statutory, regulatory and contractual requirements | ✅ Yes | Compliance documented | ISMS Scope |
| A.5.32 | Intellectual property rights | ✅ Yes | License management | Development practices |
| A.5.33 | Protection of records | ✅ Yes | Record retention policy | Data Classification |
| A.5.34 | Privacy and protection of PII | ✅ Yes | Privacy controls | Data Classification, log masking |
| A.5.35 | Independent review of information security | ✅ Yes | Annual audit readiness | ISMS Review process |
| A.5.36 | Compliance with policies and standards | ✅ Yes | Regular compliance checks | Management review |
| A.5.37 | Documented operating procedures | ✅ Yes | Operations documented | System documentation |

### A.6 People Controls

| Control | Title | Applicable | Implementation | Evidence |
|---------|-------|------------|----------------|----------|
| A.6.1 | Screening | ✅ Yes | Background checks for sensitive roles | HR procedures |
| A.6.2 | Terms and conditions of employment | ✅ Yes | Security responsibilities in contracts | Employment agreements |
| A.6.3 | Information security awareness | ✅ Yes | Security training requirements | Security Policy |
| A.6.4 | Disciplinary process | ✅ Yes | Non-compliance consequences | Security Policy Section 8 |
| A.6.5 | Responsibilities after termination | ✅ Yes | Access revocation process | Access Control Policy |
| A.6.6 | Confidentiality or NDA | ✅ Yes | NDA requirements | Contractual requirements |
| A.6.7 | Remote working | ✅ Yes | Secure remote access | Access Control Policy |
| A.6.8 | Information security event reporting | ✅ Yes | Incident reporting process | Incident Response |

### A.7 Physical Controls

| Control | Title | Applicable | Implementation | Evidence |
|---------|-------|------------|----------------|----------|
| A.7.1 | Physical security perimeters | ⚪ N/A | Cloud-hosted, provider-managed | ISMS Scope exclusion |
| A.7.2 | Physical entry | ⚪ N/A | Cloud-hosted, provider-managed | ISMS Scope exclusion |
| A.7.3 | Securing offices, rooms and facilities | ⚪ N/A | Cloud-hosted, provider-managed | ISMS Scope exclusion |
| A.7.4 | Physical security monitoring | ⚪ N/A | Cloud-hosted, provider-managed | ISMS Scope exclusion |
| A.7.5 | Protecting against physical and environmental threats | ⚪ N/A | Cloud-hosted, provider-managed | ISMS Scope exclusion |
| A.7.6 | Working in secure areas | ⚪ N/A | Remote work environment | - |
| A.7.7 | Clear desk and clear screen | ✅ Yes | Policy documented | Security Policy |
| A.7.8 | Equipment siting and protection | ⚪ N/A | Cloud-hosted | - |
| A.7.9 | Security of assets off-premises | ✅ Yes | Remote work guidelines | Access Control Policy |
| A.7.10 | Storage media | ✅ Yes | Data encryption policy | Data Classification |
| A.7.11 | Supporting utilities | ⚪ N/A | Cloud provider-managed | - |
| A.7.12 | Cabling security | ⚪ N/A | Cloud provider-managed | - |
| A.7.13 | Equipment maintenance | ⚪ N/A | Cloud provider-managed | - |
| A.7.14 | Secure disposal or re-use of equipment | ⚪ N/A | No physical equipment | - |

### A.8 Technological Controls

| Control | Title | Applicable | Implementation | Evidence |
|---------|-------|------------|----------------|----------|
| A.8.1 | User endpoint devices | ✅ Yes | Browser-based access | Access Control Policy |
| A.8.2 | Privileged access rights | ✅ Yes | Admin role with MFA | `/server/authz.py` - `system_admin_required()` |
| A.8.3 | Information access restriction | ✅ Yes | Multi-tenant isolation | `/server/auth.py` - `get_current_tenant()` |
| A.8.4 | Access to source code | ✅ Yes | Repository access controls | Git access management |
| A.8.5 | Secure authentication | ✅ Yes | Strong password policy, session management | `/server/security_audit.py` |
| A.8.6 | Capacity management | ✅ Yes | Cloud auto-scaling | Infrastructure config |
| A.8.7 | Protection against malware | ✅ Yes | Dependency scanning | CI/CD pipeline |
| A.8.8 | Management of technical vulnerabilities | ✅ Yes | Vulnerability scanning | gitleaks, dependency checks |
| A.8.9 | Configuration management | ✅ Yes | Infrastructure as code | Docker configurations |
| A.8.10 | Information deletion | ✅ Yes | Data retention policy | Data Classification |
| A.8.11 | Data masking | ✅ Yes | PII masking in logs | Log configuration |
| A.8.12 | Data leakage prevention | ✅ Yes | Access controls, encryption | Multiple controls |
| A.8.13 | Information backup | ✅ Yes | Backup procedures | `/docs/security/isms/BACKUP_AND_RECOVERY.md` |
| A.8.14 | Redundancy of information processing facilities | ✅ Yes | Cloud redundancy | Infrastructure config |
| A.8.15 | Logging | ✅ Yes | Comprehensive audit logging | `/server/security_audit.py` - `AuditLogger` |
| A.8.16 | Monitoring activities | ✅ Yes | System monitoring | Health checks, logging |
| A.8.17 | Clock synchronization | ✅ Yes | NTP via cloud | Infrastructure |
| A.8.18 | Use of privileged utility programs | ✅ Yes | Administrative controls | Access management |
| A.8.19 | Installation of software on operational systems | ✅ Yes | Controlled deployment | CI/CD pipeline |
| A.8.20 | Networks security | ✅ Yes | TLS, secure endpoints | `/server/twilio_security.py` |
| A.8.21 | Security of network services | ✅ Yes | HTTPS only, signed webhooks | Security implementations |
| A.8.22 | Segregation of networks | ✅ Yes | Environment separation | Dev/Prod separation |
| A.8.23 | Web filtering | ⚪ N/A | SaaS application | - |
| A.8.24 | Use of cryptography | ✅ Yes | TLS 1.2+, AES encryption | Data Classification |
| A.8.25 | Secure development life cycle | ✅ Yes | Code review, security scanning | Development process |
| A.8.26 | Application security requirements | ✅ Yes | Security requirements documented | Security Policy |
| A.8.27 | Secure system architecture and engineering | ✅ Yes | Security architecture | System design |
| A.8.28 | Secure coding | ✅ Yes | ORM, parameterized queries | Code standards |
| A.8.29 | Security testing in development and acceptance | ✅ Yes | Security tests | Test suite |
| A.8.30 | Outsourced development | ⚪ N/A | Internal development | - |
| A.8.31 | Separation of development, test and production environments | ✅ Yes | Environment separation | Infrastructure |
| A.8.32 | Change management | ✅ Yes | Git-based change control | CI/CD pipeline |
| A.8.33 | Test information | ✅ Yes | Test data management | Development practices |
| A.8.34 | Protection of information systems during audit testing | ✅ Yes | Audit procedures | Audit readiness |

## 4. Controls Summary

### 4.1 Statistics

| Category | Total | Applicable | Implemented | N/A |
|----------|-------|------------|-------------|-----|
| A.5 Organizational | 37 | 36 | 36 | 1 |
| A.6 People | 8 | 8 | 8 | 0 |
| A.7 Physical | 14 | 3 | 3 | 11 |
| A.8 Technological | 34 | 32 | 32 | 2 |
| **Total** | **93** | **79** | **79** | **14** |

### 4.2 Non-Applicable Controls Justification

Controls marked as N/A are excluded because:
- Physical controls (A.7.1-A.7.6, A.7.8, A.7.11-A.7.14): Cloud-hosted infrastructure, physical security managed by cloud provider
- A.5.6: No relevant special interest groups identified
- A.8.23: Web filtering not applicable to SaaS application
- A.8.30: No outsourced development activities

## 5. Evidence Repository

All evidence for control implementation is maintained in:

| Evidence Type | Location | Description |
|---------------|----------|-------------|
| Policy Documents | `/docs/security/isms/` | ISMS policy documentation |
| Code Evidence | `/server/` | Security implementations in code |
| Configuration | Docker/Infrastructure | System configuration files |
| Logs | Audit logs directory | Security event logs |
| Test Results | CI/CD pipeline | Security scan results |

## 6. Review and Updates

This Statement of Applicability shall be reviewed:
- Annually as part of management review
- When significant changes occur to the control environment
- When new ISO 27001 requirements are released
- Following security incidents that reveal control gaps

---

**Document Control**

| Version | Date       | Author      | Changes                         |
|---------|------------|-------------|---------------------------------|
| 1.0     | 2026-01-17 | System      | Initial SoA creation            |
