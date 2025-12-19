# API Endpoint 404 Fix - Deployment Guide

## Issue Summary
Frontend loads successfully but multiple API endpoints return 404 errors, making the system not production-ready.

## Root Cause
The nginx configuration was missing trailing slashes in the `/api` location directive, causing improper routing of API requests to the backend.

## Fix Applied

### 1. Nginx Configuration Update

**File: `docker/nginx.conf`**
```nginx
# BEFORE (incorrect - causes 404 on sub-paths)
location /api {
    proxy_pass http://backend:5000;
    ...
}

# AFTER (correct - properly routes all /api/* paths)
location /api/ {
    proxy_pass http://backend:5000/api/;
    ...
}
```

**File: `docker/nginx-ssl.conf`**
```nginx
# BEFORE (incorrect)
location /api/ {
    proxy_pass http://backend_servers;
    ...
}

# AFTER (correct)
location /api/ {
    proxy_pass http://backend_servers/api/;
    ...
}
```

### 2. Smoke Test Script

Created `server/scripts/smoke_api.py` to validate all critical endpoints after deployment.

## Deployment Instructions

### For Docker Deployments

1. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

2. **Restart nginx container:**
   ```bash
   docker compose restart nginx
   ```

3. **Verify nginx config is loaded:**
   ```bash
   docker compose exec nginx nginx -t
   docker compose exec nginx nginx -s reload
   ```

4. **Run smoke tests:**
   ```bash
   python3 server/scripts/smoke_api.py https://prosaas.pro
   ```

### For Manual Nginx Deployments

1. **Update nginx configuration:**
   ```bash
   # Backup existing config
   cp /etc/nginx/sites-available/prosaas /etc/nginx/sites-available/prosaas.bak
   
   # Update the config file to use trailing slashes
   # Edit /etc/nginx/sites-available/prosaas
   # Change: location /api { proxy_pass http://backend:5000; }
   # To: location /api/ { proxy_pass http://backend:5000/api/; }
   ```

2. **Test configuration:**
   ```bash
   nginx -t
   ```

3. **Reload nginx:**
   ```bash
   systemctl reload nginx
   # OR
   nginx -s reload
   ```

4. **Verify endpoints:**
   ```bash
   curl -i https://prosaas.pro/api/dashboard/stats?time_filter=today
   curl -i https://prosaas.pro/api/leads?page=1&pageSize=1
   curl -i https://prosaas.pro/api/crm/threads
   curl -i https://prosaas.pro/api/whatsapp/status
   ```

## Verification Checklist

After deployment, verify these endpoints return 200 or 401/403 (NOT 404):

- [ ] `/health` - Returns 200
- [ ] `/api/health` - Returns 200
- [ ] `/api/auth/csrf` - Returns 200 or 401
- [ ] `/api/dashboard/stats?time_filter=today` - Returns 200/401/403
- [ ] `/api/dashboard/activity?time_filter=today` - Returns 200/401/403
- [ ] `/api/leads?page=1&pageSize=1` - Returns 200/401/403
- [ ] `/api/crm/threads` - Returns 200/401/403
- [ ] `/api/whatsapp/status` - Returns 200/401/403
- [ ] `/api/whatsapp/templates` - Returns 200/401/403
- [ ] `/api/whatsapp/broadcasts` - Returns 200/401/403
- [ ] `/api/notifications` - Returns 200/204/401/403
- [ ] `/api/admin/businesses?pageSize=1` - Returns 200/401/403
- [ ] `/api/outbound/import-lists` - Returns 200/401/403
- [ ] `/api/outbound_calls/counts` - Returns 200/401/403
- [ ] `/api/statuses` - Returns 200/401/403

## Automated Testing

### Using the smoke test script:

```bash
# Test production
python3 server/scripts/smoke_api.py https://prosaas.pro

# Test local development
python3 server/scripts/smoke_api.py http://localhost:5000

# Test custom URL
python3 server/scripts/smoke_api.py https://your-domain.com
```

