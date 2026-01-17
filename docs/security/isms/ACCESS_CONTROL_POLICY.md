# Access Control Policy

## ProSaaS / AgentLocator - Access Control and Identity Management

---

| **Document Information** |                                     |
|--------------------------|-------------------------------------|
| **Document ID**          | POL-ISMS-006                        |
| **Version**              | 1.0                                 |
| **Owner**                | CTO / System Owner                  |
| **Classification**       | Internal                            |
| **Effective Date**       | 2026-01-17                          |
| **Review Cycle**         | Quarterly / 90 days                 |
| **Next Review**          | 2026-04-17                          |
| **Approved By**          | Management                          |

---

## 1. Purpose

This policy establishes the access control requirements for ProSaaS/AgentLocator in accordance with ISO/IEC 27001:2022 (A.9 Access Control).

## 2. Scope

This policy applies to:
- All system users (employees, contractors, customers)
- All application access (web, API, administrative)
- All data access (customer data, system configuration)
- All environments (development, staging, production)

## 3. Access Control Principles

### 3.1 Core Principles

| Principle | Description |
|-----------|-------------|
| **Least Privilege** | Users receive minimum access required for their role |
| **Need to Know** | Access granted only when business need is demonstrated |
| **Separation of Duties** | Critical functions require multiple approvals |
| **Defense in Depth** | Multiple layers of access controls |

### 3.2 Multi-Tenancy Isolation

All data access is strictly isolated by tenant (business_id):
- No cross-tenant data access permitted
- Tenant context validated on every request
- System admin access audited separately

**Code Reference:**
```python
# /server/auth.py - get_current_tenant()
def get_current_tenant():
    """Get current tenant ID from Flask g context or session."""
    if hasattr(g, 'tenant') and g.tenant is not None:
        tenant_id = g.tenant.id if hasattr(g.tenant, 'id') else g.tenant
        return int(tenant_id) if tenant_id else None
    # ... additional checks
```

## 4. Role-Based Access Control (RBAC)

### 4.1 System Roles

| Role | Description | Access Level |
|------|-------------|--------------|
| `system_admin` | Global system administrator | Full access to all tenants |
| `owner` | Business owner | Full control of their business |
| `admin` | Business administrator | Limited business management |
| `agent` | Customer service agent | CRM and calls only |

### 4.2 Role Permissions Matrix

| Permission | system_admin | owner | admin | agent |
|------------|:------------:|:-----:|:-----:|:-----:|
| View all tenants | ✅ | ❌ | ❌ | ❌ |
| Manage users | ✅ | ✅ | ✅ | ❌ |
| Configure business settings | ✅ | ✅ | ✅ | ❌ |
| Access CRM | ✅ | ✅ | ✅ | ✅ |
| Make/receive calls | ✅ | ✅ | ✅ | ✅ |
| View call recordings | ✅ | ✅ | ✅ | ✅ |
| Manage billing | ✅ | ✅ | ❌ | ❌ |
| View audit logs | ✅ | ✅ | ❌ | ❌ |
| Impersonate users | ✅ | ❌ | ❌ | ❌ |

### 4.3 Role Implementation

**Code Reference:**
```python
# /server/authz.py
def roles_required(*roles):
    """Require specific roles for endpoint access."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return jsonify({"error":"unauthorized"}), 401
            if "role" not in user or user["role"] not in roles:
                return jsonify({"error":"forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco

def owner_or_admin_required(fn):
    """Require owner, admin, or system_admin role."""
    return roles_required('system_admin', 'owner', 'admin')(fn)
```

## 5. Authentication Requirements

### 5.1 Password Policy

| Requirement | Minimum |
|-------------|---------|
| Length | 8 characters |
| Uppercase letters | 1 |
| Lowercase letters | 1 |
| Digits | 1 |
| Special characters | 1 |

**Code Reference:**
```python
# /server/security_audit.py
def password_strength_check(password):
    """Enterprise password policy validation."""
    if not password or len(password) < 8:
        return False, "סיסמה חייבת להכיל לפחות 8 תווים"
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    if not (has_upper and has_lower and has_digit and has_special):
        return False, "סיסמה חייבת להכיל אותיות גדולות, קטנות, ספרה ותו מיוחד"
    return True, "סיסמה תקינה"
```

### 5.2 Multi-Factor Authentication (MFA)

| Role | MFA Required |
|------|:------------:|
| system_admin | ✅ Mandatory |
| owner | ✅ Recommended |
| admin | ✅ Recommended |
| agent | Optional |

### 5.3 Session Management

| Setting | Value |
|---------|-------|
| Session timeout | 8 hours |
| Session rotation | On privilege change |
| Secure cookies | Yes (HTTPS only) |
| HttpOnly cookies | Yes |

