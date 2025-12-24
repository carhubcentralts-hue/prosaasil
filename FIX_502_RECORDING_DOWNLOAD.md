# Fix 502 Bad Gateway on Recording Download Endpoint - COMPLETE GUIDE

## בעיה
ה-endpoint `/api/calls/<CallSid>/download` מחזיר 502 Bad Gateway כשמשתמשים מנסים לנגן הקלטות בטאב שיחות יוצאות.

## שורש הבעיה - 5 גורמים קריטיים

### 1. ⚙️ Nginx לא מוגדר לסטרימינג אודיו
- חסר `proxy_buffering off` → Nginx מנסה לשמור את כל הקובץ בזיכרון
- חסר העברת Range headers → נגני iOS/Android לא יכולים לבקש חלקים מהקובץ
- Timeouts קצרים → הבקשה נכשלת לפני שההורדה מטוויליו מסתיימת
- חסר `proxy_http_version 1.1` → בעיות עם keepalive וסטרימינג

### 2. 🎯 חסרה תמיכה ב-206 Partial Content
נגני אודיו (במיוחד iOS Safari) **דורשים** תמיכה ב-Range requests:
- שולחים `Range: bytes=0-1` לבדיקה
- מצפים לקבל `206 Partial Content` עם `Content-Range` header
- בלי זה - הנגן פשוט לא מתחיל או נתקע

### 3. ⏱️ Timeouts לא מסונכרנים
אם Nginx מגדיר `proxy_read_timeout 300s` אבל הbackend (Gunicorn/Uvicorn) רץ עם timeout של 30 שניות:
- Backend יכבה את החיבור אחרי 30 שניות
- Nginx יקבל "upstream prematurely closed connection"
- תוצאה: 502 Bad Gateway

### 4. 🚫 הורדה מטוויליו בזמן Play
**זה המלכודת הגדולה ביותר:**
- אם ה-endpoint מוריד מטוויליו כל פעם שמישהו לוחץ Play
- וטוויליו איטי/לא זמין/API rate limit
- → Backend timeout → Nginx מחזיר 502

**הפתרון:** להוריד הקלטות מראש ב-webhook או worker.

### 5. 💥 חוסר טיפול בשגיאות
אם ה-endpoint קורס על חריגה (exception) במקום להחזיר JSON עם שגיאה:
- Backend לא מחזיר תשובה
- Nginx מחזיר 502

## הפתרון המלא

### 1. Nginx Configuration (`docker/nginx.conf`)

