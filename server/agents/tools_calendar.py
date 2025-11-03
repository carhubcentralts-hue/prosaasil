"""
Calendar Tools for AgentKit - Find slots and create appointments
Integrates with existing Appointment model
"""
from agents.tool import function_tool
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import pytz
from server.models_sql import db, Appointment, BusinessSettings
import logging

logger = logging.getLogger(__name__)

# ⚡ Israel timezone
tz = pytz.timezone("Asia/Jerusalem")

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
    customer_name: str = Field(..., description="Customer full name", min_length=2, max_length=200)
    customer_phone: str = Field(..., description="Customer phone in E.164 format (+972...)", pattern=r'^\+?[0-9]{10,15}$')
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

def _calendar_find_slots_impl(input: FindSlotsInput) -> FindSlotsOutput:
    """
    Find available slots for appointments
    
    Business logic:
    - Working hours: 09:00 - 22:00 Israel time
    - Slot intervals: every hour (09:00, 10:00, 11:00...)
    - Check conflicts with existing appointments
    """
    try:
        # Parse date and localize to Israel timezone
        naive_date = datetime.fromisoformat(input.date_iso)
        date = tz.localize(naive_date) if naive_date.tzinfo is None else naive_date
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"📅 Finding slots for business_id={input.business_id}, date={input.date_iso}, parsed={date}, today={today}")
        
        # Validate date is not in the past
        if date.date() < today.date():
            logger.warning(f"Requested date {input.date_iso} is in the past")
            return FindSlotsOutput(slots=[])
        
        # Get business settings for working hours
        settings = BusinessSettings.query.filter_by(tenant_id=input.business_id).first()
        working_hours = settings.working_hours if settings and settings.working_hours else "09:00-22:00"
        
        # Parse working hours (format: "09:00-22:00")
        start_hour, end_hour = 9, 22
        if '-' in working_hours:
            parts = working_hours.split('-')
            start_hour = int(parts[0].split(':')[0])
            end_hour = int(parts[1].split(':')[0])
        
        # Get existing appointments for this date
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        existing = Appointment.query.filter(
            Appointment.business_id == input.business_id,
            Appointment.start_time >= start_of_day,
            Appointment.start_time < end_of_day,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).all()
        
        logger.info(f"📊 Found {len(existing)} existing appointments on {input.date_iso}")
        for apt in existing:
            logger.info(f"   - {apt.start_time} to {apt.end_time}: {apt.title}")
        
        # Build list of available slots
        slots = []
        for hour in range(start_hour, end_hour):
            slot_start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(minutes=input.duration_min)
            
            # Skip if slot ends after working hours
            if slot_end.hour > end_hour:
                logger.debug(f"   ⏭️  Skipping {hour}:00 - ends after working hours ({slot_end.hour} > {end_hour})")
                continue
            
            # Check for conflicts with existing appointments
            has_conflict = False
            for apt in existing:
                apt_start = apt.start_time.replace(tzinfo=tz) if apt.start_time.tzinfo is None else apt.start_time
                apt_end = apt.end_time.replace(tzinfo=tz) if apt.end_time.tzinfo is None else apt.end_time
                
                # Check if slots overlap
                if (slot_start < apt_end and slot_end > apt_start):
                    has_conflict = True
                    logger.debug(f"   ❌ {hour}:00 conflicts with {apt.title}")
                    break
            
            if not has_conflict:
                logger.info(f"   ✅ {hour}:00 available")
                slots.append(Slot(
                    start_iso=slot_start.isoformat(),
                    end_iso=slot_end.isoformat(),
                    start_display=slot_start.strftime("%H:%M")
                ))
        
        logger.info(f"📅 RESULT: {len(slots)} available slots for business {input.business_id} on {input.date_iso}")
        return FindSlotsOutput(slots=slots, business_hours=working_hours)
        
    except Exception as e:
        logger.error(f"Error finding slots: {e}")
        raise ValueError(f"Failed to find slots: {str(e)}")

# Wrapped version for Agent SDK
@function_tool
def calendar_find_slots(input: FindSlotsInput) -> FindSlotsOutput:
    """Find available appointment slots - Agent SDK wrapper"""
    return _calendar_find_slots_impl(input)


