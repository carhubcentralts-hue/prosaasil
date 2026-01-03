# מדריך בדיקה ידנית - תיקון איפוס סיסמה ו-is_active

## תיאור הבעיה שתוקנה

### בעיה 1: Reset Token Lookup מסנן לפי is_active
**הבעיה:** הקוד היה מחפש משתמשים עם `is_active=True` בשאילתת הטוקן הראשונית, וכתוצאה מכך:
- משתמש לא פעיל → "no matching user found" (מטעה!)
- לא ניתן היה לדעת אם הבעיה היא טוקן שגוי או משתמש לא פעיל

**התיקון:** עכשיו הקוד:
1. מחפש משתמש לפי הטוקן בלבד (ללא סינון is_active)
2. מוצא את המשתמש → בודק is_active רק אחרי שמצא
3. מחזיר לוג מדויק: `user_inactive` במקום `no matching user`

### בעיה 2: UI מציג "לא פעיל" למרות שהמשתמש פעיל
**הבעיה:** ה-API לא החזיר את שדה `is_active` מה-DB, וה-UI היה מסתמך על שדה `status` מחושב

**התיקון:** 
- כל ה-APIs עכשיו מחזירים `is_active` ישירות מה-DB
- UI משתמש ב-`is_active` כמקור אמת יחיד
- שדה `status` נשאר לתאימות לאחור

### בעיה 3: Frontend עלול לשלוח טוקן ישן
**הבעיה:** Frontend אולי שומר טוקן ב-localStorage או מתחלף בדרך

**התיקון:**
- הוספנו console.log שמראה איזה טוקן נקרא מה-URL
- הוספנו console.log שמראה איזה טוקן נשלח לשרת
- אפשר להשוות בין השניים ולראות אם יש התאמה

---

## בדיקה 1: משתמש לא פעיל מנסה לאפס סיסמה

### שלב 1: יצירת משתמש והפיכתו ללא פעיל

```sql
-- בדוק אם המשתמש קיים
SELECT id, email, is_active FROM users WHERE email = 'test@example.com';

-- אם לא קיים, צור אותו (או השתמש במשתמש קיים)
-- אם קיים, סמן אותו כלא פעיל
UPDATE users SET is_active = false WHERE email = 'test@example.com';

-- וודא שהשינוי עבר
SELECT id, email, is_active FROM users WHERE email = 'test@example.com';
-- צריך להציג: is_active = false
```

### שלב 2: בקש איפוס סיסמה

1. **גש לדף שכחתי סיסמה:** `/forgot-password`
2. **הזן את המייל:** `test@example.com`
3. **שלח בקשה**

**תוצאה מצופה:**
- ✅ הדף יציג הצלחה (גם אם המשתמש לא פעיל - מניעת email enumeration)
- ✅ אבל מייל לא ישלח (כי המשתמש לא פעיל)

**בדוק לוגים בשרת:**
```
[AUTH] password_reset_requested email=test@example.com sent=false (user_not_found or inactive)
```

### שלב 3: אם בכל זאת קיבלת טוקן (למשל מ-DB ישירות)

```sql
-- קבל את הטוקן hash מה-DB
SELECT id, email, reset_token_hash, reset_token_expiry, is_active 
FROM users 
WHERE email = 'test@example.com';
```

אם יש לך את הטוקן המלא (לא רק hash), נסה לאפס סיסמה:

1. **גש ל:** `/reset-password?token=<PLAIN_TOKEN>`
2. **הזן סיסמה חדשה**
3. **שלח**

**תוצאה מצופה:**
- ❌ השרת יחזיר שגיאה: "Invalid or expired token"
- ✅ בלוגים תראה:

```
[AUTH][RESET_DEBUG] found_user_id=11 ... is_active=False
[AUTH] user_inactive user_id=11 - password reset not allowed for inactive users
```

**לפני התיקון היה:**
```
[AUTH] Invalid reset token - no matching user found  (מבלבל!)
```

