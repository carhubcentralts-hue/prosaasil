"""
Calendar Tools for AgentKit - Find slots and create appointments
Integrates with existing Appointment model
"""
from agents import function_tool
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import pytz
from server.models_sql import db, Appointment, BusinessSettings
from server.agent_tools.phone_utils import normalize_il_phone
import logging
import time

logger = logging.getLogger(__name__)

# ⚡ Israel timezone
tz = pytz.timezone("Asia/Jerusalem")


def _choose_phone(input_phone: Optional[str], context: Optional[Dict[str, Any]] = None, session: Optional[Any] = None) -> Optional[str]:
    """
    Smart phone number selection with fallback hierarchy
    
    Priority order:
    1. input_phone (if Agent provided it)
    2. context["customer_phone"] (from Flask g.agent_context)
    3. session.caller_number (from Twilio call)
    4. context["whatsapp_from"] (from WhatsApp message)
    
    Returns normalized E.164 format (+972...) or None
    """
    candidates = [
        input_phone,
        (context or {}).get("customer_phone"),
        getattr(session, "caller_number", None) if session else None,
        (context or {}).get("whatsapp_from"),
    ]
    
    for candidate in candidates:
        normalized = normalize_il_phone(candidate)
        if normalized:
            logger.info(f"📞 _choose_phone: selected '{normalized}' from candidate '{candidate}'")
            return normalized
    
    logger.info("📞 _choose_phone: No valid phone number found in any source")
    return None

# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class FindSlotsInput(BaseModel):
    """Input for finding available appointment slots"""
    business_id: int = Field(..., description="Business ID to check availability for", ge=1)
    date_iso: str = Field(..., description="Date in ISO format (YYYY-MM-DD) like '2025-11-04'")
    duration_min: int = Field(60, description="Duration in minutes", ge=15, le=240)

class Slot(BaseModel):
    """Single available time slot"""
    start_iso: str = Field(..., description="Start time in ISO format")
    end_iso: str = Field(..., description="End time in ISO format")
    start_display: str = Field(..., description="Display format like '10:00'")

class FindSlotsOutput(BaseModel):
    """Available time slots for the requested date"""
    slots: List[Slot]
    business_hours: str = "09:00-22:00"

class CreateAppointmentInput(BaseModel):
    """Input for creating a new appointment"""
    business_id: int = Field(..., description="Business ID", ge=1)
    customer_name: str = Field(..., description="Customer full name or placeholder", max_length=200)
    customer_phone: Optional[str] = Field(None, description="Customer phone in E.164 format (+972...) - optional, will use call context if not provided")
    treatment_type: str = Field(..., description="Type of service/treatment", min_length=2, max_length=100)
    start_iso: str = Field(..., description="Start time in ISO format")
    end_iso: str = Field(..., description="End time in ISO format")
    notes: Optional[str] = Field(None, description="Additional notes", max_length=1000)
    source: str = Field("ai_agent", description="Source of appointment")

class CreateAppointmentOutput(BaseModel):
    """Appointment creation result"""
    appointment_id: int
    status: str = "confirmed"
    confirmation_message: str

# ================================================================================
# INTERNAL FUNCTIONS (can be called directly)
# ================================================================================

