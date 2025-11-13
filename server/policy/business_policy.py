"""
Business Policy Engine - Dynamic appointment scheduling policy

NO HARDCODED HOURS! All policy comes from:
1. Database (BusinessSettings table)
2. Business prompt (parsed with regex)
3. Defaults (fallback only)

Usage:
    policy = get_business_policy(business_id, prompt_text="פתוח 24/7 כל רבע שעה")
    # Returns: BusinessPolicy(allow_24_7=True, slot_size_min=15, ...)
"""
import re
import time as time_module
from dataclasses import dataclass, asdict
from datetime import time
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class BusinessPolicy:
    """Complete business scheduling policy"""
    tz: str
    slot_size_min: int  # 15, 30, or 60 minutes
    allow_24_7: bool
    opening_hours: Dict[str, List[List[str]]]  # {"sun":[["10:00","20:00"]], ...}
    booking_window_days: int  # How far ahead can customers book
    min_notice_min: int  # Minimum notice required (in minutes)
    require_phone_before_booking: bool  # 🔥 Require phone number before booking

# Default policy (fallback if DB is empty)
DEFAULT_POLICY = BusinessPolicy(
    tz="Asia/Jerusalem",
    slot_size_min=60,
    allow_24_7=False,
    opening_hours={
        "sun": [["09:00", "22:00"]],
        "mon": [["09:00", "22:00"]],
        "tue": [["09:00", "22:00"]],
        "wed": [["09:00", "22:00"]],
        "thu": [["09:00", "22:00"]],
        "fri": [["09:00", "15:00"]],  # Friday shorter hours
        "sat": []  # Closed on Saturday
    },
    booking_window_days=30,
    min_notice_min=0,
    require_phone_before_booking=True  # 🔥 Phone required by default
)

