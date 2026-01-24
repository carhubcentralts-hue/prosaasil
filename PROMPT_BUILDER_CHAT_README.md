# Prompt Builder Chat - Natural Conversational Prompt Generation

## Overview

The Prompt Builder Chat is a new feature that creates AI prompts through natural, free-form conversation instead of structured questionnaires. It provides a more intuitive and human-like experience for business owners who want to create custom prompts for their AI agents.

## Key Features

### 1. Natural Conversation Flow
- No structured questions or forms
- Free-form dialogue in Hebrew
- AI intelligently gathers necessary information
- Feels like talking to a human consultant

### 2. Intelligent Information Gathering
- AI asks only when it genuinely improves the result
- Questions are natural and contextual
- Silent internal state management
- Infers missing information with reasonable business logic

### 3. Resilient Design
- Always produces a result
- No "missing information" errors
- Works even with minimal input
- Automatically fills gaps with sensible defaults

### 4. Automatic Prompt Generation
- Detects when sufficient context is gathered
- Generates prompt without asking permission
- Provides clear, specific, business-adapted prompts
- Not generic or robotic

## Architecture

### Backend (`server/routes_prompt_builder_chat.py`)

**Endpoints:**
1. `POST /api/ai/prompt_builder_chat/message`
   - Handles conversation messages
   - Maintains conversation history
   - Detects when to generate prompt
   - Returns AI response or generated prompt

2. `POST /api/ai/prompt_builder_chat/save`
   - Saves generated prompt to database
   - Creates version history
   - Invalidates cache
   - Supports both calls and WhatsApp channels

3. `POST /api/ai/prompt_builder_chat/reset`
   - Resets conversation (client-side)
   - Returns success confirmation

**System Prompt:**
The core of this feature is the comprehensive system prompt (`PROMPT_BUILDER_CHAT_SYSTEM`) that instructs the AI to:
- Conduct natural conversations like a human
- Never ask technical questions
- Never say "missing information"
- Fill in gaps with reasonable business logic
- Silently process and update internal understanding
- Automatically generate prompts when ready
- Be resilient - always produce results

**Security:**
- Requires authentication (admin/owner roles)
- CSRF protection via `@csrf.exempt` with `@require_api_auth`
- Conversation history limited to 20 messages
- Rate limiting inherited from Flask app configuration

### Frontend (`client/src/components/settings/PromptBuilderChat.tsx`)

**Component Features:**
- Chat interface with message bubbles
- Real-time typing indicators
- Conversation history display
- Automatic prompt detection
- Channel selection (calls/WhatsApp)
- Edit capability for generated prompts
- Reset conversation functionality

**State Management:**
- Message history
- Input state
- Loading states
- Generated prompt storage
- Channel selection

**Accessibility:**
- Proper ARIA labels
- Keyboard navigation support
- Screen reader friendly
- RTL (Right-to-Left) layout for Hebrew

## Integration

The chat builder is integrated into:

1. **AgentPromptsPage** (`client/src/pages/Admin/AgentPromptsPage.tsx`)
   - New button: "שיחה ליצירת פרומפט" (Chat to Create Prompt)
   - Placed alongside "Smart Prompt Generator"
   - Gradient button styling (blue to purple)

2. **PromptStudioPage** (`client/src/pages/Admin/PromptStudioPage.tsx`)
   - Available in the prompts tab
   - Integrated with existing prompt management

## Usage Flow

### For End Users:

1. **Open Chat:**
   - Click "שיחה ליצירת פרומפט" button
   - See welcome message

2. **Conversation:**
   - Describe your business naturally
   - AI asks clarifying questions if needed
   - No forms to fill out

3. **Prompt Generation:**
   - AI automatically generates prompt when ready
   - Shows summary of what was created
   - Prompt is editable

4. **Save:**
   - Choose channel (calls or WhatsApp)
   - Save prompt
   - Prompt is versioned and stored

### Example Conversation:

