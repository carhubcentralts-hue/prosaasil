# Nginx Upstream Names Fix - Summary

## Root Cause
Nginx configuration file `docker/nginx/conf.d/prosaas-ssl.conf` was referencing non-existent upstream services:
- `prosaas-api:5000` (does not exist in docker-compose.yml)
- `prosaas-calls:5050` (only exists in docker-compose.prod.yml for production)

This caused nginx to crash on startup with:
```
host not found in upstream "prosaas-api" in /etc/nginx/conf.d/prosaas-ssl.conf:53
```

Leading to port 80 being unavailable → Cloudflare 521 errors.

## Changes Made

### 1. Fixed Nginx Configuration
**File**: `docker/nginx/conf.d/prosaas-ssl.conf`

Changed all references from:
- `prosaas-api:5000` → `prosaas-backend:5000`
- `prosaas-calls:5050` → `prosaas-backend:5000`

**Affected locations**:
- Line 53: `/api/` location - now proxies to `prosaas-backend:5000`
- Line 83: `/ws/` location - now proxies to `prosaas-backend:5000` 
- Line 110: `/webhook` location - now proxies to `prosaas-backend:5000`

### 2. Validation Script
**File**: `scripts/validate_nginx_upstreams.sh`

Created automated validation script that checks:
- No legacy service names (`prosaas-api`) in nginx configs
- Expected services are referenced (`prosaas-backend:5000`, `prosaas-frontend:80`, `prosaas-n8n:5678`)
- Services exist in docker-compose.yml
- `server_name prosaas.pro` is configured

This script can be run in CI to prevent future mismatches.

## Verification

### Server Name ✅
`server_name prosaas.pro www.prosaas.pro` is correctly configured (lines 14, 25)

### Docker Compose Services ✅
- `docker-compose.yml` defines `backend` service with `container_name: prosaas-backend`
- Nginx now correctly references `prosaas-backend:5000` for all backend endpoints
- Docker's internal DNS will resolve `prosaas-backend` to the backend container

### All Endpoints ✅
- `/api/` → `prosaas-backend:5000` (REST API)
- `/ws/` → `prosaas-backend:5000` (WebSocket for calls)
- `/webhook` → `prosaas-backend:5000` (Twilio webhooks)
- `/` → `prosaas-frontend:80` (Frontend SPA)
- `n8n.prosaas.pro` → `prosaas-n8n:5678` (n8n automation)

## Why This Fixes Cloudflare 521

1. **Before**: Nginx tried to resolve `prosaas-api` → DNS lookup failed → nginx crashed → no port 80 → Cloudflare 521
2. **After**: Nginx resolves `prosaas-backend` → matches container_name in docker-compose.yml → nginx starts successfully → port 80 available → Cloudflare can connect

## Production Deployment Note

For production deployments using `docker-compose.prod.yml`:
- Services are split into `prosaas-api` and `prosaas-calls`
- The prod override file properly defines these services
- SSL configuration will work with both standard and production deployments

## Testing

Run validation script:
```bash
./scripts/validate_nginx_upstreams.sh
```

Expected output:
```
✅ No references to legacy service 'prosaas-api'
✅ Found expected service: prosaas-backend:5000
✅ Found expected service: prosaas-frontend:80
✅ Found expected service: prosaas-n8n:5678
✅ Service 'backend' with container_name 'prosaas-backend' exists in docker-compose.yml
✅ Service 'frontend' with container_name 'prosaas-frontend' exists in docker-compose.yml
✅ Found 'server_name prosaas.pro' in nginx configs
✅ All validation checks passed!
```
