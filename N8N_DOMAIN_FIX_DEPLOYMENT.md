# n8n Domain Fix Deployment Guide

## Problem Fixed
The domain `n8n.prosaas.pro` was serving the frontend (AI CRM) instead of proxying to the n8n container. This fix removes legacy subpath configuration and ensures the domain properly routes to n8n.

## Changes Made

### 1. docker/nginx.conf
- ✅ Kept dedicated n8n.prosaas.pro server block (lines 8-34)
- ✅ Added `client_max_body_size 64m` for file uploads
- ❌ Removed legacy `/n8n/` subpath proxy (was lines 101-116)
- ❌ Removed legacy `/n8nstatic/` proxy (was lines 118-125)
- ❌ Removed legacy `/n8nassets/` proxy (was lines 127-134)

### 2. docker/nginx-ssl.conf
- ✅ Kept n8n.prosaas.pro HTTP → HTTPS redirect (lines 30-34)
- ✅ Kept dedicated n8n.prosaas.pro HTTPS server block (lines 37-78)
- ✅ Added `client_max_body_size 64m` for file uploads
- ❌ Removed legacy `/n8n/` subpath proxy (was lines 152-167)

### 3. docker-compose.yml
- ✅ No changes needed - already correctly configured with:
  - Image: `n8nio/n8n:2.3.1`
  - N8N_HOST: `n8n.prosaas.pro`
  - N8N_PROTOCOL: `https`
  - WEBHOOK_URL: `https://n8n.prosaas.pro/`
  - N8N_TRUST_PROXY: `true`
  - N8N_PROXY_HOPS: `1`
  - NODE_ENV: `production`

## Deployment Instructions

### Step 1: Pull Latest Changes
```bash
git pull origin <branch-name>
```

### Step 2: Reload/Restart Nginx Only
**IMPORTANT**: You do NOT need to restart the n8n container or any other containers. Only nginx needs to be reloaded.

#### Option A: If nginx is running as a Docker service
```bash
# Reload nginx configuration without downtime
docker exec prosaas-frontend nginx -s reload
```

#### Option B: If nginx is running as a standalone service
```bash
# Test configuration first
sudo nginx -t

# Reload nginx
sudo nginx -s reload
# OR
sudo systemctl reload nginx
```

### Step 3: Verify the Fix
```bash
# Test that n8n.prosaas.pro returns n8n content
curl -I https://n8n.prosaas.pro/rest/ping

# Expected output should include:
# - HTTP/2 200 or similar success status
# - Content-Type: application/json (NOT text/html)
# - Should NOT see <title>AI CRM</title>

# Also verify the n8n container is running
docker ps | grep prosaas-n8n

# Should see prosaas-n8n container running on port 5678
```

### Step 4: Test in Browser
1. Navigate to `https://n8n.prosaas.pro`
2. You should see the n8n login/interface (NOT the AI CRM interface)
3. Log in and verify functionality

## What This Fix Does

### Before
- `https://n8n.prosaas.pro` → Served frontend (AI CRM) ❌
- Had conflicting subpath configuration at `/n8n/` (legacy)

### After
- `https://n8n.prosaas.pro` → Properly proxies to n8n container ✅
- Clean configuration with only domain-based routing ✅
- Legacy subpath routes removed ✅

## Architecture

```
Internet → nginx (port 443)
           ├─ n8n.prosaas.pro → prosaas-n8n:5678 (n8n)
           └─ *.prosaas.pro   → prosaas-frontend:80 (AI CRM)
```

## Troubleshooting

### If n8n.prosaas.pro still shows AI CRM:

1. **Check nginx is using the updated config**:
   ```bash
   docker exec prosaas-frontend nginx -T | grep -A 20 "server_name n8n.prosaas.pro"
   ```
   Should show the dedicated n8n server block.

2. **Verify DNS is pointing to the correct server**:
   ```bash
   nslookup n8n.prosaas.pro
   dig n8n.prosaas.pro
   ```

3. **Check Docker network connectivity**:
   ```bash
   docker exec prosaas-frontend curl http://prosaas-n8n:5678/
   ```
   Should return n8n HTML content.

4. **Check nginx logs**:
   ```bash
   docker logs prosaas-frontend --tail 50
   ```

### If webhooks don't work:

1. Verify n8n environment variables in docker-compose.yml:
   - `WEBHOOK_URL=https://n8n.prosaas.pro/`
   - `N8N_HOST=n8n.prosaas.pro`
   - `N8N_PROTOCOL=https`

2. Restart n8n container (only if environment was changed):
   ```bash
   docker-compose restart n8n
   ```

## Notes

- **No downtime**: Only nginx needs to be reloaded, not the entire stack
- **DNS changes**: If you recently updated DNS, it may take time to propagate (typically 5-60 minutes)
- **SSL certificates**: The fix uses existing SSL certificates, no certificate changes needed
- **Database**: n8n database configuration remains unchanged
- **Existing workflows**: All existing n8n workflows and data remain intact

## Rollback

If needed, you can rollback by reverting the nginx configuration files:
```bash
git checkout HEAD~1 docker/nginx.conf docker/nginx-ssl.conf
docker exec prosaas-frontend nginx -s reload
```
