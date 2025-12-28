"""
Twilio Cost Analysis & Metrics Tracker
💰 Identifies high-cost calls and billing anomalies
🎯 SSOT: Single place for cost classification logic
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

log = logging.getLogger(__name__)

# Cost classification thresholds
STREAM_DURATION_RATIO_HIGH = 0.6  # Stream > 60% of call duration = suspicious
RECONNECT_COUNT_HIGH = 1  # More than 1 reconnect = cost issue
RECORDING_COUNT_HIGH = 1  # More than 1 recording = duplication cost


def calculate_cost_bucket(call_log) -> str:
    """
    Calculate estimated cost bucket for a call.
    
    Returns: "LOW" | "MED" | "HIGH"
    
    HIGH cost indicators:
    - Multiple stream reconnects (>1)
    - Stream duration >> call duration
    - Multiple recordings created
    - Many webhook retries
    """
    issues = []
    
    # Check stream reconnects
    if call_log.stream_connect_count and call_log.stream_connect_count > RECONNECT_COUNT_HIGH:
        issues.append(f"reconnects={call_log.stream_connect_count}")
    
    # Check stream to call duration ratio
    if (call_log.stream_duration_sec and call_log.duration and 
        call_log.duration > 0):
        ratio = call_log.stream_duration_sec / call_log.duration
        if ratio > STREAM_DURATION_RATIO_HIGH:
            issues.append(f"stream_ratio={ratio:.2f}")
    
    # Check recording count
    if call_log.recording_count and call_log.recording_count > RECORDING_COUNT_HIGH:
        issues.append(f"recordings={call_log.recording_count}")
    
    # Check webhook issues
    if call_log.webhook_11205_count and call_log.webhook_11205_count > 0:
        issues.append(f"11205_errors={call_log.webhook_11205_count}")
    
    if call_log.webhook_retry_count and call_log.webhook_retry_count > 2:
        issues.append(f"retries={call_log.webhook_retry_count}")
    
    # Classify
    if len(issues) >= 2:
        bucket = "HIGH"
    elif len(issues) == 1:
        bucket = "MED"
    else:
        bucket = "LOW"
    
    if issues:
        log.info(f"[COST] call_sid={call_log.call_sid} bucket={bucket} issues={issues}")
    
    return bucket


def update_cost_metrics(call_log, **metrics) -> None:
    """
    Update cost metrics for a call and recalculate bucket.
    
    Usage:
        update_cost_metrics(call_log, stream_connect_count=2, webhook_retry_count=1)
    """
    from server.app_factory import db
    
    # Update provided metrics
    for key, value in metrics.items():
        if hasattr(call_log, key):
            setattr(call_log, key, value)
    
    # Recalculate cost bucket
    call_log.estimated_cost_bucket = calculate_cost_bucket(call_log)
    
    try:
        db.session.commit()
    except Exception as e:
        log.error(f"[COST] Failed to update metrics for {call_log.call_sid}: {e}")
        db.session.rollback()


def log_cost_warning(call_sid: str, issue: str, details: str) -> None:
    """
    Log a cost-related warning for monitoring.
    
    These logs should be monitored for billing optimization.
    """
    log.warning(f"[COST_WARNING] call_sid={call_sid} issue={issue} details={details}")
    print(f"💰 [COST_WARNING] {call_sid}: {issue} - {details}")


def get_high_cost_calls_summary(business_id: Optional[int] = None, days: int = 7) -> Dict[str, Any]:
    """
    Get summary of high-cost calls for monitoring.
    
    Returns:
        {
            "total_calls": int,
            "high_cost_calls": int,
            "duplicate_recordings": int,
            "multiple_reconnects": int,
            "recommendations": [str]
        }
    """
    from server.models_sql import CallLog, db
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = db.session.query(CallLog).filter(CallLog.created_at > cutoff)
    if business_id:
        query = query.filter(CallLog.business_id == business_id)
    
    total = query.count()
    high_cost = query.filter(CallLog.estimated_cost_bucket == "HIGH").count()
    
    # Specific issues
    duplicate_recordings = query.filter(CallLog.recording_count > 1).count()
    multiple_reconnects = query.filter(CallLog.stream_connect_count > 1).count()
    
    recommendations = []
    if duplicate_recordings > 0:
        recommendations.append(f"⚠️ {duplicate_recordings} calls have duplicate recordings - check recording_mode SSOT")
    if multiple_reconnects > total * 0.1:  # More than 10% with reconnects
        recommendations.append(f"⚠️ {multiple_reconnects} calls had reconnects - check WebSocket stability")
    if high_cost > total * 0.2:  # More than 20% high cost
        recommendations.append(f"⚠️ {high_cost} high-cost calls ({high_cost/total*100:.1f}%) - review billing")
    
    return {
        "total_calls": total,
        "high_cost_calls": high_cost,
        "duplicate_recordings": duplicate_recordings,
        "multiple_reconnects": multiple_reconnects,
        "recommendations": recommendations,
        "period_days": days
    }


# Guard function to prevent recording mode conflicts
def validate_recording_mode(call_log) -> bool:
    """
    Validate that recording mode is consistent (no conflicts).
    
    🎙️ SSOT Guard: Ensures only one recording method is used
    
    Returns:
        True if valid, False if conflict detected
    """
    # Check for conflict: both TWILIO_CALL_RECORD and RECORDING_API
    # This should NEVER happen - it means double recording cost
    
    if call_log.recording_mode == "TWILIO_CALL_RECORD":
        # If using Twilio call record, should have been set at call creation
        # Check if recording_sid exists (which would indicate API recording too)
        if call_log.recording_sid:
            log_cost_warning(
                call_log.call_sid,
                "RECORDING_CONFLICT",
                f"Both TWILIO_CALL_RECORD and recording_sid exist - double billing!"
            )
            return False
    
    return True
