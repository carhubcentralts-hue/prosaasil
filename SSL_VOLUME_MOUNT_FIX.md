# SSL Volume Mount Fix - Implementation Summary

## Problem Analysis

The nginx container was failing to start with SSL errors because:
1. SSL certificate files were not being mounted into the container
2. nginx configuration referenced `/etc/nginx/ssl/prosaas-origin.crt` and `prosaas-origin.key`
3. Files existed on the host but `docker inspect` showed no volume mounts (`[]`)
4. This caused nginx to crash in a restart loop, resulting in connection refused errors

## Root Cause

The docker-compose files were missing critical volume mount configurations:
- `docker-compose.yml` had NO volume mounts for nginx service at all
- `docker-compose.prod.yml` used an absolute path that wouldn't work in all environments
- Without volume mounts, the container couldn't access SSL certificates on the host

## Solution Implemented

### 1. Fixed docker-compose.yml
Added three volume mounts to the nginx service:
```yaml
volumes:
  - ./docker/nginx/conf.d:/etc/nginx/conf.d:ro
  - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
  - ./docker/nginx/ssl:/etc/nginx/ssl:ro
```

**Why this works:**
- Mounts the entire conf.d directory for configuration files
- Mounts the main nginx.conf file
- **Critically:** Mounts the SSL directory where certificates should be placed
- Uses relative paths that work in any environment

### 2. Fixed docker-compose.prod.yml
Removed the absolute path SSL mount:
```yaml
# REMOVED:
- /opt/prosaasil/docker/nginx/ssl:/etc/nginx/ssl:ro

# Instead, inherits from docker-compose.yml:
- ./docker/nginx/ssl:/etc/nginx/ssl:ro
```

**Why this is better:**
- Production inherits the SSL mount from base configuration
- Uses relative path instead of absolute path
- Works consistently across different server setups
- Follows Docker Compose override pattern correctly

### 3. Created SSL Directory Structure
```
docker/nginx/ssl/
├── .gitkeep          # Ensures directory is tracked by git
└── README.md         # Documentation for SSL setup
```

**Certificate files to place here:**
- `prosaas-origin.crt` (SSL certificate)
- `prosaas-origin.key` (private key)

These are excluded by .gitignore to prevent committing sensitive data.

### 4. Verified Configuration Correctness
✅ nginx config paths are correct:
- `/etc/nginx/ssl/prosaas-origin.crt`
- `/etc/nginx/ssl/prosaas-origin.key`

✅ Dockerfile.nginx has NO COPY commands for SSL (correct approach - use volumes)

✅ .gitignore excludes certificate files (`*.crt`, `*.key`, `*.pem`)

## How Volume Mounting Works

When using `docker compose -f docker-compose.yml -f docker-compose.prod.yml`:

1. **Base (docker-compose.yml)** provides:
   - Config directory mount
   - nginx.conf mount
   - SSL directory mount (the critical fix!)

2. **Production (docker-compose.prod.yml)** adds:
   - SSL-specific config file override (prosaas-ssl.conf → prosaas.conf)
   - Inherits all base volume mounts automatically

3. **Result:** nginx container has access to:
   - All configuration files
   - SSL certificates directory
   - Both HTTP and HTTPS configurations work

## Deployment Instructions

### For Local Development (HTTP only)
```bash
# Place certificates if testing with SSL locally
cp your-cert.crt docker/nginx/ssl/prosaas-origin.crt
cp your-key.key docker/nginx/ssl/prosaas-origin.key

# Start services
docker compose up -d
```

### For Production (HTTPS)
```bash
# 1. Obtain SSL certificates from Cloudflare or your provider
# 2. Place them in the repository directory:
cp cloudflare-origin.crt docker/nginx/ssl/prosaas-origin.crt
cp cloudflare-origin.key docker/nginx/ssl/prosaas-origin.key

# 3. Set proper permissions
chmod 644 docker/nginx/ssl/prosaas-origin.crt
chmod 600 docker/nginx/ssl/prosaas-origin.key

# 4. Deploy with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Verification

After deploying, verify the fix:

```bash
# 1. Check that nginx container has volume mounts
docker inspect prosaas-nginx --format '{{json .Mounts}}' | jq

# Should show:
# - conf.d directory mounted
# - nginx.conf mounted
# - ssl directory mounted

# 2. Verify SSL files are accessible inside container
docker exec prosaas-nginx ls -l /etc/nginx/ssl/

# Should show:
# prosaas-origin.crt
# prosaas-origin.key

# 3. Test nginx configuration
docker exec prosaas-nginx nginx -t

# Should output:
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful

# 4. Check nginx is running
curl -I http://localhost/health
curl -Ik https://localhost/health  # If SSL is configured
```

## Why This Fix Works

1. **Volume Mounts Present:** nginx container now has access to host filesystem
2. **Relative Paths:** Works in any environment, not tied to specific server path
3. **Proper Inheritance:** Production configuration inherits and extends base
4. **No Hardcoded Certs:** Certificates are mounted at runtime, not baked into image
5. **Security:** Certificate files excluded from version control

## Impact

✅ nginx will start successfully with SSL certificates mounted  
✅ No more "cannot load certificate" errors  
✅ No more restart loops  
✅ Ports 80/443 will be accessible  
✅ Cloudflare will receive proper responses (no more 521 errors)

## Files Changed

1. `docker-compose.yml` - Added volume mounts
2. `docker-compose.prod.yml` - Removed absolute path, updated docs
3. `docker/nginx/ssl/README.md` - SSL setup documentation
4. `docker/nginx/ssl/.gitkeep` - Directory tracking

## Testing Checklist

- [ ] Deploy to test environment
- [ ] Verify `docker inspect prosaas-nginx` shows volume mounts
- [ ] Verify `/etc/nginx/ssl/` directory exists in container
- [ ] Verify nginx starts without errors
- [ ] Verify HTTP endpoint (port 80) responds
- [ ] Verify HTTPS endpoint (port 443) responds with valid SSL
- [ ] Verify Cloudflare can reach the origin server
- [ ] Monitor nginx logs for SSL errors (should be none)
