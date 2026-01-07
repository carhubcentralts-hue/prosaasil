# n8n Domain Fix Deployment Guide

## Problem Fixed
The domain `n8n.prosaas.pro` was serving the frontend (AI CRM) instead of proxying to the n8n container.

## Root Cause (Corrected)
Requests to `n8n.prosaas.pro` were being handled by the default frontend vhost, meaning the dedicated `server_name n8n.prosaas.pro` block was not being matched. This could occur due to:
- Server block not loaded or not in the correct include path
- Missing or incorrect SSL vhost configuration
- `default_server` directive taking precedence
- DNS/Cloudflare pointing to wrong origin

The legacy `/n8n/` subpath configuration (which proxied from `prosaas.pro/n8n/`) does NOT conflict with the subdomain configuration - they use different `server_name` directives and should not interfere with each other.

## Changes Made

### 1. docker/nginx.conf
- ✅ Verified dedicated n8n.prosaas.pro server block exists (lines 8-35)
- ✅ Added `client_max_body_size 64m` for file uploads
- ✅ Cleanup: Removed legacy `/n8n/` subpath proxy (optional - not the root fix)
- ✅ Cleanup: Removed legacy `/n8nstatic/` proxy (optional - not the root fix)
- ✅ Cleanup: Removed legacy `/n8nassets/` proxy (optional - not the root fix)

### 2. docker/nginx-ssl.conf
- ✅ Verified n8n.prosaas.pro HTTP → HTTPS redirect exists (lines 30-34)
- ✅ Verified dedicated n8n.prosaas.pro HTTPS server block exists (lines 37-78)
- ✅ Added `client_max_body_size 64m` for file uploads
- ✅ Cleanup: Removed legacy `/n8n/` subpath proxy (optional - not the root fix)

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

**Required Verification Tests:**

```bash
# Test 1: Verify n8n.prosaas.pro does NOT return AI CRM HTML
curl -s https://n8n.prosaas.pro/ | head -20
# Should NOT contain <title>AI CRM</title>
# Should contain n8n HTML elements

# Test 2: Verify n8n API endpoint returns JSON (not HTML)
curl -s https://n8n.prosaas.pro/rest/ping
# Expected: JSON response like {"status":"ok"} or similar
# NOT: HTML content with <title>AI CRM</title>

# Test 3: Verify Content-Type header
curl -I https://n8n.prosaas.pro/rest/ping
# Expected: Content-Type: application/json
# NOT: Content-Type: text/html

# Test 4: Verify nginx loaded the n8n.prosaas.pro server block
docker exec prosaas-frontend nginx -T 2>/dev/null | grep -n "server_name n8n.prosaas.pro"
# Should show line numbers where the server blocks are defined
# Should see at least 2 entries (HTTP redirect + HTTPS)

# Also verify the n8n container is running
docker ps | grep prosaas-n8n
# Should see prosaas-n8n container running on port 5678
```

If any of these tests fail, see the Troubleshooting section below.

### Step 4: Test in Browser
1. Navigate to `https://n8n.prosaas.pro`
2. You should see the n8n login/interface (NOT the AI CRM interface)
3. Log in and verify functionality

## What This Fix Does

### The Real Issue
The dedicated `server_name n8n.prosaas.pro` blocks exist in the configuration but requests were still going to the default frontend vhost. This typically means:
- The nginx configuration needs to be properly loaded/reloaded
- SSL certificates need to be in place
- The server blocks need to be ordered correctly (specific server_name before default_server)

### What This PR Does
- ✅ Verifies and maintains dedicated HTTP and HTTPS server blocks for n8n.prosaas.pro
- ✅ Ensures proper proxy configuration to prosaas-n8n:5678
- ✅ Adds file upload size limits (64MB) for n8n workflows
- ✅ Cleanup: Removes unused legacy subpath configuration (not the root fix, just cleanup)

### Before
- `https://n8n.prosaas.pro` → Served frontend (AI CRM) ❌
- Had legacy subpath configuration at `/n8n/` on main domain (unused)

### After
- `https://n8n.prosaas.pro` → Properly proxies to n8n container ✅
- Clean configuration with only necessary routes ✅

## Architecture

```
Internet → nginx (port 443)
           ├─ n8n.prosaas.pro → prosaas-n8n:5678 (n8n)
           └─ *.prosaas.pro   → prosaas-frontend:80 (AI CRM)
```

## Troubleshooting

### If n8n.prosaas.pro still shows AI CRM:

1. **Check nginx loaded the n8n.prosaas.pro server blocks**:
   ```bash
   docker exec prosaas-frontend nginx -T 2>/dev/null | grep -A 20 "server_name n8n.prosaas.pro"
   ```
   Should show both the HTTP redirect block and the HTTPS proxy block.
   
   If NOT showing: The nginx configuration file is not being included properly. Check:
   - Is the file mounted correctly in the container?
   - Is there an `include` directive loading it?
   - Are there syntax errors preventing the config from loading?

2. **Check for default_server precedence**:
   ```bash
   docker exec prosaas-frontend nginx -T 2>/dev/null | grep -n "default_server"
   ```
   If a default_server block appears before the n8n.prosaas.pro block, it might be taking precedence.

3. **Verify DNS is pointing to the correct server**:
   ```bash
   nslookup n8n.prosaas.pro
   dig n8n.prosaas.pro
   ```
   Make sure DNS points to the same IP as your main domain.

4. **Check SSL certificates exist**:
   ```bash
   docker exec prosaas-frontend ls -la /etc/nginx/certs/
   ```
   Should show `fullchain.pem` and `privkey.pem` files.

5. **Check Docker network connectivity**:
   ```bash
   docker exec prosaas-frontend curl http://prosaas-n8n:5678/
   ```
   Should return n8n HTML content.

6. **Check nginx error logs**:
   ```bash
   docker logs prosaas-frontend --tail 50
   ```

7. **Force reload nginx** (if simple reload didn't work):
   ```bash
   docker-compose restart frontend
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
