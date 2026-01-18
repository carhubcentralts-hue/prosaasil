# תיקון משוב - מערכת הערות לשירות לקוחות

## תיקונים שבוצעו (קומיט 64549b9)

### 1. ✅ הסיכום הדינמי הרגיל לא נפגע

**החשש**: האם השינויים הרסו את הסיכום הדינמי הרגיל?

**התשובה**: לא! יש 2 סיכומים נפרדים:

1. **`call_log.summary`** (הסיכום הרגיל):
   - נשמר ב-DB בטבלת `call_log`
   - משמש לתצוגה בממשק
   - לא השתנה בכלל!
   - נוצר ב-`tasks_recording.py` בשורות 917, 954, 1571

2. **`LeadNote (note_type='call_summary')`** (סיכום להערות):
   - נשמר כהערה בטבלת `lead_notes`
   - ממוקד שירות לקוחות
   - כולל ניתוח: כוונה, סנטימנט, פעולה הבאה
   - משמש את ה-AI בשיחות הבאות

```python
# tasks_recording.py - קו 917, 954
call_log.summary = summary  # ✅ הסיכום הרגיל - לא השתנה!

# tasks_recording.py - קו 1278
call_note = LeadNote(
    note_type='call_summary',
    content=cs_note_content  # 🆕 סיכום חדש להערות
)
```

### 2. ✅ הערות AI ניתנות כעת למחיקה

**הבעיה**: הערות שנוצרו על ידי AI לא היו ניתנות למחיקה.

**התיקון**: 

**לפני** (`client/src/pages/Leads/LeadDetailPage.tsx`):
```tsx
{isManualNote && (
  <>
    <button onClick={() => startEditing(note)}>✏️ ערוך</button>
    <button onClick={() => handleDeleteNote(note.id)}>🗑️ מחק</button>
  </>
)}
{!isManualNote && (
  <span>לא ניתן לערוך הערות AI</span>
)}
```

**אחרי**:
```tsx
{isManualNote && (
  <button onClick={() => startEditing(note)}>✏️ ערוך</button>
)}
{/* כל ההערות ניתנות למחיקה - כולל AI */}
<button onClick={() => handleDeleteNote(note.id)}>🗑️ מחק</button>
```

**תוצאה**:
- ✅ הערות ידניות: ניתנות לעריכה ומחיקה
- ✅ הערות AI: ניתנות למחיקה בלבד (לא לעריכה)

### 3. ✅ AI מקבל קונטקסט רק מטאב שירות לקוחות

**הבעיה**: ה-AI היה מקבל את **כל** ההערות, כולל הערות חופשיות עם קבצים מצורפים.

**התיקון**: 

**לפני** (`server/agent_tools/tools_crm_context.py`):
```python
notes_query = LeadNote.query.filter_by(
    lead_id=input.lead_id,
    tenant_id=input.business_id
).order_by(LeadNote.created_at.desc()).limit(10)
# 👆 מחזיר את כל ההערות ללא סינון!
```

**אחרי**:
```python
notes_query = LeadNote.query.filter(
    LeadNote.lead_id == input.lead_id,
    LeadNote.tenant_id == input.business_id,
    db.or_(
        LeadNote.note_type == 'call_summary',  # סיכומי שיחות AI
        LeadNote.note_type == 'system',  # הערות מערכת
        db.and_(
            db.or_(LeadNote.note_type == 'manual', LeadNote.note_type == None),
            db.or_(
                LeadNote.attachments == None,  # ללא קבצים מצורפים
                LeadNote.attachments == '[]',
                db.cast(db.func.json_array_length(LeadNote.attachments), db.Integer) == 0
            )
        )
    )
).order_by(LeadNote.created_at.desc()).limit(10)
```

**מה זה מסנן**:
- ✅ **נכלל**: סיכומי שיחות AI (`call_summary`)
- ✅ **נכלל**: הערות מערכת (`system`)
- ✅ **נכלל**: הערות ידניות ללא קבצים מצורפים (מטאב שירות לקוחות)
- ❌ **לא נכלל**: הערות ידניות עם קבצים מצורפים (מטאב הערות חופשיות)

**תוצאה**:
- ה-AI רואה רק הערות רלוונטיות לשירות לקוחות
- הערות חופשיות עם קבצים לא מזהמות את ההקשר
- מקטין את כמות הטוקנים וממקד את ההקשר

## סיכום השינויים

| נושא | לפני | אחרי | סטטוס |
|------|------|------|--------|
| סיכום דינמי רגיל | ✓ עובד | ✓ עובד (לא השתנה!) | ✅ |
| מחיקת הערות AI | ❌ לא אפשרי | ✅ אפשרי | ✅ תוקן |
| עריכת הערות AI | ❌ לא אפשרי | ❌ לא אפשרי (במכוון) | ✅ |
| הקשר AI | כל ההערות | רק טאב שירות לקוחות | ✅ תוקן |
| הערות עם קבצים בהקשר | ✓ נכללו | ❌ לא נכללות | ✅ תוקן |

## קבצים ששונו

1. **`client/src/pages/Leads/LeadDetailPage.tsx`**
   - הסרת התנאי שמנע מחיקת הערות AI
   - כל ההערות כעת ניתנות למחיקה

2. **`server/agent_tools/tools_crm_context.py`**
   - הוספת סינון מורכב להערות
   - AI מקבל רק הערות מטאב שירות לקוחות

## בדיקות מומלצות

- [ ] פתח דף ליד ועבור לטאב "שירות לקוחות AI"
- [ ] וודא שכפתור מחיקה מופיע על הערות AI
- [ ] מחק הערת AI וודא שהמחיקה עובדת
- [ ] נסה לערוך הערת AI - אמור להיות רק מחיקה (לא עריכה)
- [ ] הוסף הערה ידנית עם קובץ מצורף בטאב "הערות חופשיות"
- [ ] בדוק בשיחה הבאה שה-AI לא רואה את ההערה עם הקובץ
- [ ] וודא שהסיכום הדינמי הרגיל ממשיך לעבוד (בפרטי שיחה)
