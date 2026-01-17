# ISMS Scope Definition

## ProSaaS / AgentLocator - Information Security Management System Scope

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-002                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Annual (or upon significant change) |
| **Next Review**          | 2027-01-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This document defines the scope and boundaries of the Information Security Management System (ISMS) for ProSaaS/AgentLocator in accordance with ISO/IEC 27001:2022 requirements.

## 2. Organization Context

### 2.1 About ProSaaS/AgentLocator

ProSaaS/AgentLocator is a multi-tenant SaaS platform providing:
- AI-powered call center and CRM functionality
- WhatsApp business messaging integration
- Appointment scheduling and management
- Customer relationship management (CRM)
- Voice communications via Twilio integration
- Business intelligence and analytics

### 2.2 Business Environment

- **Operating Model:** Cloud-based SaaS (Software as a Service)
- **Target Market:** Small to medium businesses (SMBs)
- **Primary Regions:** Israel and international markets
- **Service Availability:** 24/7 with defined SLAs

## 3. ISMS Scope Statement

The ISMS scope covers the following:

### 3.1 Included in Scope

| Category | Description |
|----------|-------------|
| **Applications** | ProSaaS platform including frontend, backend APIs, and databases |
| **Infrastructure** | Cloud hosting environment, containers, and networking |
| **Data** | Customer data, business data, call recordings, and system logs |
| **Services** | Voice calls, WhatsApp messaging, email, and webhook integrations |
| **Personnel** | All employees and contractors with system access |
| **Processes** | Development, deployment, operations, and support |
| **Third-party Services** | Twilio, OpenAI, WhatsApp, and hosting providers |

### 3.2 Explicitly Excluded from Scope

> **CRITICAL LIMITATION:**  
> The ISMS scope explicitly excludes storage or processing of raw payment card data (PAN, CVV, expiry date, or full magnetic stripe data).

| Exclusion | Justification |
|-----------|---------------|
| **Raw Credit Card Storage** | All payment processing uses tokenization via certified third-party providers |
| **PCI DSS Certification** | Not applicable as no cardholder data is stored or processed |
| **Physical Data Centers** | Cloud-hosted environment; physical security managed by cloud provider |
| **End-user Devices** | Customer/user devices are outside organizational control |

## 4. Interfaces and Dependencies

### 4.1 External Service Providers

| Provider | Service | Data Flow |
|----------|---------|-----------|
| **Twilio** | Voice calls and SMS | Call metadata, recordings, phone numbers |
| **OpenAI** | AI/LLM processing | Conversation transcripts, prompts |
| **WhatsApp/Meta** | Business messaging | Messages, media, phone numbers |
| **Cloud Hosting** | Infrastructure | All application data |

### 4.2 Customer Interfaces

- Web application (HTTPS)
- REST APIs (authenticated, HTTPS)
- WebSocket connections (secure)
- Webhook endpoints (signed, authenticated)

## 5. Regulatory and Compliance Requirements

### 5.1 Applicable Regulations

| Regulation | Applicability |
|------------|---------------|
| **ISO 27001:2022** | Full compliance targeted |
| **GDPR** | Applicable for EU customers |
| **Israeli Privacy Law** | Applicable for Israeli customers |
| **PCI DSS** | **Not applicable** - no cardholder data stored |

### 5.2 Contractual Requirements

- Customer Data Processing Agreements (DPAs)
- Service Level Agreements (SLAs)
- Non-disclosure Agreements (NDAs)
- Supplier agreements with security terms

## 6. Organizational Units in Scope

| Unit | Responsibility |
|------|----------------|
| **Engineering** | Development, security implementation |
| **Operations** | System administration, monitoring |
| **Support** | Customer support, incident handling |
| **Management** | ISMS oversight, resource allocation |

## 7. Assets in Scope

### 7.1 Information Assets

- Customer personal data (PII)
- Business configuration and settings
- Call recordings and transcripts
- AI prompts and model configurations
- System logs and audit trails

### 7.2 Technology Assets

- Application source code
- Databases (PostgreSQL)
- API endpoints and services
- Container images and deployments
- Encryption keys and certificates

### 7.3 Supporting Assets

- Documentation and procedures
- Development tools and environments
- Monitoring and alerting systems
- Backup and recovery systems

## 8. Scope Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                         ISMS SCOPE                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Frontend   │  │   Backend    │  │   Database   │          │
│  │   (React)    │  │  (Python)    │  │ (PostgreSQL) │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   WhatsApp   │  │    Twilio    │  │    OpenAI    │          │
│  │  Integration │  │  Integration │  │  Integration │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Security & Audit Systems                   │   │
│  │  (Logging, Access Control, Encryption, Monitoring)       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                     OUT OF SCOPE                                │
│  ❌ Raw credit card storage    ❌ Physical data centers         │
│  ❌ End-user devices           ❌ PCI DSS scope                  │
└─────────────────────────────────────────────────────────────────┘
```

## 9. Review and Maintenance

This scope document shall be reviewed:
- Annually as part of management review
- When new services or systems are introduced
- When significant organizational changes occur
- When new regulatory requirements apply

---

**Document Control**

| Version | Date       | Author      | Changes                    |
|---------|------------|-------------|----------------------------|
| 1.0     | 2026-01-17 | System      | Initial scope definition   |