---

## בדיקה 2: משתמש פעיל מאפס סיסמה (תרחיש רגיל)

### שלב 1: ודא שהמשתמש פעיל

```sql
-- בדוק או עדכן
UPDATE users SET is_active = true WHERE email = 'test@example.com';

SELECT id, email, is_active FROM users WHERE email = 'test@example.com';
-- צריך להציג: is_active = true
```

### שלב 2: בקש איפוס סיסמה

1. **גש ל:** `/forgot-password`
2. **הזן מייל:** `test@example.com`
3. **שלח**

**תוצאה מצופה:**
- ✅ הצלחה
- ✅ מייל נשלח עם לינק

**בדוק לוגים:**
```
[AUTH][RESET_DEBUG] token_generated user_id=11 token_len=43 token_first8=ZQT5kfvx token_last8=abc12345 hash8=dd6ed0c6
[AUTH] password_reset_requested email=test@example.com sent=true
```

### שלב 3: פתח את המייל וקבל את הטוקן

מייל יכיל לינק כמו:
```
https://app.prosaas.co/reset-password?token=ZQT5kfvx...abc12345
```

### שלב 4: לחץ על הלינק ופתח Console בדפדפן

**בדוק ב-Console:**
```
RESET TOKEN FROM URL: ZQT5kfvx...abc12345
RESET TOKEN LENGTH: 43
URL SEARCH PARAMS: ?token=ZQT5kfvx...abc12345
```

✅ **ודא שהטוקן תואם לטוקן שנשלח במייל!**

### שלב 5: הזן סיסמה חדשה ושלח

**תוצאה מצופה:**
- ✅ הצלחה
- ✅ סיסמה התעדכנה

**בדוק Console לפני השליחה:**
```
SUBMITTING RESET - Token first 8 chars: ZQT5kfvx
SUBMITTING RESET - Token last 8 chars: abc12345
SUBMITTING RESET - Token length: 43
```

**בדוק לוגים בשרת:**
```
[AUTH][RESET_DEBUG] got_token=True len=43 first8=ZQT5kfvx last8=abc12345
[AUTH][RESET_DEBUG] found_user_id=11 stored_hash8=dd6ed0c6 computed_hash8=dd6ed0c6 used=False exp=2026-01-03 21:00:00 is_active=True
[AUTH] password_reset_completed user_id=11
```

✅ **ודא שה-first8 וה-last8 תואמים בין Frontend ו-Backend!**

---

## בדיקה 3: בדיקת UI - is_active מוצג נכון

### שלב 1: התחבר כ-system_admin או owner

### שלב 2: גש לדף ניהול משתמשים

**נתיב:** `/users` או דרך התפריט

### שלב 3: בדוק את המשתמשים ברשימה

**ודא:**
- ✅ כל משתמש מציג "פעיל" או "לא פעיל" לפי `is_active` בלבד
- ✅ לא לפי role, plan, או כל שדה אחר

### שלב 4: בדוק ב-Network Tab

1. פתח DevTools → Network
2. מצא את הבקשה: `GET /api/admin/users`
3. בדוק את התשובה:

```json
[
  {
    "id": "11",
    "email": "test@example.com",
    "name": "Test User",
    "role": "agent",
    "is_active": true,    ← צריך להיות כאן!
    "status": "active",   ← זה מחושב מ-is_active
    ...
  }
]
```

✅ **ודא ש-is_active קיים בכל משתמש!**

### שלב 5: שנה סטטוס משתמש

1. לחץ "ערוך" על משתמש
2. שנה את "משתמש פעיל" (סמן/בטל סימון)
3. שמור

**בדוק:**
- ✅ הרשימה מתעדכנת מיד
- ✅ הסטטוס שמוצג תואם ל-checkbox שסימנת

**בדוק ב-DB:**
```sql
SELECT id, email, is_active FROM users WHERE id = 11;
```