```
User: אני מנהל מוסך רכב בתל אביב

AI: נשמע מעניין! תספר לי קצת יותר - האם אתה מתמחה בסוג מסוים של רכבים או תיקונים?

User: בעיקר רכבים פרטיים, כל סוגי התיקונים

AI: מעולה. בדרך כלל מי שמתקשר אליך כבר יודע מה הוא רוצה, או שצריך להסביר לו מה אתה עושה?

User: רוב האנשים מתקשרים כשיש להם תקלה ספציפית

AI: הבנתי. הכנתי עבורך פרומפט מותאם!

[Prompt is generated and displayed]
```

## Technical Details

### AI Model:
- Uses GPT-4o for natural conversation
- Temperature: 0.8 (for natural, varied responses)
- Max tokens: 2000
- No response format constraint (except for final JSON)

### Conversation Management:
- History limited to 20 messages to control costs
- Messages stored in client state during session
- History sent with each API call for context

### Prompt Detection:
- AI returns JSON when ready to generate:
  ```json
  {
    "type": "prompt_generated",
    "prompt_text": "...",
    "summary": "..."
  }
  ```
- Robust JSON parsing with error handling
- Falls back to regular message if not valid JSON

### Database Integration:
- Saves to `BusinessSettings.ai_prompt` as JSON
- Creates version in `PromptRevisions` table
- Invalidates AI service cache
- Supports multi-channel (calls/WhatsApp)

## Testing

### Backend Validation:
Run: `python3 test_prompt_builder_chat.py`

Validates:
- System prompt presence and content
- All key instruction elements
- Route definitions
- Blueprint configuration

### TypeScript Compilation:
The component passes TypeScript strict checks with proper type definitions.

### Security Scan:
CodeQL analysis shows zero vulnerabilities.

## Configuration

### Environment Variables:
- `OPENAI_API_KEY`: Required for GPT-4o API access

### Flask Blueprint:
Registered in `app_factory.py`:
```python
from server.routes_prompt_builder_chat import prompt_builder_chat_bp
app.register_blueprint(prompt_builder_chat_bp)
```

## Monitoring

### Logging:
- All conversations logged with user input preview
- Generation success/failure logged
- Errors logged with full details server-side

### Metrics to Track:
- Conversation length (number of messages)
- Generation success rate
- Prompt save rate (vs. abandonment)
- Average time to generation

## Future Enhancements

### Potential Improvements:
1. **Multi-turn Refinement:**
   - "שפר את הפרומפט עוד קצת" button
   - Iterative improvement cycle

2. **Templates:**
   - Pre-built conversation starters by industry
   - Quick-start templates

3. **Learning:**
   - Learn from successful prompts
   - Improve suggestions over time

4. **Multi-language:**
   - Support English conversations
   - Automatic language detection

5. **Voice Input:**
   - Speech-to-text for mobile users
   - More natural for some business owners

## Comparison with Other Builders

| Feature | Chat Builder | Smart Generator V2 | Original Wizard |
|---------|-------------|-------------------|-----------------|
| Input Method | Free conversation | Structured form | Short questionnaire |
| User Experience | Most natural | Professional | Quick |
| Flexibility | Highest | Medium | Low |
| Speed | Variable | Fast | Fastest |
| Output Quality | Adaptive | Consistent | Good |
| Best For | First-time users | Power users | Quick setup |

## Troubleshooting

### Common Issues:

1. **"שגיאה בעיבוד ההודעה"**
   - Check OpenAI API key
   - Verify API quota/rate limits
   - Check server logs for details

2. **Conversation doesn't generate prompt:**
   - Continue conversation with more details
   - AI needs sufficient context
   - Try being more specific about business

3. **Generated prompt is too generic:**
   - This shouldn't happen with the system prompt
   - If it does, report as bug
   - Edit manually before saving

## Support

For issues or questions:
1. Check server logs: `LOG_LEVEL=DEBUG`
2. Review conversation in browser console
3. Test with simple business description
4. Contact development team with session details

---

**Created:** January 2026  
**Version:** 1.0  
**Status:** Production Ready
