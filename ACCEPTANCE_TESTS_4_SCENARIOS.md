# ✅ בדיקות קבלה סופיות - Final Acceptance Tests

## 🎯 4 תרחישים חובה

### תרחיש 1: לקוח עונה "כן" ישר אחרי הברכה ✅

**צעדים:**
1. התקשר לשיחה
2. הבוט: "שלום, הגעתם ל[עסק]. איך אפשר לעזור?"
3. לקוח: "כן" (מיד)
4. הבוט: צריך להמשיך לשלב הבא בפרומפט העסקי

**בדיקות בלוגים:**
```
✅ [SESSION] session.updated confirmed in XXms
✅ [PROMPT_SEPARATION] global_system_prompt=injected hash=XXXXXXXX
✅ [NAME_ANCHOR] injected (אם יש שם)
✅ [LATENCY] session.updated → greeting = 20-80ms (should be <100ms)
✅ [BUILD 200] GREETING response.create sent!
✅ [BUILD 200] response.create triggered (TOOL_...) [TOTAL: 2]
```

**מה לבדוק:**
- [ ] הבוט לא נתקע אחרי "כן"
- [ ] השיחה ממשיכה לשלב הבא
- [ ] אין שגיאות בלוג
- [ ] Latency <100ms

---

### תרחיש 2: לקוח שואל "מי זה?" ישר ✅

**צעדים:**
1. התקשר לשיחה
2. הבוט: "שלום, הגעתם ל[עסק]..."
3. לקוח: "מי זה?" (מיד)
4. הבוט: צריך להסביר מי הוא (לפי הפרומפט העסקי)

**בדיקות בלוגים:**
```
✅ Same as תרחיש 1
✅ [BUILD 200] response.create triggered (USER_QUESTION) [TOTAL: 2]
```

**מה לבדוק:**
- [ ] הבוט לא עושה "תגובה גנרית"
- [ ] הבוט מסביר מי הוא (לפי business prompt)
- [ ] התגובה מתאימה לזהות העסק
- [ ] אין שגיאות

---

### תרחיש 3: Tool handler רץ בזמן שהלקוח מדבר ⚠️

**צעדים:**
1. התחל שיחה
2. הבוט שואל "מה השם שלך?"
3. לקוח מתחיל לומר "השם שלי הוא..."
4. **באמצע** הדיבור של הלקוח, ה-AI קורא ל-`save_lead_info`
5. כלי ה-`save_lead_info` מסתיים ורוצה ליצור response

**בדיקות בלוגים:**
```
✅ [BUILD 313] Lead info from AI: {"name": "..."}
✅ [BUILD 313] Saved name = '...'
⚠️ 🛑 [RESPONSE GUARD] USER_SPEAKING=True - blocking response until speech complete (TOOL_save_lead_info)
```

**מה לבדוק:**
- [ ] הבוט **לא** חותך את הלקוח באמצע
- [ ] הלוג מראה `USER_SPEAKING=True - blocking response`
- [ ] הבוט ממתין שהלקוח יסיים
- [ ] **אחרי** שהלקוח מסיים, הבוט עונה
- [ ] אין `await client.send_event({"type": "response.create"})` ישיר

---

### תרחיש 4: שיחה נסגרת/ניתוק ⚠️

**צעדים:**
1. התחל שיחה
2. באמצע שיחה, לחץ "סיום שיחה" או נתק
3. במקביל, tool handler (או כל דבר אחר) מנסה ליצור response

**בדיקות בלוגים:**
```
✅ [HANGUP] Hangup initiated
⚠️ ⏸️ [RESPONSE GUARD] Hangup pending - blocking new responses (TOOL_...)
או:
⚠️ 🛑 [RESPONSE GUARD] Call in CLOSING state - blocking response (TOOL_...)
```

**מה לבדוק:**
- [ ] הבוט **לא** יוצר תגובות אחרי pending_hangup
- [ ] הלוג מראה `Hangup pending - blocking new responses`
- [ ] השיחה נסגרת מהר (לא ממתינה לתגובות מיותרות)
- [ ] אין בזבוז טוקנים

---

## 📊 סיכום תוצאות

| תרחיש | סטטוס | הערות |
|-------|--------|-------|
| 1. "כן" אחרי ברכה | ⬜ | |
| 2. "מי זה?" | ⬜ | |
| 3. Tool + user speaking | ⬜ | |
| 4. Hangup + response | ⬜ | |

## ✅ קריטריונים להצלחה

### Must Have (חובה)
- [ ] אין שיחות תקועות
- [ ] אין חיתוך לקוח באמצע דיבור
- [ ] אין יצירת תגובות אחרי hangup
- [ ] Latency <100ms (session→greeting)
- [ ] אין שגיאות ב-console

### Nice to Have (רצוי)
- [ ] תגובות טבעיות וברורות
- [ ] שם לקוח משומש (אם יש + policy)
- [ ] כלים עובדים חלק
- [ ] לוגים ברורים

## 🚨 Red Flags (דגלים אדומים)

אם אתה רואה אחד מאלה - **עצור מיד**:

❌ `strategy=COMPACT→FULL` - לא אמור להיות!
❌ `PROMPT UPGRADE` - לא אמור להיות!
❌ `Expanding from COMPACT to FULL` - לא אמור להיות!
❌ `[LATENCY] session→greeting = 500ms+` - bottleneck!
❌ `await client.send_event({"type": "response.create"})` (מחוץ ל-trigger_response)
❌ שיחה תקועה אחרי "כן"
❌ בוט חותך לקוח באמצע
❌ תגובות אחרי hangup

## 🎯 לפני Production

**3 דברים אחרונים:**

1. **הרץ את 4 התרחישים** - תעד תוצאות
2. **שמור screenshots של לוגים** - במיוחד תרחישים 3-4
3. **בדוק חיוב** - וודא שספירת response.create נכונה

---

**תאריך**: 2025-12-31  
**סטטוס**: ⬜ ממתין לבדיקות  
**אחראי**: Manual testing required
