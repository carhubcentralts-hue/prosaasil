# Smart Prompt Generator v2 - Implementation Guide

## Overview

The Smart Prompt Generator v2 is a structured, template-based AI prompt generation system for creating professional SYSTEM PROMPTS for voice and WhatsApp AI agents. It replaces free-form text generation with a rigid, validated template structure.

## Key Principles (חובה - Mandatory)

1. ❌ The generator does NOT write free-form text
2. ✅ The generator builds prompts using a rigid template structure
3. ✅ The LLM serves as a conversation architect, not a copywriter
4. ✅ Every prompt MUST include 6 sections in exact order:
   - זהות הסוכן (Agent Identity)
   - מטרת השיחה (Conversation Goal)
   - חוקי שיחה (Conversation Rules)
   - מהלך שיחה (Conversation Flow)
   - תנאי עצירה / העברה (Stop/Handoff Conditions)
   - מגבלות ואיסורים (Limitations and Prohibitions)
5. ❌ No long paragraphs
6. ❌ No mixing information in sentences
7. ✅ Everything is lists, rules, and steps

## Architecture

### Input Schema (Structured Questionnaire)

```json
{
  "business_name": "string (required)",
  "business_type": "string (required)",
  "target_audience": "string (optional)",
  "main_goal": "select (required)",
  "what_is_quality_lead": "textarea (optional)",
  "services": "array of strings (optional)",
  "working_hours": "string (optional)",
  "conversation_style": "select (required)",
  "forbidden_actions": "array of strings (optional)",
  "handoff_rules": "textarea (optional)",
  "integrations": "array of strings (optional)"
}
```

### Internal System Prompt (Meta-Prompt)

This is THE CORE of the generator. Without it, output quality will be poor.

```
אתה מחולל SYSTEM PROMPTS לסוכני AI קולים וכתובים.

המטרה שלך:
לייצר פרומפט מקצועי לסוכן שירות / מכירה,
שיעבוד בשיחה חיה עם לקוחות אמיתיים.

חוקים:
- כתוב בעברית בלבד
- אל תכתוב טקסט שיווקי
- אל תכתוב פסקאות
- אל תסביר דברים ללקוח
- כתוב רק הוראות לסוכן
- השתמש בכותרות ברורות
- השתמש ברשימות
- שאלות – אחת בכל פעם
- סוכן חייב לדעת מתי לעצור

[... continues with exact structure requirements]
```

### Output Template (Rigid Structure)

```
========================
זהות הסוכן
========================
[content]

========================
מטרת השיחה
========================
[content]

========================
חוקי שיחה
========================
- [rule 1]
- [rule 2]
...

========================
מהלך שיחה
========================
1. [step 1]
2. [step 2]
...

========================
תנאי עצירה / העברה
========================
- [condition 1]
- [condition 2]
...

========================
מגבלות ואיסורים
========================
- [limitation 1]
- [limitation 2]
...
```

### Quality Gate Validation

Automatic validation after generation. If ANY check fails → regenerate:

1. ❌ Missing "שאלה אחת בכל פעם" → REJECT
2. ❌ Missing clear conversation goal → REJECT
3. ❌ Missing stop conditions → REJECT
4. ❌ Has long paragraphs (>300 chars without list formatting) → REJECT
5. ❌ Has marketing language → REJECT
6. ✅ Has all 6 required sections in correct order → ACCEPT

## API Endpoints

### 1. Get Input Schema
```
GET /api/ai/smart_prompt_generator/schema
```

Returns structured questionnaire definition with field types, validation rules, and options.

### 2. Get Available Providers
```
GET /api/ai/smart_prompt_generator/providers
```

Returns list of available AI providers (OpenAI, Gemini) with availability status.

### 3. Generate Prompt
```
POST /api/ai/smart_prompt_generator/generate
Body: {
  "questionnaire": { ... },
  "provider": "openai" | "gemini",
  "provider_config": { ... }
}
```

