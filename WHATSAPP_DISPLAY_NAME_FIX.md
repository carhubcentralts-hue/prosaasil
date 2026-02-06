# WhatsApp Conversation Display Name Fix

## Problem Statement (Hebrew)
הבעיה הייתה שברגע ששולחים הודעה, היה קורה עדכון אופטימי (או refresh של הרשימה) שהחליף את ה־displayName/title של השיחה ל־chatId / lid@... כי זה היה ה־fallback של WhatsApp/JID — ואז במקום השם "אברהם אלפנדרי" זה היה הופך ל־lid@8762....

## Root Cause
The issue occurred in two places:

1. **Backend (`server/routes_crm.py`)**: 
   - The `/api/crm/threads` endpoint was returning `to_number` field directly as fallback for display name
   - `to_number` could contain WhatsApp JID identifiers like `lid@87621728518253` 
   - These @lid identifiers are NOT real phone numbers - they're internal WhatsApp identifiers
   - The backend was using: `display_name = lead_name or push_name or customer_name or to_number`
   - This meant if no names were available, users would see raw `lid@...` identifiers

2. **Frontend (`client/src/pages/wa/WhatsAppPage.tsx`)**:
   - Had inline fallback logic: `name: thread.lead_name || thread.push_name || thread.name || thread.peer_name || thread.phone_e164 || 'לא ידוע'`
   - No filtering of @lid identifiers
   - No single source of truth for name display logic
   - After sending messages, the optimistic update would refresh threads and potentially show @lid if that's what the backend returned

## Solution

### 1. Created Centralized Utility (`client/src/shared/utils/conversation.ts`)

```typescript
export function getConversationDisplayName(
  thread: {
    lead_name?: string | null;
    push_name?: string | null;
    name?: string | null;
    peer_name?: string | null;
    phone?: string | null;
    phone_e164?: string | null;
  },
  fallback: string = 'ללא שם'
): string
```

**Key Features**:
- Single source of truth for all conversation name display
- Implements strict priority: lead_name > push_name > name > peer_name > phone (formatted)
- **Filters out @lid identifiers** - never shown to users
- Removes WhatsApp JID suffixes (@s.whatsapp.net, @c.us, @lid, etc.)
- Formats phone numbers with + prefix when appropriate
- Validates names don't look like JIDs or @lid before using them

### 2. Updated Frontend (`client/src/pages/wa/WhatsAppPage.tsx`)

```typescript
// Before:
name: thread.lead_name || thread.push_name || thread.name || thread.peer_name || thread.phone_e164 || 'לא ידוע'

// After:
name: getConversationDisplayName(thread, 'לא ידוע')
```

**Benefits**:
- Consistent name display throughout the application
- All @lid filtering happens in one place
- Easy to maintain and update logic
- Preserves lead names after sending messages

### 3. Fixed Backend (`server/routes_crm.py`)

```python
# Added @lid detection and filtering:
display_phone = to_number
if display_phone and '@lid' in display_phone:
    # @lid identifiers are not real phone numbers - don't display them
    display_phone = None
elif display_phone:
    # Clean up WhatsApp JID suffixes
    display_phone = display_phone.replace('@s.whatsapp.net', '').replace('@c.us', '')

# Updated fallback logic:
display_name = lead_name or push_name or customer_name or display_phone or 'לא ידוע'
```

**Benefits**:
- Backend no longer returns @lid identifiers in display names
- Cleans phone numbers before returning them
- Returns 'לא ידוע' (Unknown) instead of @lid
- Double protection: both backend and frontend filter @lid

### 4. Added Comprehensive Tests

Created `client/src/shared/utils/__tests__/conversation.test.ts` with test cases for:
- @lid identifier filtering
- WhatsApp JID suffix removal
- Name priority logic (lead_name > push_name > phone)
- Edge cases (null, empty, phone-like names, JIDs in name field)

## Acceptance Criteria ✅

1. **Conversation with lead - before sending**: Shows lead name ✅
2. **Same conversation - after sending message**: Still shows lead name ✅
3. **Page refresh**: Lead name persists ✅
4. **Conversation without lead**: Shows contact name or formatted phone (never @lid) ✅
5. **Search by name**: Works correctly after sending messages ✅

## Technical Details

### What are @lid identifiers?
- LID (Linkage Identifier) is used by WhatsApp for users who haven't shared their phone number
- Format: `82399031480511@lid` 
- The digits are NOT phone numbers - they're internal WhatsApp identifiers
- Should NEVER be displayed to end users

### Name Priority Logic
1. **Lead Name** (`lead_name`): From CRM system - highest priority
2. **Push Name** (`push_name`): From WhatsApp contact saved name
3. **Generic Name** (`name`): From various sources
4. **Peer Name** (`peer_name`): Alternative name field
5. **Phone Number**: E.164 formatted (with +)
6. **Fallback**: 'ללא שם' (No name) or custom fallback

### Files Changed
- `client/src/shared/utils/conversation.ts` - NEW utility functions
- `client/src/pages/wa/WhatsAppPage.tsx` - Use utility for name display
- `server/routes_crm.py` - Filter @lid in backend response
- `client/src/shared/utils/__tests__/conversation.test.ts` - NEW test suite

## Future Improvements

1. **Consider exporting the utility** to be used in other components that display conversation names
2. **Add integration tests** that verify the full flow from backend to frontend
3. **Consider caching** lead names to reduce database queries
4. **Add telemetry** to track if @lid identifiers are still appearing (they shouldn't)

## References

- Original issue: Hebrew specification in problem statement
- Related files:
  - `server/services/contact_identity_service.py` - Contains @lid handling utilities
  - `server/utils/whatsapp_utils.py` - WhatsApp normalization functions
  - Documentation: `WHATSAPP_LID_FIX_HE.md`, `WHATSAPP_LID_PHONE_RESOLUTION.md`
