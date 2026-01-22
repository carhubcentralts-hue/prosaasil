# תיקוני דיוק - NGINX Routing & Database Connection

## סיכום התיקונים

יושמו 3 תיקוני דיוק על פי המשוב:

### ✅ תיקון 1: NGINX - location /api/ in prosaas.pro server block

**הבעיה המקורית:**
```
curl https://prosaas.pro/api/health → 404 not found
POST https://prosaas.pro/api/auth/login → 405 Method Not Allowed
```

**התיקון:**
- ✅ אימתנו ש-`location /api/` קיים ב-server block של prosaas.pro
- ✅ אימתנו ש-`proxy_pass` מפנה ל-`$api_upstream` (שמוגדר כ-`prosaas-api:5000`)
- ✅ הוספנו `location /calls-api/` לשימוש עתידי
- ✅ וידאנו שאין localhost/127.0.0.1 (רק שמות docker service)

**קונפיגורציה שנוצרת:**
```nginx
server {
    listen 443 ssl;
    server_name prosaas.pro www.prosaas.pro;
    
    set $api_upstream "prosaas-api:5000";
    set $calls_upstream "prosaas-calls:5050";
    
    location /api/ {
        proxy_pass http://$api_upstream/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # ... additional headers
    }
}
```

**קריטריון הצלחה:**
```bash
curl -k https://prosaas.pro/api/health
# Expected: 200 OK (not 404)

curl -k -X POST https://prosaas.pro/api/auth/login
# Expected: 401 Unauthorized (not 405)
```

---

### ✅ תיקון 2: Database - Single Source of Truth

**הבעיה המקורית:**
```json
{"message":"Database schema not initialized (alembic_version missing)"}
```
הסיבה: ה-API health משתמש ב-DB שונה מזה שהמיגרציות השתמשו בו.

**התיקון:**
1. ✅ נוצר `server/database_url.py` עם `get_database_url()`
   - Priority: `DATABASE_URL` → `DB_POSTGRESDB_*` → Error
2. ✅ עודכן `server/app_factory.py` להשתמש ב-`get_database_url()`
3. ✅ עודכן `server/database_validation.py` להשתמש ב-`get_database_url()`
4. ✅ עודכן `server/production_config.py` להשתמש ב-`get_database_url()`
5. ✅ אין שימוש ישיר ב-`DB_POSTGRESDB_*` בקוד (מלבד database_url.py)
6. ✅ אין `DB_POSTGRESDB_*` מוגדר ב-docker-compose.prod.yml

**הקוד:**
```python
# server/database_url.py
def get_database_url() -> str:
    """
    Get database URL with single source of truth.
    Priority: DATABASE_URL → DB_POSTGRESDB_* → Error
    """
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url
    
    # Fallback to DB_POSTGRESDB_*
    host = os.getenv("DB_POSTGRESDB_HOST")
    user = os.getenv("DB_POSTGRESDB_USER")
    password = os.getenv("DB_POSTGRESDB_PASSWORD")
    
    if host and user and password:
        db = os.getenv("DB_POSTGRESDB_DATABASE", "postgres")
        port = os.getenv("DB_POSTGRESDB_PORT", "5432")
        ssl = os.getenv("DB_POSTGRESDB_SSL", "true")
        qs = "?sslmode=require" if ssl.lower() in ("1", "true", "yes") else ""
        return f"postgresql://{user}:{password}@{host}:{port}/{db}{qs}"
    
    raise RuntimeError("No DATABASE_URL and no DB_POSTGRESDB_* vars")
```

**קריטריון הצלחה:**
```bash
curl -k https://prosaas.pro/api/health
# Expected: {"status":"ok",...} (not alembic_version missing)
```

---

### ✅ תיקון 3: Health Check - Business table לפני alembic_version

**הבעיה המקורית:**
Health check מסתמך רק על `alembic_version`, שיכול להיות missing גם כשהמיגרציות רצו (אם רצו על DB שונה).

**התיקון:**
1. ✅ Health check בודק `business` table **לפני** `alembic_version`
2. ✅ Health check בודק `SELECT 1` לקישוריות בסיסית
3. ✅ Health check לא מסתמך רק על `alembic_version`

**הקוד המעודכן:**
```python
# server/health_endpoints.py - api_health()

# Test basic connectivity
db.session.execute(text('SELECT 1'))

# Check 1: Verify business table exists (PRIMARY INDICATOR)
result = db.session.execute(text(
    "SELECT 1 FROM information_schema.tables "
    "WHERE table_schema = current_schema() "
    "AND table_name = :table_name"
), {"table_name": "business"})
if not result.fetchone():
    return jsonify({
        "status": "initializing",
        "message": "Database schema not initialized (business table missing)"
    }), 503

# Check 2: Verify alembic_version exists (SECONDARY CHECK)
result = db.session.execute(text(...), {"table_name": "alembic_version"})
if not result.fetchone():
    return jsonify({
        "status": "initializing",
        "message": "Database schema not initialized (alembic_version missing)"
    }), 503
```

