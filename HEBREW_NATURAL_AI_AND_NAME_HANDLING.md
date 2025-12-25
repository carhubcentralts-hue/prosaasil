# Hebrew Natural AI + Customer Name Handling Implementation

## Overview

Two system prompt enhancements:
1. **Hebrew Natural Language**: Native Israeli Hebrew (not translated)
2. **Customer Name Handling**: Strict prompt-driven (NO default behavior)

## Implementation

### Location
`server/services/realtime_prompt_builder.py` → `_build_universal_system_prompt()`

### Hebrew Language Rules

```python
"Hebrew Language Rules: "
"You think, reason, and formulate responses ONLY in native Israeli Hebrew. "
"Do NOT translate from English. Do NOT use book-style, academic, or formal Hebrew. "
"Avoid high-register words like לרבות, לפיכך, בנוסף לכך, בהתאם לכך. "
"Before responding, internally rewrite the sentence to sound like spoken Israeli Hebrew..."
```

### Customer Name Rules (STRICT)

```python
"Customer name usage (strict): "
"MUST NOT mention or use customer's name unless BUSINESS PROMPT explicitly instructs. "
"NO default behavior. Do NOT use name in greeting or anywhere unless business prompt requests it. "
"If instructed: use ONLY customer_name field value if valid (not empty/null/'unknown'/'test'/'-'). "
"Never guess or generate names. If missing/invalid, continue without mentioning name. "
"Frequency and placement MUST follow business prompt exactly. Do NOT apply politeness rules or defaults. "
"If business prompt doesn't mention name usage: behave as if name doesn't exist, even if field present."
```

## Key Principle

**NO DEFAULT BEHAVIOR**
- Name is NEVER used unless business prompt explicitly instructs
- Not in greeting, not anywhere
- No "politeness defaults", no "typically once"
- AI executes, doesn't decide

## Lead Context Structure

**Field:** `customer_name` (from CRM context)
**Source:** Lead model (`first_name`, `last_name`) or extracted from conversation
**Validation:** Reject if: `null`, `""`, `"unknown"`, `"test"`, `"-"`

## Business Prompt Examples

### Example 1: NO name usage (default)

```
אתה נציג שירות מקצועי.
נהל את השיחה בצורה עניינית וברורה.
```

**Result:** Name is NEVER mentioned, even if `customer_name="דני"` exists

### Example 2: WITH name usage

```
אם קיים שם לקוח, פנה אליו בשמו בברכה הראשונית בלבד.
```

**Result:** 
- If valid name exists → uses it in greeting only
- If no name → continues without name
- No deviation from instruction

### Example 3: Specific control

```
השתמש בשם הלקוח רק לאחר שהשיחה התחילה, ולא בברכה.
השתמש בשם פעם אחת בלבד.
```

**Result:** Exactly as instructed - not in greeting, only once later

## Decision Matrix

| Valid Name | Business Instructs | Behavior |
|------------|-------------------|----------|
| Yes | Yes | Uses name per instruction |
| Yes | No | NEVER uses name |
| No | Yes | No name available |
| No | No | No name available |

## Technical Details

- **Prompt Length:** ~1904 chars (inbound), ~1898 chars (outbound)
- **Max Limit:** 2,000 chars
- **Architecture:** System prompt = behavior only, Business prompt = content
- **Default:** NO name usage (strict)

## Code Changes

**Modified:**
- `server/services/realtime_prompt_builder.py` (system prompt function)

**Created:**
- Test suite: `test_hebrew_natural_ai.py`
- User guide: `מדריך_שימוש_בשם_לקוח.md`
