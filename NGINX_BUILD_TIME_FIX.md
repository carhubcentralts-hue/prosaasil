# Nginx Build-Time Templating Fix - Production Safe ✅

## תקציר (Hebrew Summary)

**הבעיה**: nginx נפל בלופ אינסופי כי ניסה להריץ `envsubst` בזמן runtime וכתב ל-`/etc/nginx/conf.d` שהוא Read-Only.

**הפתרון**: העברנו את כל ה-templating לזמן BUILD - לא runtime.

**התוצאה**: nginx יציב, לא כותב לדיסק בזמן ריצה, והכול נאפה פנימה בזמן בניית התמונה.

---

## Root Cause

nginx was failing in a restart loop because:
1. The entrypoint script ran `envsubst` at **runtime**
2. It tried to write to `/etc/nginx/conf.d` which is **read-only** (security hardening)
3. This caused nginx to crash repeatedly

Result:
- ❌ nginx restart loop
- ❌ No port 80/443 listener
- ❌ Cloudflare 521 errors
- ❌ Site down

---

## Solution: Build-Time Templating

### The Correct Architecture

**Before (BROKEN)**:
```
Docker Build → Copy templates → Start Container → 
  Run entrypoint → envsubst → Write to /etc/nginx/conf.d (FAILS - Read-Only)
```

**After (CORRECT)**:
```
Docker Build → Copy templates → ARG→ENV → envsubst → 
  Bake configs into image → Start Container → nginx just runs ✅
```

### Key Principle

**🔥 Golden Rule**: Never render nginx config at runtime. Always at BUILD time.

---

## Critical Implementation Details

### 1. gettext/envsubst Availability ✅

**Issue**: `envsubst` may not exist in all nginx:alpine versions.

**Solution**:
```dockerfile
# Try to install, fallback to verify if already exists
RUN apk add --no-cache gettext || \
    (echo "⚠️  gettext install failed, verifying envsubst exists..." && \
     which envsubst && echo "✅ envsubst found, continuing...")
```

This ensures envsubst is ALWAYS available, preventing silent failures.

### 2. ARG → ENV Conversion ✅

**Issue**: `envsubst` can only see ENV variables, not ARG.

**Solution**:
```dockerfile
# Define build arguments
ARG API_UPSTREAM=backend
ARG API_PORT=5000

# CRITICAL: Convert to ENV for envsubst access
ENV API_UPSTREAM=${API_UPSTREAM} \
    API_PORT=${API_PORT}

# Now envsubst can see these variables
RUN envsubst '${API_UPSTREAM} ${API_PORT}' < template.conf > /etc/nginx/conf.d/nginx.conf
```

**Without this**: Variables would be empty → `proxy_pass http://:;` → nginx fails silently.

### 3. Sanity Checks ✅

**Critical verification** during build:
```dockerfile
RUN grep -q "proxy_pass http://" /etc/nginx/conf.d/prosaas.conf && \
    ! grep -q "proxy_pass http://:;" /etc/nginx/conf.d/prosaas.conf || \
    (echo "❌ Config substitution FAILED" && exit 1)
```

This **fails the build** if substitution didn't work. Better to fail at build than in production!

---

## File Structure

```
docker/nginx/
├── templates/                    # NEW: Template files
│   ├── prosaas.conf.template    # HTTP config template
│   ├── prosaas-ssl.conf.template # HTTPS config template
│   └── 00-health.conf.template  # Health check config
├── conf.d/                      # OLD: Keep for reference only
│   └── ...
├── nginx.conf                   # Main nginx config (unchanged)
└── ssl/                        # SSL certificates (mounted read-only)
```

---

## Docker Compose Configuration

### Development (HTTP)
```yaml
nginx:
  build:
    context: .
    dockerfile: Dockerfile.nginx
    args:
      API_UPSTREAM: backend      # Single monolith
      API_PORT: "5000"
      USE_SSL: "false"           # HTTP only
```

### Production (HTTPS + Split Services)
```yaml
nginx:
  build:
    context: .
    dockerfile: Dockerfile.nginx
    args:
      API_UPSTREAM: prosaas-api       # Separate API service
      CALLS_UPSTREAM: prosaas-calls   # Separate Calls service
      CALLS_PORT: "5050"
      USE_SSL: "true"                  # HTTPS with SSL
  volumes:
    - ./docker/nginx/ssl:/etc/nginx/ssl:ro  # SSL certs read-only
```

---

## Build Process

1. **Copy templates** to `/templates/` in image
2. **Set ARG values** from docker-compose build args
3. **Convert ARG → ENV** so envsubst can access them
4. **Run envsubst** on templates → generate final configs in `/etc/nginx/conf.d/`
5. **Verify substitution** worked (sanity check)
6. **Clean up** templates (no longer needed)
7. **nginx starts** with pre-baked configuration

---

## Validation

### Build-Time Checks

```bash
# Run validation script
./scripts/validate_compose.sh

# It checks:
# 1. Compose files merge correctly ✅
# 2. Upstream services exist ✅
# 3. Nginx image builds ✅
# 4. Config files generated ✅
# 5. Variable substitution worked ✅
```

### Manual Verification

```bash
# Check generated config
docker run --rm prosaasil-nginx-test cat /etc/nginx/conf.d/prosaas.conf | grep proxy_pass

# Should see:
# proxy_pass http://prosaas-api:5000;
# proxy_pass http://prosaas-calls:5050;

# NOT:
# proxy_pass http://:;  ❌
```

---

## Deployment

### Development
```bash
docker compose --profile dev up -d
```

### Production
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

**Note**: `--build` is important to ensure latest config is baked in.

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| nginx doesn't run envsubst at runtime | ✅ |
| nginx config generated at build time | ✅ |
| gettext/envsubst verified available | ✅ |
| ARG → ENV conversion working | ✅ |
| Sanity checks prevent broken deploys | ✅ |
| No runtime filesystem writes | ✅ |
| DEV uses HTTP config | ✅ |
| PROD uses SSL config | ✅ |
| Validation script enhanced | ✅ |
| Healthcheck uses curl | ✅ |

---

## Post-Deployment Verification

After deploying, verify:

```bash
# 1. nginx is running (not restarting)
docker ps | grep nginx

# 2. No envsubst errors in logs
docker logs nginx 2>&1 | grep -i envsubst
# Should be empty

# 3. Port 80/443 listening
ss -tulpn | grep :80
ss -tulpn | grep :443

# 4. Health check works
curl -I http://localhost/health
# Should return 200 OK

# 5. Site is accessible
curl -I https://prosaas.pro
# Should return 200/301/302 (not 521)
```

---

## Troubleshooting

### Build fails with "envsubst: command not found"

**Cause**: gettext not installed and envsubst not in base image.

**Fix**: Ensure gettext installation succeeds. Check Alpine repo access.

### Build succeeds but nginx has empty upstreams

**Cause**: ARG → ENV conversion missing.

**Verification**: Sanity check should have caught this and failed the build.

### nginx starts but can't reach backends

**Cause**: Wrong upstream service names in build args.

**Fix**: Verify docker-compose build args match service names.

---

## References

- Original issue description (Hebrew)
- Code review feedback
- Docker build-time vs runtime best practices

---

**Status**: ✅ PRODUCTION READY

**Last Updated**: 2026-01-21

**Contributors**: carhubcentralts-hue, GitHub Copilot
