# Security Guidelines

This document outlines security best practices for ProSaaS.

## Secrets Management

### Environment Variables

✅ **DO:**
- Store all secrets in `.env` files (never committed)
- Use strong random keys (64+ characters)
- Rotate credentials regularly
- Use different keys for dev/staging/prod
- Use secret management services (AWS Secrets Manager, Railway Variables, etc.)

❌ **DON'T:**
- Commit secrets to version control
- Hardcode API keys in source code
- Share production credentials
- Reuse keys across environments
- Store secrets in client-side code

### Key Generation

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate encryption key (for Gmail)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate webhook secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Application Security

### Authentication

- **JWT Tokens**: Used for API authentication
  - Tokens expire after configurable time
  - Refresh tokens for long-lived sessions
  - Token validation on every request

- **Session Management**: Flask-Login with secure cookies
  - HTTPOnly cookies (prevent XSS)
  - Secure flag in production (HTTPS only)
  - SameSite=Lax (CSRF protection)

- **Password Hashing**: Bcrypt with salt
  - Minimum 12-character passwords
  - Password strength validation
  - Rate limiting on login attempts

### CSRF Protection

- Flask-SeaSurf enabled for all state-changing operations
- CSRF tokens required for POST/PUT/DELETE
- Token validation on server side
- Exempt only explicitly safe endpoints

### Rate Limiting

- Flask-Limiter protects against abuse
- Default: 1000 requests per hour per IP
- Custom limits for sensitive endpoints:
  - Login: 5 attempts per minute
  - API calls: 100 per minute
  - File uploads: 10 per minute

### Input Validation

- All user input sanitized and validated
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via HTML escaping
- File upload validation (type, size, content)
- URL validation for webhooks and callbacks

### SQL Injection Prevention

✅ **DO:**
```python
# Use SQLAlchemy ORM or parameterized queries
user = User.query.filter_by(email=email).first()
results = db.session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

❌ **DON'T:**
```python
# Never use string formatting for queries
query = f"SELECT * FROM users WHERE email = '{email}'"  # VULNERABLE
```

### XSS Prevention

- All HTML output escaped by default (Jinja2, React)
- User-generated content sanitized with Bleach
- Content Security Policy headers set
- No `dangerouslySetInnerHTML` without sanitization

## API Security

### Webhook Validation

- **Twilio**: Validate X-Twilio-Signature header
- **WhatsApp/Baileys**: Validate webhook secret
- **N8N**: Validate webhook tokens
- Always verify origin before processing

```python
# Example: Twilio signature validation
from server.twilio_security import validate_twilio_request

@app.route('/api/voice/incoming', methods=['POST'])
def incoming_call():
    if not validate_twilio_request(request):
        abort(403)
    # Process call...
```

### CORS Configuration

- Restrictive CORS policy in production
- Only allow trusted origins
- Credentials allowed only for same-origin
- No wildcard origins in production

```python
# Production CORS (app_factory.py)
CORS(app, origins=[
    "https://your-domain.com",
    "https://www.your-domain.com"
], supports_credentials=True)
```

### API Key Management

- API keys stored hashed in database
- Keys prefixed with environment (prod_, dev_)
- Keys rotatable via admin panel
- Audit log for key usage

## Data Security

### Database

- **Encryption at Rest**: Use managed database encryption
- **Encryption in Transit**: Require SSL/TLS connections
- **Connection Pooling**: Use pooler for API, direct for migrations
- **Backups**: Automated daily backups with encryption
- **Access Control**: Least privilege database users

```bash
# PostgreSQL SSL connection
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

### Sensitive Data

- **PII**: Minimal collection, encrypt if stored
- **Phone Numbers**: Stored in normalized format
- **Email Addresses**: Validated before storage
- **API Keys**: Hashed with bcrypt
- **Tokens**: Encrypted with Fernet
- **Recordings**: Stored with access controls

### File Storage

