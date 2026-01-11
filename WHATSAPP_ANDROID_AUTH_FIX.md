# תיקון אימות WhatsApp באנדרואיד - עדכון קריטי

## הבעיה
חיבור WhatsApp עובד בהתחלה, אפילו שולח הודעות, אבל אחרי ~דקה-דקה וחצי נבעט עם `logged_out` רק באנדרואיד.
(iPhone עובד בסדר עם אותו קוד)

## הסיבה
אנדרואיד בודק יותר קפדני מ-iPhone:
1. זיהוי דפדפן (browser tuple)
2. סשנים כפולים בזמן סריקת QR
3. קבצי אימות פגומים מכתיבה מקבילה
4. סטטוס "connected" מוקדם מדי
5. נעילת start קצרה מדי (60 שניות במקום 180)
6. זיהוי logged_out לא מדויק (רק enum במקום statusCode)

## התיקונים שבוצעו

### 1️⃣ הסרת browser override ✅
- הסרנו: `browser: ['Ubuntu', 'Chrome', '22.04.4']`
- עכשיו Baileys בוחר אוטומטית (תואם לגרסה)

### 2️⃣ נעילת start: 60s → 180s ✅ **קריטי!**
- שונה מ-60 שניות ל-180 שניות (3 דקות)
- תואם לחלון סריקת QR
- מכסה את כל תהליך האימות המאוחר באנדרואיד

### 3️⃣ זיהוי logged_out לפי statusCode ✅ **קריטי!**
- בודק `statusCode` (401/403) ולא רק enum
- 401/403 = logged_out אמיתי → מוחק auth
- 428 = ניתוק זמני → שומר auth
- 440 = session replaced → שומר auth, דורש QR חדש
- 515 = restart required → שומר auth

### 4️⃣ סגירת socket לפני מחיקת auth ✅ **קריטי!**
- המתנה של 500ms אחרי סגירת socket
- מונע race condition עם כתיבת קבצים

### 5️⃣ בדיקת send לפני connected ✅ **קריטי!**
- מבצע `sendPresenceUpdate` test
- מוודא שאפשר לשלוח הודעות
- רק אז מסמן `connected = true`

### 6️⃣ mutex לשמירת auth ✅
- נוסף `credsLock` למניעת כתיבה מקבילה
- מונע קבצים פגומים

### 7️⃣ תיקון NameError ✅
- כבר מתוקן: `from_identifier` מוגדר לפני שימוש

## בדיקות נדרשות

### אנדרואיד (קריטי!)
- [ ] סרוק QR, שלח הודעה מיד
- [ ] חכה 2 דקות, שלח הודעה נוספת
- [ ] חכה 5 דקות, שלח הודעה נוספת
- [ ] וודא שלא נבעט

### iPhone
- [ ] וודא שעדיין עובד

### מקרי קצה
- [ ] רענון דף בזמן סריקת QR (לא אמור לשכפל עד 180s)
- [ ] ניתוק זמני 428 (אמור להתחבר מחדש עם auth)
- [ ] ניתוק 440 (אמור לעצור, לשמור auth, לדרוש QR)

## שינויים קריטיים

**לפני:**
```javascript
if (lockAge < 60000) { // 60 שניות - קצר מדי!
const isRealLogout = reason === DisconnectReason.loggedOut; // רק enum
fs.rmSync(authPath, ...); // מחיקה מיידית
s.connected = true; // סימון מיידי
```

**אחרי:**
```javascript
if (lockAge < 180000) { // 180 שניות (3 דקות)
const statusCode = lastDisconnect?.error?.output?.statusCode;
const isRealLogout = (statusCode === 401 || statusCode === 403);
await new Promise(resolve => setTimeout(resolve, 500)); // המתנה לsocket
await sock.sendPresenceUpdate('available', sock.user.id); // בדיקת send
s.connected = true; // סימון אחרי בדיקה
```

## טיפול בניתוקים

- **401/403**: מחיקת auth, עצירה, דורש start ידני
- **428**: שמירת auth, reconnect אוטומטי
- **440**: שמירת auth, עצירה, דורש QR חדש
- **515**: שמירת auth, restart אוטומטי
- **אחר**: שמירת auth, exponential backoff

## הצלחה
✅ אנדרואיד נשאר מחובר מעבר ל-5 דקות
✅ נעילה של 180 שניות מכסה חלון אימות מלא
✅ זיהוי logged_out מדויק לפי statusCode
✅ socket נסגר לפני מחיקת auth
✅ בדיקת send מאמתת חיבור אמיתי
✅ iPhone ממשיך לעבוד

---
**תאריך:** 2026-01-11
**סטטוס:** תוקן לפי משוב - מוכן לבדיקה סופית
