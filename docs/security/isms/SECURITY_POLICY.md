# Information Security Policy

## ProSaaS / AgentLocator - Master Security Policy

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-001                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This policy establishes the information security management framework for ProSaaS/AgentLocator, ensuring protection of business information, customer data, and system assets in accordance with ISO/IEC 27001:2022 requirements.

## 2. Scope

This policy applies to:
- All employees, contractors, and third-party personnel
- All information systems and data processing activities
- All business locations and remote work environments
- All data classifications: Public, Internal, Confidential, and Restricted

### Scope Limitations

**IMPORTANT:** The ISMS scope explicitly excludes storage or processing of raw payment card data (PAN, CVV, expiry). All payment processing is handled via tokenization through certified third-party payment providers (e.g., Stripe, Tranzila, Pelecard).

## 3. Policy Statement

ProSaaS/AgentLocator is committed to:

1. **Protecting** the confidentiality, integrity, and availability of all information assets
2. **Complying** with applicable legal, regulatory, and contractual requirements
3. **Managing** information security risks through a systematic risk management process
4. **Continually improving** the information security management system (ISMS)
5. **Providing** appropriate training and awareness to all personnel

## 4. Security Principles

### 4.1 Confidentiality
- Information is accessible only to authorized personnel
- Data classification determines access requirements
- Encryption at rest and in transit for sensitive data

### 4.2 Integrity
- Information is accurate, complete, and unaltered
- Change management processes protect system integrity
- Audit trails track all modifications

### 4.3 Availability
- Systems and data are available when needed
- Business continuity and disaster recovery plans maintained
- Service level agreements define availability requirements

## 5. Key Security Controls

| Control Area | Implementation |
|--------------|----------------|
| Access Control | RBAC with MFA for administrators |
| Encryption | TLS 1.2+ for transit, AES/Fernet for data at rest |
| Logging | Comprehensive audit logging with retention policy |
| Incident Response | Documented incident response procedures |
| Supplier Security | Vendor risk assessments and DPA agreements |
| Physical Security | Cloud-hosted with certified provider controls |

## 6. Roles and Responsibilities

### 6.1 ISMS Owner (CTO / System Owner)
- Overall accountability for information security
- Ensuring ISMS implementation and maintenance
- Reporting to management on ISMS performance

### 6.2 Security Operations
- Day-to-day security monitoring and response
- Security incident handling
- Access management and provisioning

### 6.3 All Personnel
- Compliance with security policies and procedures
- Reporting security incidents and concerns
- Protecting information assets in their custody

## 7. Evidence Requirements

For every control implemented, at least one form of evidence must exist:
- Log files demonstrating control operation
- Configuration files showing security settings
- Code references implementing security controls
- Screenshots or test results for verification
- Documented procedures and processes

## 8. Compliance

Non-compliance with this policy may result in:
- Disciplinary action for employees
- Contract termination for contractors
- Legal action where appropriate

## 9. Related Documents

- [ISMS Scope](ISMS_SCOPE.md)
- [Risk Assessment](RISK_ASSESSMENT.md)
- [Statement of Applicability](STATEMENT_OF_APPLICABILITY.md)
- [Incident Response](INCIDENT_RESPONSE.md)
- [Access Control Policy](ACCESS_CONTROL_POLICY.md)
- [Data Classification](DATA_CLASSIFICATION.md)
- [Backup and Recovery](BACKUP_AND_RECOVERY.md)
- [Supplier Security](SUPPLIER_SECURITY.md)

## 10. Review and Updates

This policy shall be reviewed:
- Annually as part of the management review process
- Upon significant changes to the organization or technology
- Following major security incidents
- When regulatory or legal requirements change

---

**Document Control**

| Version | Date       | Author      | Changes                  |
|---------|------------|-------------|--------------------------|
| 1.0     | 2026-01-17 | System      | Initial policy creation  |
