# P1 Security Hardening - Acceptance Criteria

## Overview

This document defines exact acceptance criteria for each P1 security task.
Each criterion includes validation methods and quick checks.

---

## P1-1: Rate Limiting ✅

### Acceptance Criteria

1. **✅ Limiter Initialized in Production**
   - Rate limiter is initialized when `PRODUCTION=1`
   - Uses Redis storage (not memory)
   - NO default limits (to avoid breaking UI/API)

2. **✅ Proxy-Aware IP Detection**
   - Uses `X-Forwarded-For` header correctly
   - Gets rightmost IP (closest to client)
   - Works behind nginx/cloudflare

3. **✅ No Accidental Blocking**
   - Default limits removed (was: 200/day, 50/hour)
   - UI/API calls work normally
   - No 429 errors in normal operation

### Quick Validation

```bash
# Check rate limiter code
grep -A 5 "init_rate_limiter" server/app_factory.py

# Verify no default limits
grep "default_limits=\[\]" server/rate_limiter.py

# Verify proxy awareness
grep "get_real_ip" server/rate_limiter.py
```

### Manual Test (Optional)
- Start app with PRODUCTION=1
- Check logs for "Rate limiting initialized (Redis-backed)"
- Verify normal API calls work without 429 errors

---

## P1-2: CORS Lockdown ✅

### Acceptance Criteria

1. **✅ Production Mode Strict Origins**
   - When `PRODUCTION=1`: Only explicit origins allowed
   - No localhost, no replit regex patterns
   - Origins from: PUBLIC_BASE_URL, FRONTEND_URL, CORS_ALLOWED_ORIGINS

2. **✅ Development Mode Permissive**
   - When `PRODUCTION=0`: localhost + replit patterns allowed
   - Enables local development

3. **✅ Fail-Fast on Missing Origins**
   - Production with credentials but no origins → RuntimeError
   - Clear error message with remediation steps

4. **✅ Supports Credentials Correctly**
   - `supports_credentials=True` (required for session cookies)
   - Explicit origins only (no wildcards)
   - Logging of configured origins

### Quick Validation

```bash
# Check CORS lockdown code
grep -A 30 "P1: CORS with Production Lockdown" server/app_factory.py

# Verify production check
grep "if is_production_mode:" server/app_factory.py | grep -A 5 CORS

# Verify fail-fast
grep "Production requires CORS origins" server/app_factory.py
```

### Manual Test

**Production Mode:**
```bash
export PRODUCTION=1
export PUBLIC_BASE_URL=https://prosaas.pro
# Start app - should work with explicit origin

export PRODUCTION=1
unset PUBLIC_BASE_URL
unset CORS_ALLOWED_ORIGINS
# Start app - should FAIL with clear error
```

**Development Mode:**
```bash
export PRODUCTION=0
# Start app - should allow localhost patterns
```

---

## P1-3: SECRET_KEY Fail-Fast ✅

### Acceptance Criteria

1. **✅ Production Requires SECRET_KEY**
   - When `PRODUCTION=1` and no `SECRET_KEY` → RuntimeError
   - Clear error message with generation command

2. **✅ Development Has Fallback**
   - When `PRODUCTION=0`: Generates random SECRET_KEY
   - Logs warning about non-persistence

3. **✅ Clear Error Message**
   - Includes command to generate key
   - Mentions production requirement

### Quick Validation

```bash
# Check SECRET_KEY handling
grep -A 10 "SECRET_KEY Fail-Fast" server/app_factory.py

# Verify production check
grep "is_production_mode and not secret_key" server/app_factory.py

# Verify error message
grep "Generate with: python3" server/app_factory.py
```

### Manual Test

**Production Without SECRET_KEY:**
```bash
export PRODUCTION=1
unset SECRET_KEY
python -m server
# Should fail with: "PRODUCTION=1 requires SECRET_KEY environment variable"
```

**Production With SECRET_KEY:**
```bash
export PRODUCTION=1
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
python -m server
# Should start successfully
```

**Development:**
```bash
export PRODUCTION=0
unset SECRET_KEY
python -m server
# Should start with warning about generated key
```

---

## P1-4: CSRF Exemptions Audit ✅

### Acceptance Criteria

1. **✅ Audit Script Created**
   - `scripts/audit_csrf_exemptions.py` exists
   - Executable permissions set
   - Analyzes all @csrf.exempt usages

2. **✅ Categorization Accurate**
   - Webhooks identified correctly (50 exemptions)
   - Auth endpoints identified (4 exemptions)
   - Suspicious internal APIs identified (22 exemptions)

3. **✅ Documentation Complete**
   - Golden rule documented
   - Risk assessment included
   - Remediation plan provided

4. **✅ Production Not Broken**
   - No exemptions removed yet (safety first)
   - Suspicious endpoints documented for review
   - Testing plan provided before changes

### Quick Validation