def _calendar_find_slots_impl(input: FindSlotsInput, context: Optional[Dict[str, Any]] = None) -> FindSlotsOutput:
    """
    Find available slots for appointments - DYNAMIC POLICY (no hardcoded hours!)
    
    Uses business_policy.py to determine:
    - Slot size (15/30/60 minutes)
    - Working hours (24/7 or specific hours)
    - Booking window
    - Minimum notice
    """
    tool_start = time.time()
    try:
        from server.policy.business_policy import get_business_policy
        
        # 🔥 LOAD POLICY (DB + Prompt)
        prompt_text = (context or {}).get("business_prompt") if context else None
        policy = get_business_policy(input.business_id, prompt_text=prompt_text)
        
        # Parse date and localize to business timezone
        business_tz = pytz.timezone(policy.tz)
        naive_date = datetime.fromisoformat(input.date_iso)
        date = business_tz.localize(naive_date) if naive_date.tzinfo is None else naive_date
        today = datetime.now(business_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"📅 Finding slots for business_id={input.business_id}, date={input.date_iso}, policy: 24/7={policy.allow_24_7}, slot={policy.slot_size_min}min")
        
        # Validate date is not in the past
        if date.date() < today.date():
            logger.warning(f"Requested date {input.date_iso} is in the past")
            return FindSlotsOutput(slots=[])
        
        # Validate booking window
        days_ahead = (date.date() - today.date()).days
        if days_ahead > policy.booking_window_days:
            logger.warning(f"Date {input.date_iso} is beyond booking window ({policy.booking_window_days} days)")
            return FindSlotsOutput(slots=[])
        
        # Get weekday name for opening hours
        weekday_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        weekday_key = weekday_map[date.weekday()]
        
        # Get existing appointments for this date
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)
        
        existing = Appointment.query.filter(
            Appointment.business_id == input.business_id,
            Appointment.start_time >= start_of_day,
            Appointment.start_time < end_of_day,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).all()
        
        logger.info(f"📊 Found {len(existing)} existing appointments on {input.date_iso}")
        
        # Build list of available slots
        slots = []
        
        if policy.allow_24_7:
            # 24/7 mode - generate slots for entire day
            logger.info("🌐 24/7 mode - generating all-day slots")
            total_minutes = 24 * 60
            for minute_offset in range(0, total_minutes, policy.slot_size_min):
                hour = minute_offset // 60
                minute = minute_offset % 60
                
                slot_start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=input.duration_min)
                
                # Check minimum notice
                now = datetime.now(business_tz)
                if (slot_start - now).total_seconds() < policy.min_notice_min * 60:
                    continue
                
                # Check conflicts
                has_conflict = any(
                    (business_tz.localize(apt.start_time) if apt.start_time.tzinfo is None else apt.start_time) < slot_end and
                    (business_tz.localize(apt.end_time) if apt.end_time.tzinfo is None else apt.end_time) > slot_start
                    for apt in existing
                )
                
                if not has_conflict:
                    slots.append(Slot(
                        start_iso=slot_start.isoformat(),
                        end_iso=slot_end.isoformat(),
                        start_display=slot_start.strftime("%H:%M")
                    ))
        else:
            # Use opening hours from policy
            opening_windows = policy.opening_hours.get(weekday_key, [])
            logger.info(f"📆 Day: {weekday_key}, Windows: {opening_windows}")
            
            for window in opening_windows:
                if not window or len(window) < 2:
                    continue
                
                start_time_str, end_time_str = window[0], window[1]
                start_hour, start_min = map(int, start_time_str.split(':'))
                end_hour, end_min = map(int, end_time_str.split(':'))
                
                # Calculate total minutes in window
                window_start_min = start_hour * 60 + start_min
                window_end_min = end_hour * 60 + end_min
                
                # Generate slots for this window
                for minute_offset in range(window_start_min, window_end_min, policy.slot_size_min):
                    hour = minute_offset // 60
                    minute = minute_offset % 60
                    
                    slot_start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    slot_end = slot_start + timedelta(minutes=input.duration_min)
                    
                    # Skip if slot ends outside window
                    slot_end_min = slot_end.hour * 60 + slot_end.minute
                    if slot_end_min > window_end_min:
                        continue
                    
                    # Check minimum notice
                    now = datetime.now(business_tz)
                    if (slot_start - now).total_seconds() < policy.min_notice_min * 60:
                        continue
                    
                    # Check conflicts
                    has_conflict = any(
                        (business_tz.localize(apt.start_time) if apt.start_time.tzinfo is None else apt.start_time) < slot_end and
                        (business_tz.localize(apt.end_time) if apt.end_time.tzinfo is None else apt.end_time) > slot_start
                        for apt in existing
                    )
                    
                    if not has_conflict:
                        slots.append(Slot(
                            start_iso=slot_start.isoformat(),
                            end_iso=slot_end.isoformat(),
                            start_display=slot_start.strftime("%H:%M")
                        ))
        
        tool_latency = (time.time() - tool_start) * 1000  # ms
        logger.info(f"📅 RESULT: {len(slots)} available slots (slot_size={policy.slot_size_min}min, latency={tool_latency:.0f}ms)")
        return FindSlotsOutput(slots=slots, business_hours="24/7" if policy.allow_24_7 else "dynamic")
        
    except Exception as e:
        tool_latency = (time.time() - tool_start) * 1000
        logger.error(f"Error finding slots: {e}, latency={tool_latency:.0f}ms")
        raise ValueError(f"Failed to find slots: {str(e)}")

# Wrapped version for Agent SDK
@function_tool
def calendar_find_slots(input: FindSlotsInput) -> FindSlotsOutput:
    """Find available appointment slots - Agent SDK wrapper"""
    return _calendar_find_slots_impl(input)