**Code Reference:**
```python
# /server/security_audit.py - SessionSecurity
class SessionSecurity:
    @staticmethod
    def rotate_session():
        """Rotate session ID while preserving user data."""
        # Preserves user data while generating new session ID
        
    @staticmethod
    def is_session_valid():
        """Check if current session is valid."""
        last_activity = session.get('_last_activity')
        if last_activity:
            last_time = datetime.fromisoformat(last_activity)
            if datetime.now() - last_time > timedelta(hours=8):
                return False
        return True
```

## 6. Access Provisioning

### 6.1 Access Request Process

1. **Request:** User submits access request with business justification
2. **Approval:** Manager/owner approves request
3. **Verification:** Security verifies appropriateness
4. **Provisioning:** Access granted and documented
5. **Notification:** User notified of access

### 6.2 Access Review Schedule

| Review Type | Frequency | Responsible |
|-------------|-----------|-------------|
| User access review | Every 90 days | Business Owner |
| Privileged access review | Every 30 days | ISMS Owner |
| Service account review | Every 90 days | Technical Lead |
| Third-party access review | Every 90 days | ISMS Owner |

### 6.3 Access Revocation

**Immediate Revocation Required:**
- Employment termination
- Role change
- Security incident
- Extended leave

**Revocation Checklist:**
```
□ Disable user account
□ Revoke active sessions
□ Rotate shared credentials (if any)
□ Remove from groups/roles
□ Revoke API keys
□ Document revocation
□ Verify access removed
```

## 7. Privileged Access Management

### 7.1 Privileged Accounts

| Account Type | Controls |
|--------------|----------|
| system_admin | MFA, audit logging, access review |
| Database admin | Separate credentials, audit logging |
| CI/CD service | Limited scope, secret rotation |
| API service accounts | Token rotation, scope limitation |

### 7.2 Privileged Access Rules

1. No shared privileged accounts
2. Privileged access limited to specific tasks
3. All privileged actions logged
4. Regular review of privileged access
5. Time-limited elevated access when possible

## 8. API Access Control

### 8.1 API Authentication

| Method | Use Case |
|--------|----------|
| Session Cookie | Web application access |
| X-Internal-Secret | Internal service communication |
| Webhook Secret | External webhook validation |

### 8.2 Webhook Security

All external webhooks must be signed:

**Code Reference:**
```python
# /server/twilio_security.py
def require_twilio_signature(f):
    """Decorator to validate Twilio webhook signatures."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get('X-Twilio-Signature')
        if not signature:
            abort(403)
        # Validate HMAC-SHA1 signature
```

## 9. Third-Party Access

### 9.1 Service Integrations

| Service | Access Type | Controls |
|---------|-------------|----------|
| Twilio | API keys | Secret management, audit |
| OpenAI | API keys | Secret management, rate limiting |
| WhatsApp | API integration | Token management, audit |

### 9.2 Third-Party Access Requirements

1. Documented business need
2. Data processing agreement
3. Security assessment
4. Minimum necessary access
5. Regular access review

## 10. Logging and Monitoring

### 10.1 Access Events Logged

| Event | Logged Details |
|-------|----------------|
| Login success | User, IP, timestamp |
| Login failure | User, IP, timestamp, reason |
| Access denied | User, resource, reason |
| Privilege change | User, old/new role |
| Session events | Creation, rotation, termination |
| Impersonation | Admin user, target user |

### 10.2 Audit Trail

**Code Reference:**
```python
# /server/security_audit.py - AuditLogger
def log_action(self, action_type, resource, resource_id=None, details=None):
    """Log audit action with full context."""
    audit_entry = {
        'timestamp': datetime.now().isoformat(),
        'action_type': action_type,
        'resource': resource,
        'user_id': user.get('id'),
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR'),
        'user_agent': request.headers.get('User-Agent'),
        # ...
    }
```

## 11. Compliance Requirements

### 11.1 ISO 27001 Controls

| Control | Implementation |
|---------|----------------|
| A.9.1.1 | Access control policy (this document) |
| A.9.1.2 | Network access (TLS, firewall) |
| A.9.2.1 | User registration (provisioning process) |
| A.9.2.2 | Access provisioning (RBAC) |
| A.9.2.3 | Privileged access (admin controls) |
| A.9.2.5 | Access rights review (90-day review) |
| A.9.2.6 | Access revocation (immediate deactivation) |
| A.9.4.1 | Information access restriction (tenant isolation) |
| A.9.4.2 | Secure log-on (password policy, MFA) |
| A.9.4.3 | Password management (strength checks) |

## 12. Review and Updates

This policy shall be reviewed:
- Every 90 days (quarterly)
- Following security incidents
- When roles or systems change significantly

---

**Document Control**

| Version | Date       | Author      | Changes                       |
|---------|------------|-------------|-------------------------------|
| 1.0     | 2026-01-17 | System      | Initial access control policy |
