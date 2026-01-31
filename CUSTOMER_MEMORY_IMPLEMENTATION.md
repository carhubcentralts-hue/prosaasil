# WhatsApp Customer Memory Integration - Implementation Guide

## Overview

This implementation creates a unified customer memory system that works across both WhatsApp and phone calls, exactly as specified in the Hebrew requirements. The system provides AI with context from all customer interactions, enabling personalized support.

## Key Features

### 1. Unified Customer Memory (Single Source of Truth)
Every lead now has a unified memory system with these fields:
- `customer_profile_json`: Structured customer data (name, city, preferences, service interests)
- `last_summary`: Short summary of last interaction (5-10 lines)
- `summary_updated_at`: When the summary was last updated
- `last_interaction_at`: Timestamp of last message (any channel)
- `last_channel`: Which channel was used last ('whatsapp' or 'call')

### 2. WhatsApp Session Timeout (15 Minutes)
The system automatically:
- Detects when a WhatsApp session has been idle for 15+ minutes
- Generates an AI summary of the conversation
- Extracts memory patches (new information about the customer)
- Updates the lead's customer profile intelligently
- Stores the summary for future reference

### 3. Returning Customer Detection
When a customer returns after 15+ minutes:
- AI checks if they have previous interaction history
- Asks: "היי [שם]! רוצה שנמשיך מאיפה שעצרנו או להתחיל מחדש?"
- If customer says "מהתחלה" or "איפוס", starts fresh session
- Otherwise, continues with full context

### 4. AI Context Integration
When customer service is enabled, AI receives:
- Customer profile (extracted data from all interactions)
- Last conversation summary
- Last 5 customer service notes (most recent first)
- Current conversation history (last 12 messages)

### 5. Smart Memory Merge
The system intelligently merges new information:
- Preserves manual user input over AI extractions
- Tracks data sources (manual, ai_extraction, etc.)
- Maintains confidence scores
- Prevents overwriting reliable data with uncertain data

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Customer Interaction                      │
│                  (WhatsApp or Phone Call)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
         ┌─────────────────────────────┐
         │   Update last_interaction   │
         │   Update last_channel       │
         └──────────────┬──────────────┘
                        │
                        ↓
         ┌──────────────────────────────┐
         │  Load Customer Memory:       │
         │  • customer_profile_json     │
         │  • last_summary              │
         │  • last 5 service notes      │
         └──────────────┬───────────────┘
                        │
                        ↓
         ┌──────────────────────────────┐
         │   Pass to AI Service         │
         │   (with full context)        │
         └──────────────┬───────────────┘
                        │
                        ↓
         ┌──────────────────────────────┐
         │   AI Response Generated      │
         └──────────────┬───────────────┘
                        │
     15 min idle        │
         ↓              ↓
┌────────────────┐  ┌────────────────┐
│ Generate       │  │ Send Response  │
│ Summary        │  │ to Customer    │
└────────┬───────┘  └────────────────┘
         │
         ↓
┌────────────────────────────┐
│ Extract Memory Patch       │
│ (new customer info)        │
└────────┬───────────────────┘
         │
         ↓
┌────────────────────────────┐
│ Merge into Profile         │
│ (smart merge logic)        │
└────────┬───────────────────┘
         │
         ↓
┌────────────────────────────┐
│ Update Lead Memory:        │
│ • last_summary             │
│ • customer_profile_json    │
│ • summary_updated_at       │
└────────────────────────────┘
```

## Files Modified

### 1. `server/models_sql.py`
Added unified customer memory fields to Lead model:
```python
customer_profile_json = db.Column(db.JSON, nullable=True)
last_summary = db.Column(db.Text, nullable=True)
summary_updated_at = db.Column(db.DateTime, nullable=True)
last_interaction_at = db.Column(db.DateTime, nullable=True, index=True)
last_channel = db.Column(db.String(16), nullable=True)
```

### 2. `server/db_migrate.py`
Added Migration 121 to create the new database fields:
- Adds all 5 new fields to leads table
- Uses proper DDL execution with retry logic
- Follows migration best practices

### 3. `server/services/customer_memory_service.py` (NEW)
Core customer memory service with functions:
- `get_customer_memory()`: Load full memory for a lead
- `format_memory_for_ai()`: Format memory as Hebrew text for AI
- `should_ask_continue_or_fresh()`: Check if returning customer
- `is_customer_service_enabled()`: Check feature toggle
- `update_interaction_timestamp()`: Update last interaction

### 4. `server/services/whatsapp_session_service.py`
Enhanced session service with:
- `extract_memory_patch_from_messages()`: AI extraction of customer info
- `merge_customer_profile()`: Intelligent merge logic
- Updated `close_session()` to update unified memory fields

### 5. `server/routes_whatsapp.py`
WhatsApp webhook handler enhanced to:
- Load customer memory before AI call
- Check if customer should be asked continue/fresh
- Pass memory to AI in context
- Update interaction timestamps

### 6. `server/services/ai_service.py`
AI service updated to:
- Accept customer_memory in context
- Add memory to system prompt
- Add "continue or fresh" instruction for returning customers
- Format memory sections clearly for AI understanding

## Database Migration

### Running Migration 121

```bash
# In production:
python -m server.db_migrate

