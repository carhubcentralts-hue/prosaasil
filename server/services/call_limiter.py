"""
BUILD 174: Call Concurrency Limiter Service
מגביל מספר שיחות פעילות לכל עסק - מונע עומס יתר

Limits:
- MAX_OUTBOUND_CALLS_PER_BUSINESS = 3 (max parallel outbound calls)
- MAX_TOTAL_CALLS_PER_BUSINESS = 5 (inbound + outbound combined)
"""
import logging
from typing import Tuple
from server.models_sql import CallLog, db

log = logging.getLogger(__name__)

MAX_OUTBOUND_CALLS_PER_BUSINESS = 3
MAX_TOTAL_CALLS_PER_BUSINESS = 5

ACTIVE_CALL_STATUSES = ['initiated', 'ringing', 'in-progress', 'queued', 'in_progress']


def count_active_calls(business_id: int) -> int:
    """
    Count total active calls (inbound + outbound) for a business
    
    Active = status in ['initiated', 'ringing', 'in-progress', 'queued']
    """
    try:
        count = CallLog.query.filter(
            CallLog.business_id == business_id,
            CallLog.status.in_(ACTIVE_CALL_STATUSES)
        ).count()
        return count
    except Exception as e:
        log.error(f"Error counting active calls for business {business_id}: {e}")
        return 0


def count_active_outbound_calls(business_id: int) -> int:
    """
    Count active outbound calls for a business
    """
    try:
        count = CallLog.query.filter(
            CallLog.business_id == business_id,
            CallLog.direction == 'outbound',
            CallLog.status.in_(ACTIVE_CALL_STATUSES)
        ).count()
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
