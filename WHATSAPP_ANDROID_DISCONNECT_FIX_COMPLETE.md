# WhatsApp Android Disconnection - Complete Fix

## תיאור הבעיה המקורית

**תסמינים:**
- באייפון: סריקת QR עובדת מצוין ✅
- באנדרואיד: סריקת QR נכשלת עם `logged_out` אחרי דקה ❌
- הלוג מראה: `event: disconnected reason=logged_out`
- לא קשור ל-AgentKit - זה WhatsApp שדוחה את הסשן

## הסיבות שזוהו

### 1. Browser String שגוי 🔴 CRITICAL
**הבעיה:** 
```javascript
browser: ['Chrome (Linux)', 'Chrome', '110.0.5481.100']  // ❌ שגוי!
```

**למה זה גורם לבעיה באנדרואיד:**
- הפורמט: `[OS_NAME, BROWSER_NAME, OS_VERSION]`
- הפרמטר השלישי צריך להיות **גרסת OS** (לא גרסת דפדפן!)
- אנדרואיד בודק את זה בקפדנות, אייפון פחות

**הפתרון:**
```javascript
browser: ['Ubuntu', 'Chrome', '22.04.4']  // ✅ נכון!
```
זה **בדיוק** ברירת המחדל של Baileys שעובדת מושלם.

### 2. Race Condition ב-logged_out 🔴 CRITICAL
**הבעיה:**
```javascript
setTimeout(() => startSession(tenantId, true), 5000);  // ❌ יוצר race!
```

אחרי `logged_out`, הקוד היה מנסה auto-restart, אבל אם המשתמש לוחץ Start במקביל - יש שתי sessions שמתחרות → WhatsApp דוחה אחת מהן.

**הפתרון:**
```javascript
sessions.delete(tenantId);
console.log('User must scan QR again via /start endpoint.');  // ✅ עוצר!
```
אין auto-restart. המשתמש חייב ללחוץ Start מחדש ידנית.

### 3. Clock Drift (שעון לא מסונכרן) ⚠️ IMPORTANT
**הבעיה:**
WhatsApp דורש סנכרון זמן מדויק. הפרש של דקה → `logged_out` אחרי קצת זמן.

**הפתרון:**
```dockerfile
ENV TZ=UTC  # ב-Dockerfile.baileys
```
```yaml
environment:
  TZ: UTC   # ב-docker-compose.yml
```

## מה תוקן

### קבצים שהשתנו

1. **services/whatsapp/baileys_service.js**
   - Browser string תוקן לברירת מחדל של Baileys
   - הוסר auto-restart אחרי logged_out
   - נוספה בדיקת timezone בהפעלה
   - נוספו לוגים מפורטים של statusCode
   - נוסף endpoint `/clock` לבדיקת שעון
   - נוסף פרט clock ב-`/diagnostics`

2. **Dockerfile.baileys**
   - נוסף `ENV TZ=UTC`

3. **docker-compose.yml**
   - נוסף `TZ: UTC` ל-baileys environment

## איך לבדוק שהתיקון עובד

### בדיקה 1: שעון מסונכרן ✅

```bash
# בדיקה מהירה
curl http://localhost:3300/clock

# תוצאה צפויה:
{
  "unix_ms": 1736551234567,
  "iso": "2026-01-10T23:27:14.567Z",
  "timezone": "UTC",
  "is_utc": true,
  "ok": true,
  "warning": null
}
```

אם `ok: false` או יש warning - השעון לא תקין!

### בדיקה 2: Diagnostics מלא 🔍

```bash
curl -H "X-Internal-Secret: your_secret" \
  http://localhost:3300/whatsapp/business_1/diagnostics | jq .
```

בדוק:
- `clock.is_utc: true` ✅
- `clock.warning: null` ✅
- `config.browser_string: ["Ubuntu", "Chrome", "22.04.4"]` ✅

### בדיקה 3: Test עם אנדרואיד 📱

1. **Reset מלא:**
```bash
curl -X POST -H "X-Internal-Secret: your_secret" \
  http://localhost:3300/whatsapp/business_1/reset
```

2. **Start חדש:**
```bash
curl -X POST -H "X-Internal-Secret: your_secret" \
  http://localhost:3300/whatsapp/business_1/start
```