- User uploads validated (type, size, content)
- Files stored outside web root
- Access via signed URLs (time-limited)
- Malware scanning on upload (if configured)
- Automatic cleanup of expired files

## Infrastructure Security

### Docker

- Non-root users in containers
- Read-only filesystem where possible
- Security updates applied regularly
- Minimal base images (Alpine)
- No secrets in Docker images

```dockerfile
# Example: Non-root user
USER appuser:appuser
```

### Network Security

- **Firewall**: Allow only ports 80, 443
- **Internal Network**: Services communicate via Docker network
- **No External Exposure**: Database, Redis not exposed
- **Rate Limiting**: At Nginx level
- **DDoS Protection**: Cloudflare or similar

### SSL/TLS

- TLS 1.2+ only
- Strong cipher suites
- HTTPS redirect enforced
- HSTS headers enabled
- Certificate auto-renewal (Let's Encrypt)

```nginx
# Nginx SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
add_header Strict-Transport-Security "max-age=31536000" always;
```

## Logging and Monitoring

### Audit Logging

- All authentication events logged
- Failed login attempts tracked
- API access logged with user context
- Sensitive operations audited (delete, export)
- Logs never contain secrets or PII

### Security Monitoring

- Failed authentication alerts
- Rate limit violations tracked
- Unusual API usage patterns detected
- Database query anomalies monitored
- Error tracking (Sentry recommended)

### Log Security

- Logs stored securely
- Access restricted to authorized personnel
- Logs rotated and archived
- PII redacted from logs
- Retention policy enforced

## Dependency Security

### Package Management

- Regular dependency updates
- Vulnerability scanning (Dependabot, Snyk)
- Pin exact versions in production
- Review security advisories
- Use trusted package sources only

```bash
# Check for vulnerabilities
pip-audit
npm audit

# Update dependencies safely
pip install --upgrade package-name
npm update package-name
```

### Supply Chain

- Verify package signatures
- Use lock files (uv.lock, package-lock.json)
- Scan Docker images for vulnerabilities
- Use official base images only

## Compliance

### Data Protection (GDPR, CCPA)

- **Right to Access**: Export user data on request
- **Right to Deletion**: Delete user data on request
- **Data Minimization**: Collect only necessary data
- **Consent**: Explicit consent for data processing
- **Data Retention**: Delete data after retention period

### Privacy

- Privacy policy published and accessible
- Cookie consent for non-essential cookies
- Data processing agreements with vendors
- Data breach notification procedures
- Regular privacy audits

## Incident Response

### Security Incidents

1. **Detection**: Monitor logs, alerts, user reports
2. **Containment**: Isolate affected systems
3. **Investigation**: Analyze logs, identify root cause
4. **Remediation**: Patch vulnerabilities, restore from backup
5. **Notification**: Inform affected users if required
6. **Post-Mortem**: Document incident, improve processes

### Breach Notification

- Notify affected users within 72 hours
- Notify authorities if required by law
- Document breach details
- Implement corrective measures
- Update security procedures

## Security Checklist

### Development
- [ ] No secrets in code
- [ ] Input validation on all endpoints
- [ ] Output encoding/escaping
- [ ] Parameterized queries only
- [ ] CSRF protection enabled
- [ ] Rate limiting configured

### Deployment
- [ ] SSL/TLS certificates valid
- [ ] Secrets in environment variables
- [ ] Strong SECRET_KEY generated and set
- [ ] Database uses SSL
- [ ] Firewall rules configured
- [ ] Backups enabled and tested

### Operations
- [ ] Regular security updates
- [ ] Dependency vulnerability scanning
- [ ] Log monitoring active
- [ ] Access controls reviewed
- [ ] Incident response plan tested
- [ ] Security training for team

## Security Contacts

For security issues:
- **Email**: security@your-domain.com
- **Disclosure Policy**: Responsible disclosure within 90 days
- **Bug Bounty**: Contact for details

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask.palletsprojects.com/en/latest/security/)
- [Docker Security](https://docs.docker.com/engine/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
