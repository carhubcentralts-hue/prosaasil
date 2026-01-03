# תיקון ניפוי שגיאות - איפוס סיסמה

## הבעיה שדווחה
- המייל נשלח בהצלחה ✅
- אבל ה-backend אומר: `[AUTH] Invalid reset token` ❌
- כלומר: הטוקן שמגיע לשרת לא תואם לטוקן שנשמר ב-DB

## מה עשינו - פתרון מלא בהתאם להנחיות

### 1. הוספת לוגים מפורטים (✅ הושלם)

#### א. לוג בזמן יצירת טוקן (`/api/auth/forgot`)
```python
logger.warning(
    "[AUTH][RESET_DEBUG] token_generated user_id=%s token_len=%s token_first8=%s token_last8=%s hash8=%s",
    user.id,
    len(plain_token),
    plain_token[:8],
    plain_token[-8:],
    token_hash[:8]
)
```

**מה זה מראה:** את הטוקן שנוצר ונשלח במייל (8 תווים ראשונים ואחרונים), האורך שלו, וה-hash שנשמר ב-DB.

#### ב. לוג בזמן קבלת הטוקן (`/api/auth/reset`)
```python
logger.warning(
    "[AUTH][RESET_DEBUG] got_token=%s len=%s first8=%s last8=%s keys=%s args=%s",
    bool(token),
    len(token) if token else None,
    token[:8] if token else None,
    token[-8:] if token else None,
    list((request.json or {}).keys()),
    dict(request.args) if request.args else {}
)
```

**מה זה מראה:**
- האם הטוקן הגיע בכלל (`got_token=True/False`)
- מה האורך שלו
- איזה תווים ראשונים ואחרונים (כדי להשוות למייל)
- באיזה שדות הוא הגיע (`keys=['token', 'password']`)
- האם הוא הגיע ב-query params במקום JSON (`args=...`)

#### ג. לוג בזמן ולידציה
```python
logger.warning(
    "[AUTH][RESET_DEBUG] stored_hash8=%s computed_hash8=%s used=%s exp=%s",
    (user.reset_token_hash or "")[:8],
    (token_hash or "")[:8],
    user.reset_token_used,
    user.reset_token_expiry
)
```

**מה זה מראה:**
- האם ה-hash השמור ב-DB תואם לחישוב מהטוקן שהתקבל
- האם הטוקן כבר שומש (`used=True`)
- מתי הטוקן פג תוקף

### 2. שיפור קבלת הטוקן (✅ הושלם)

הוספנו תמיכה לקבלת הטוקן גם מ-query params וגם מ-JSON body:
```python
token = (request.json or {}).get('token') or (request.args or {}).get('token')
```

**למה:** למקרה שה-frontend שולח את הטוקן בטעות בשני מקומות.

### 3. וידוא שהמימוש נכון (✅ אומת)

בדקנו שהקוד קיים תואם להמלצות:
- ✅ יצירת טוקן: `secrets.token_urlsafe(32)` - מייצר 43 תווים של base64url
- ✅ Hash: `hashlib.sha256(token.encode('utf-8')).hexdigest()` - SHA-256 של string
- ✅ אותו טוקן נשלח במייל ונשמר כ-hash ב-DB
- ✅ Frontend שולח `{ token, password }` בדיוק כמו שצריך
- ✅ אין endpoint של GET שמבטל את הטוקן - רק POST

### 4. בדיקות שרצו (✅ עבר)

יצרנו בדיקה עצמאית שמאמתת:
- ✅ `secrets.token_urlsafe` מייצר טוקנים תקינים
- ✅ ה-hash דטרמיניסטי (אותו טוקן = אותו hash)
- ✅ Round-trip עובד: יצירה → hash → ולידציה
- ✅ הטוקן URL-safe (אין +, /, =)

## איך להשתמש בלוגים לאבחון

### תרחיש 1: הטוקן לא מגיע
```
[AUTH][RESET_DEBUG] got_token=False len=None first8=None last8=None keys=['password'] args={}
```
**אבחנה:** Frontend לא שולח את השדה `token` בכלל.
**פתרון:** לבדוק ב-Frontend ש-`ResetPasswordPage.tsx` שולח את הטוקן.

### תרחיש 2: הטוקן מגיע אבל באורך שגוי
```
[AUTH][RESET_DEBUG] got_token=True len=35 first8=abc12345 last8=xyz98765 keys=['token', 'password'] args={}
```
**אבחנה:** הטוקן נחתך/שונה בדרך.
**פתרון:** לבדוק encoding/URL encoding בדרך.

### תרחיש 3: הטוקן מגיע אבל ה-hash לא תואם
```
[AUTH][RESET_DEBUG] stored_hash8=a1b2c3d4 computed_hash8=e5f6g7h8 used=False exp=2026-01-03 20:16:00
```
**אבחנה:** הטוקן שמגיע שונה מהטוקן שנשלח במייל.
**פתרון:** להשוות את ה-`first8` וה-`last8` מהלוג הקודם ללוג של יצירת הטוקן.

### תרחיש 4: הטוקן כבר שומש
```
[AUTH][RESET_DEBUG] stored_hash8=a1b2c3d4 computed_hash8=a1b2c3d4 used=True exp=2026-01-03 20:16:00
```
**אבחנה:** הטוקן כבר שומש פעם אחת.
**פתרון:** זה תקין! המשתמש צריך לבקש טוקן חדש.

### תרחיש 5: הטוקן פג תוקף
```
[AUTH][RESET_DEBUG] stored_hash8=a1b2c3d4 computed_hash8=a1b2c3d4 used=False exp=2026-01-03 18:00:00
```
(והשעה הנוכחית: 19:16)
**אבחנה:** הטוקן פג תוקף (60 דקות).
**פתרון:** זה תקין! המשתמש צריך לבקש טוקן חדש.

## מה הלאה

1. **לפרוס את הגרסה הזו לפרודקשן**
2. **לנסות איפוס סיסמה ולתפוס את הלוגים**
3. **בהתאם ללוגים - נדע בדיוק מה הבעיה:**
   - Frontend לא שולח נכון
   - הטוקן משתבש בדרך
   - בעיית encoding
   - בעיית DB

## קבצים ששונו

1. `server/auth_api.py` - הוספת לוגים ב-endpoint של `/api/auth/reset`
2. `server/services/auth_service.py` - הוספת לוגים ב-`generate_password_reset_token` וב-`validate_reset_token`
3. `MANUAL_TESTING_GUIDE_PASSWORD_RESET.md` - עדכון מדריך הבדיקות עם הלוגים החדשים

## הערות חשובות

- הלוגים משתמשים ב-`logger.warning` כדי שיופיעו בפרודקשן (לא רק ב-DEBUG mode)
- הלוגים מציגים רק 8 תווים ראשונים ואחרונים (לא את הטוקן המלא) - לאבטחה
- אפשר להסיר את הלוגים אחרי שתפסו את הבעיה

## בטיחות

- ✅ אין חשיפה של טוקן מלא בלוגים
- ✅ רק 8 תווים ראשונים/אחרונים
- ✅ לא חושפים אם המייל קיים או לא (email enumeration protection)
- ✅ כל הסשנים מתנתקים אחרי איפוס סיסמה
