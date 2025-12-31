# Tool Response.create Fixes - Ready for Copy-Paste

## Replacements for check_availability handler

### Fix 1: No business_id error (around line 13554)
```python
# OLD:
                    await client.send_event({"type": "response.create"})
                    return

# NEW:
                    await self.trigger_response_from_tool(client, "check_availability_no_business", force=False)
                    return
```

### Fix 2: Call goal not appointment (around line 13573)
```python
# OLD:
                    await client.send_event({"type": "response.create"})
                    return

# NEW:
                    await self.trigger_response_from_tool(client, "check_availability_disabled", force=False)
                    return
```

### Fix 3: Missing date (around line 13616)
```python
# OLD:
                    await client.send_event({"type": "response.create"})

# NEW:
                    await self.trigger_response_from_tool(client, "check_availability_missing_date", force=False)
```

### Fix 4: Success case (around line 13670)
```python
# OLD:
                        await client.send_event({"type": "response.create"})

# NEW:
                        await self.trigger_response_from_tool(client, "check_availability_success", force=False)
```

### Fix 5: More success cases (around lines 13740, 13843)
```python
# OLD:
                    await client.send_event({"type": "response.create"})

# NEW:
                    await self.trigger_response_from_tool(client, "check_availability_result", force=False)
```

### Fix 6: JSON parse error (around line 13889)
```python
# OLD:
                await client.send_event({"type": "response.create"})

# NEW:
                await self.trigger_response_from_tool(client, "check_availability_error", force=False)
```

---

## Replacements for schedule_appointment handler

### Fix 7: No business_id (around line 13912)
```python
# OLD:
                    await client.send_event({"type": "response.create"})
                    return

# NEW:
                    await self.trigger_response_from_tool(client, "schedule_appointment_no_business", force=False)
                    return
```

### Fix 8: Already created (around line 13929)
```python
# OLD:
                    await client.send_event({"type": "response.create"})
                    return

# NEW:
                    await self.trigger_response_from_tool(client, "schedule_appointment_duplicate", force=False)
                    return
```

### Fix 9: Scheduling disabled (around line 13949)
```python
# OLD:
                    await client.send_event({"type": "response.create"})
                    return

# NEW:
                    await self.trigger_response_from_tool(client, "schedule_appointment_disabled", force=False)
                    return
```

---

## Pattern for remaining calls

For any remaining `await client.send_event({"type": "response.create"})` in function handlers:

1. Identify the context (success/error/which tool)
2. Replace with: `await self.trigger_response_from_tool(client, "<tool>_<context>", force=False)`
3. Use descriptive names: `check_availability_success`, `schedule_appointment_error`, etc.

## Why force=False?

- Tools should respect user_speaking check
- Tools should respect hangup check
- Only use `force=True` for critical error recovery (rare!)

## Verification

After changes, search for:
```bash
grep -n 'await client.send_event({"type": "response.create"})' server/media_ws_ai.py
```

Should only find calls OUTSIDE function handlers (lines <13400 or >14600).