✅ **ודא שה-DB מעודכן בהתאם!**

---

## בדיקה 4: התאמת טוקן (אבחון "טוקן מתחלף")

### תסמינים של בעיית טוקן מתחלף:

**בלוגים תראה:**
```
[AUTH][RESET_DEBUG] token_generated ... token_first8=ZQT5kfvx ...
[AUTH][RESET_DEBUG] got_token=True ... first8=-92Q1z5w ...  ← שונה!
```

### איך לאבחן:

1. **בדוק מייל:** תעתיק את הטוקן המלא מהלינק
2. **פתח Console:** תראה מה Frontend מציג
3. **השווה:**
   - אם first8 זהה → הטוקן נכון ✅
   - אם first8 שונה → יש בעיה בטוקן ❌

### סיבות אפשריות לטוקן מתחלף:

- ❌ Frontend שומר טוקן ב-localStorage
- ❌ Redirect מוחק query string
- ❌ Encoding/decoding של הטוקן
- ❌ State management מחליף את הטוקן

### הפתרון שיושם:

```tsx
// ResetPasswordPage.tsx
const token = searchParams.get('token');  // ✅ קורא מה-URL בכל פעם
console.log('RESET TOKEN FROM URL:', token);  // ✅ לוג לאבחון
```

✅ **ודא שאין קריאה מ-localStorage או state management אחר!**

---

## בדיקת אמת SQL

אחרי כל תיקון, הרץ:

```sql
-- בדיקה 1: וודא שיש משתמשים פעילים
SELECT COUNT(*) as active_users FROM users WHERE is_active = true;

-- בדיקה 2: בדוק משתמש ספציפי
SELECT id, email, is_active, role, business_id, last_login 
FROM users 
WHERE id = 11;

-- בדיקה 3: משתמשים עם טוקן reset פעיל
SELECT id, email, is_active, reset_token_hash, reset_token_expiry, reset_token_used
FROM users 
WHERE reset_token_hash IS NOT NULL 
  AND reset_token_expiry > NOW();
```

---

## סיכום - מה צריך לראות אחרי התיקון

### ✅ אם משתמש לא פעיל:
```
[AUTH][RESET_DEBUG] found_user_id=11 ... is_active=False
[AUTH] user_inactive user_id=11
```

### ✅ אם משתמש פעיל:
```
[AUTH][RESET_DEBUG] found_user_id=11 ... is_active=True
[AUTH] password_reset_completed user_id=11
```

### ✅ אם טוקן לא תואם:
```
[AUTH] Invalid reset token - no matching user found
```

### ✅ Frontend מראה טוקן נכון:
```
RESET TOKEN FROM URL: ZQT5kfvx...
SUBMITTING RESET - Token first 8 chars: ZQT5kfvx  ← זהה!
```

### ✅ UI מציג is_active נכון:
- כל API מחזיר `is_active` מה-DB
- UI מציג לפי `is_active` בלבד
- אין חישובים או היסקים אחרים

---

## אם יש בעיה - צעדי פתרון

### בעיה: "Invalid reset token" גם עם משתמש פעיל

**צעדי בדיקה:**
1. בדוק ש-`token_first8` זהה בין המייל ל-Frontend
2. בדוק ש-`token_first8` זהה בין Frontend ל-Backend
3. בדוק שהטוקן לא פג תוקף (60 דקות)
4. בדוק שהטוקן לא שומש (`reset_token_used=false`)

### בעיה: משתמש נראה "לא פעיל" ב-UI אבל פעיל ב-DB

**צעדי פתרון:**
1. בדוק ב-Network Tab ש-`is_active` מגיע מה-API
2. בדוק ב-Console שאין שגיאות JavaScript
3. נקה Cache של הדפדפן
4. התחבר מחדש

### בעיה: מייל לא מגיע

**זה לא קשור לתיקון הזה!** בדוק:
1. Email service configuration
2. SMTP settings
3. Spam folder
