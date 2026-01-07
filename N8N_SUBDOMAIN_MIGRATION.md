# ✅ n8n Migration to Subdomain - Complete

## מה שונה?

n8n הועבר מ-**subpath** (`https://prosaas.pro/n8n/`) ל-**subdomain** (`https://n8n.prosaas.pro`)

### שינויים טכניים

#### 1. docker-compose.yml
- **גרסה:** שודרג מ-2.2.4 ל-**2.3.1** (גרסה יציבה עדכנית)
- **משתני סביבה:** פושטו ל-6 משתנים בלבד
  - ✅ `N8N_HOST=n8n.prosaas.pro`
  - ✅ `N8N_PROTOCOL=https`
  - ✅ `WEBHOOK_URL=https://n8n.prosaas.pro/`
  - ✅ `N8N_TRUST_PROXY=true`
  - ✅ `N8N_PROXY_HOPS=1`
  - ✅ `NODE_ENV=production`
- **הוסרו:** כל המשתנים הקשורים ל-subpath, DB חיצוני, והצפנה

#### 2. nginx.conf & nginx-ssl.conf
- **הוסרו:** כל ה-location blocks של `/n8n/`, `/n8nstatic/`, `/n8nassets/`
- **נוסף:** Virtual Host ייעודי ל-`n8n.prosaas.pro`
- **הוסר:** `X-Forwarded-Prefix` מכל מקום

---

## איך להפעיל?

### 1. הגדרת DNS
ודא שה-DNS מכוון ל-subdomain:
```
n8n.prosaas.pro  →  [כתובת IP של השרת]
```

### 2. SSL (אם משתמש ב-nginx-ssl.conf)
ודא שיש תעודת SSL ל-subdomain:
```bash
# דוגמה עם certbot
sudo certbot certonly --standalone -d n8n.prosaas.pro
sudo cp /etc/letsencrypt/live/n8n.prosaas.pro/fullchain.pem ./certs/
sudo cp /etc/letsencrypt/live/n8n.prosaas.pro/privkey.pem ./certs/
```

### 3. הפעלת השירותים
```bash
# עצור את השירותים הקיימים
docker compose down

# שלוף את הגרסה החדשה של n8n
docker pull n8nio/n8n:2.3.1

# הפעל מחדש
docker compose up -d

# בדוק לוגים
docker compose logs -f n8n
```

---

## בדיקה

1. **גישה ל-n8n:**
   ```
   https://n8n.prosaas.pro
   ```

2. **בדוק שאין שגיאות:**
   - ✅ אין שגיאות Vue/Store
   - ✅ אין Mixed Content warnings
   - ✅ אין 404 על `/rest/*`
   - ✅ UI נטען מהר ויציב

3. **בדוק webhooks:**
   - Webhooks יהיו בפורמט: `https://n8n.prosaas.pro/webhook/...`
   - **לא** `https://prosaas.pro/n8n/webhook/...`

---

## Troubleshooting

### בעיה: n8n לא עולה
```bash
# בדוק לוגים
docker compose logs n8n

# בדוק שהפורט 5678 פתוח
docker ps | grep n8n
```

### בעיה: SSL לא עובד
```bash
# ודא שהתעודות במקום
ls -la certs/

# ודא שנפתחו הפורטים 80, 443
sudo netstat -tlnp | grep -E ':(80|443)'
```

### בעיה: DNS לא מכוון
```bash
# בדוק DNS resolution
nslookup n8n.prosaas.pro
dig n8n.prosaas.pro
```

---

## הערות חשובות

- ⚠️ **workflows קיימים:** כל ה-workflows יישארו שלמים (שמורים ב-volume `n8n_data`)
- ⚠️ **webhooks חיצוניים:** יש לעדכן כל webhook חיצוני שמפנה ל-URL הישן
- ✅ **גרסה 2.3.1:** גרסה יציבה ועדכנית, מומלצת לפרודקשן
- ✅ **subdomain:** הפתרון המומלץ על ידי n8n לפרודקשן (לא subpath)

---

## Next Steps (אופציונלי)

אחרי שהכל עובד, אפשר להוסיף:

1. **🔐 Security Hardening**
   - Rate limiting
   - Security headers נוספים
   - IP whitelisting

2. **🚀 Performance**
   - Caching
   - Compression optimization
   - Load balancing

3. **🤖 Automation**
   - בניית workflows לאוטומציה
   - אינטגרציה עם מערכות נוספות