Generates structured prompt using selected provider. Returns:
- `prompt_text`: Generated prompt
- `validation`: Quality gate results
- `provider`: Used provider
- `model`: Used model
- Error if quality gate fails

### 4. Save Generated Prompt
```
POST /api/ai/smart_prompt_generator/save
Body: {
  "prompt_text": "...",
  "channel": "calls" | "whatsapp",
  "metadata": { ... }
}
```

Saves generated prompt to business settings with version tracking.

## Frontend Components

### SmartPromptGeneratorV2

Main React component for the generator wizard.

**Features:**
- Two-step wizard: Questionnaire → Preview
- Provider selection (OpenAI/Gemini)
- Structured form fields (text, textarea, select, tags)
- Read-only preview with warnings
- Channel selection (calls/WhatsApp)
- Error handling and validation messages
- Success banners with generation metadata

**Usage:**
```tsx
<SmartPromptGeneratorV2
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  onSave={(promptText, channel, metadata) => {
    // Handle save
  }}
  initialChannel="calls"
/>
```

### Integration in AgentPromptsPage

Added "מחולל פרומפטים חכם v2" button with Sparkles icon.

**Features:**
- Gradient button styling (purple to blue)
- Opens modal on click
- Integrates generated prompt into existing form
- Shows success message after generation

## Provider Support

### OpenAI (Default)
- Model: `gpt-4o-mini` (default) or `gpt-4o`
- API Key: `OPENAI_API_KEY` environment variable
- Fast and reliable
- Good Hebrew support

### Google Gemini
- Model: `gemini-pro` (default) or `gemini-1.5-pro`
- API Key: `GEMINI_API_KEY` environment variable
- Alternative option
- Good Hebrew support

**Provider Selection:**
- UI allows choosing provider before generation
- Shows availability status based on configured API keys
- Displays description and default badge

## Security Features

### Input Validation
- Max field length: 500 characters per field
- Max total input: 4000 characters
- Field sanitization and trimming
- No prompt injection patterns allowed

### Output Validation
- Structure validation (all sections present)
- Content validation (rules, goals, conditions present)
- Length validation (no excessive paragraphs)
- Marketing language detection
- Automatic rejection and regeneration if needed

### Session Security
- Requires authentication: `system_admin`, `owner`, or `admin`
- CSRF exempt (but auth required)
- Business ID from session
- User tracking in revisions

## Database Schema

Uses existing tables:
- `BusinessSettings`: Stores prompt in `ai_prompt` field as JSON
- `PromptRevisions`: Tracks versions with metadata
- Version increment on each save
- Cache invalidation after updates

## User Experience Flow

1. **Open Generator**
   - Click "מחולל פרומפטים חכם v2" button
   - Modal opens with questionnaire

2. **Select Provider**
   - Choose OpenAI (default) or Gemini
   - See provider description and status

3. **Fill Questionnaire**
   - Structured fields with validation
   - Tags input with Enter key
   - Required fields marked with *
   - Max length indicators

4. **Generate**
   - Click "צור פרומפט מובנה"
   - Loading state with spinner
   - Error handling if quality gate fails

5. **Preview**
   - Success banner with metadata
   - Warning about system prompt
   - Read-only preview
   - Copy to clipboard option
   - Character count display

6. **Select Channel**
   - Choose calls or WhatsApp
   - Visual radio buttons

7. **Save**
   - Click "שמור פרומפט"
   - Prompt inserted into form
   - Success message
   - Modal closes

8. **Final Save**
   - User reviews in main form
   - Saves using existing save flow
   - Version tracked
   - Cache invalidated

## Configuration

### Environment Variables

Required:
```bash
OPENAI_API_KEY=sk-...
```

Optional:
```bash
GEMINI_API_KEY=...
```

### Constants (Configurable)

