# Auth Routing Fix - Complete Documentation

## 🔥 ROOT CAUSE FOUND!

**The Problem:** NGINX `proxy_pass` was configured with a trailing `/api/` which caused double path:
```nginx
❌ WRONG: proxy_pass http://backend:5000/api/;
✅ FIXED: proxy_pass http://backend:5000;
```

**Why it broke:**
- Request: `GET /api/auth/login`
- NGINX with `/api/` suffix sends: `GET /api/api/auth/login` (double!)
- Flask can't find `/api/api/auth/login` → **404/405**

**After fix:**
- Request: `GET /api/auth/login`
- NGINX without suffix sends: `GET /api/auth/login` (correct!)
- Flask finds `/api/auth/login` → **200**

See detailed explanation: [NGINX_PROXY_PASS_BUG_FIX.md](./NGINX_PROXY_PASS_BUG_FIX.md)

---

## Problem Statement

The system was experiencing 404/405 errors on auth endpoints:
- `GET /api/auth/csrf` → 404 (Not Found)
- `GET /api/auth/me` → 404 (Not Found)  
- `POST /api/auth/login` → 405 (Method Not Allowed)

## Root Cause Analysis

After thorough investigation, the **code configuration is correct**:

### ✅ Backend Configuration (Correct)

**File: `server/auth_api.py`**
```python
auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')

@auth_api.get("/csrf")
def get_csrf():
    # Returns CSRF token
    
@auth_api.get("/me") 
def get_current_user():
    # Returns 401 when not authenticated, not 404
    
@csrf.exempt
@auth_api.post("/login")
def login():
    # Accepts POST method
```

**File: `server/app_factory.py`**
```python
from server.auth_api import auth_api
app.register_blueprint(auth_api)  # Registered with url_prefix='/api/auth'
```

### ✅ NGINX Configuration (Correct)

**File: `docker/nginx/templates/prosaas.conf.template`**
```nginx
location /api/ {
    proxy_pass http://$api_upstream/api/;  # Proper trailing slashes
    proxy_http_version 1.1;
    # ... headers ...
}
```

Build-time substitution:
- Dev: `API_UPSTREAM=backend:5000`
- Prod: `API_UPSTREAM=prosaas-api:5000`

### ✅ Frontend Configuration (Correct)

**File: `client/src/services/http.ts`**
```typescript
class HttpClient {
  private baseURL = '/';  // Root URL
  
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;  // /api/auth/login
  }
}
```

**File: `client/src/features/auth/api.ts`**
```typescript
export const authApi = {
  csrf: () => http.get<{ csrfToken: string }>('/api/auth/csrf'),
  me: () => http.get<AuthResponse>('/api/auth/me'),
  login: (data: LoginRequest) => http.post<AuthResponse>('/api/auth/login', data),
}
```

## Why 404/405 Might Still Occur

Even though the code is correct, these errors can occur due to:

1. **Service Not Running**: Backend service (`backend` or `prosaas-api`) not started
2. **NGINX Variable Substitution Failed**: `${API_UPSTREAM}` not replaced at build time
3. **Docker Network Issues**: Services can't communicate via Docker network
4. **Container Not Rebuilt**: Old NGINX container with incorrect config
5. **Port Conflicts**: Service running on wrong port

## Solution: Guardrails

### Guardrail #1: Route Map Audit

**File: `server/app_factory.py`** (added at startup)

```python
# Log all auth routes at startup
logger.info("🔍 [STARTUP] Auth route audit:")
for rule in app.url_map.iter_rules():
    if 'auth' in rule.rule.lower():
        methods = sorted([m for m in rule.methods if m not in ["HEAD", "OPTIONS"]])
        logger.info(f"   ✅ {rule.rule} → methods={methods}")
        
        # Verify critical endpoints
        if rule.rule == '/api/auth/csrf' and 'GET' not in methods:
            logger.error(f"   ❌ CRITICAL: /api/auth/csrf missing GET method!")
```

**Expected Output:**
```
🔍 [STARTUP] Auth route audit:
   ✅ /api/auth/csrf → methods=['GET'] endpoint=auth_api.get_csrf
   ✅ /api/auth/me → methods=['GET'] endpoint=auth_api.get_current_user
   ✅ /api/auth/login → methods=['POST'] endpoint=auth_api.login
   ✅ /api/auth/logout → methods=['POST'] endpoint=auth_api.logout
   ✅ /api/auth/forgot → methods=['POST'] endpoint=auth_api.forgot_password
   ✅ /api/auth/reset → methods=['POST'] endpoint=auth_api.reset_password
   ✅ /api/auth/refresh → methods=['POST'] endpoint=auth_api.refresh_token
   ✅ /api/auth/current → methods=['GET'] endpoint=auth_api.get_current_user_legacy
   ✅ /api/auth/init-admin → methods=['POST'] endpoint=auth_api.init_admin
```