3. **קבל QR:**
```bash
curl -H "X-Internal-Secret: your_secret" \
  http://localhost:3300/whatsapp/business_1/qr
```

4. **סרוק באנדרואיד:**
   - פתח WhatsApp באנדרואיד
   - לך ל-"Linked Devices" → "Link a Device"
   - סרוק את ה-QR
   - **צפוי:** חיבור מצליח בלי logged_out! ✅

5. **בדוק לוגים:**
```bash
docker logs prosaas-baileys --tail 50
```

חפש:
```
[WA] business_1: ✅ Connected AND Paired! pushName=...
```

אם יש disconnect, תראה:
```
[WA-DIAGNOSTIC] business_1: 🔍 DISCONNECT REASON DETAILS:
[WA-DIAGNOSTIC] business_1: - statusCode: 401
[WA-DIAGNOSTIC] business_1: ⚠️ 401 = WhatsApp rejected authentication
```

## פענוח StatusCode

אם יש disconnect, הלוג יראה את ה-statusCode:

| Code | משמעות | פתרון |
|------|---------|-------|
| 401 | WhatsApp דחה authentication | בדוק browser string + שעון |
| 403 | WhatsApp חסם גישה | יתכן חשבון חסום |
| 428 | חיבור נכשל באמצע | בדיקת רשת + timeout |
| 440 | Session הוחלף | מכשיר אחר סרק את אותו QR |
| 515 | WhatsApp מבקש restart | נסה שוב אחרי 5 שניות |

## Troubleshooting

### בעיה: עדיין logged_out באנדרואיד

**בדוק:**

1. **השעון תקין?**
```bash
# בקונטיינר:
docker exec prosaas-baileys date -u

# בהוסט:
date -u

# הפרש צריך להיות < 10 שניות
```

אם יש הפרש גדול → בעיית NTP ב-host. תקן:
```bash
# Linux:
sudo systemctl restart systemd-timesyncd

# בדוק:
timedatectl status
```

2. **Browser string נכון?**
```bash
curl -H "X-Internal-Secret: your_secret" \
  http://localhost:3300/whatsapp/business_1/diagnostics | \
  jq .config.browser_string

# צריך להיות: ["Ubuntu", "Chrome", "22.04.4"]
```

3. **אין race conditions?**
```bash
# בדוק שאין שני calls ל-/start במקביל
docker logs prosaas-baileys | grep "Starting session"

# צריך לראות רק קריאה אחת בכל פעם
```

### בעיה: השעון לא UTC

**Dockerfile עודכן?**
```bash
grep "TZ=UTC" Dockerfile.baileys
# צריך להופיע: ENV TZ=UTC
```

**docker-compose עודכן?**
```bash
grep -A 5 "baileys:" docker-compose.yml | grep TZ
# צריך להופיע: TZ: UTC
```

**Rebuild הקונטיינר:**
```bash
docker-compose build baileys
docker-compose up -d baileys
```

### בעיה: Auth files מלוכלכים

**נקה ידנית:**
```bash
# עצור את הקונטיינר
docker-compose stop baileys

# מחק auth files
rm -rf storage/whatsapp/business_1/auth

# הפעל מחדש
docker-compose up -d baileys

# עכשיו עשה start + סרוק QR
```

## Testing Checklist

לפני deploy לפרודקשן, ודא:

- [ ] `curl localhost:3300/clock` מחזיר `ok: true`
- [ ] Timezone הוא UTC בקונטיינר
- [ ] Browser string הוא `['Ubuntu', 'Chrome', '22.04.4']`
- [ ] אין auto-restart אחרי logged_out
- [ ] Test חיבור מאנדרואיד עובד
- [ ] Test חיבור מאייפון עדיין עובד
- [ ] לוגים מראים statusCode ברור אם יש disconnect

## Summary

**3 התיקונים הקריטיים:**

1. ✅ **Browser string תקין** - `['Ubuntu', 'Chrome', '22.04.4']`
2. ✅ **TZ=UTC** - מונע clock drift
3. ✅ **אין auto-restart** - מונע race conditions

**בונוס:**
- ✅ לוגים מפורטים של statusCode
- ✅ endpoint `/clock` לבדיקת שעון
- ✅ diagnostics משופר עם clock info

**אם כל 3 מתקיימים - אנדרואיד צריך לעבוד מושלם! 🎯**