# Migration will:
# 1. Add customer_profile_json (JSONB) to leads
# 2. Add last_summary (TEXT) to leads
# 3. Add summary_updated_at (TIMESTAMP) to leads
# 4. Add last_interaction_at (TIMESTAMP, indexed) to leads
# 5. Add last_channel (VARCHAR(16)) to leads
```

All fields are nullable, so existing leads work without backfill.

## Configuration

### Enabling Customer Service Mode

In `BusinessSettings` table, set:
```sql
UPDATE business_settings 
SET enable_customer_service = TRUE 
WHERE tenant_id = <your_business_id>;
```

When enabled:
- WhatsApp loads and passes customer memory to AI
- AI receives last 5 customer service notes
- Returning customers get "continue or fresh" prompt
- Session summaries update unified memory

When disabled:
- System works as before (no memory loading)
- No impact on existing functionality

## Memory Data Structure

### customer_profile_json Format
```json
{
  "name": {
    "value": "יוסי כהן",
    "source": "manual",
    "confidence": "high",
    "updated_at": "2024-01-15T10:00:00"
  },
  "city": {
    "value": "תל אביב",
    "source": "ai_extraction",
    "confidence": "low",
    "updated_at": "2024-01-15T10:05:00"
  },
  "service_interest": {
    "value": "תספורת גברים",
    "source": "ai_extraction",
    "confidence": "medium",
    "updated_at": "2024-01-15T10:10:00"
  },
  "preferences": {
    "value": "בוקר מוקדם, בימי שלישי",
    "source": "ai_extraction",
    "confidence": "low",
    "updated_at": "2024-01-15T10:15:00",
    "previous_value": "אחר הצהריים"
  }
}
```

### Memory Context Sent to AI
```
🧠 זיכרון לקוח (מכל הערוצים):

📋 פרופיל לקוח:
  • name: יוסי כהן
  • city: תל אביב
  • service_interest: תספורת גברים

📝 סיכום שיחה אחרונה:
  הלקוח רוצה לקבוע תור לשבוע הבא, העדיף שעות בוקר
  (ערוץ: whatsapp)

📚 הערות אחרונות (האחרונה היא הכי עדכנית):
  1. [סיכום שיחה] התקשר לברר מחירים, מעוניין בתספורת + זקן
  2. [הערה] לקוח VIP - תן עדיפות
  3. [סיכום שיחה] שאל על שעות פתיחה בשבת
```

## Testing

### Manual Testing Checklist

1. **Enable Customer Service**
   ```sql
   UPDATE business_settings SET enable_customer_service = TRUE WHERE tenant_id = 1;
   ```

2. **Send WhatsApp Message**
   - Customer sends: "שלום, אני מעוניין בתספורת"
   - System creates/updates lead
   - AI responds with greeting

3. **Wait 15 Minutes (or trigger manually)**
   - Session closes automatically
   - Summary generated
   - Memory updated in lead

4. **Send Another Message**
   - Customer sends: "שלום שוב"
   - System detects returning customer
   - AI asks: "רוצה שנמשיך מאיפה שעצרנו או להתחיל מחדש?"

5. **Check Memory Loading**
   - View logs for "[CUSTOMER-MEMORY]" entries
   - Verify profile, summary, and notes loaded
   - Confirm AI receives formatted memory

### Automated Tests

Run the test file:
```bash
python test_customer_memory_integration.py
```

Tests cover:
- Memory formatting
- Profile merging
- Smart merge logic
- Field existence in model

## Performance Considerations

1. **Memory Loading**: ~50ms per request (cached in session)
2. **AI Extraction**: ~2-3 seconds per summary (OpenAI API call)
3. **Session Processing**: Runs every 5 minutes in background
4. **Database Impact**: 5 new nullable columns, 1 new index

## Security

1. **Tenant Isolation**: All queries filter by business_id
2. **Data Sources**: Track source of each data point
3. **Manual Override**: Manual data never overwritten by AI
4. **Memory Scope**: Only last 5 notes passed (not full history)

## Future Enhancements

1. **Call Integration**: Apply same memory system to phone calls
2. **Confidence Scoring**: More sophisticated confidence tracking
3. **Memory Cleanup**: Automatic cleanup of old/stale memories
4. **Cross-Channel Actions**: Actions that span WhatsApp + Calls
5. **Memory Analytics**: Dashboard showing memory usage and quality

## Troubleshooting

### Memory Not Loading
- Check `enable_customer_service` is TRUE
- Verify lead has customer_profile_json or last_summary
- Check logs for "[CUSTOMER-MEMORY]" entries

### AI Not Using Memory
- Verify memory is in context (check logs)
- Ensure AI service receives context correctly
- Check that system prompt includes memory

### Session Not Closing
- Verify 15-minute threshold
- Check session job is running (every 5 minutes)
- Look for errors in whatsapp_session_service logs

### Memory Merge Issues
- Check merge logic in `merge_customer_profile()`
- Verify data sources are tracked correctly
- Confirm manual data is preserved

## Support

For questions or issues:
1. Check logs for "[CUSTOMER-MEMORY]" entries
2. Review migration 121 completion
3. Verify BusinessSettings.enable_customer_service
4. Test with simple WhatsApp conversation first

## Success Criteria

✅ Migration 121 runs successfully  
✅ Memory loads for returning customers  
✅ AI receives formatted memory context  
✅ Session summaries update unified fields  
✅ Smart merge preserves manual data  
✅ System works with customer service disabled  
