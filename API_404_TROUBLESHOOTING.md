# API 404 Troubleshooting Guide

## Overview
This guide helps diagnose and fix API 404 errors where the frontend UI loads but API endpoints return 404.

## Quick Diagnostic Steps

### 1. Verify Backend is Running
```bash
docker ps | grep backend
# Should show: prosaas-backend container running on port 5000
```

If backend is not running:
```bash
docker compose up -d backend
docker logs prosaas-backend
```

### 2. Test Backend Directly (Bypass Nginx)
```bash
# From inside the production server
curl -i http://127.0.0.1:5000/api/health
curl -i http://127.0.0.1:5000/api/dashboard/stats?time_filter=today
```

**If this returns 404** → Flask routes are not registered (backend issue)  
**If this returns 200/401** → Nginx routing issue

### 3. Test Public Endpoints (Through Nginx)
```bash
curl -i https://prosaas.pro/api/health
curl -i https://prosaas.pro/api/dashboard/stats?time_filter=today
```

### 4. Check Registered Routes
```bash
# List all API routes registered in Flask
curl https://prosaas.pro/api/debug/routes | jq '.api_routes'
```

Expected output should include:
- `/api/health`
- `/api/dashboard/stats`
- `/api/dashboard/activity`
- `/api/business/current`
- `/api/notifications`
- `/api/admin/businesses`
- `/api/search`
- `/api/whatsapp/status`
- `/api/whatsapp/templates`
- `/api/whatsapp/broadcasts`
- `/api/crm/threads`
- `/api/statuses`
- `/api/leads`

## Common Root Causes

### Case 1: Nginx Routing Issue

**Symptoms:**
- Direct backend test works (200/401)
- Public test fails (404)
- Nginx logs show 404

**Diagnosis:**
```bash
# Check nginx config
docker exec prosaas-frontend cat /etc/nginx/conf.d/default.conf

# Check nginx logs
docker logs prosaas-frontend
```

**Fix:**
Verify nginx has proper `/api/` routing:

```nginx
location /api/ {
    proxy_pass http://backend:5000/api/;  # Note trailing slashes!
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Common nginx mistakes:**
- ❌ `proxy_pass http://backend:5000/api;` (missing trailing slash)
- ❌ `location /api {` (missing trailing slash)
- ❌ `proxy_pass http://backend:5000;` (strips /api prefix)
- ❌ Wrong backend service name or port

After fixing nginx config:
```bash
docker exec prosaas-frontend nginx -t
docker exec prosaas-frontend nginx -s reload
# OR
docker compose restart frontend
```

### Case 2: Flask Routes Not Registered

**Symptoms:**
- Direct backend test fails (404)
- `/api/debug/routes` shows missing routes or returns 0 routes
- Backend logs show blueprint registration errors

**Diagnosis:**
```bash
# Check backend logs for errors during startup
docker logs prosaas-backend | grep -i "blueprint\|error\|traceback"

# Test route registration
docker exec -it prosaas-backend python3 -c "
from server.app_factory import create_app
app = create_app()
print('\n'.join([str(r) for r in app.url_map.iter_rules()]))
" | grep api
```

**Fix:**

1. Check for import errors in blueprints:
```bash
docker exec -it prosaas-backend python3 -c "
from server.api_adapter import api_adapter_bp
from server.routes_admin import admin_bp
from server.routes_leads import leads_bp
print('All blueprints imported successfully')
"
```

2. Verify blueprints are registered in `server/app_factory.py`:
- api_adapter_bp (dashboard endpoints)
- admin_bp (admin endpoints)
- leads_bp (notifications, leads)
- biz_mgmt_bp (business/current)
- search_api (search)
- health_bp (health, debug routes)
- whatsapp_bp (WhatsApp endpoints)
- crm_bp (CRM threads)
- status_management_bp (statuses)

3. Restart backend:
```bash
docker compose restart backend
docker logs -f prosaas-backend  # Watch for errors
```

### Case 3: Backend on Wrong Port/Container

**Symptoms:**
- Nginx shows "Connection refused" or "Bad Gateway"
- Backend appears to be running but unreachable

**Diagnosis:**
```bash
# Check if backend is listening on port 5000
docker exec prosaas-backend netstat -tlnp | grep 5000

# Check docker network
docker network inspect prosaasil_default | grep backend

# Test connection from frontend container
docker exec prosaas-frontend wget -O- http://backend:5000/api/health
```

