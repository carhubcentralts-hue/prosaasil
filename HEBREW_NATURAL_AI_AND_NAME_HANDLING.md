# Hebrew Natural AI + Customer Name Handling Implementation

## Overview

Two system prompt enhancements:
1. **Hebrew Natural Language**: Native Israeli Hebrew (not translated)
2. **Customer Name Handling**: Prompt-driven name usage

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

### Customer Name Rules

```python
"Customer Name Usage (Prompt-Driven): "
"You may receive lead context with customer_name field. "
"Default behavior: do NOT use the customer's name unless the business prompt explicitly instructs to use it. "
"If instructed to use the name: use it only if customer_name exists and is valid (not 'unknown', 'test', '-', or empty). "
"Never invent a name. If no valid name exists, continue naturally without mentioning a name. "
"Never ask for the customer's name unless the business prompt explicitly instructs you to ask. "
"When using the name: use it sparingly, typically once in greeting."
```

## Lead Context Structure

The AI receives customer name via `crm_context.customer_name` field.

**Source:** Lead model fields (`first_name`, `last_name`) or extracted from conversation.

**Validation:**
- Reject if value is: `null`, `""`, `"unknown"`, `"test"`, `"-"`
- Extract first word if full name (e.g., "דני לוי" → "דני")

## Business Prompt Control

**Enable name usage:**
```
אם יש שם לקוח בליד, פנה אליו בשמו פעם אחת בברכה.
```

**Disable name usage:**
(Don't mention name in business prompt)

## Decision Matrix

| Has Valid Name | Business Instructs | Behavior |
|----------------|-------------------|----------|
| Yes | Yes | Uses name |
| Yes | No | Ignores name |
| No | Yes | No name available |
| No | No | No name available |

## Technical Details

- **Prompt Length:** ~1850 chars (inbound), ~1844 chars (outbound)
- **Max Limit:** 2000 chars
- **Architecture:** System prompt = behavior only, Business prompt = content
- **Backward Compatible:** Yes (default = no name usage)

## Code Changes

**Modified:**
- `server/services/realtime_prompt_builder.py` (system prompt function)

**Created:**
- Test suite: `test_hebrew_natural_ai.py`
- User guide: `מדריך_שימוש_בשם_לקוח.md`