### Guardrail #2: Automated Tests

**File: `test_auth_routing.py`**

Run with: `python test_auth_routing.py`

Tests:
1. ✅ Auth routes are registered
2. ✅ GET /api/auth/csrf returns 200 (not 404)
3. ✅ GET /api/auth/me returns 401 (not 404)
4. ✅ POST /api/auth/login accepts POST (not 405)

### Guardrail #3: Smoke Tests

**File: `smoke_test_auth.sh`**

Run with: `./smoke_test_auth.sh https://prosaas.pro`

Tests:
1. ✅ GET /health → 200
2. ✅ GET /api/auth/csrf → 200
3. ✅ GET /api/auth/me → 401 (not 404)
4. ✅ POST /api/auth/login → 401 (not 405)

## Deployment Checklist

### 1. Verify Docker Compose Configuration

**Dev (`docker-compose.yml`):**
```yaml
nginx:
  build:
    args:
      API_UPSTREAM: backend:5000
      CALLS_UPSTREAM: backend:5000
      FRONTEND_UPSTREAM: frontend
```

**Prod (`docker-compose.prod.yml`):**
```yaml
nginx:
  build:
    args:
      API_UPSTREAM: prosaas-api:5000
      CALLS_UPSTREAM: prosaas-calls:5050
      FRONTEND_UPSTREAM: frontend
```

### 2. Rebuild NGINX Container

```bash
# Rebuild with no cache to ensure variables are substituted
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache nginx

# Restart services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 3. Verify Backend is Running

```bash
# Check backend service
docker compose ps prosaas-api

# Check backend logs
docker compose logs -f prosaas-api | grep "Auth route audit"
```

Expected output:
```
prosaas-api-1 | 🔍 [STARTUP] Auth route audit:
prosaas-api-1 |    ✅ /api/auth/csrf → methods=['GET']
prosaas-api-1 |    ✅ /api/auth/me → methods=['GET']
prosaas-api-1 |    ✅ /api/auth/login → methods=['POST']
```

### 4. Test Auth Endpoints

```bash
# Run smoke tests
./smoke_test_auth.sh https://prosaas.pro
```

Expected output:
```
✅ Testing GET /health ... PASS (200)
✅ Testing GET /api/auth/csrf ... PASS (200)
✅ Testing GET /api/auth/me ... PASS (401)
✅ Testing POST /api/auth/login ... PASS (401)
```

### 5. Verify NGINX Configuration

```bash
# Check NGINX config
docker compose exec nginx cat /etc/nginx/conf.d/prosaas.conf | grep "proxy_pass"
```

Expected output:
```nginx
proxy_pass http://prosaas-api:5000/api/;
proxy_pass http://prosaas-calls:5050;
```

**NOT:**
```nginx
proxy_pass http://${API_UPSTREAM}/api/;  # ❌ Variable not substituted!
```

## Troubleshooting

### Issue: Still Getting 404

**Cause:** Backend service not running or not reachable

**Solution:**
```bash
# Check if backend is running
docker compose ps

# Check backend health
curl http://localhost/api/health

# Check backend logs for errors
docker compose logs prosaas-api
```

### Issue: Still Getting 405

**Cause:** NGINX blocking POST method or wrong route

**Solution:**
```bash
# Test directly to backend (bypass NGINX)
docker compose exec prosaas-api curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test","password":"test"}'

# Should return 401, not 405
```

### Issue: Variable Not Substituted in NGINX

**Cause:** Old NGINX container or build cache

**Solution:**
```bash
# Remove old containers and rebuild
docker compose down
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Acceptance Criteria

System is considered **fixed** when:

- ✅ GET /api/auth/csrf returns 200 (not 404)
- ✅ GET /api/auth/me returns 401 when not authenticated (not 404)
- ✅ POST /api/auth/login returns 401 for invalid credentials (not 405)
- ✅ Login works from UI
- ✅ Route audit shows all auth routes on startup
- ✅ Smoke tests pass

## References

- Backend auth routes: `server/auth_api.py`
- Blueprint registration: `server/app_factory.py:640`
- NGINX config template: `docker/nginx/templates/prosaas.conf.template`
- Docker Compose dev: `docker-compose.yml`
- Docker Compose prod: `docker-compose.prod.yml`
- Frontend API client: `client/src/features/auth/api.ts`