def _calendar_create_appointment_impl(input: CreateAppointmentInput, context: Optional[Dict[str, Any]] = None, session: Optional[Any] = None) -> CreateAppointmentOutput:
    """
    Create a new appointment in the calendar
    
    CRITICAL - TIME FORMAT RULES:
    - start_iso & end_iso MUST be in ISO format with timezone info
    - Example: "2025-11-05T10:00:00+02:00" for 10:00 AM on Nov 5
    - Always use Asia/Jerusalem timezone (+02:00 or +03:00)
    - Calculate dates correctly: "tomorrow" = add 1 day to today
    - "next Tuesday" = find the next Tuesday from today
    
    Phone Number Handling:
    - Uses _choose_phone with fallback hierarchy
    - Can proceed with phone=None if not available
    - Phone will be in call log/WhatsApp context
    
    Validations (STRICTLY ENFORCED):
    - Business hours: 09:00-22:00 Asia/Jerusalem - appointments outside will be REJECTED
    - No conflicts with existing appointments - overlapping times will be REJECTED  
    - Start time must be in the future
    - Duration: 15-240 minutes
    - Treatment type: Required field
    
    Returns clear Hebrew error messages if validation fails.
    """
    try:
        # ⚡ Validate duration (15-240 minutes)
        duration_min = (datetime.fromisoformat(input.end_iso) - datetime.fromisoformat(input.start_iso)).total_seconds() / 60
        if duration_min < 15 or duration_min > 240:
            raise ValueError(f"משך הפגישה חייב להיות בין 15-240 דקות (קיבלתי: {duration_min:.0f} דקות)")
        
        # ⚡ Validate customer name (MUST be clear and specific!)
        if not input.customer_name or input.customer_name.strip() == "":
            raise ValueError("חובה לציין שם לקוח מלא. אנא שאל: 'על איזה שם לרשום?'")
        
        # Don't allow generic names
        generic_names = ["לקוח", "customer", "client", "unknown", "לא ידוע"]
        if input.customer_name.strip().lower() in generic_names:
            raise ValueError(f"שם הלקוח '{input.customer_name}' אינו ספציפי מספיק. אנא בקש שם מלא.")
        
        # Name must be at least 2 characters
        if len(input.customer_name.strip()) < 2:
            raise ValueError("שם הלקוח חייב להכיל לפחות 2 תווים")
        
        # 🔥 POLICY CHECK: Require phone before booking (Sect 3 from instructions)
        from server.policy.business_policy import get_business_policy
        policy = get_business_policy(input.business_id, context.get("business_prompt") if context else None)
        
        # 🔥 USE SMART PHONE SELECTION
        phone = _choose_phone(input.customer_phone, context, session)
        logger.info(f"📞 Final phone for appointment: {phone}")
        
        # 🔥 CRITICAL: Guard - phone required before booking (if policy requires it)
        if policy.require_phone_before_booking and not phone:
            logger.warning(f"❌ Phone required by policy but not provided for business {input.business_id}")
            return {
                "ok": False,
                "error": "need_phone",
                "message": "נדרש מספר טלפון לפני קביעת תור. תקליד/י עכשיו את מספר הטלפון במקלדת הטלפון ואז סיים/י ב-#"
            }
        
        # ⚡ Validate phone number IF provided
        if phone and phone.strip():
            # Phone must be reasonable length (9-15 digits with +)
            phone_digits = ''.join(c for c in phone if c.isdigit())
            if len(phone_digits) < 9 or len(phone_digits) > 15:
                return {
                    "ok": False,
                    "error": "validation_error",
                    "message": f"מספר הטלפון '{phone}' אינו תקין. אנא בקש את המספר שוב."
                }
        else:
            # No phone provided - that's OK, continue without it
            logger.warning("⚠️ Creating appointment without phone number")
            phone = None
        
        # ⚡ Validate treatment type
        if not input.treatment_type or input.treatment_type.strip() == "":
            raise ValueError("חובה לציין סוג טיפול/שירות")
        
        # 🔥 POLICY already loaded above - import additional validation helpers
        from server.policy.business_policy import validate_slot_time, get_nearby_slots
        
        # Parse times
        logger.info(f"📅 Parsing times from Agent: start={input.start_iso}, end={input.end_iso}")
        
        start = datetime.fromisoformat(input.start_iso)
        end = datetime.fromisoformat(input.end_iso)
        
        # Add timezone if not present
        business_tz = pytz.timezone(policy.tz)
        if start.tzinfo is None:
            start = business_tz.localize(start)
        if end.tzinfo is None:
            end = business_tz.localize(end)
        
        # Validate time range
        if start >= end:
            raise ValueError("זמן סיום חייב להיות אחרי זמן התחלה")
        
        # Validate not in the past
        now = datetime.now(business_tz)
        if start < now:
            raise ValueError("לא ניתן לקבוע פגישה בעבר")
        
        # 🔥 ON-GRID VALIDATION - Check if time is valid for slot size
        if not validate_slot_time(policy, start.hour, start.minute):
            nearby = get_nearby_slots(policy, start.hour, start.minute)
            return {
                "ok": False,
                "error": "off_grid",
                "message": f"השעה {start.strftime('%H:%M')} לא על הגריד (מרווחי {policy.slot_size_min} דקות)",
                "suggestions": nearby
            }
        
        # ⚡ Validate business hours (dynamic from policy)
        if not policy.allow_24_7:
            weekday_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
            weekday_key = weekday_map[start.weekday()]
            opening_windows = policy.opening_hours.get(weekday_key, [])
            
            # Check if time is within any window
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            is_within_hours = False
            
            for window in opening_windows:
                if len(window) >= 2:
                    window_start_h, window_start_m = map(int, window[0].split(':'))
                    window_end_h, window_end_m = map(int, window[1].split(':'))
                    window_start_min = window_start_h * 60 + window_start_m
                    window_end_min = window_end_h * 60 + window_end_m
                    
                    if start_minutes >= window_start_min and end_minutes <= window_end_min:
                        is_within_hours = True
                        break
            
            if not is_within_hours:
                hours_str = ", ".join([f"{w[0]}-{w[1]}" for w in opening_windows if len(w) >= 2])
                raise ValueError(f"שעות הפעילות: {hours_str}")
        
        # 🔥 CRITICAL FIX: Remove timezone BEFORE checking conflicts
        # DB stores naive datetimes, so comparison must use naive datetimes too
        start_naive = start.replace(tzinfo=None)
        end_naive = end.replace(tzinfo=None)
        
        # Check for conflicts (using naive datetimes to match DB storage)
        existing = Appointment.query.filter(
            Appointment.business_id == input.business_id,
            Appointment.start_time < end_naive,
            Appointment.end_time > start_naive,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).first()
        
        if existing:
            raise ValueError(f"יש חפיפה עם פגישה קיימת בשעה {existing.start_time.strftime('%H:%M')}")
        
        print(f"   🔥 TIMEZONE FIX:")
        print(f"      Before: start={start} (with timezone)")
        print(f"      After: start={start_naive} (naive, local Israel time)")
        print(f"      This ensures 14:00 Israel time saves as 14:00 in DB (not 12:00 UTC!)")
        
        # Create appointment (phone can be None - that's OK!)
        customer_name = input.customer_name or "לקוח"
        
        print(f"\n🔥🔥🔥 CREATING APPOINTMENT IN DATABASE 🔥🔥🔥")
        print(f"   business_id: {input.business_id}")
        print(f"   customer_name: {customer_name}")
        print(f"   phone: {phone}")
        print(f"   treatment_type: {input.treatment_type}")
        print(f"   start_time: {start_naive}")
        print(f"   end_time: {end_naive}")
        
        appointment = Appointment(
            business_id=input.business_id,
            title=f"{input.treatment_type} - {customer_name}",
            description=input.notes,
            start_time=start_naive,  # Save naive datetime (local Israel time)
            end_time=end_naive,      # Save naive datetime (local Israel time)
            status='confirmed',
            appointment_type='treatment',
            contact_name=customer_name,
            contact_phone=phone,  # Can be None! Phone is in call log
            auto_generated=True,
            notes=f"נקבע ע״י AI Agent\nמקור: {input.source}\nסוג טיפול: {input.treatment_type}"
        )
        
        print(f"   Appointment object created: {appointment}")
        
        db.session.add(appointment)
        print(f"   Added to session")
        
        db.session.commit()
        print(f"   ✅✅✅ COMMITTED TO DATABASE! Appointment ID: {appointment.id}")
        
        # Generate confirmation message
        day_name = start.strftime("%A")
        day_name_he = {
            "Monday": "שני", "Tuesday": "שלישי", "Wednesday": "רביעי",
            "Thursday": "חמישי", "Friday": "שישי", "Sunday": "ראשון", "Saturday": "שבת"
        }.get(day_name, day_name)
        
        confirmation = (
            f"מעולה! קבעתי לך {input.treatment_type} ליום {day_name_he} "
            f"{start.strftime('%d/%m')} בשעה {start.strftime('%H:%M')}. "
            f"נתראה! 😊"
        )
        
        logger.info(f"✅ Created appointment #{appointment.id} for {input.customer_name} on {start}")
        
        # 🔥 Phase 2G: Auto-send WhatsApp confirmation after phone bookings
        try:
            # 🔥 FIX: Use context parameter (passed from wrapper) instead of flask.g
            agent_context = context or {}
            channel = agent_context.get('channel')
            
            logger.info(f"📱 WhatsApp check: channel={channel}, context_keys={list(agent_context.keys())}")
            
            # Send WhatsApp confirmation ONLY for phone calls (not for WhatsApp conversations)
            # Support multiple channel names: 'phone', 'calls', 'voice_call'
            if channel in ['phone', 'calls', 'voice_call']:
                # Check if we have customer phone
                customer_phone_wa = phone or agent_context.get('customer_phone') or agent_context.get('whatsapp_from')
                
                if customer_phone_wa:
                    wa_start = time.time()
                    logger.info(f"📱 Sending WhatsApp confirmation to {customer_phone_wa} (booked via phone)")
                    
                    # Compute day name in Hebrew for WhatsApp message
                    day_name_eng = start.strftime("%A")
                    day_name_hebrew = {
                        "Monday": "שני", "Tuesday": "שלישי", "Wednesday": "רביעי",
                        "Thursday": "חמישי", "Friday": "שישי", "Sunday": "ראשון", "Saturday": "שבת"
                    }.get(day_name_eng, day_name_eng)
                    
                    # Format WhatsApp confirmation message
                    wa_message = (
                        f"🎉 *אישור פגישה*\n\n"
                        f"שלום {input.customer_name}!\n\n"
                        f"פגישתך נקבעה בהצלחה:\n"
                        f"📅 יום {day_name_hebrew} {start.strftime('%d/%m/%Y')}\n"
                        f"🕐 שעה {start.strftime('%H:%M')}\n"
                        f"💼 {input.treatment_type}\n\n"
                        f"נתראה! 😊"
                    )
                    
                    # Import WhatsApp service
                    from server.whatsapp_provider import get_whatsapp_service
                    wa_service = get_whatsapp_service()
                    
                    # Send WhatsApp message with error handling
                    try:
                        result = wa_service.send_message(to=customer_phone_wa, message=wa_message)
                        wa_latency = (time.time() - wa_start) * 1000  # Convert to ms
                        
                        if result.get('status') == 'sent':
                            logger.info(f"✅ WhatsApp confirmation sent successfully to {customer_phone_wa} (latency: {wa_latency:.0f}ms)")
                        else:
                            logger.warning(f"⚠️ WhatsApp confirmation failed: {result.get('error')} (latency: {wa_latency:.0f}ms)")
                    except Exception as wa_error:
                        wa_latency = (time.time() - wa_start) * 1000
                        logger.error(f"❌ WhatsApp send exception: {wa_error} (latency: {wa_latency:.0f}ms)")
                        # Don't re-raise - booking should succeed even if WhatsApp fails
                else:
                    logger.info("📱 Skipping WhatsApp confirmation - no phone number available")
            else:
                logger.info(f"📱 Skipping WhatsApp confirmation - channel is '{channel}' (not phone)")
                
        except Exception as e:
            # Don't fail the booking if WhatsApp send fails
            logger.error(f"❌ WhatsApp confirmation error: {e}")
            import traceback
            traceback.print_exc()
        
        return CreateAppointmentOutput(
            appointment_id=appointment.id,
            status='confirmed',
            confirmation_message=confirmation
        )
        
    except ValueError as e:
        # Return structured error instead of raising
        logger.warning(f"Validation error: {e}")
        return {
            "ok": False,
            "error": "validation_error",
            "message": str(e)
        }
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating appointment: {e}")
        return {
            "ok": False,
            "error": "appointment_error",
            "message": f"Failed to create appointment: {str(e)}"
        }

# Wrapped version for Agent SDK
@function_tool
def calendar_create_appointment(input: CreateAppointmentInput) -> CreateAppointmentOutput:
    """Create a new appointment - Agent SDK wrapper"""
    return _calendar_create_appointment_impl(input)