**Fix:**
Verify docker-compose.yml has correct service name and port:
```yaml
services:
  backend:
    container_name: prosaas-backend
    ports:
      - "5000:5000"
```

And nginx uses correct upstream:
```nginx
proxy_pass http://backend:5000/api/;
```

### Case 4: Frontend Calling Wrong URLs

**Symptoms:**
- Backend routes work when tested directly
- Frontend shows 404 in browser console
- URLs in console don't match backend routes

**Diagnosis:**
Check browser console for actual URLs being called. They should all start with `/api/`.

**Fix:**
Check `client/src/services/http.ts` - base URL should be `'/'` (relative), not an absolute URL.

## Automated Verification

### Run Comprehensive Smoke Tests
```bash
# From project root
python3 server/scripts/smoke_api.py https://prosaas.pro
```

### Run Deployment Verification
```bash
# From project root
./scripts/verify_deployment.sh https://prosaas.pro http://127.0.0.1:5000
```

Both scripts should show all tests passing with ✅.

## Critical Endpoints Checklist

Test each endpoint manually if automated tests fail:

```bash
BASE="https://prosaas.pro"

# Health
curl -i $BASE/health
curl -i $BASE/api/health

# Dashboard (requires auth - expect 401/403, not 404)
curl -i "$BASE/api/dashboard/stats?time_filter=today"
curl -i "$BASE/api/dashboard/activity?time_filter=today"

# Business
curl -i $BASE/api/business/current

# Notifications
curl -i $BASE/api/notifications

# Admin
curl -i "$BASE/api/admin/businesses?pageSize=1"

# Search
curl -i "$BASE/api/search?q=test"

# WhatsApp
curl -i $BASE/api/whatsapp/status
curl -i $BASE/api/whatsapp/templates
curl -i $BASE/api/whatsapp/broadcasts

# CRM
curl -i $BASE/api/crm/threads

# Statuses
curl -i $BASE/api/statuses

# Leads
curl -i "$BASE/api/leads?page=1&pageSize=1"
```

**Expected results:**
- ✅ 200 (success)
- ✅ 401 (unauthorized - endpoint exists, needs auth)
- ✅ 403 (forbidden - endpoint exists, insufficient permissions)
- ❌ 404 (not found - PROBLEM!)

## Production Deployment Checklist

Before deploying, verify:

- [ ] All blueprints are imported and registered in `server/app_factory.py`
- [ ] Nginx config has correct `/api/` routing with trailing slashes
- [ ] Docker service names match nginx upstream (backend:5000)
- [ ] Backend is exposed on port 5000 in docker-compose
- [ ] Environment variables are set (DATABASE_URL, SECRET_KEY, etc.)
- [ ] Run `python3 server/scripts/smoke_api.py` locally - all tests pass
- [ ] Run `./scripts/verify_deployment.sh` after deployment - all tests pass
- [ ] Check `/api/debug/routes` shows all expected API routes
- [ ] Browser console shows no 404 errors for API calls

## Quick Fixes

### Fix 1: Restart Everything
```bash
docker compose down
docker compose up -d
sleep 10
docker logs prosaas-backend
docker logs prosaas-frontend
```

### Fix 2: Rebuild Backend
```bash
docker compose build backend --no-cache
docker compose up -d backend
docker logs -f prosaas-backend
```

### Fix 3: Rebuild Frontend
```bash
docker compose build frontend --no-cache
docker compose up -d frontend
docker logs -f prosaas-frontend
```

### Fix 4: Check Database Connection
```bash
curl https://prosaas.pro/db-check
# Should show "connection_test": "success"
```

## Debug Mode

Enable debug logging:
```bash
# In .env file
export FLASK_ENV=development
export LOG_LEVEL=DEBUG

# Restart backend
docker compose restart backend

# Watch logs
docker logs -f prosaas-backend
```

## Contact Support

If issue persists after following this guide:

1. Run verification script and save output:
```bash
./scripts/verify_deployment.sh > verification_output.txt 2>&1
```

2. Get route registration info:
```bash
curl https://prosaas.pro/api/debug/routes > routes.json
```

3. Get backend logs:
```bash
docker logs prosaas-backend > backend_logs.txt 2>&1
```

4. Get nginx logs:
```bash
docker logs prosaas-frontend > nginx_logs.txt 2>&1
```

5. Share all output files for analysis.
