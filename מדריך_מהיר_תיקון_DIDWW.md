# תיקון DIDWW/PJSIP - מדריך מהיר לפריסה 🚀

## מה תוקן?

בעיה: שיחות מ-DIDWW התנתקו מיד עם השגיאה "No matching endpoint found"

פתרון: הסרת משתני ENV מ-pjsip.conf והחלפתם בערכים קשיחים

## ✅ 3 נקודות קריטיות אומתו

1. **identify משתמש ב-`match=`** (ולא `ip=`) ✅
2. **from-trunk תופס את כל המספרים** (דפוס `_X.`) ✅  
3. **טיפול ב-External IP** (הוסבר במדריך) ✅

## פריסה מהירה

```bash
# 1. אתחל Asterisk עם הקונפיג החדש
docker-compose -f docker-compose.sip.yml restart asterisk

# חכה 10 שניות
sleep 10

# 2. בדוק endpoints
docker exec -it prosaas-asterisk asterisk -rx 'pjsip show endpoints'

# 3. **קריטי!** בדוק identify
docker exec -it prosaas-asterisk asterisk -rx 'pjsip show identify'
```

## מה צריך להופיע ב-'pjsip show identify'?

```
Identify:  didww-identify/didww
           Match: 46.19.210.14
           Match: 89.105.196.76
           Match: 80.93.48.76
           Match: 89.105.205.76
```

אם זה מופיע - **התיקון עבד!** ✅

## בדיקת שיחה אמיתית

```bash
# התקשר למספר DIDWW שלך ובמקביל הרץ:
docker logs -f prosaas-asterisk
```

### ✅ מה אתה *רוצה* לראות בלוג:

```
INVITE from 46.19.210.14:5060
Matched endpoint 'didww'
Executing [XXX@from-trunk:1]
Stasis("prosaas_ai",...)
```

### ❌ מה אתה *לא רוצה* לראות:

```
No matching endpoint found
Unable to create outbound OPTIONS request
Invalid contact URI
```

## אם יש בעיות

### בעיה: עדיין "No matching endpoint found"

**פתרון:**
1. בדוק שה-IP בלוגים תואם ל-match בקונפיג
2. הוסף IP חדש ל-`infra/asterisk/pjsip.conf`:
   ```ini
   [didww-identify]
   match=NEW_IP_HERE
   ```
3. אתחל שוב

### בעיה: שיחה מתחברת אבל אין אודיו

**פתרון (אם השרת מאחורי NAT):**
1. ערוך `infra/asterisk/pjsip.conf`:
   ```ini
   [transport-udp]
   external_media_address=213.199.43.223      # ה-IP הציבורי שלך
   external_signaling_address=213.199.43.223  # ה-IP הציבורי שלך
   ```
2. אתחל Asterisk

## תזרים השיחה הצפוי

```
DIDWW (46.19.210.14)
    ↓ SIP INVITE
Asterisk PJSIP
    ↓ match IP in [didww-identify]
    ↓ route to endpoint=didww
    ↓ context=from-trunk
Dialplan [from-trunk]
    ↓ Answer()
    ↓ Stasis(prosaas_ai)
ARI Application
    ↓ Bridge + Media Gateway
OpenAI Realtime
    ✅ שיחה עובדת!
```

## תזכורת חשובה

- ❌ אל תוסיף משתני ENV ב-pjsip.conf (Asterisk לא מחליף אותם!)
- ✅ השתמש רק בערכים קשיחים
- ✅ משתני ENV מותרים רק ב-Docker Compose / Scripts

## קבצים רלוונטיים

- `/infra/asterisk/pjsip.conf` - קונפיג PJSIP (תוקן)
- `/infra/asterisk/extensions.conf` - תוכנית חיוג (לא שונה)
- `/verify_3_critical_points.sh` - סקריפט אימות
- `/DIDWW_PJSIP_FIX_COMPLETE.md` - מדריך מלא באנגלית

## סטטוס

🎯 **התיקון מוכן לפריסה!**

כל 3 הנקודות הקריטיות אומתו ועוברות את הבדיקות.

---

**נוצר:** 2025-12-29  
**גרסה:** 1.0  
**סטטוס:** ✅ מאומת ומוכן