def _calendar_create_appointment_impl(input: CreateAppointmentInput) -> CreateAppointmentOutput:
    """
    Create a new appointment in the calendar
    
    CRITICAL - TIME FORMAT RULES:
    - start_iso & end_iso MUST be in ISO format with timezone info
    - Example: "2025-11-05T10:00:00+02:00" for 10:00 AM on Nov 5
    - Always use Asia/Jerusalem timezone (+02:00 or +03:00)
    - Calculate dates correctly: "tomorrow" = add 1 day to today
    - "next Tuesday" = find the next Tuesday from today
    
    Validations (STRICTLY ENFORCED):
    - Business hours: 09:00-22:00 Asia/Jerusalem - appointments outside will be REJECTED
    - No conflicts with existing appointments - overlapping times will be REJECTED  
    - Start time must be in the future
    - Duration: 15-240 minutes
    - Phone format: Must start with + or 0
    - Treatment type: Required field
    
    Returns clear Hebrew error messages if validation fails.
    """
    try:
        # ⚡ Validate duration (15-240 minutes)
        duration_min = (datetime.fromisoformat(input.end_iso) - datetime.fromisoformat(input.start_iso)).total_seconds() / 60
        if duration_min < 15 or duration_min > 240:
            raise ValueError(f"משך הפגישה חייב להיות בין 15-240 דקות (קיבלתי: {duration_min:.0f} דקות)")
        
        # ⚡ Validate phone format
        phone = input.customer_phone.strip()
        if not phone.startswith('+') and not phone.startswith('0'):
            raise ValueError("מספר טלפון חייב להתחיל ב-+ או 0")
        if phone.startswith('0') and len(phone) < 9:
            raise ValueError("מספר טלפון לא תקין (קצר מדי)")
        
        # ⚡ Validate treatment type
        if not input.treatment_type or input.treatment_type.strip() == "":
            raise ValueError("חובה לציין סוג טיפול/שירות")
        
        # Parse times
        start = datetime.fromisoformat(input.start_iso)
        end = datetime.fromisoformat(input.end_iso)
        
        # Add timezone if not present
        if start.tzinfo is None:
            start = tz.localize(start)
        if end.tzinfo is None:
            end = tz.localize(end)
        
        # Validate time range
        if start >= end:
            raise ValueError("זמן סיום חייב להיות אחרי זמן התחלה")
        
        # Validate not in the past
        now = datetime.now(tz)
        if start < now:
            raise ValueError("לא ניתן לקבוע פגישה בעבר")
        
        # ⚡ Validate business hours (09:00-22:00 Asia/Jerusalem)
        if start.hour < 9 or end.hour > 22 or (end.hour == 22 and end.minute > 0):
            raise ValueError("שעות הפעילות הן 09:00-22:00 (שעון ישראל)")
        
        # Check for conflicts
        existing = Appointment.query.filter(
            Appointment.business_id == input.business_id,
            Appointment.start_time < end,
            Appointment.end_time > start,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).first()
        
        if existing:
            raise ValueError(f"יש חפיפה עם פגישה קיימת בשעה {existing.start_time.strftime('%H:%M')}")
        
        # Create appointment
        appointment = Appointment(
            business_id=input.business_id,
            title=f"{input.treatment_type} - {input.customer_name}",
            description=input.notes,
            start_time=start,
            end_time=end,
            status='confirmed',
            appointment_type='treatment',
            contact_name=input.customer_name,
            contact_phone=input.customer_phone,
            auto_generated=True,
            notes=f"נקבע ע״י AI Agent\nמקור: {input.source}\nסוג טיפול: {input.treatment_type}"
        )
        
        db.session.add(appointment)
        db.session.commit()
        
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
        
        return CreateAppointmentOutput(
            appointment_id=appointment.id,
            status='confirmed',
            confirmation_message=confirmation
        )
        
    except ValueError as e:
        # Re-raise validation errors
        logger.warning(f"Validation error: {e}")
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating appointment: {e}")
        raise ValueError(f"Failed to create appointment: {str(e)}")

# Wrapped version for Agent SDK
@function_tool
def calendar_create_appointment(input: CreateAppointmentInput) -> CreateAppointmentOutput:
    """Create a new appointment - Agent SDK wrapper"""
    return _calendar_create_appointment_impl(input)