Expected output:
```
✅ ALL TESTS PASSED - PRODUCTION READY
```

If any tests fail with 404:
1. Check nginx configuration has trailing slashes
2. Verify nginx has been reloaded
3. Check backend logs for errors
4. Verify all blueprints are registered in `server/app_factory.py`

### Using curl commands (manual):

```bash
# Quick test script
BASE_URL="https://prosaas.pro"

echo "Testing critical endpoints..."
curl -i $BASE_URL/api/dashboard/stats?time_filter=today | head
curl -i $BASE_URL/api/leads?page=1\&pageSize=1 | head
curl -i $BASE_URL/api/crm/threads | head
curl -i $BASE_URL/api/whatsapp/status | head
curl -i $BASE_URL/api/notifications | head
```

## Troubleshooting

### All /api/* endpoints return 404

**Cause:** Nginx configuration not updated or not reloaded

**Fix:**
1. Verify nginx config has `location /api/` with trailing slash
2. Verify proxy_pass includes `/api/` path
3. Reload nginx: `docker compose restart nginx` or `nginx -s reload`

### Some endpoints work, others return 404

**Cause:** Blueprint not registered in app_factory.py

**Fix:**
1. Run blueprint verification: `python3 server/scripts/verify_blueprints.py`
2. Check `server/app_factory.py` for missing `app.register_blueprint()` calls
3. Restart backend: `docker compose restart backend`

### Endpoints return 401/403 instead of data

**Status:** This is expected! These endpoints require authentication.
- 401 = Not authenticated (needs login)
- 403 = Authenticated but not authorized (needs different role)

**Action:** Test with authenticated session or verify frontend can access them.

### Backend not starting

**Cause:** Database connection or blueprint import errors

**Fix:**
1. Check backend logs: `docker compose logs backend`
2. Verify database is running: `docker compose ps`
3. Check for Python import errors in blueprints

## Backend Blueprint Registration

All required blueprints are registered in `server/app_factory.py`:

```python
# Dashboard & Activity
app.register_blueprint(api_adapter_bp)

# Leads & Notifications  
app.register_blueprint(leads_bp)

# CRM Threads
app.register_blueprint(crm_bp)

# WhatsApp
app.register_blueprint(whatsapp_bp)

# Admin
app.register_blueprint(admin_bp)

# Outbound Calls
app.register_blueprint(outbound_bp)

# Status Management
app.register_blueprint(status_management_bp)
```

Verify with: `python3 server/scripts/verify_blueprints.py`

## Production Readiness Validation

Before marking as production-ready, complete the full acceptance gate:

### API Endpoints
- [ ] All endpoints from verification checklist return non-404 status
- [ ] Dashboard stats/activity load without errors
- [ ] WhatsApp + Broadcast load data
- [ ] Notifications polling does not 404

### Feature Testing
- [ ] **Kanban**: Load board, move card, verify status persists after refresh
- [ ] **Lead Notes**: Open lead, add note, save, refresh, verify note persists
- [ ] **Calls**: List loads, call details page works
- [ ] **WhatsApp**: Threads list loads, messages load, can send text

All checks must pass before deployment to production.

## Files Modified

1. `docker/nginx.conf` - Added trailing slashes to /api location
2. `docker/nginx-ssl.conf` - Added /api/ path to proxy_pass
3. `server/scripts/smoke_api.py` - New smoke test script
4. `server/scripts/verify_blueprints.py` - New blueprint verification script

## Additional Notes

- The trailing slash in nginx `location` and `proxy_pass` is critical for proper path matching
- Without trailing slashes, nginx only matches exact `/api` and not `/api/dashboard/stats`
- All backend blueprints were already registered correctly - this was purely a routing issue
- The smoke test should be integrated into CI/CD pipeline to catch this automatically
