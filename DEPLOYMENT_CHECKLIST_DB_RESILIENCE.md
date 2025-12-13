# DB Resilience - Deployment Checklist

## Pre-Deployment Verification ✅

- [x] Code review completed - all issues resolved
- [x] Security scan passed (CodeQL) - 0 alerts
- [x] Verification script passes all checks
- [x] All files syntactically valid
- [x] No circular imports
- [x] All acceptance criteria met

## Deployment Steps

### 1. Review Changes (5 minutes)
```bash
# Review the changes in this PR
git diff main...copilot/fix-db-endpoint-crashes

# Files changed:
# - server/app_factory.py (logger fix, statement timeout)
# - server/ui/routes.py (logger fix)
# - server/error_handlers.py (503 responses for DB errors)
# - server/services/whatsapp_session_service.py (standardized logging)
# - server/utils/db_retry.py (NEW - retry utility)
# - server/utils/safe_thread.py (NEW - thread safety)
# + verification and documentation files
```

### 2. Merge to Main (2 minutes)
```bash
# Merge the PR
git checkout main
git merge copilot/fix-db-endpoint-crashes
git push origin main
```

### 3. Deploy to Production (Platform-specific)

**Replit:**
```bash
# Replit auto-deploys from main branch
# Monitor deployment logs for errors
```

**Railway/Render:**
```bash
# Deploy from main branch
railway up  # or: render deploy
```

**Manual/Docker:**
```bash
# Pull latest code
git pull origin main

# Restart services
docker-compose down
docker-compose up -d

# Or for systemd:
sudo systemctl restart prosaasil-backend
```

### 4. Post-Deployment Verification (10 minutes)

#### A. Check Server Started Successfully
```bash
# Check logs for startup
tail -f /var/log/prosaasil.log | grep -E "DB_POOL|STARTUP"

# Expected:
# [DB_POOL] pool_pre_ping=True pool_recycle=300s (Neon-optimized)
```

#### B. Test API Endpoints
```bash
# Test login endpoint
curl -X POST https://your-app.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Should return normal response (200 or 401)
# NOT a 500 error with "logger is not defined"
```

#### C. Verify Background Loops
```bash
# Check WhatsApp session processor
tail -f /var/log/prosaasil.log | grep WHATSAPP_SESSION

# Expected within 60 seconds:
# [WHATSAPP_SESSION] 📱 Background processor thread started
# [WHATSAPP_SESSION] 📱 Check #1: Found X stale sessions
```

#### D. Monitor for Errors
```bash
# Watch for any new errors
tail -f /var/log/prosaasil.log | grep -E "ERROR|CRITICAL|NameError"

# Should NOT see:
# NameError: name 'logger' is not defined
```

## Testing DB Resilience (Optional but Recommended)

### Test 1: Simulate DB Outage

**On Neon Console:**
1. Go to https://console.neon.tech
2. Select your project
3. Click "Suspend" on compute endpoint
4. Wait 30 seconds

**Monitor Logs:**
```bash
# Watch logs during outage
tail -f /var/log/prosaasil.log | grep -E "DB_DOWN|DB_RECOVERED|503"

# Expected behavior:
# [DB_DOWN] op=whatsapp_session_loop try=1/5 sleep=2s reason=NeonEndpointDisabled
# [WHATSAPP_SESSION] 🔴 Neon endpoint disabled - backing off 2s
# ... (repeated with increasing backoff)
```

**Test API Endpoint:**
```bash
# API should return 503, not crash
curl -v https://your-app.com/api/leads

# Expected response:
# HTTP/1.1 503 Service Unavailable
# {"error":"SERVICE_UNAVAILABLE","detail":"Database temporarily unavailable","status":503}
```

**Resume Endpoint:**
1. Click "Resume" in Neon console
2. Watch logs for recovery

```bash
# Expected:
# [DB_RECOVERED] op=whatsapp_session_loop after 3 attempts
# [WHATSAPP_SESSION] ✅ DB recovered after 3 attempts
```

### Test 2: Verify Server Stays Up

**During DB outage, verify:**
```bash
# Server process should still be running
ps aux | grep python | grep server

# Health check should respond (even if degraded)
curl https://your-app.com/health

# WebSocket connections should stay alive
# (may not be able to save data, but won't crash)
```

## Monitoring Commands

### Check DB Health
```bash
# View recent DB errors
tail -n 100 /var/log/prosaasil.log | grep "DB_DOWN\|DB_RECOVERED"

# Count DB outages in last hour
grep "[DB_DOWN]" /var/log/prosaasil.log | \
  grep "$(date +%Y-%m-%d\ %H)" | wc -l
```

### Check Background Loops
```bash
# WhatsApp session processor
grep "WHATSAPP_SESSION" /var/log/prosaasil.log | tail -20

# Should see regular checks every 5 minutes
```

### Check API Error Rates
```bash
# Count 503 responses (DB unavailable)
grep " 503 " /var/log/nginx/access.log | tail -20

# Count 500 responses (should be rare)
grep " 500 " /var/log/nginx/access.log | tail -20
```

## Rollback Plan (If Needed)

If deployment causes issues:

```bash
# Revert to previous commit
git revert HEAD
git push origin main

# Or reset to previous version
git reset --hard <previous-commit-hash>
git push origin main --force  # BE CAREFUL!

# Redeploy
# (platform-specific commands as above)
```

## Success Criteria

✅ **Server starts without errors**
✅ **No "NameError: name 'logger' is not defined"**
✅ **API endpoints return 503 (not 500) when DB down**
✅ **Background loops continue running during DB outage**
✅ **Logs show [DB_DOWN] and [DB_RECOVERED] messages**
✅ **No unhandled exceptions in logs**

## Support

**If you see issues:**

1. **Check logs first:**
   ```bash
   tail -n 500 /var/log/prosaasil.log
   ```

2. **Common issues:**
   - Import errors → Check Python version (requires 3.11+)
   - Missing dependencies → Run `pip install -r requirements.txt`
   - DB connection issues → Check DATABASE_URL environment variable

3. **Get help:**
   - Review `DB_RESILIENCE_IMPLEMENTATION.md`
   - Run `python3 verify_db_resilience.py`
   - Check GitHub issues for similar problems

## Environment Variables

No new environment variables required! This implementation uses existing config.

**Existing variables used:**
- `DATABASE_URL` - PostgreSQL connection string
- `RUN_MIGRATIONS_ON_START` - Whether to run migrations on startup

## Performance Impact

- **Minimal overhead** - Error handlers only trigger on exceptions
- **Improved stability** - Server stays up during DB outages
- **Better user experience** - 503 responses are more actionable than 500

## Next Steps (Optional Enhancements)

1. **Add health check endpoint:**
   ```python
   @app.route('/health/db')
   def db_health():
       from server.utils.db_health import db_ping
       if db_ping():
           return {"status": "healthy"}, 200
       return {"status": "degraded"}, 503
   ```

2. **Apply safe_thread to more background tasks:**
   - Media processing threads in `media_ws_ai.py`
   - Recording download workers
   - N8N integration loops

3. **Add metrics/alerting:**
   - Alert when DB_DOWN count > 10 in 5 minutes
   - Dashboard showing DB uptime percentage
   - Slack/email notifications on prolonged outages

---

**Deployment Date:** _____________________
**Deployed By:** _____________________
**Notes:** _____________________
