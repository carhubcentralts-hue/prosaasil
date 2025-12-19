# תיקון בדיקת הגדרות תיאום פגישות

## סיכום השינוי

### ❌ לפני: שני תנאים
```python
if call_goal == 'appointment' and enable_calendar_scheduling:
    # Enable tools
```

### ✅ אחרי: תנאי אחד בלבד
```python
if call_goal == 'appointment':
    # Enable tools - business policy handles everything else
```

---

## הסבר

### מה השתנה?
הוסרה הבדיקה של `enable_calendar_scheduling` לחלוטין.

**כעת רק `call_goal` קובע אם תיאום פגישות זמין:**
- `call_goal = "appointment"` → כלי תיאום פגישות זמינים ✅
- `call_goal = "lead_only"` → כלי תיאום פגישות לא זמינים ❌

### מי מטפל בשעות ובמשך תור?
**Business Policy** (`server/policy/business_policy.py`) מטפל בכל ההגדרות:
- ✅ שעות פתיחה (`opening_hours`)
- ✅ משך תור (`slot_size_min`)
- ✅ אזור זמן (`tz`)
- ✅ חלון הזמנה (`booking_window_days`)
- ✅ זמן מינימום מראש (`min_notice_min`)
- ✅ 24/7 או שעות מוגדרות (`allow_24_7`)

---

## קבצים שתוקנו

### 1. `/workspace/server/media_ws_ai.py`

#### 🔧 תיקון 1: רישום כלים ל-Realtime API
```python
# Before:
if call_goal == 'appointment' and enable_scheduling:
    tools.append(availability_tool)
    tools.append(appointment_tool)

# After:
if call_goal == 'appointment':
    tools.append(availability_tool)
    tools.append(appointment_tool)
```

#### 🔧 תיקון 2: בדיקה ב-check_availability handler
```python
# Before:
if call_goal != 'appointment' or not call_config or not call_config.enable_calendar_scheduling:
    return error

# After:
if call_goal != 'appointment':
    return error
```

#### 🔧 תיקון 3: בדיקה ב-schedule_appointment handler
```python
# Before:
if call_goal != 'appointment':
    return error
if not call_config or not call_config.enable_calendar_scheduling:
    return error

# After:
if call_goal != 'appointment':
    return error
# That's it!
```

### 2. `/workspace/server/agent_tools/agent_factory.py`

#### 🔧 תיקון 4: בדיקת כלים ל-AgentKit
```python
# Before:
call_goal = getattr(settings, 'call_goal', 'lead_only')
enable_scheduling = getattr(settings, 'enable_calendar_scheduling', False)
calendar_tools_enabled = (call_goal == 'appointment' and enable_scheduling)

# After:
call_goal = getattr(settings, 'call_goal', 'lead_only')
calendar_tools_enabled = (call_goal == 'appointment')
```

#### 🔧 תיקון 5: בדיקה בwrapper של calendar_find_slots
```python
# Before:
if call_goal != 'appointment' or not enable_scheduling:
    return error

# After:
if call_goal != 'appointment':
    return error
```

#### 🔧 תיקון 6: בדיקה בwrapper של calendar_create_appointment
```python
# Before:
if call_goal != 'appointment' or not enable_scheduling:
    return error

# After:
if call_goal != 'appointment':
    return error
```

---

## איך Business Policy עובד

### טעינת Policy
```python
from server.policy.business_policy import get_business_policy

policy = get_business_policy(business_id, prompt_text=None)
```

### מה Policy מכיל?
```python
class BusinessPolicy:
    tz: str = "Asia/Jerusalem"
    slot_size_min: int = 60  # מתוך DB: appointment_slot_minutes
    allow_24_7: bool = False
    opening_hours: Dict[str, List[List[str]]] = {
        "sun": [["09:00", "17:00"]],
        "mon": [["09:00", "17:00"]],
        ...
    }
    booking_window_days: int = 30
    min_notice_min: int = 60
    require_phone_before_booking: bool = True
```

### שימוש ב-Implementation
```python
# מתוך _calendar_find_slots_impl
policy = get_business_policy(business_id)

# שעות פתיחה
weekday_key = weekday_map[date.weekday()]
opening_windows = policy.opening_hours.get(weekday_key, [])

# משך תור
slot_end = slot_start + timedelta(minutes=input.duration_min or policy.slot_size_min)

# 24/7?
if not policy.allow_24_7:
    # Check business hours
```

---

## דוגמה: זרימה מלאה

