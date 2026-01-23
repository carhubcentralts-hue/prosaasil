# Smart Prompt Generator v2 - Example Output

## Input (Questionnaire)

```json
{
  "business_name": "קליניקת אסתטיקה 'יופי טבעי'",
  "business_type": "קליניקת אסתטיקה",
  "target_audience": "נשים בגילאי 25-50 המעוניינות בטיפולי פנים וגוף",
  "main_goal": "תיאום פגישה",
  "what_is_quality_lead": "לקוחה שרוצה לקבוע טיפול בשבועיים הקרובים, מעוניינת בטיפולים מתקדמים",
  "services": ["טיפולי פנים", "לייזר", "בוטוקס", "חומצה היאלורונית", "פילינג"],
  "working_hours": "א-ה 09:00-19:00, ו 09:00-14:00",
  "conversation_style": "מקצועי",
  "forbidden_actions": ["הבטחת מחירים סופיים", "התחייבות לתוצאות", "אבחון רפואי"],
  "handoff_rules": "העברה לרופא במקרים של בעיות רפואיות, תלונות רציניות, או בקשה מפורשת",
  "integrations": ["Google Calendar", "מערכת תורים"]
}
```

## Output (Generated Prompt)

```
========================
זהות הסוכן
========================
אתה סוכן AI מקצועי של קליניקת אסתטיקה 'יופי טבעי'.
אתה עוזר ללקוחות בתיאום פגישות ומתן מידע על טיפולים.
אתה דובר עברית בצורה מקצועית, ברורה ואדיבה.

========================
מטרת השיחה
========================
המטרה העיקרית: תיאום פגישה לטיפולים אסתטיים.

יעד איכותי:
- לקוחה שמעוניינת לקבוע טיפול בשבועיים הקרובים
- מעוניינת בטיפולים מתקדמים
- מוכנה להגיע לפגישת ייעוץ

========================
חוקי שיחה
========================
- שאל שאלה אחת בכל פעם
- אל תחפור מידע - התמקד במטרה
- המשך מהנקודה שבה הפסקת
- הקשב למה שהלקוחה אומרת ובנה על זה
- דבר בצורה טבעית - לא רובוטית
- השתמש בשם הלקוחה אם ניתן
- אל תחזור על עצמך
- אל תשאל שוב שאלות שכבר נענו

========================
מהלך שיחה
========================
1. ברכה ראשונית - "שלום, קליניקת אסתטיקה 'יופי טבעי', במה אוכל לעזור?"
2. זיהוי צורך - "באיזה טיפול את מעוניינת?"
3. איסוף פרטים בסיסיים:
   - שם
   - מספר טלפון
   - העדפות תאריך ושעה
4. בדיקת זמינות במערכת התורים
5. אישור הפגישה
6. סיכום והודעה שתשלח אישור ב-WhatsApp/SMS

========================
תנאי עצירה / העברה
========================
- בעיות רפואיות או שאלות מורכבות רפואיות → העברה לרופא
- תלונות רציניות → העברה למנהלת
- בקשה מפורשת לדבר עם אדם → העברה
- אי אפשר לתאם מועד מתאים → העברה למזכירה
- שאלות על מחירים מיוחדים/הנחות → העברה

========================
מגבלות ואיסורים
========================
- אל תבטיח מחירים סופיים - רק טווחים כלליים
- אל תתחייב לתוצאות טיפול
- אל תבצע אבחון רפואי
- אל תמליץ על טיפול ספציפי ללא ייעוץ מקצועי
- אל תדון בתופעות לוואי או סיכונים רפואיים
- אל תשתף מידע רפואי של לקוחות אחרות
- אל תקבל החלטות רפואיות

שעות פעילות: א-ה 09:00-19:00, ו 09:00-14:00
טיפולים זמינים: טיפולי פנים, לייזר, בוטוקס, חומצה היאלורונית, פילינג
מערכות מחוברות: Google Calendar, מערכת תורים
```

## Quality Gate Validation

✅ **Passed All Checks:**

1. ✅ Contains all 6 required sections in correct order
2. ✅ "שאלה אחת בכל פעם" rule is present
3. ✅ Clear conversation goal is defined
4. ✅ Stop/handoff conditions are specified
5. ✅ No long paragraphs (all structured as lists/steps)
6. ✅ No marketing language detected
7. ✅ Professional and actionable instructions

## Key Features of This Output

### Structure
- **Rigid Template**: Exactly 6 sections with clear separators
- **Lists Over Paragraphs**: Uses bullet points and numbered lists
- **No Free Text**: Everything is structured and actionable

### Content Quality
- **Clear Identity**: Agent knows who it is and what it does
- **Specific Goal**: Not generic - tailored to business needs
- **Practical Rules**: Actionable conversation guidelines
- **Step-by-Step Flow**: Clear progression through conversation
- **Safety Mechanisms**: Clear conditions for human handoff
- **Boundaries**: Explicit prohibitions to prevent issues

### Hebrew Language
- Written in proper Hebrew
- Professional tone
- No translation artifacts
- Natural conversation style

## Comparison with Old System

### Old System (Prompt Builder)
```
אתה סוכן AI של קליניקת אסתטיקה 'יופי טבעי'. 
אתה עוזר ללקוחות בתיאום פגישות. 
היה מקצועי ואדיב. 
שאל על הטיפול המבוקש, תאם פגישה, ואשר את הפרטים.
```

**Problems:**
- ❌ Unstructured text
- ❌ No clear conversation flow
- ❌ No stop conditions
- ❌ No specific rules
- ❌ Generic and vague

### New System (Smart Prompt Generator v2)
```
[Full structured output as shown above]
```

**Benefits:**
- ✅ Rigid structure
- ✅ Clear flow with numbered steps
- ✅ Specific rules and prohibitions
- ✅ Safety mechanisms built-in
- ✅ Production-ready

## Usage in Application

### 1. User Fills Questionnaire
```typescript
const questionnaire = {
  business_name: "...",
  business_type: "...",
  // ... other fields
};
```

### 2. System Generates with AI
```typescript
const result = await generateSmartPrompt({
  questionnaire,
  provider: "openai"
});
```

### 3. Quality Gate Validates
```typescript
if (result.validation.passed) {
  // Show to user for review
} else {
  // Show validation errors and regenerate
}
```

### 4. User Reviews and Saves
```typescript
await saveSmartPrompt({
  prompt_text: result.prompt_text,
  channel: "calls",
  metadata: result.metadata
});
```

## Integration Notes

The Smart Prompt Generator v2 is fully integrated into the existing system:
- Accessible from AgentPromptsPage
- Uses existing prompt storage (BusinessSettings)
- Version tracked in PromptRevisions
- Cache invalidation on save
- Works with both calls and WhatsApp channels
