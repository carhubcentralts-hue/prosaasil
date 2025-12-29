# SSOT Ownership - Single Source of Truth

## Purpose
Ensure the system operates with a single authoritative source for each domain, preventing "prompt soup", duplicate injections, and ensuring customer name and business script behavior exactly as configured.

## Ownership Map

### 1. System Behavior Rules
**Owner:** `server/services/realtime_prompt_builder.py`
- Universal behavior rules (turn-taking, voice style, customer name usage rules)
- Built once via `build_global_system_prompt()`
- Injected as conversation.item.create (system message)
- **Never modified** after injection

### 2. Business Script/Content
**Owner:** Database - `BusinessSettings` table
- Inbound: `BusinessSettings.ai_prompt`
- Outbound: `BusinessSettings.outbound_ai_prompt`
- **COMPACT version:** sent via `session.update.instructions` for fast greeting
- **FULL version:** injected via `conversation.item.create` after first response
- Built via `build_compact_greeting_prompt()` and `build_full_business_prompt()`

### 3. Customer Data (Name, etc.)
**Owner:** `NAME_ANCHOR` system in `media_ws_ai.py`
- Single injection point for customer name and usage policy
- Format: `CustomerName="..." NameUsage=ENABLED/DISABLED`
- Sources: `outbound_lead_name`, `crm_context.customer_name`, `pending_customer_name`
- Policy detected once from business prompt via `detect_name_usage_policy()`
- Re-injected only if name or policy changes (hash-based)

### 4. Realtime Session State
**Owner:** `server/media_ws_ai.py` - MediaStreamHandler class
- Per-call state (not global, not shared)
- Hash tracking: `_system_prompt_hash`, `_business_prompt_hash`, `_name_anchor_hash`
- Counters: `_system_items_count`, `_business_items_count`, `_name_anchor_count`
- **Scope:** Per MediaStreamHandler instance (per call)

### 5. WhatsApp Prompts
**Owner:** `server/ai_service.py`
- Separate from Realtime API prompts
- Should NOT share injection logic with Realtime
- If common logic needed, use helper functions with clear SSOT

## Anti-Patterns to Avoid

❌ **Do NOT:**
- Inject system rules from multiple places
- Mix business prompt sources (DB + hardcoded)
- Guess customer name usage (only explicit detection)
- Share session state across calls (global variables)
- Inject COMPACT as conversation.item (use session.instructions only)
- Re-inject prompts without hash comparison
- Add dynamic content (timestamps, call_sid) to prompts before hashing

✅ **Do:**
- Always hash-normalize text before comparison
- Use per-session scope for all state
- Log injection with hash for verification
- Follow SSOT for each domain
- Use idempotent injection logic

## Verification

### Expected Item Counts
- **At call start:** `system=1 business=0 name_anchor=1`
- **After PROMPT_UPGRADE:** `system=1 business=1 name_anchor=1`

### Expected Hash Behavior
- Hashes remain stable across same content
- Only NAME_ANCHOR hash may change (if name/policy changes)
- System and business hashes should NEVER change mid-call

### Expected Logging Pattern
```
[PROMPT_SEPARATION] global_system_prompt=injected hash=abc123
[NAME_POLICY] source=business_prompt result=True matched="תשתמש בשם"
[NAME_ANCHOR] injected name="דוד כהן" policy=ENABLED hash=def456
[PROMPT_SUMMARY] system=1 business=0 name_anchor=1 hashes: sys=abc123, biz=none, name=def456
[PROMPT_UPGRADE] call_sid=... hash=ghi789 type=EXPANSION_NOT_REBUILD
[NAME_ANCHOR] ensured ok (no change) hash=def456
[PROMPT_SUMMARY] system=1 business=1 name_anchor=1 hashes: sys=abc123, biz=ghi789, name=def456
```

## Enforcement

1. **Code Reviews:** Check for SSOT violations
2. **Tests:** Run anti-duplicate tests before deployment
3. **Monitoring:** Watch PROMPT_SUMMARY logs for anomalies
4. **Alerts:** Flag calls with `system>1`, `business>1`, or `name_anchor>2`

## Last Updated
2025-12-29 - Initial SSOT documentation