### שיחה קולית (Realtime API)
```
1. Session starts → _build_realtime_tools_for_call()
   ├─ Load settings from DB
   ├─ Check: call_goal == "appointment"? ✅
   └─ Register tools: check_availability, schedule_appointment

2. User: "רוצה תור מחר ב-14:00"
   └─ AI calls check_availability(date="2025-12-20", preferred_time="14:00")

3. check_availability handler
   ├─ Verify: call_goal == "appointment"? ✅
   ├─ Call: _calendar_find_slots_impl(business_id, date, ...)
   └─ Inside implementation:
       ├─ Load policy: get_business_policy(business_id)
       ├─ Get opening_hours from policy
       ├─ Get slot_size_min from policy (e.g., 60 minutes)
       ├─ Generate slots within business hours
       └─ Return available slots

4. AI: "יש פנוי ב-14:00 או 15:00, מה מתאים?"

5. User: "14:00" + provides name
   └─ AI calls schedule_appointment(name, date, time)

6. schedule_appointment handler
   ├─ Verify: call_goal == "appointment"? ✅
   ├─ Call: _calendar_create_appointment_impl(...)
   └─ Inside implementation:
       ├─ Load policy: get_business_policy(business_id)
       ├─ Validate against policy.opening_hours
       ├─ Validate against policy.min_notice_min
       ├─ Create Appointment in DB
       └─ Return appointment_id

7. AI: "מעולה! הפגישה נקבעה ל-20/12 בשעה 14:00. נקבע ביומן!"
```

### WhatsApp (AgentKit)
```
1. Message arrives → ai_service.py → get_or_create_agent()
   ├─ Load settings from DB
   ├─ Check: call_goal == "appointment"? ✅
   └─ Add tools to agent: calendar_find_slots_wrapped, calendar_create_appointment_wrapped

2. User: "רוצה תור"

3. calendar_find_slots_wrapped
   ├─ Verify: call_goal == "appointment"? ✅
   ├─ Call: _calendar_find_slots_impl(business_id, ...)
   └─ Same implementation as Realtime!

4. calendar_create_appointment_wrapped
   ├─ Verify: call_goal == "appointment"? ✅
   ├─ Call: _calendar_create_appointment_impl(...)
   └─ Same implementation as Realtime!
```

---

## לוגים לאימות

### הצלחה
```bash
# Realtime
[TOOLS][REALTIME] Appointment tools ENABLED (call_goal=appointment) for business 123
✅ [CHECK_AVAIL] CAL_AVAIL_OK business_id=123 slots_found=3
✅ [APPOINTMENT] CAL_CREATE_OK event_id=456

# AgentKit
📅 [AGENTKIT] Calendar tools check: call_goal=appointment, enabled=True
✅ [AGENTKIT] Calendar tools ENABLED for business 123
🔧 TOOL CALLED: calendar_find_slots_wrapped
✅ calendar_find_slots_wrapped RESULT: 3 slots found
```

### כלים לא זמינים
```bash
# Realtime
[TOOLS][REALTIME] Appointments DISABLED (call_goal=lead_only) - no tools for business 123

# AgentKit
📅 [AGENTKIT] Calendar tools check: call_goal=lead_only, enabled=False
📵 [AGENTKIT] Calendar tools DISABLED for business 123 (call_goal != 'appointment')
```

---

## סיכום

| אלמנט | מי מטפל | איפה מוגדר |
|-------|---------|-----------|
| **האם תיאום פגישות זמין?** | `call_goal == "appointment"` | `BusinessSettings` table |
| **שעות פתיחה** | `policy.opening_hours` | `BusinessSettings.business_hours` (JSON) |
| **משך תור** | `policy.slot_size_min` | `BusinessSettings.appointment_slot_minutes` |
| **אזור זמן** | `policy.tz` | Hard-coded `Asia/Jerusalem` |
| **חלון הזמנה** | `policy.booking_window_days` | Default 30 days |
| **זמן מינימום** | `policy.min_notice_min` | Default 60 minutes |

---

## תזכורת חשובה

❌ **אל תבדוק `enable_calendar_scheduling` - שדה זה לא משמש יותר!**

✅ **רק `call_goal` קובע:**
- `call_goal = "appointment"` → כלים זמינים
- `call_goal = "lead_only"` → כלים לא זמינים

✅ **Business Policy מטפל בכל השאר:**
- שעות
- משך תור
- חלון הזמנה
- אזור זמן
- 24/7 או שעות מוגדרות

---

**תאריך**: 19 דצמבר 2025  
**סטטוס**: ✅ תוקן ואומת
