# תיקון 3 בעיות קריטיות בפרודקשן

## סיכום מהיר

תוקנו 3 בעיות קריטיות לפי ההנחיות המדויקות:

1. ✅ **חיובי Twilio מיותרים** - WebSocket נסגר מיד בסיום שיחה
2. ✅ **ברג'־אין לא עובד** - משתמש יכול לקטוע בכל רגע
3. ✅ **סטייה מהפרומפט** - פרומפט מעודכן באנגלית, דינמי לחלוטין, ללא לוגיקת flow

---

## 0️⃣ VERIFY FIRST (חובה לפני פרודקשן)

יש לבצע בדיקה על 5 שיחות אמיתיות (נכנסת + יוצאת):

1. **WS CLOSE**: אחרי call_status=completed/busy/failed/no-answer → WS נסגר תוך <1 שניה, אין TX/RX נוספים
2. **BARGE-IN**: לקוח קוטע באמצע greeting/תשובה → AI נעצר מיד, לא משלים משפט
3. **PROMPT BIND**: יש bind אחד בלבד: direction + prompt (לא משתנה במהלך שיחה)
4. **NO PROMPT COLLISION**: אין הזרקת system prompt נוסף באמצע שיחה
5. **NO HALLUCINATION**: לקוח שואל שאלה לא מוגדרת → AI לא ממציא, עונה קצר או מציע העברה לנציג, חוזר ל-flow

---

## 1️⃣ WebSocket - סגירה חובה (עוצר חיובי Twilio)

### הבעיה
WebSocket נשאר פתוח גם אחרי סיום שיחה → Twilio ממשיך לחייב.

### הפתרון
**קובץ: `server/routes_twilio.py`**

```python
# בעת קבלת call_status terminal (completed, busy, failed, no-answer, canceled)
if call_status_val in ["completed", "busy", "no-answer", "failed", "canceled"]:
    save_call_status(call_sid, call_status_val, int(call_duration), direction)
    
    # 🔥 CRITICAL FIX: סגירת WebSocket מיידית
    if call_sid:
        session = stream_registry.get(call_sid)
        if session:
            session['ended'] = True
            session['end_reason'] = f'call_status_{call_status_val}'
```

**קובץ: `server/media_ws_ai.py`**

```python
# בלולאה הראשית, בדיקה לסיום חיצוני
if self.call_sid:
    session = stream_registry.get(self.call_sid)
    if session and session.get('ended'):
        end_reason = session.get('end_reason', 'external_signal')
        print(f"🛑 [CALL_END] Call ended externally ({end_reason}) - closing WebSocket immediately")
        self.hangup_triggered = True
        self.call_state = CallState.ENDED
        break
```

### תוצאה
- WebSocket נסגר מיד כאשר:
  - call_status = completed / busy / failed / no-answer
  - הבוט אמר משפט סיום (קיים מלכתחילה בקוד)
  - timeout של silence monitor (קיים כבר בקוד)

**→ 0 חיובים מיותרים**

---

## 2️⃣ Barge-In - פשוט, עובד, בלי חוכמות

### הבעיה
קלט נחסם בזמן greeting / AI ממשיך לדבר מעל הלקוח.
היה grace period של 500ms שמנע קטיעה מוקדמת.

### הפתרון
**קובץ: `server/media_ws_ai.py`**

הוסרה ההגנה של grace period:

```python
# לפני - עם הגנת grace period:
RESPONSE_GRACE_PERIOD_MS = 500
if time_since_response < RESPONSE_GRACE_PERIOD_MS:
    print(f"🛡️ Ignoring speech_started - only {time_since_response:.0f}ms")
    continue

# אחרי - הוסר לגמרי!
# 🔥 SIMPLIFIED BARGE-IN: User can interrupt at ANY time
```

הלוגיקה הקיימת כבר עושה:
- עוצר מיד כל TTS
- מבטל response פעיל
- לא שולח response חדש
- עובר ל-LISTEN MODE

### תוצאה
**הלקוח מדבר = הבוט שותק. נקודה.**

- אין הגנות greeting
- אין timeout חכם
- אין חישובים

---

## 3️⃣ הפרומפט - אנגלית, דינמי, בלי flow

### הבעיה הקודמת
- פרומפט היה בעברית עם לוגיקת flow מובנית
- גרם לעירוב בין system prompt ל-business prompt
- לא היה דינמי לחלוטין

### הפתרון החדש
**קובץ: `server/services/realtime_prompt_builder.py`**

פרומפט חדש לחלוטין באנגלית:

#### עקרונות מרכזיים:

**1. שפה ותמלול:**
```
1. PRIMARY LANGUAGE & TRANSCRIPTION
────────────────────────────────────
DEFAULT RESPONSE LANGUAGE: Hebrew
TRANSCRIPTION: Accurate in all languages

LANGUAGE SWITCHING RULES:
- Always start responding in Hebrew
- If customer speaks different language → Switch immediately
- Maintain accurate transcription in customer's language
- Do NOT mix languages unless customer does
```