def parse_policy_from_prompt(prompt: str) -> Dict[str, Any]:
    """
    Parse business policy from AI prompt text
    
    Supported patterns:
    - "24/7" → allow_24_7=True
    - "כל רבע שעה" / "15 דקות" → slot_size_min=15
    - "כל חצי שעה" / "30 דקות" → slot_size_min=30
    - "שעה עגולה" / "רק שעה שלמה" → slot_size_min=60
    - "10:00-20:00" or "10-20" → opening_hours
    - "ראשון עד חמישי" / "ימים א'-ה'" → days
    
    Returns:
        Dict with parsed policy fields (only those found in prompt)
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return {}
    
    parsed = {}
    
    # 24/7 detection
    if "24/7" in prompt or "24 שעות" in prompt or "כל היום" in prompt:
        parsed["allow_24_7"] = True
        logger.info("📅 Parsed: 24/7 mode enabled")
    
    # Slot size detection
    if "רבע שעה" in prompt or "15 דק" in prompt:
        parsed["slot_size_min"] = 15
        logger.info("📅 Parsed: 15-minute slots")
    elif "חצי שעה" in prompt or "30 דק" in prompt:
        parsed["slot_size_min"] = 30
        logger.info("📅 Parsed: 30-minute slots")
    elif "שעה עגולה" in prompt or "שעה שלמה" in prompt or "רק שעות עגולות" in prompt:
        parsed["slot_size_min"] = 60
        logger.info("📅 Parsed: Full hour slots only")
    
    # Opening hours detection (e.g., "10:00-20:00" or "10-20")
    hours_patterns = [
        r"(\d{1,2}):?00\s*[–\-]\s*(\d{1,2}):?00",  # "10:00-20:00" or "10-20"
        r"(\d{1,2})\s*עד\s*(\d{1,2})",  # "10 עד 20"
    ]
    
    for pattern in hours_patterns:
        matches = re.findall(pattern, prompt)
        if matches:
            start_h, end_h = matches[0]
            start_hour = int(start_h)
            end_hour = int(end_h)
            
            # Build opening hours for all weekdays
            opening_hours = {}
            
            # Check if specific days mentioned
            if "ראשון" in prompt or "א'" in prompt:
                days_list = []
                if "ראשון" in prompt or "א'" in prompt:
                    days_list.append("sun")
                if "שני" in prompt or "ב'" in prompt:
                    days_list.append("mon")
                if "שלישי" in prompt or "ג'" in prompt:
                    days_list.append("tue")
                if "רביעי" in prompt or "ד'" in prompt:
                    days_list.append("wed")
                if "חמישי" in prompt or "ה'" in prompt:
                    days_list.append("thu")
                if "שישי" in prompt or "ו'" in prompt:
                    days_list.append("fri")
                if "שבת" in prompt or "ש'" in prompt:
                    days_list.append("sat")
                
                # Check for ranges like "ראשון עד חמישי"
                if "עד" in prompt:
                    if "ראשון" in prompt and "חמישי" in prompt:
                        days_list = ["sun", "mon", "tue", "wed", "thu"]
                    elif "ראשון" in prompt and "שישי" in prompt:
                        days_list = ["sun", "mon", "tue", "wed", "thu", "fri"]
                
                for day in days_list:
                    opening_hours[day] = [[f"{start_hour:02d}:00", f"{end_hour:02d}:00"]]
            else:
                # Default: apply to all weekdays
                for day in ["sun", "mon", "tue", "wed", "thu"]:
                    opening_hours[day] = [[f"{start_hour:02d}:00", f"{end_hour:02d}:00"]]
                opening_hours["fri"] = [[f"{start_hour:02d}:00", "15:00"]]  # Friday shorter
                opening_hours["sat"] = []  # Closed Saturday
            
            parsed["opening_hours"] = opening_hours
            logger.info(f"📅 Parsed: Opening hours {start_hour}:00-{end_hour}:00")
            break
    
    # Minimum notice (e.g., "שעתיים לפני")
    notice_match = re.search(r"(\d+)\s*(שעות?|דקות?)\s*לפני", prompt)
    if notice_match:
        amount = int(notice_match.group(1))
        unit = notice_match.group(2)
        if "שע" in unit:
            parsed["min_notice_min"] = amount * 60
        else:
            parsed["min_notice_min"] = amount
        logger.info(f"📅 Parsed: Minimum notice {parsed['min_notice_min']} minutes")
    
    # Booking window (e.g., "עד 60 יום קדימה")
    window_match = re.search(r"(\d+)\s*יום", prompt)
    if window_match:
        parsed["booking_window_days"] = int(window_match.group(1))
        logger.info(f"📅 Parsed: Booking window {parsed['booking_window_days']} days")
    
    return parsed

# 🔥 FIX #5: Policy cache to reduce DB queries (MUST be after BusinessPolicy class!)
_POLICY_CACHE: Dict[int, tuple["BusinessPolicy", float]] = {}  # Use quoted annotation
_POLICY_CACHE_TTL = 300  # 5 minutes in seconds

def get_business_policy(
    business_id: int,
    prompt_text: Optional[str] = None,
    db_session: Optional[Any] = None
) -> BusinessPolicy:
    """
    Get complete business policy from DB + Prompt
    
    Priority (last wins):
    1. DEFAULT_POLICY (hardcoded fallback)
    2. Database BusinessSettings
    3. Parsed from prompt
    
    Args:
        business_id: Business ID
        prompt_text: Optional AI prompt to parse
        db_session: SQLAlchemy session (optional, will import if not provided)
    
    Returns:
        BusinessPolicy with all fields populated
    """
    from server.models_sql import BusinessSettings
    from server.db import db
    
    # 🔥 FIX #5: Check cache first (5min TTL) - SKIP if prompt override provided!
    now = time_module.time()
    if not prompt_text and business_id in _POLICY_CACHE:
        cached_policy, cached_time = _POLICY_CACHE[business_id]
        if now - cached_time < _POLICY_CACHE_TTL:
            # Cache hit! (only when NO prompt override)
            return cached_policy
    
    # Start with defaults
    merged = asdict(DEFAULT_POLICY)
    
    # Try to load from DB
    try:
        if db_session:
            settings = db_session.query(BusinessSettings).filter_by(tenant_id=business_id).first()
        else:
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if settings:
            # Override with DB values (if not None)
            if settings.timezone:
                merged["tz"] = settings.timezone
            if settings.slot_size_min is not None:
                merged["slot_size_min"] = settings.slot_size_min
            if settings.allow_24_7 is not None:
                merged["allow_24_7"] = settings.allow_24_7
            if settings.opening_hours_json:
                merged["opening_hours"] = settings.opening_hours_json
                logger.info(f"📅 Using opening_hours_json from BusinessSettings")
            else:
                # 🔥 NO FALLBACK! If opening_hours_json is empty, user MUST set it in UI
                logger.error(f"❌ opening_hours_json is EMPTY for business {business_id}! User must set hours in 'הגדרות תורים'")
                # Return empty hours - agent will see no slots available
                merged["opening_hours"] = {}
                    
            if settings.booking_window_days is not None:
                merged["booking_window_days"] = settings.booking_window_days
            if settings.min_notice_min is not None:
                merged["min_notice_min"] = settings.min_notice_min
            if hasattr(settings, 'require_phone_before_booking') and settings.require_phone_before_booking is not None:
                merged["require_phone_before_booking"] = settings.require_phone_before_booking
            
            logger.info(f"📊 Loaded policy from DB for business {business_id}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load policy from DB: {e}")
    
    # Parse prompt (highest priority)
    if prompt_text:
        try:
            prompt_overrides = parse_policy_from_prompt(prompt_text)
            merged.update(prompt_overrides)
            logger.debug(f"📝 Applied prompt overrides: {prompt_overrides}")  # 🔥 FIX #5: info → debug
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse prompt: {e}")
    
    # Build final policy
    policy = BusinessPolicy(**merged)
    
    # 🔥 FIX #5: Store in cache (only if NO prompt override)
    if not prompt_text:
        _POLICY_CACHE[business_id] = (policy, now)
    
    logger.debug(  # 🔥 FIX #5: info → debug (reduce noise)
        f"✅ Final policy for business {business_id}: "
        f"24/7={policy.allow_24_7}, slot={policy.slot_size_min}min, "
        f"tz={policy.tz}, window={policy.booking_window_days}days"
    )
    
    return policy


def validate_slot_time(policy: BusinessPolicy, hour: int, minute: int) -> bool:
    """
    Check if a specific time is on-grid for the slot size
    
    Args:
        policy: Business policy
        hour: Hour (0-23)
        minute: Minute (0-59)
    
    Returns:
        True if minute is valid for slot size (e.g., 0/15/30/45 for 15min slots)
    """
    return minute % policy.slot_size_min == 0


def get_nearby_slots(policy: BusinessPolicy, hour: int, minute: int) -> List[str]:
    """
    Get 2 nearest on-grid times if current time is off-grid
    
    Args:
        policy: Business policy
        hour: Requested hour
        minute: Requested minute
    
    Returns:
        List of 2 time strings (e.g., ["10:00", "10:15"])
    """
    slot_size = policy.slot_size_min
    
    # Round down to nearest slot
    minutes_before = (minute // slot_size) * slot_size
    
    # Round up to next slot
    minutes_after = minutes_before + slot_size
    hour_after = hour
    if minutes_after >= 60:
        minutes_after = 0
        hour_after = (hour + 1) % 24
    
    return [
        f"{hour:02d}:{minutes_before:02d}",
        f"{hour_after:02d}:{minutes_after:02d}"
    ]