In `routes_smart_prompt_generator.py`:
```python
MAX_FIELD_LENGTH = 500  # Max chars per field
MAX_TOTAL_INPUT = 4000  # Max total chars
REQUIRED_SECTIONS = [...]  # Section names
GENERATOR_SYSTEM_PROMPT = "..."  # Meta-prompt
```

## Error Handling

### Quality Gate Failures
```json
{
  "error": "הפרומפט שנוצר לא עמד בבדיקת איכות",
  "validation_error": "חסר כלל 'שאלה אחת בכל פעם'",
  "suggestion": "נסה שוב או שנה את התשובות בשאלון"
}
```

### Input Validation Errors
```json
{
  "error": "שם העסק הוא שדה חובה"
}
```

### Generation Errors
```json
{
  "error": "שגיאה ביצירת הפרומפט עם openai"
}
```

## Testing

### Manual Testing Checklist

- [ ] Load schema successfully
- [ ] Provider selection works
- [ ] Required field validation works
- [ ] Tags input works (add/remove)
- [ ] Generation with OpenAI works
- [ ] Generation with Gemini works (if configured)
- [ ] Quality gate validation catches bad prompts
- [ ] Preview shows correctly
- [ ] Channel selection works
- [ ] Save to database works
- [ ] Version increment works
- [ ] Cache invalidation works
- [ ] Error messages display correctly
- [ ] Success messages display correctly
- [ ] Modal close/reset works

### Test Scenarios

1. **Basic Clinic**
   - business_type: "קליניקת אסתטיקה"
   - Expect: Structured prompt with appointment focus

2. **Law Office**
   - business_type: "משרד עורכי דין"
   - Expect: Professional, formal tone

3. **Car Garage**
   - business_type: "מוסך רכב"
   - Expect: Technical service focus

4. **Missing Required Fields**
   - Don't fill business_name
   - Expect: Validation error

5. **Quality Gate Failure**
   - Manually inject bad prompt
   - Expect: Rejection with specific error

## Troubleshooting

### "שגיאה בטעינת השאלון"
- Check backend is running
- Check `/api/ai/smart_prompt_generator/schema` endpoint
- Check authentication

### "שגיאה ביצירת הפרומפט"
- Check API keys are configured
- Check OpenAI/Gemini API status
- Check backend logs for details
- Try different provider

### "הפרומפט שנוצר לא עמד בבדיקת איכות"
- This is expected for some inputs
- Try regenerating with different answers
- Check which validation rule failed
- Adjust questionnaire answers

### Prompt Not Saving
- Check authentication
- Check business ID in session
- Check database connection
- Check backend logs

## Future Enhancements

Potential improvements (not in current scope):

1. **Multiple Languages**
   - Support English system prompts
   - Auto-detect language from business

2. **Templates Library**
   - Pre-built templates for common business types
   - User can start from template

3. **A/B Testing**
   - Generate multiple versions
   - Let user choose best one

4. **AI Refinement**
   - User can ask AI to adjust specific sections
   - Iterative improvement

5. **Export/Import**
   - Download prompt as file
   - Import prompt from file
   - Share prompts between businesses

6. **Analytics**
   - Track which prompts perform better
   - Suggest improvements based on data

## Files Modified/Created

### Backend
- `server/routes_smart_prompt_generator.py` ⭐ NEW
- `server/app_factory.py` (register blueprint)

### Frontend
- `client/src/components/settings/SmartPromptGeneratorV2.tsx` ⭐ NEW
- `client/src/pages/Admin/AgentPromptsPage.tsx` (add button + integration)

### Documentation
- `SMART_PROMPT_GENERATOR_V2_EXAMPLE.md` ⭐ NEW
- `SMART_PROMPT_GENERATOR_V2_GUIDE.md` ⭐ NEW (this file)

## Credits

Implementation based on Hebrew specification for structured prompt generation system for AI voice agents.

**Core Principle:** The generator is an architect, not a writer. It structures information, it doesn't create marketing copy.