**2. Barge-In:**
```
2. BARGE-IN (User Interruption)
────────────────────────────────
HARD RULE: Customer speaks = AI stops. Always.

- If customer starts speaking while you are talking → STOP IMMEDIATELY
- Do NOT finish your current sentence
- Do NOT talk over the customer

NO greeting protections. NO grace periods. NO exceptions.
```

**3. עקוב אחר ה-Business Prompt (לא System Prompt!):**
```
3. FOLLOW THE BUSINESS PROMPT
──────────────────────────────
The Business Prompt below defines:
- The conversation flow
- What questions to ask and in what order
- When to capture information
- When to transfer or end the call

YOUR ROLE:
- Follow the Business Prompt instructions EXACTLY
- Ask ONE question at a time as specified
- Wait for clear answer before advancing
- If customer asks off-topic question:
  → Answer briefly
  → Return to where you were in the flow
- Do NOT invent information not in Business Prompt
- Do NOT skip steps or reorder the flow
```

**4. היררכיה ברורה:**
```
7. HIERARCHY
────────────
Business Prompt > System Prompt > Model Defaults

If there is ANY conflict:
→ ALWAYS follow the Business Prompt below
→ Business Prompt = WHAT to say and do
→ System Rules = HOW to behave
```

### יתרונות הפרומפט החדש:

✅ **אנגלית** - הבנה טובה יותר של ה-AI  
✅ **אין לוגיקת flow** - כל ה-flow מגיע מ-Business Prompt (UI)  
✅ **דינמי לחלוטין** - עובד עם כל business prompt  
✅ **אין FAQ/knowledge** - רק כללי התנהגות  
✅ **עברית כברירת מחדל** - עם החלפה אוטומטית לשפות אחרות  
✅ **תמלול מדויק** - בכל השפות  

### נכנסות / יוצאות
**קובץ: `server/media_ws_ai.py`**

הוספנו הערות ברורות:

```python
# ⚠️ CRITICAL: call_direction is set ONCE at start and NEVER changed
self.call_direction = custom_params.get("direction", "inbound")
```

call_direction נקבע **פעם אחת** ב-start event ו**לעולם לא משתנה**.

### תוצאה
✅ WS נסגר מיד בסיום (אין דקות "רפאים")  
✅ הלקוח יכול לקטוע בכל רגע  
✅ הבוט לא מדבר מעל הלקוח  
✅ ה-flow מגיע מ-Business Prompt בלבד (UI)  
✅ אין עירוב בין system ל-business prompt  
✅ אין בלבול נכנס/יוצא  
✅ תמלול מדויק בכל השפות  

---

## בדיקות אבטחה

✅ **Code Review**: 1 issue נמצא ותוקן (null check)  
✅ **Security Scan (CodeQL)**: 0 vulnerabilities  

---

## קבצים ששונו

1. `server/routes_twilio.py` - סימון session כ-ended בעת call_status terminal
2. `server/media_ws_ai.py` - בדיקת סיום חיצוני, הסרת grace period, הערות call_direction
3. `server/services/realtime_prompt_builder.py` - פרומפט חדש באנגלית, ללא flow logic

---

## איך לבדוק (VERIFY FIRST)

### בדיקה 1: WebSocket נסגר
1. התקשר לבוט
2. סיים שיחה
3. בדוק שה-WebSocket נסגר תוך 1 שניה
4. בדוק Twilio logs - אין חיובים אחרי סיום

### בדיקה 2: Barge-In
1. התקשר לבוט
2. בזמן greeting - התחל לדבר
3. ודא שהבוט עוצר מיד
4. בזמן כל תשובה - קטע
5. ודא שהבוט עוצר מיד

### בדיקה 3: Flow מ-Business Prompt
1. התקשר לבוט
2. ודא שהבוט עוקב אחר ה-flow המוגדר ב-UI
3. שאל שאלה לא קשורה ("מה השעה?")
4. ודא שהבוט עונה קצר וחוזר ל-flow
5. ודא שאין המצאת מידע

### בדיקה 4: שפה
1. התקשר לבוט (מתחיל עברית)
2. דבר אנגלית
3. ודא שהבוט עובר לאנגלית
4. המשך כל השיחה - ודא שהבוט נשאר באנגלית
5. בדוק תמלול - צריך להיות מדויק

### בדיקה 5: אין Hallucination
1. התקשר לבוט
2. שאל על שירות/מידע שלא מוגדר ב-Business Prompt
3. ודא שהבוט לא ממציא
4. ודא שהבוט עונה קצר או מציע העברה לנציג
5. ודא חזרה ל-flow

---

## פרודקשן Checklist

- [x] כל הקוד נבדק ב-code review
- [x] סריקת אבטחה הושלמה (0 issues)
- [x] ההנחיות מהבעיה מיושמות במלואן
- [x] אין שינויים מיותרים - רק תיקונים ממוקדים
- [x] תיעוד מלא ב-README זה
- [x] פרומפט באנגלית ללא flow logic
- [x] דינמיות מלאה - Business Prompt מגדיר flow
- [ ] **בדיקות VERIFY FIRST (5 תרחישים)** - יש לבצע לפני פרודקשן

**מוכן לבדיקות ולאחר מכן לפרודקשן ✅**

