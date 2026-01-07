# n8n HTTPS Configuration Fix - Deployment Guide

## Problem Summary

The n8n service was experiencing Mixed Content warnings and 404 errors because it was configured to run with HTTP protocol (`N8N_PROTOCOL=http`) but was being accessed via HTTPS at `https://prosaas.pro/n8n/`.

This caused:
1. **Mixed Content Warnings** - Browser blocking HTTP resources loaded from HTTPS page
2. **404 Errors** - API calls going to incorrect paths
3. **Perceived Slowness** - Failed requests appearing as slow performance

## Changes Made

### 1. docker-compose.yml
Updated n8n environment variables:
- `N8N_PROTOCOL`: `http` → `https`
- `N8N_HOST`: `0.0.0.0` → `prosaas.pro`
- Added `WEBHOOK_URL=https://prosaas.pro/n8n/`
- Added `N8N_SECURE_COOKIE=true` (security best practice)

### 2. docker/nginx.conf
Updated `/n8n/` location block:
- Changed `X-Forwarded-Proto` from `$scheme` to explicit `https`
- Added `X-Forwarded-Host $host` header
- Added `X-Forwarded-Prefix /n8n` header

### 3. docker/nginx-ssl.conf
Added complete `/n8n/` location block for production SSL:
- Full proxy configuration with proper headers
- WebSocket upgrade support
- Proper timeouts and buffering settings

## Deployment Instructions

### Step 1: Pull the changes
```bash
git pull origin <branch-name>
```

### Step 2: Recreate the n8n container
```bash
docker compose up -d --force-recreate n8n
```

This will:
- Stop the existing n8n container
- Pull the new configuration
- Start n8n with the correct HTTPS settings

### Step 3: Restart frontend (nginx) if needed
If you're using the SSL configuration, restart the frontend to load the new nginx config:
```bash
docker compose restart frontend
```

### Step 4: Verify the fix

1. **Open browser** and navigate to `https://prosaas.pro/n8n/`
2. **Hard refresh** the page (Ctrl+Shift+R or Cmd+Shift+R on Mac) to clear cache
3. **Check browser console** (F12) - Mixed Content warnings should be gone
4. **Test functionality** - UI should be responsive, no 404 errors in network tab

### Expected Results

✅ No Mixed Content warnings in browser console  
✅ No 404 errors for API calls  
✅ Fast, responsive UI  
✅ Proper HTTPS URLs in network requests  
✅ Secure cookies (if using authentication)

## Troubleshooting

### If still seeing issues after deployment:

1. **Clear browser cache completely**
   - Chrome: Settings → Privacy → Clear browsing data
   - Include "Cached images and files"

2. **Check n8n logs**
   ```bash
   docker logs prosaas-n8n
   ```
   Look for any startup errors or warnings

3. **Verify environment variables**
   ```bash
   docker exec prosaas-n8n env | grep N8N
   ```
   Should show:
   - `N8N_PROTOCOL=https`
   - `N8N_HOST=prosaas.pro`
   - `N8N_PUBLIC_URL=https://prosaas.pro/n8n/`

4. **Check nginx configuration**
   ```bash
   docker exec prosaas-frontend nginx -t
   ```

## Rollback Plan

If issues occur, rollback by reverting the commits:
```bash
git revert <commit-hash>
docker compose up -d --force-recreate n8n
docker compose restart frontend
```

## Technical Details

### Why these changes fix the issue:

1. **N8N_PROTOCOL=https** - Tells n8n to generate HTTPS URLs for all internal links and API calls
2. **N8N_HOST=prosaas.pro** - Sets the correct hostname for URL generation
3. **X-Forwarded-Proto=https** - Informs n8n that the original request was HTTPS
4. **X-Forwarded-Prefix=/n8n** - Tells n8n it's running under a subpath
5. **N8N_SECURE_COOKIE=true** - Ensures cookies have the Secure flag for HTTPS

These settings align n8n's internal URL generation with the actual reverse proxy setup, eliminating the HTTP/HTTPS mismatch.
