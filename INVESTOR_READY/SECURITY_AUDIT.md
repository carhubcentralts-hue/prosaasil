# Security Audit

## Summary

All critical security controls are in place. No hardcoded secrets found.
CI enforces security audits as blocking checks (no `|| true`).

## Checklist

| Control | Status | Details |
|---------|--------|---------|
| **.env protection** | ✅ Pass | `.env` in `.gitignore`, multiple patterns prevent leaks |
| **No hardcoded secrets** | ✅ Pass | All secrets loaded from environment variables |
| **CSP headers** | ✅ Pass | Strict policy: `default-src 'self'`, `frame-ancestors 'none'` |
| **HSTS** | ✅ Pass | Enabled for secure connections |
| **Cookies: HttpOnly** | ✅ Pass | `SESSION_COOKIE_HTTPONLY: True` |
| **Cookies: Secure** | ✅ Pass | Enforced in production (`PRODUCTION=1`) |
| **Cookies: SameSite** | ✅ Pass | `Lax` or `None` based on secure mode |
| **CSRF protection** | ✅ Pass | Flask-SeaSurf enabled, token endpoint at `/api/auth/csrf` |
| **CORS locked** | ✅ Pass | Production: explicit origins only, no wildcards with credentials |
| **Rate limiting** | ✅ Pass | Login: 5/min, Password reset: 3/min, Webhooks: 200/min, TTS: 20/min |
| **Security headers** | ✅ Pass | X-Frame-Options, X-Content-Type-Options, X-XSS-Protection |
| **Secret key enforcement** | ✅ Pass | Fails fast in production if SECRET_KEY not set |
| **Database SSL** | ✅ Pass | SSL support + connection timeout protection |
| **npm audit** | ✅ Pass | CI blocks on high/critical (no `\|\| true`) |
| **pip-audit** | ✅ Pass | CI blocks on all severities (`continue-on-error: false`) |
| **Docker hardening** | ✅ Pass | `no-new-privileges`, `cap_drop: ALL`, read-only FS where possible |
| **Calls concurrency** | ✅ Pass | MAX_CONCURRENT_CALLS enforced via Redis (default: 50) |
| **Metrics auth** | ✅ Pass | `/metrics.json` protected by token |

## Dependency Security

| Ecosystem | Tool | CI Blocking | Allowlist |
|-----------|------|-------------|-----------|
| Python | `pip-audit` | ✅ Yes | `server/AUDIT_ALLOWLIST.md` |
| Node.js | `npm audit` | ✅ Yes (high/critical) | `client/AUDIT_ALLOWLIST.md` |

## Docker Security

- `security_opt: no-new-privileges:true` on all production services
- `cap_drop: ALL` with minimal `cap_add` where needed
- `read_only: true` filesystem for nginx and frontend
- Internal services expose ports only within Docker network
- External DNS configured to prevent DNS rebinding

## What Was Fixed

1. **Removed `|| true` from npm audit** — CI now blocks on high/critical vulnerabilities
2. **MAX_CONCURRENT_CALLS enforcement** — No longer allows `0` (unlimited)
3. **Metrics endpoint auth** — `/metrics.json` requires token
4. **OpenAI client lazy initialization** — Prevented import-time crash
5. **No sourcemaps in production** — CI verifies no `.map` files

## Recommendations

- Ensure Nginx is configured with HTTPS (443) + TLS certificates in production
- Rotate API keys and secrets periodically
- Enable database SSL in production if not already active
- Review audit allowlists monthly
