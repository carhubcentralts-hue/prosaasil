"""
BUILD 174: Call Concurrency Limiter Service
מגביל מספר שיחות פעילות לכל עסק - מונע עומס יתר

Limits:
- MAX_OUTBOUND_CALLS_PER_BUSINESS = 3 (max parallel outbound calls)
- MAX_TOTAL_CALLS_PER_BUSINESS = 5 (inbound + outbound combined)
"""
import logging
from datetime import datetime, timedelta
from typing import Tuple
from server.models_sql import CallLog, db

log = logging.getLogger(__name__)

MAX_OUTBOUND_CALLS_PER_BUSINESS = 3
MAX_TOTAL_CALLS_PER_BUSINESS = 5

# 🔥 FIX: Terminal statuses for BOTH fields (status + call_status for backward compat)
# These indicate the call has ended
TERMINAL_CALL_STATUSES = ['completed', 'busy', 'no-answer', 'canceled', 'failed', 'ended', 'hangup']

# 🔥 FIX: Reduce max call age to 10 minutes (calls shouldn't last longer than this)
# This prevents counting stuck/stale calls that never properly completed
MAX_CALL_AGE_MINUTES = 10


def count_active_calls(business_id: int) -> int:
    """
    Count total active calls (inbound + outbound) for a business
    
    🔥 FIX: Use status as PRIMARY field (per models_sql.py line 105)
    Active = status NOT IN terminal statuses
    AND created within last MAX_CALL_AGE_MINUTES (to exclude stale entries)
    
    Note: We check status field (not deprecated call_status field)
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(minutes=MAX_CALL_AGE_MINUTES)
        
        # 🔥 FIX: Check 'status' field (PRIMARY) per models_sql.py documentation
        # A call is active if BOTH status AND call_status are NOT in terminal states
        # This prevents counting calls where one field was updated but not the other
        # 
        # CRITICAL BUG FIX: Changed from AND to OR logic using SQLAlchemy's or_()
        # Before: Both fields must be non-terminal (counted stuck calls as active)
        # After: If either field is terminal, the call is inactive
        from sqlalchemy import or_
        
        active_calls_query = CallLog.query.filter(
            CallLog.business_id == business_id,
            ~or_(
                CallLog.status.in_(TERMINAL_CALL_STATUSES),
                CallLog.call_status.in_(TERMINAL_CALL_STATUSES)
            ),
            CallLog.created_at >= cutoff_time
        )
        
        count = active_calls_query.count()
        
        # 🔥 DEBUG: Log details of active calls for troubleshooting
        if count > 0:
            active_calls = active_calls_query.limit(10).all()
            for call in active_calls:
                age_minutes = (datetime.utcnow() - call.created_at).total_seconds() / 60
                log.info(f"  📞 Active call: sid={call.call_sid[:20]}... status={call.status}, call_status={call.call_status}, age={age_minutes:.1f}min, direction={call.direction}")
        
        log.info(f"📊 Business {business_id}: {count} active calls (checked last {MAX_CALL_AGE_MINUTES} min)")
        return count
    except Exception as e:
        log.error(f"Error counting active calls for business {business_id}: {e}")
        return 0


def count_active_outbound_calls(business_id: int) -> int:
    """
    Count active outbound calls for a business
    
    🔥 FIX: Use status as PRIMARY field (per models_sql.py)
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(minutes=MAX_CALL_AGE_MINUTES)
        
        # 🔥 FIX: Check 'status' field (PRIMARY) + call_status (backward compat)
        # A call is active if BOTH status AND call_status are NOT in terminal states
        # CRITICAL BUG FIX: Changed from AND to OR logic using SQLAlchemy's or_()
        from sqlalchemy import or_
        
        active_calls_query = CallLog.query.filter(
            CallLog.business_id == business_id,
            CallLog.direction == 'outbound',
            ~or_(
                CallLog.status.in_(TERMINAL_CALL_STATUSES),
                CallLog.call_status.in_(TERMINAL_CALL_STATUSES)
            ),
            CallLog.created_at >= cutoff_time
        )
        
        count = active_calls_query.count()
        
        # 🔥 DEBUG: Log outbound calls specifically
        if count > 0:
            active_calls = active_calls_query.limit(10).all()
            for call in active_calls:
                age_minutes = (datetime.utcnow() - call.created_at).total_seconds() / 60
                log.info(f"  📤 Active outbound: sid={call.call_sid[:20]}... status={call.status}, call_status={call.call_status}, age={age_minutes:.1f}min")
        
        log.info(f"📊 Business {business_id}: {count} active outbound calls")
        return count
    except Exception as e:
        log.error(f"Error counting active outbound calls for business {business_id}: {e}")
        return 0


def check_call_limits(business_id: int, num_new_outbound: int = 1) -> Tuple[bool, str]:
    """
    Check if business can start new outbound calls
    
    Args:
        business_id: The business ID
        num_new_outbound: Number of new outbound calls to start (1-3)
    
    Returns:
        Tuple of (allowed: bool, error_message: str)
        If allowed=True, error_message is empty
    """
    active_total = count_active_calls(business_id)
    active_outbound = count_active_outbound_calls(business_id)
    
    log.info(f"📊 Call limits check: business={business_id}, active_total={active_total}, active_outbound={active_outbound}, new={num_new_outbound}")
    
    if active_total >= MAX_TOTAL_CALLS_PER_BUSINESS:
        return False, "כרגע יש יותר מדי שיחות פעילות עבור העסק. המתן לסיום חלק מהשיחות ונסה שוב."
    
    if active_total + num_new_outbound > MAX_TOTAL_CALLS_PER_BUSINESS:
        available = MAX_TOTAL_CALLS_PER_BUSINESS - active_total
        return False, f"ניתן להתחיל רק {available} שיחות נוספות. יש כרגע {active_total} שיחות פעילות."
    
    if active_outbound + num_new_outbound > MAX_OUTBOUND_CALLS_PER_BUSINESS:
        available = MAX_OUTBOUND_CALLS_PER_BUSINESS - active_outbound
        if available <= 0:
            return False, "ניתן להוציא עד שלוש שיחות יוצאות במקביל. המתן לסיום שיחה פעילה ונסה שוב."
        return False, f"ניתן להתחיל רק {available} שיחות יוצאות נוספות."
    
    return True, ""


def check_inbound_call_limit(business_id: int) -> Tuple[bool, str]:
    """
    Check if business can receive another inbound call
    
    Returns:
        Tuple of (allowed: bool, reject_message: str)
    """
    active_total = count_active_calls(business_id)
    
    if active_total >= MAX_TOTAL_CALLS_PER_BUSINESS:
        log.warning(f"⚠️ Inbound call rejected: business {business_id} at limit ({active_total} active)")
        return False, "כרגע כל הקווים של העסק תפוסים. נסה שוב בעוד מספר דקות, תודה."
    
    return True, ""


def get_call_counts(business_id: int) -> dict:
    """
    Get current call counts for UI display
    """
    return {
        "active_total": count_active_calls(business_id),
        "active_outbound": count_active_outbound_calls(business_id),
        "max_total": MAX_TOTAL_CALLS_PER_BUSINESS,
        "max_outbound": MAX_OUTBOUND_CALLS_PER_BUSINESS
    }
