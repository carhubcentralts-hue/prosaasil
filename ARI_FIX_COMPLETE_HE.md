# תיקון ARI - prosaas_ai Registration

## ✅ מה תוקן

### 1. **Healthcheck Dependencies (קריטי!)**
```yaml
media-gateway:
  depends_on:
    asterisk:
      condition: service_healthy  # ✅ חובה!
      
backend:
  depends_on:
    asterisk:
      condition: service_healthy  # ✅ חובה!
```

**למה זה קריטי:**
- בלי `service_healthy` → Backend עולה לפני Asterisk מוכן
- ARI WebSocket לא מצליח להתחבר
- Stasis app לא נרשם
- שיחה נכנסת → "Stasis app 'prosaas_ai' not registered" → ניתוק

### 2. **CallLog Fields תוקנו**
```python
# ❌ לפני:
call_log = CallLog(
    tenant_id=tenant_id,          # שדה לא קיים!
    started_at=datetime.utcnow()  # שדה לא קיים!
)

# ✅ אחרי:
call_log = CallLog(
    business_id=tenant_id,        # ✅ שדה קיים
    # created_at מוגדר אוטומטית
)
```

### 3. **Recording Permissions יותר מאובטחות**
```bash
chmod 750  # במקום 755
```

---

## 🔍 איך לבדוק שזה עובד

### שלב 1: הרץ את המערכת
```bash
docker-compose -f docker-compose.sip.yml up -d
```

### שלב 2: בדוק רישום ARI
```bash
./verify_ari_registration.sh
```

או ידנית:
```bash
docker exec -it prosaas-asterisk asterisk -rvvv
```

בתוך Asterisk CLI:
```
stasis show apps
```

**אם הכל תקין תראה:**
```
Name        : prosaas_ai
Debug       : No
Subscriptions:
  0 channels subscribed
  0 bridges subscribed
  0 endpoints subscribed
```

**אם לא רשום:**
```
No Stasis applications found
```

---

## 🔥 תרחיש בדיקה מהיר

### 1. בדוק services רצים:
```bash
docker-compose -f docker-compose.sip.yml ps
```

צריך לראות:
- ✅ `asterisk` - healthy
- ✅ `backend` - running (עלה אחרי asterisk)
- ✅ `media-gateway` - running

### 2. בדוק ARI connection ב-backend logs:
```bash
docker-compose -f docker-compose.sip.yml logs backend | grep ARI
```

צריך לראות:
```
✅ ARI service initialized: app=prosaas_ai
[ARI] ✅ WebSocket connected
```

### 3. בדוק Stasis app רשום:
```bash
docker exec prosaas-asterisk asterisk -rx "stasis show apps"
```

צריך לראות: `prosaas_ai`

---

## ❌ אם עדיין לא עובד

### בעיה: "No Stasis applications found"

**סיבות אפשריות:**

1. **Backend לא הצליח להתחבר ל-ARI:**
   ```bash
   docker logs prosaas-backend 2>&1 | grep -i "ari\|websocket"
   ```
   
   אם רואה: `Connection refused` → בדוק שAsterisk רץ ו-port 8088 פתוח

2. **ARI_APP_NAME לא מוגדר:**
   ```bash
   docker exec prosaas-backend env | grep ARI_APP_NAME
   ```
   
   צריך לראות: `ARI_APP_NAME=prosaas_ai`

3. **Credentials לא תואמים:**
   ```bash
   # בדוק backend:
   docker exec prosaas-backend env | grep ASTERISK_ARI
   
   # בדוק Asterisk config:
   docker exec prosaas-asterisk cat /etc/asterisk/ari.conf
   ```
   
   Username/Password חייבים להיות זהים!

---

## 📝 Checklist מלא

- [ ] `docker-compose.sip.yml` מעודכן עם `condition: service_healthy`
- [ ] Backend ו-media-gateway מוגדרים עם `ARI_APP_NAME=prosaas_ai`
- [ ] `.env` מכיל `ASTERISK_ARI_PASSWORD` (אותו ב-ari.conf)
- [ ] `docker-compose up` מצליח לכל השירותים
- [ ] `stasis show apps` מציג `prosaas_ai`
- [ ] Backend logs מציג "ARI WebSocket connected"

---

## 🎯 מה אמור לקרות אחרי התיקונים

1. **Asterisk עולה ראשון** → healthcheck עובר
2. **Backend מחכה ל-Asterisk** → depends_on מבטיח זאת
3. **Backend מתחבר ל-ARI WebSocket** → `ws://asterisk:8088/ari/events?app=prosaas_ai`
4. **Stasis app נרשם** → Asterisk רואה את `prosaas_ai`
5. **שיחה נכנסת** → `Stasis(prosaas_ai, ...)` עובד
6. **CallLog נוצר** → `/internal/calls/start` מתקבל
7. **AI מדברת** → Media Gateway מקבל RTP

---

## 🚀 כל מה שצריך להריץ

```bash
# 1. עדכן קבצים (כבר עשית)
git pull origin copilot/register-ari-app-prosaas-ai

# 2. הרץ מחדש עם התיקונים
docker-compose -f docker-compose.sip.yml down
docker-compose -f docker-compose.sip.yml up -d

# 3. בדוק רישום ARI (חכה 30 שניות)
sleep 30
./verify_ari_registration.sh

# 4. אם רואה "prosaas_ai" → מוכן לשיחות! 🎉
```

---

## 💡 טיפ פרודקשן

אחרי שזה עובד, הוסף monitoring:

```bash
# בדיקה אוטומטית שStasis app רשום
docker exec prosaas-asterisk asterisk -rx "stasis show apps" | grep -q prosaas_ai && echo "✅ OK" || echo "❌ FAILED"
```

הוסף ל-cron job או healthcheck שלך.