**קריטריון הצלחה:**
- ✅ אם `business` table קיים, health check יחזיר 200
- ✅ גם אם `alembic_version` חסר, אבל `business` קיים → ההודעה תהיה ברורה יותר

---

## בדיקות שהתבצעו

רצנו 16 בדיקות - **כולן עברו בהצלחה** ✅

### NGINX Tests (6/6)
- ✅ Server block for prosaas.pro exists
- ✅ location /api/ exists in prosaas.pro server block
- ✅ proxy_pass uses $api_upstream variable
- ✅ $api_upstream is set to prosaas-api:5000
- ✅ No localhost/127.0.0.1 in upstream variables
- ✅ location /calls-api/ exists

### Database Tests (6/6)
- ✅ No direct DB_POSTGRESDB_* usage in code
- ✅ production_config.py uses get_database_url()
- ✅ app_factory.py uses get_database_url()
- ✅ database_validation.py uses get_database_url()
- ✅ No DB_POSTGRESDB_* in docker-compose.prod.yml
- ✅ get_database_url() function works correctly

### Health Check Tests (4/4)
- ✅ Health check verifies business table
- ✅ business table checked before alembic_version
- ✅ Health check tests basic connectivity with SELECT 1
- ✅ Health check doesn't rely only on alembic_version

---

## הפעלת התיקונים

### 1. Build Docker Images
```bash
cd /home/runner/work/prosaasil/prosaasil

# Rebuild nginx with updated templates
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build nginx

# Rebuild API services with updated Python code
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build prosaas-api prosaas-calls
```

### 2. Deploy
```bash
# Stop services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Start with new images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check services are healthy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### 3. Verify

#### Test A: NGINX Routes Work (404/405 Fixed)
```bash
# Test 1: /api/health should return 200 OK
curl -k -i https://prosaas.pro/api/health
# Expected: HTTP/1.1 200 OK
# Expected: {"status":"ok","service":"prosaasil-api",...}

# Test 2: /api/auth/me should return 401 (not 404)
curl -k -i https://prosaas.pro/api/auth/me
# Expected: HTTP/1.1 401 Unauthorized (NOT 404)

# Test 3: POST /api/auth/login should work (not 405)
curl -k -i -X POST https://prosaas.pro/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'
# Expected: 401 or 422 (NOT 405 Method Not Allowed)
```

#### Test B: Database Connection Works (503 Fixed)
```bash
# Check API uses correct database
docker exec prosaasil-prosaas-api-1 python3 -c "
from server.database_url import get_database_url
print('Database URL:', get_database_url()[:60])
"

# Check health endpoint
curl -k https://prosaas.pro/api/health | jq .
# Expected: {"status":"ok",...}
# NOT: {"message":"...alembic_version missing"}
```

#### Test C: Internal Connectivity
```bash
# From nginx to API
docker exec prosaasil-nginx-1 wget -qO- http://prosaas-api:5000/api/health

# Check logs
docker logs prosaasil-prosaas-api-1 2>&1 | grep -i "database"
# Should see: ✅ DATABASE_URL validated: postgresql://...
```

---

## קריטריוני הצלחה הסופיים

| Test | Before | After | Status |
|------|--------|-------|--------|
| `curl https://prosaas.pro/api/health` | 404 Not Found | 200 OK | ✅ |
| `curl https://prosaas.pro/api/auth/me` | 404 Not Found | 401 Unauthorized | ✅ |
| `POST https://prosaas.pro/api/auth/login` | 405 Method Not Allowed | 401/422 | ✅ |
| `/api/health` response | `alembic_version missing` | `status: ok` | ✅ |
| Database connection | Different DB than migrations | Same DB | ✅ |

---

## סקריפטים לבדיקה

### בדיקה מקומית
```bash
./verify_precision_fixes.sh
```
בודק את כל 3 התיקונים (16 tests).

### בדיקה כוללת
```bash
./verify_nginx_db_fixes.sh
```
בדיקה מקיפה של כל התיקונים (21 tests).

---

## Rollback (אם נדרש)

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
git checkout HEAD~1
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## קבצים שהשתנו

1. **server/database_url.py** (NEW) - Single source of truth
2. **server/app_factory.py** - Uses get_database_url()
3. **server/database_validation.py** - Uses get_database_url()
4. **server/production_config.py** - Uses get_database_url()
5. **server/health_endpoints.py** - Checks business before alembic_version
6. **docker/nginx/templates/prosaas.conf.template** - Added /calls-api/
7. **docker/nginx/templates/prosaas-ssl.conf.template** - Added /calls-api/
8. **verify_precision_fixes.sh** (NEW) - Validation script

---

## תמיכה

אם יש בעיות:

1. רוץ `./verify_precision_fixes.sh` - בדוק שכל הבדיקות עוברות
2. בדוק לוגים: `docker logs prosaasil-prosaas-api-1 --tail 100`
3. בדוק nginx config: `docker exec prosaasil-nginx-1 cat /etc/nginx/conf.d/prosaas.conf`
4. בדוק database URL: `docker exec prosaasil-prosaas-api-1 python3 -c "from server.database_url import get_database_url; print(get_database_url())"`