```bash
# Run audit script
python3 scripts/audit_csrf_exemptions.py

# Verify output categories
python3 scripts/audit_csrf_exemptions.py | grep "LEGITIMATE EXEMPTIONS"
python3 scripts/audit_csrf_exemptions.py | grep "SUSPICIOUS EXEMPTIONS"

# Check documentation
cat P1_CSRF_AUDIT_SUMMARY.md | grep "Golden Rule"
```

### Manual Test

```bash
# Full audit
cd /home/runner/work/prosaasil/prosaasil
python3 scripts/audit_csrf_exemptions.py

# Verify counts
# Expected: 50 webhooks, 4 auth, 22 suspicious
```

---

## P1-5: n8n Token Security ✅

### Acceptance Criteria

1. **✅ Token in Header (Primary)**
   - Token sent as `X-N8N-Token` header
   - Prevents token leaks in logs

2. **✅ Temporary Fallback**
   - Also sends token in query param for compatibility
   - Debug log indicates dual-mode
   - Allows gradual migration

3. **✅ No Breaking Changes**
   - Existing n8n webhooks continue working
   - Fallback can be removed after n8n update

### Quick Validation

```bash
# Check token header code
grep -A 10 "X-N8N-Token" server/services/n8n_integration.py

# Verify fallback
grep "Temporary fallback" server/services/n8n_integration.py

# Verify both modes
grep "params=params if token" server/services/n8n_integration.py
```

### Manual Test

**If n8n is configured:**
```python
# Test event sending
from server.services.n8n_integration import send_event_to_n8n

result = send_event_to_n8n('test_event', {
    'business_id': 'test_123',
    'test_data': 'hello'
}, async_send=False)

print(result)  # Should show success
# Check n8n webhook logs - should receive event with token in header
```

---

## Overall P1 Success Criteria

### All Criteria Met ✅

1. **✅ No Production Breaking Changes**
   - All changes are backward compatible
   - Existing functionality works as before
   - New security features activate only in production mode

2. **✅ Security Improvements Active**
   - Rate limiting ready for deployment
   - CORS lockdown enforced in production
   - SECRET_KEY required in production
   - n8n tokens secured
   - CSRF audit completed with actionable findings

3. **✅ Documentation Complete**
   - All changes documented
   - Acceptance criteria defined
   - Testing procedures provided
   - Future work identified (CSRF remediation)

4. **✅ Environment Requirements Clear**
   - `PRODUCTION=1` triggers security features
   - Required env vars documented
   - Fail-fast on missing configuration

---

## Quick Verification Commands

Run all checks at once:

```bash
# 1. Rate limiting
grep -q "default_limits=\[\]" server/rate_limiter.py && echo "✅ P1-1: Rate limiting OK" || echo "❌ P1-1 FAIL"

# 2. CORS lockdown
grep -q "if is_production_mode:" server/app_factory.py && grep -q "cors_origins = \[\]" server/app_factory.py && echo "✅ P1-2: CORS lockdown OK" || echo "❌ P1-2 FAIL"

# 3. SECRET_KEY fail-fast
grep -q "is_production_mode and not secret_key" server/app_factory.py && echo "✅ P1-3: SECRET_KEY fail-fast OK" || echo "❌ P1-3 FAIL"

# 4. CSRF audit
[ -f scripts/audit_csrf_exemptions.py ] && [ -x scripts/audit_csrf_exemptions.py ] && echo "✅ P1-4: CSRF audit OK" || echo "❌ P1-4 FAIL"

# 5. n8n token security
grep -q "X-N8N-Token" server/services/n8n_integration.py && echo "✅ P1-5: n8n token OK" || echo "❌ P1-5 FAIL"
```

---

## Production Deployment Checklist

Before deploying P1 changes to production:

- [ ] Set `PRODUCTION=1` in environment
- [ ] Set `SECRET_KEY` (generate with command from error message)
- [ ] Set `PUBLIC_BASE_URL` to production domain
- [ ] Optionally set `FRONTEND_URL` if different from PUBLIC_BASE_URL
- [ ] Set `CORS_ALLOWED_ORIGINS` if additional origins needed
- [ ] Verify Redis is available (for rate limiting)
- [ ] Test authentication flow (login, session, CSRF token)
- [ ] Monitor logs for CORS/rate limiting warnings
- [ ] Test n8n integrations if configured

---

## Future Work (P1-4 CSRF Remediation)

After P1 deployment and testing:

1. **Frontend CSRF Token Validation**
   - Verify frontend reads `csrf_token` cookie
   - Verify frontend sends `X-CSRFToken` header on API calls

2. **Remove Suspicious Exemptions**
   - Remove @csrf.exempt from 22 internal endpoints
   - Test each endpoint thoroughly
   - Monitor for 403 CSRF errors

3. **Re-run Audit**
   - `python3 scripts/audit_csrf_exemptions.py`
   - Verify only legitimate exemptions remain
   - Update documentation

See `P1_CSRF_AUDIT_SUMMARY.md` for detailed remediation plan.