```nginx
# Map for WebSocket Connection upgrade (before server block)
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    # ... existing config ...
    
    location /api/ {
        proxy_pass http://backend:5000/api/;
        
        # 🔥 FIX 502: HTTP/1.1 required for keepalive and streaming
        proxy_http_version 1.1;
        
        # 🔥 FIX 502: Clear Connection header for proper keepalive
        proxy_set_header Connection "";
        
        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        
        # Standard headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 🔥 FIX 502: Audio streaming support
        proxy_buffering off;
        proxy_request_buffering off;
        
        # Pass Range headers for iOS/Android
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        
        # Increase timeouts (MUST match backend timeout!)
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

**למה זה חשוב:**
- `proxy_http_version 1.1` + `Connection ""` → keepalive תקין
- `proxy_buffering off` → סטרימינג ללא שמירה בזיכרון
- Range headers → תמיכה ב-iOS/Android
- Timeouts גבוהים → מספיק זמן להורדה מטוויליו

### 2. Backend Timeout (`Dockerfile.backend`)

```dockerfile
# Uvicorn with proper timeouts
CMD ["uvicorn", "asgi:app", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--ws", "websockets", \
     "--timeout-keep-alive", "75", \
     "--timeout-graceful-shutdown", "30", \
     "--limit-max-requests", "0"]
```

**או עם Gunicorn:**
```dockerfile
CMD ["gunicorn", "wsgi:app", \
     "--bind", "0.0.0.0:5000", \
     "--timeout", "300", \
     "--keep-alive", "75", \
     "--workers", "4"]
```

### 3. Backend - תמיכה ב-206 Partial Content (`server/routes_calls.py`)

הקוד כבר כולל תמיכה מלאה:
- בודק Range header
- מחזיר 206 עם Content-Range
- תומך ב-Accept-Ranges: bytes
- מטפל בשגיאות ללא קריסות

### 4. Pre-download Strategy

**כרגע:** הקלטות מורדות on-demand (fallback מקובל)

**מומלץ להוסיף:** הורדה מראש ב-webhook:

```python
# In webhook handler after recording is ready
@app.route('/webhook/recording-status', methods=['POST'])
def recording_status_callback():
    call_sid = request.form.get('CallSid')
    recording_url = request.form.get('RecordingUrl')
    
    # Download immediately and save locally
    from server.services.recording_service import get_recording_file_for_call
    call = Call.query.filter_by(call_sid=call_sid).first()
    if call:
        get_recording_file_for_call(call)  # Downloads and caches
    
    return Response(status=200)
```

### 5. Error Handling

הקוד כבר כולל:
- Try-except על כל הפעולות הקריטיות
- החזרת JSON במקום קריסה
- לוגים מפורטים לאבחון

## בדיקה ואימות

### הרצת סקריפט הבדיקה

```bash
./verify_502_fix.sh
```

הסקריפט בודק את כל 5 הדברים הקריטיים:
1. ✅ שירותים רצים
2. ✅ Nginx מוגדר נכון
3. ✅ Backend timeout מספיק
4. ✅ תמיכה ב-206 Partial Content
5. ✅ אסטרטגיית הורדה

### בדיקה ידנית עם curl

```bash
# 1. בדוק שה-endpoint עונה
curl -I http://localhost/api/calls/CAxxxx/download

# 2. בדוק תמיכה ב-Range (חייב להחזיר 206!)
curl -I -H "Range: bytes=0-1" http://localhost/api/calls/CAxxxx/download

# Expected output:
# HTTP/1.1 206 Partial Content
# Content-Range: bytes 0-1/12345
# Accept-Ranges: bytes
# Content-Type: audio/mpeg
```

### אבחון 502

אם עדיין יש 502:

**1. בדוק לוגים של Nginx:**
```bash
docker compose logs nginx -n 200 | grep -A 5 "502\|upstream"
```

חפש:
- `connect() failed (111)` → Backend לא זמין
- `upstream prematurely closed` → Backend timeout
- `upstream timed out` → Nginx timeout

**2. בדוק לוגים של Backend:**
```bash
docker compose logs backend -n 300 | grep -A 10 "Download recording"
```

חפש:
- Tracebacks (Python exceptions)
- "Failed to fetch recording"
- Timeout errors

**3. בדוק ישירות את Backend (bypass Nginx):**
```bash
# From host
curl -I http://localhost:5000/api/calls/CAxxxx/download

# From inside nginx container
docker compose exec frontend curl -I http://backend:5000/api/calls/CAxxxx/download
```

אם הראשון עובד והשני נכשל → בעיה ב-Nginx routing
אם שניהם נכשלים → בעיה ב-Backend

## הוראות פריסה

### 1. Rebuild Containers
```bash
docker compose build --no-cache backend frontend
```

### 2. Restart Services
```bash
docker compose restart nginx backend
```

או restart מלא:
```bash
docker compose down
docker compose up -d
```

### 3. בדוק שהכל עובד
```bash
# Health check
curl http://localhost/health

# Test endpoint
curl -I -H "Range: bytes=0-1" http://localhost/api/calls/CAxxxx/download
```

### 4. צפה בלוגים
```bash
# Real-time monitoring
docker compose logs -f nginx backend

# Watch for 502 errors
docker compose logs -f nginx | grep 502

# Watch for download attempts
docker compose logs -f backend | grep "Download recording"
```

## שאלות נפוצות

### ❓ עדיין מקבל 502 אחרי כל התיקונים

1. **בדוק timeout matching:** Nginx timeout ≤ Backend timeout
2. **בדוק שהקלטה קיימת:** `recording_url` לא NULL בדאטאבייס
3. **בדוק Twilio credentials:** TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
4. **בדוק network:** Backend יכול להגיע ל-api.twilio.com

### ❓ iOS עדיין לא מנגן

1. **בדוק 206:** `curl -I -H "Range: bytes=0-1" ...` חייב להחזיר 206
2. **בדוק Content-Type:** חייב להיות `audio/mpeg` או `audio/wav`
3. **בדוק CORS:** אם Frontend בדומיין אחר, צריך CORS headers

### ❓ הורדה מטוויליו איטית/נכשלת

1. **הוסף worker:** הורד הקלטות ב-background
2. **הוסף retry logic:** נסה שוב אם נכשל
3. **שקול S3/GCS:** שמור בcloud storage במקום דיסק מקומי

### ❓ איך לדעת אם ההקלטה נשמרה מקומית?

```bash
# Check recordings directory
docker compose exec backend ls -lh /app/server/recordings/

# Should see *.mp3 files with call_sid as filename
```

## קבצים ששונו

- ✅ `docker/nginx.conf` - הוספת streaming support
- ✅ `Dockerfile.backend` - תיקון timeouts
- ✅ `server/routes_calls.py` - טיפול בשגיאות
- ✅ `server/services/recording_service.py` - resilience
- ✅ `verify_502_fix.sh` - סקריפט בדיקה מקיף

## תיעוד נוסף

- [Twilio Recording API](https://www.twilio.com/docs/voice/api/recording)
- [Nginx Proxy Configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Uvicorn Settings](https://www.uvicorn.org/settings/)
- [HTTP Range Requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)

