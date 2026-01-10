# Deployment Guide - Android WhatsApp Authentication Fix

## Pre-Deployment Checklist

### 1. Code Review
- [x] All 7 fixes implemented in baileys_service.js
- [x] No syntax errors (verified with `node -c`)
- [x] Documentation complete

### 2. Backup Plan
```bash
# If rollback needed:
git revert 2f60481
git push
# Then restart Baileys service
```

### 3. Environment Check
- [ ] Verify Docker volumes for auth storage exist
- [ ] Verify INTERNAL_SECRET is set
- [ ] Verify BAILEYS_PORT (default 3300)

## Deployment Steps

### Option 1: Docker Compose (Recommended)

```bash
# 1. Pull latest code
cd /path/to/prosaasil
git pull origin main  # or your branch

# 2. Rebuild Baileys service
docker-compose build baileys

# 3. Stop current Baileys
docker-compose stop baileys

# 4. Remove old container
docker-compose rm -f baileys

# 5. Start new Baileys
docker-compose up -d baileys

# 6. Check logs
docker-compose logs -f baileys
```

### Option 2: Direct Node.js

```bash
# 1. Pull latest code
cd /path/to/prosaasil
git pull origin main

# 2. Stop current process
pm2 stop baileys
# or: kill -9 <pid>

# 3. Start new process
cd services/whatsapp
node baileys_service.js
# or: pm2 start baileys_service.js --name baileys
```

## Post-Deployment Verification

### 1. Service Health
```bash
# Check if service is running
curl http://localhost:3300/healthz
# Expected: "ok"

# Check clock sync
curl http://localhost:3300/clock
# Expected: {"unix_ms": ..., "is_utc": true, "ok": true}
```

### 2. Session Management
```bash
# Check existing sessions (replace with actual tenant)
curl -H "X-Internal-Secret: YOUR_SECRET" \
  http://localhost:3300/whatsapp/business_1/status
# Expected: JSON with connected status
```

### 3. Test Android Connection

**First Test (Immediate):**
1. Go to WhatsApp settings in UI
2. Click "Start" / "התחל"
3. Scan QR with Android device
4. Send test message immediately
5. ✅ Message should send successfully

**Second Test (Critical - 2 minutes):**
1. Wait 2 minutes (past the 1-1.5 minute failure window)
2. Send another test message
3. ✅ Should still send (no logged_out)
4. ✅ Connection should stay alive

**Third Test (Edge Cases):**
1. Refresh page during QR scan
   - ✅ Should NOT create duplicate session
   - ✅ Should return existing QR or "already starting" error
2. Click "Start" multiple times rapidly
   - ✅ Should return SESSION_START_IN_PROGRESS error after first
3. Simulate temporary disconnect (network blip)
   - ✅ Should auto-reconnect without requiring QR rescan

### 4. Test iPhone Connection (Regression)
1. Scan QR with iPhone device
2. Send test messages
3. ✅ Should work as before (no regression)

## Monitoring

### Key Metrics to Watch

1. **logged_out frequency**
   ```bash
   # Check Baileys logs for logged_out
   docker-compose logs baileys | grep "logged_out"
   # Should be significantly reduced for Android
   ```

2. **Duplicate session attempts**
   ```bash
   # Check for SESSION_START_IN_PROGRESS errors
   docker-compose logs baileys | grep "SESSION_START_IN_PROGRESS"
   # Some expected (good - means lock is working)
   ```

3. **Auth file corruption**
   ```bash
   # Check for "Auth files cleared" on non-logout disconnects
   docker-compose logs baileys | grep "Auth files cleared"
   # Should ONLY appear with "LOGGED_OUT (401)"
   ```

4. **Reconnection success rate**
   ```bash
   # Check for successful reconnects after 428/515
   docker-compose logs baileys | grep "KEEPING AUTH"
   # Should see this for temporary disconnects
   ```

### Expected Log Changes

**Before Fix:**
```
[WA] business_1: ❌ Disconnected. reason=428
[WA] business_1: Auth files cleared, will restart with fresh QR
```

**After Fix:**
```
[WA] business_1: ❌ Disconnected. reason=428
[WA] business_1: Temporary disconnect (reason=428) - keeping auth, will reconnect
[WA] business_1: 🔄 Auto-reconnecting in 5s (KEEPING AUTH)
```

## Troubleshooting

### Issue: Service won't start
```bash
# Check logs
docker-compose logs baileys

# Common causes:
# 1. Port already in use
sudo lsof -i :3300

# 2. Missing environment variables
docker-compose exec baileys env | grep -E "INTERNAL_SECRET|BAILEYS"

# 3. Auth directory permissions
docker-compose exec baileys ls -la /app/storage/whatsapp/
```

### Issue: SESSION_START_IN_PROGRESS error persists
```bash
# This is NORMAL during QR scan
# If it persists for > 60 seconds, restart:
docker-compose restart baileys
```

### Issue: Android still gets logged_out
```bash
# 1. Check browser string in logs
docker-compose logs baileys | grep "browser"
# Should see: "Baileys default (not overridden)"

# 2. Check if auth is being deleted on 428
docker-compose logs baileys | grep "428"
# Should see: "KEEPING AUTH"

# 3. Check for duplicate sockets
docker-compose logs baileys | grep "SOCK_CREATE"
# Should be minimal during QR scan

# 4. Verify connected status requirements
docker-compose logs baileys | grep "FULLY AUTHENTICATED"
# Should appear before "connected" status
```

### Issue: iPhone stopped working
```bash
# Rollback immediately
git revert 2f60481
docker-compose up -d --build baileys

# Report issue with logs
docker-compose logs baileys > baileys_issue.log
```

## Rollback Procedure

If critical issues occur:

```bash
# 1. Immediate rollback
git revert 2f60481
git push

# 2. Rebuild and restart
docker-compose up -d --build baileys

# 3. Verify service is up
curl http://localhost:3300/healthz

# 4. Notify team
# - What went wrong
# - Logs from the failure
# - Steps to reproduce
```

## Success Indicators

After 24 hours of deployment:

✅ Zero logged_out errors from Android after 1-1.5 minutes
✅ iPhone connections unchanged
✅ No increase in support tickets about WhatsApp
✅ Logs show "KEEPING AUTH" on temporary disconnects
✅ Logs show SESSION_START_IN_PROGRESS on duplicate starts

## Next Steps

If successful:
1. Monitor for 48 hours
2. Update user documentation about manual restart after logout
3. Consider adding UI notification for SESSION_START_IN_PROGRESS
4. Add metrics dashboard for WhatsApp connection health

If issues:
1. Rollback immediately
2. Gather detailed logs
3. Test in staging environment
4. Review fix #6 (connected status timing) as most likely culprit

---

**Deployment Checklist**
- [ ] Code reviewed and merged
- [ ] Backup plan documented
- [ ] Service rebuilt
- [ ] Service restarted
- [ ] Health checks passed
- [ ] Android test (2+ minutes) passed
- [ ] iPhone regression test passed
- [ ] Monitoring in place
- [ ] Team notified

**Deployed:** _____________
**Verified:** _____________
**Status:** _____________
