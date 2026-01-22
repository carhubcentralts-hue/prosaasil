# 🔥 ROOT CAUSE: NGINX proxy_pass Double Path Bug

## הבעיה המדויקת

**שורה אחת גרמה לכל השגיאות 404/405:**

```nginx
❌ WRONG:
location /api/ {
    proxy_pass http://backend:5000/api/;
}
```

### למה זה שובר הכל?

כאשר NGINX מקבל request ל-`/api/auth/login`:

1. NGINX תופס את ה-location block `/api/`
2. NGINX **מסיר** את ה-prefix `/api/` מה-path
3. נשאר: `/auth/login`
4. NGINX **מוסיף** את זה ל-proxy_pass
5. תוצאה: `http://backend:5000/api/` + `auth/login` = `http://backend:5000/api/auth/login`

**אבל!** אם proxy_pass כולל path (`/api/`), NGINX **לא מסיר** את ה-prefix!

התוצאה האמיתית:
- Request: `GET /api/auth/csrf`
- NGINX שולח: `GET /api/api/auth/csrf` (double!)
- Flask מחפש: `/api/api/auth/csrf`
- Flask לא מוצא → **404**

## התיקון הנכון

```nginx
✅ CORRECT:
location /api/ {
    proxy_pass http://backend:5000;
}
```

עכשיו:
- Request: `GET /api/auth/csrf`
- NGINX שולח: `GET /api/auth/csrf` (correct!)
- Flask מוצא: `/api/auth/csrf` → **200**

## Documentation מ-NGINX

מתוך [NGINX documentation](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass):

> If the proxy_pass directive is specified with a URI, then when a request is passed to the server, 
> the part of a normalized request URI matching the location is **replaced** by the URI specified in the directive.

```nginx
location /name/ {
    proxy_pass http://127.0.0.1/remote/;  # WITH URI - replaces /name/ with /remote/
}

location /name/ {
    proxy_pass http://127.0.0.1;  # NO URI - appends full path
}
```

## למה זה היה קשה לגלות?

1. **Flask health endpoint עבד** - כי הוא לא תחת `/api/`:
   ```
   GET /health → Flask /health ✅
   ```

2. **הלוגים לא הראו את זה** - כי Flask מדפיס רק מה שהוא מקבל:
   ```
   Flask log: "GET /api/api/auth/csrf HTTP/1.1" 404
   ```
   נראה כמו באג ב-Flask, לא ב-NGINX!

3. **curl ישיר ל-backend עבד**:
   ```bash
   curl http://localhost:5000/api/auth/csrf  # ✅ 200
   ```
   כי bypass NGINX!

## הקבצים שתוקנו

1. ✅ `docker/nginx/templates/prosaas.conf.template`
2. ✅ `docker/nginx/templates/prosaas-ssl.conf.template`
3. ✅ `docker/nginx.conf`
4. ✅ `docker/nginx-ssl.conf`

## איך לוודא שהתיקון עובד

### Option 1: בדיקה פנימית (בתוך Docker)

```bash
# Login to nginx container
docker exec -it prosaasil-nginx-1 sh

# Check config (must NOT have /api/ suffix!)
cat /etc/nginx/conf.d/*.conf | grep -A2 "location /api/"

# Expected:
# location /api/ {
#     proxy_pass http://prosaas-api:5000;  ← NO /api/ suffix!

# Test from nginx to backend directly
wget -qO- http://prosaas-api:5000/api/auth/csrf
# Expected: {"csrfToken":"..."}
```

### Option 2: בדיקה חיצונית (production)

```bash
# Rebuild nginx with new config
docker compose build --no-cache nginx
docker compose restart nginx

# Run verification
./verify_auth_endpoints.sh https://prosaas.pro

# Expected output:
# ✅ Testing GET /api/auth/csrf ... PASS (200)
# ✅ Testing GET /api/auth/me ... PASS (401)
# ✅ Testing POST /api/auth/login ... PASS (401)
```

## Guardrail להבא

הוספנו script אוטומטי: `verify_auth_endpoints.sh`

הוסף לזה ל-CI/CD pipeline:

```yaml
# .github/workflows/deploy.yml
- name: Verify Auth Endpoints
  run: ./verify_auth_endpoints.sh https://prosaas.pro
  # If exit code != 0, deployment fails
```

או manually לפני כל deploy:

```bash
./verify_auth_endpoints.sh https://prosaas.pro || echo "❌ CANNOT DEPLOY"
```

## תסמינים שזה התיקון הנכון

אחרי deploy עם התיקון:

- ✅ `GET /api/auth/csrf` → **200** (לא 404)
- ✅ `GET /api/auth/me` → **401** (לא 404)
- ✅ `POST /api/auth/login` → **401** (לא 405)
- ✅ UI יכול להתחבר
- ✅ Baileys מפסיק לצעוק על auth errors

## Summary

**The Problem:**
```nginx
proxy_pass http://backend:5000/api/;  ← This /api/ suffix breaks everything
```

**The Fix:**
```nginx
proxy_pass http://backend:5000;  ← Remove the /api/ suffix
```

**The Result:**
- Request: `/api/auth/login`
- NGINX sends: `/api/auth/login` (not `/api/api/auth/login`)
- Flask receives correct path → **Works!**

---

**זה היה באג של NGINX configuration, לא של Flask, לא של auth, לא של DB.**

**שורה אחת. תיקון של 5 שניות. סובלנות של שעות.**
