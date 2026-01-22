# Deployment Guide: NGINX Routing and Database URL Fixes

## Overview

This deployment fixes two critical issues:

### Issue 1: NGINX Routing
**Problem:** The `/api/` routes were returning 404/405 errors when accessed through the domain, even though direct access from within nginx worked.

**Solution:** 
- Verified nginx templates properly use `${API_UPSTREAM}` and `${CALLS_UPSTREAM}` variables
- Added explicit `/calls-api/` location block for future use
- Ensured all proxy headers are correctly set

### Issue 2: Database Connection
**Problem:** The API health check was connecting to a different database than where migrations ran, causing "alembic_version missing" errors.

**Solution:**
- Created `server/database_url.py` with `get_database_url()` function
- Implements single source of truth: prioritizes `DATABASE_URL`, falls back to `DB_POSTGRESDB_*`
- Updated `app_factory.py` and `database_validation.py` to use the unified function

## Files Changed

1. **server/database_url.py** (NEW)
   - Single source of truth for database URL
   - Priority: DATABASE_URL → DB_POSTGRESDB_* → Error

2. **server/app_factory.py**
   - Updated to use `get_database_url()`
   - Both `create_minimal_app()` and `create_app()` updated

3. **server/database_validation.py**
   - Updated to use `get_database_url()`
   - Now supports fallback configuration

4. **docker/nginx/templates/prosaas.conf.template**
   - Added `/calls-api/` location block
   - Verified `/api/` routing to `${API_UPSTREAM}`

5. **docker/nginx/templates/prosaas-ssl.conf.template**
   - Added `/calls-api/` location block
   - Verified `/api/` routing to `${API_UPSTREAM}`

## Deployment Steps

### Step 1: Verify Current State

```bash
# Check current nginx configuration
docker exec prosaasil-nginx-1 cat /etc/nginx/conf.d/prosaas.conf | grep -A 5 "location /api/"

# Check current database connectivity
docker exec prosaasil-prosaas-api-1 env | grep DATABASE_URL
```

### Step 2: Rebuild Docker Images

The nginx configuration is baked in at build time, so you need to rebuild:

```bash
# Rebuild nginx with updated templates
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build nginx

# Rebuild API service with updated Python code
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build prosaas-api prosaas-calls
```

### Step 3: Deploy

```bash
# Stop services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Start with new images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Wait for services to be healthy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### Step 4: Verify Deployment

#### Test 1: NGINX Routes Work

```bash
# Test /api/health from outside (should return 200 OK)
curl -k -i https://prosaas.pro/api/health

# Expected response:
# HTTP/1.1 200 OK
# {"status":"ok","service":"prosaasil-api",...}

# Test /api/auth/me (should not return 404)
curl -k -i https://prosaas.pro/api/auth/me

# Expected: 401 Unauthorized (not 404)
```

#### Test 2: Database Connection Works

```bash
# Check API logs for database connection
docker logs prosaasil-prosaas-api-1 2>&1 | grep -i "database"

# Should see:
# ✅ DATABASE_URL validated: postgresql://...

# Test health endpoint shows DB is ready
curl -k https://prosaas.pro/api/health | jq .

# Should return:
# {
#   "status": "ok",
#   "service": "prosaasil-api",
#   "timestamp": "..."
# }
```

#### Test 3: Internal Connectivity

```bash
# From nginx to API
docker exec prosaasil-nginx-1 wget -qO- http://prosaas-api:5000/api/health

# From API to database (check it connects)
docker exec prosaasil-prosaas-api-1 python3 -c "
from server.database_url import get_database_url
print('Database URL:', get_database_url()[:50] + '...')
"
```

## Rollback Plan

If deployment fails:

```bash
# Quick rollback
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
git checkout HEAD~1
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build nginx prosaas-api prosaas-calls
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Environment Variables

### Production Environment

Ensure you have either:

**Option A: DATABASE_URL (Preferred)**
```env
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
```

**Option B: DB_POSTGRESDB_* (Fallback)**
```env
DB_POSTGRESDB_HOST=your-db-host
DB_POSTGRESDB_USER=your-db-user
DB_POSTGRESDB_PASSWORD=your-db-password
DB_POSTGRESDB_DATABASE=your-database
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_SSL=true
```

### NGINX Build Arguments

The following are set in `docker-compose.prod.yml`:
```yaml
API_UPSTREAM: prosaas-api:5000
CALLS_UPSTREAM: prosaas-calls:5050
FRONTEND_UPSTREAM: frontend
USE_SSL: "true"
```

## Troubleshooting

### Issue: Still getting 404 on /api/ routes

**Cause:** Nginx container was not rebuilt

**Solution:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache nginx
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
```

### Issue: "alembic_version missing" error

**Cause:** Database connection string mismatch

**Solution:**
```bash
# Check which database URL is being used
docker exec prosaasil-prosaas-api-1 python3 -c "
from server.database_url import get_database_url
print(get_database_url())
"

# Ensure DATABASE_URL points to the same database where migrations ran
```

### Issue: 503 Service Unavailable

**Cause:** Backend service not healthy yet

**Solution:**
```bash
# Check service health
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Check logs
docker logs prosaasil-prosaas-api-1 --tail 100

# Wait for migrations to complete
docker logs prosaasil-prosaas-api-1 2>&1 | grep -i "migration"
```

## Success Criteria

✅ `curl -k https://prosaas.pro/api/health` returns 200 OK  
✅ `curl -k https://prosaas.pro/api/auth/me` returns 401 (not 404)  
✅ POST `https://prosaas.pro/api/auth/login` returns 401 or 422 (not 405)  
✅ API logs show "DATABASE_URL validated"  
✅ `/api/health` does not return "alembic_version missing"  

## Support

If you encounter issues during deployment:

1. Check the verification script output: `./verify_nginx_db_fixes.sh`
2. Review Docker logs: `docker logs prosaasil-prosaas-api-1`
3. Test nginx config: `docker exec prosaasil-nginx-1 nginx -t`
4. Review this guide's troubleshooting section

## Related Documentation

- NGINX configuration: `docker/nginx/templates/`
- Database setup: `server/database_url.py`
- Health checks: `server/health_endpoints.py`
