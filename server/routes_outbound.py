"""
BUILD 174: Outbound Calls API Routes
שיחות יוצאות - API להתחלת שיחות AI יוצאות ללידים

Endpoints:
- POST /api/outbound_calls/start - Start outbound calls to leads
- GET /api/outbound_calls/templates - Get outbound call templates
- GET /api/outbound_calls/counts - Get current active call counts
"""
import os
import re
import logging
import json
import uuid
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import quote  # 🔧 BUILD 177: URL encode Hebrew characters
from sqlalchemy import func
from sqlalchemy import text
from flask import Blueprint, jsonify, request, g, session
from server.models_sql import db, CallLog, Lead, Business, OutboundCallTemplate, BusinessSettings, OutboundCallRun, OutboundCallJob, RecordingRun
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.services.call_limiter import check_call_limits, get_call_counts, MAX_TOTAL_CALLS_PER_BUSINESS, MAX_OUTBOUND_CALLS_PER_BUSINESS
from twilio.rest import Client

log = logging.getLogger(__name__)

# ✅ Compile regex pattern once at module level for performance
STATUS_FILTER_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def normalize_israeli_phone(phone: str) -> str:
    """
    Normalize Israeli phone number to E.164 format (+972XXXXXXXXX)
    
    Handles:
    - +972XXXXXXXXX -> +972XXXXXXXXX (already E.164)
    - 972XXXXXXXXX -> +972XXXXXXXXX (missing +)
    - 0XXXXXXXXX -> +972XXXXXXXXX (local format)
    - 05XXXXXXXX -> +9725XXXXXXXX (mobile local)
    
    Returns the original string if it can't be normalized
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    # Already in E.164 format with +972
    if cleaned.startswith('+972'):
        return cleaned
    
    # Has 972 prefix but missing +
    if cleaned.startswith('972') and len(cleaned) >= 12:
        return '+' + cleaned
    
    # Israeli local format (starts with 0)
    if cleaned.startswith('0') and len(cleaned) >= 10:
        # Remove leading 0 and add +972
        return '+972' + cleaned[1:]
    
    # If it already has a different country code (starts with +), keep it
    if cleaned.startswith('+'):
        return cleaned
    
    # Fallback: assume it's missing the leading 0 for Israeli mobile
    if len(cleaned) == 9 and cleaned[0] in '5':  # Israeli mobile without 0
        return '+972' + cleaned
    
    # Return original if we can't normalize
    log.warning(f"Could not normalize phone number: {phone}")
    return phone

outbound_bp = Blueprint("outbound", __name__)


def _get_lead_display_name(lead) -> str | None:
    """
    Get display name for lead - SSOT for name extraction from Lead model.
    
    🔥 NAME SSOT: Single function for lead name extraction
    Used when storing lead name in CallLog.customer_name or OutboundCallJob.lead_name
    
    Returns:
        - Lead.full_name (if available)
        - "first_name last_name" (if both available)
        - first_name or last_name (if only one available)
        - None (if no name available)
    """
    if not lead:
        return None
    
    # Try full_name property first
    full_name = getattr(lead, 'full_name', None)
    if full_name and full_name != "ללא שם":  # Don't use default placeholder
        return full_name
    
    # Fallback: Construct from first_name + last_name
    first = (lead.first_name or "").strip()
    last = (lead.last_name or "").strip()
    
    if first and last:
        return f"{first} {last}"
    elif first:
        return first
    elif last:
        return last
    
    return None


def get_business_phone(business_id: int) -> str | None:
    """Get the business phone number for outbound calls"""
    business = Business.query.get(business_id)
    if business and business.phone_e164:
        return business.phone_e164
    
    # 🔥 BUILD 186 FIX: Handle missing columns gracefully
    try:
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if settings and settings.phone_number:
            return settings.phone_number
    except Exception as db_err:
        log.warning(f"⚠️ Could not load settings for {business_id} (DB schema issue): {db_err}")
    
    return None


def get_public_host() -> str:
    """
    Get public host for webhook URLs
    
    CRITICAL: Must return valid host for Twilio callbacks to work
    Fails fast if no valid host configured (prevents silent failures)
    
    Returns:
        Valid hostname (never empty/None)
    
    Raises:
        RuntimeError: If no valid host is configured
    """
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        return public_host
    
    # Fallback to Replit domains
    replit_host = os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
    if replit_host:
        return replit_host
    
    # Localhost fallback only for development
    if os.environ.get('FLASK_ENV') == 'development' or os.environ.get('DEBUG') == '0':
        log.warning("⚠️ Using localhost for webhooks - this will not work in production!")
        return 'localhost'
    
    # FAIL FAST: No valid host in production
    error_msg = (
        "❌ CRITICAL: No public host configured for webhooks!\n"
        "Set PUBLIC_HOST environment variable to your domain (e.g., myapp.com)\n"
        "Without this, Twilio callbacks will fail and calls will not work."
    )
    log.error(error_msg)
    raise RuntimeError(error_msg)


@outbound_bp.route("/api/outbound_calls/templates", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_outbound_templates():
    """
    Get outbound call templates for current business
    
    Returns list of active templates with their prompts
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    # For system_admin without tenant context, return empty list (they need to view a specific business)
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"templates": [], "message": "בחר עסק לצפייה בתבניות"})
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        templates = OutboundCallTemplate.query.filter_by(
            business_id=tenant_id,
            is_active=True
        ).order_by(OutboundCallTemplate.name).all()
        
        result = []
        for t in templates:
            result.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "prompt_text": t.prompt_text,
                "greeting_template": t.greeting_template
            })
        
        return jsonify({"templates": result})
    
    except Exception as e:
        log.error(f"Error fetching templates: {e}")
        return jsonify({"error": "שגיאה בטעינת תבניות"}), 500


@outbound_bp.route("/api/outbound_calls/counts", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_call_counts_endpoint():
    """
    Get current active call counts for the business
    
    Returns:
        active_total: Total active calls
        active_outbound: Active outbound calls
        max_total: Maximum allowed total calls
        max_outbound: Maximum allowed outbound calls
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    # For system_admin without tenant context, return zero counts
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({
                "active_total": 0,
                "active_outbound": 0,
                "max_total": MAX_TOTAL_CALLS_PER_BUSINESS,
                "max_outbound": MAX_OUTBOUND_CALLS_PER_BUSINESS,
                "message": "בחר עסק לצפייה בשיחות פעילות"
            })
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        counts = get_call_counts(tenant_id)
        return jsonify(counts)
    except Exception as e:
        log.error(f"Error getting call counts: {e}")
        return jsonify({"error": "שגיאה בטעינת נתונים"}), 500


@outbound_bp.route("/api/inbound_calls/counts", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_inbound')
def get_inbound_call_counts_endpoint():
    """
    Get current active call counts for the business (inbound endpoint)
    
    This endpoint provides the same data as /api/outbound_calls/counts
    but is used by the inbound calls page for consistency.
    
    Returns:
        active_total: Total active calls
        active_outbound: Active outbound calls
        max_total: Maximum allowed total calls
        max_outbound: Maximum allowed outbound calls
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    # For system_admin without tenant context, return zero counts
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({
                "active_total": 0,
                "active_outbound": 0,
                "max_total": MAX_TOTAL_CALLS_PER_BUSINESS,
                "max_outbound": MAX_OUTBOUND_CALLS_PER_BUSINESS,
                "message": "בחר עסק לצפייה בשיחות פעילות"
            })
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        counts = get_call_counts(tenant_id)
        return jsonify(counts)
    except Exception as e:
        log.error(f"Error getting call counts: {e}")
        return jsonify({"error": "שגיאה בטעינת נתונים"}), 500


def _validate_project_access(project_id: int, tenant_id: int) -> bool:
    """
    Validate that project exists and belongs to tenant.
    
    Args:
        project_id: Project ID to validate
        tenant_id: Tenant ID to check ownership
        
    Returns:
        True if project exists and belongs to tenant, False otherwise
    """
    if not project_id:
        return True  # No project_id is valid (not all calls are from projects)
    
    project_exists = db.session.execute(text("""
        SELECT id FROM outbound_projects WHERE id = :project_id AND tenant_id = :tenant_id
    """), {'project_id': project_id, 'tenant_id': tenant_id}).scalar()
    
    return bool(project_exists)


def _start_bulk_queue(tenant_id: int, lead_ids: list, project_id: int = None) -> tuple:
    """
    Helper function to start bulk call queue with concurrency control
    
    Creates a run with concurrency=3 and starts background worker
    Returns JSON response with run_id and queued count
    
    Args:
        tenant_id: Business/tenant ID
        lead_ids: List of lead IDs to call
        project_id: Optional project ID to associate calls with
    """
    try:
        # Verify all leads belong to this tenant
        leads = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id
        ).all()
        
        if len(leads) != len(lead_ids):
            return jsonify({"error": "לא נמצאו כל הלידים שנבחרו"}), 404
        
        # Create run with concurrency=3
        run = OutboundCallRun()
        run.business_id = tenant_id
        run.concurrency = MAX_OUTBOUND_CALLS_PER_BUSINESS  # 3
        run.total_leads = len(lead_ids)
        run.queued_count = len(lead_ids)
        run.status = "running"
        db.session.add(run)
        db.session.flush()
        
        # Create jobs for each lead
        for lead_id in lead_ids:
            job = OutboundCallJob()
            job.run_id = run.id
            job.lead_id = lead_id
            job.status = "queued"
            # 🔥 NAME SSOT: Store lead name for NAME_ANCHOR system
            lead_obj = next((l for l in leads if l.id == lead_id), None)
            if lead_obj:
                job.lead_name = _get_lead_display_name(lead_obj)
            # 🎯 PROJECT TRACKING: Associate job with project if provided
            if project_id:
                job.project_id = project_id
            db.session.add(job)
        
        db.session.commit()
        
        log.info(f"✅ Created bulk call run {run.id} with {len(lead_ids)} leads, concurrency={MAX_OUTBOUND_CALLS_PER_BUSINESS}, project_id={project_id}")
        
        # Start background worker to process the queue
        # Note: Using daemon thread is safe here because:
        # 1. All state is persisted in database (OutboundCallRun, OutboundCallJob)
        # 2. cleanup_stuck_dialing_jobs() handles any interrupted jobs on restart
        # 3. This matches the pattern used in bulk_enqueue_outbound_calls endpoint
        thread = Thread(target=process_bulk_call_run, args=(run.id,), daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "message": f"הופעלו {len(lead_ids)} שיחות בתור ({MAX_OUTBOUND_CALLS_PER_BUSINESS} במקביל)",
            "run_id": run.id,
            "queued": len(lead_ids),
            "mode": "bulk_queue"
        }), 201
        
    except Exception as e:
        log.error(f"Error creating bulk call run: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"שגיאה בהפעלת השיחות: {str(e)}"}), 500


@outbound_bp.route("/api/outbound_calls/start", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def start_outbound_calls():
    """
    Start outbound AI calls to selected leads.
    Uses outbound_ai_prompt from business settings.
    
    For 1-3 leads: Starts calls immediately in parallel
    For >3 leads: Uses bulk queue system with concurrency control (max 3 concurrent)
    
    Request body:
    {
        "lead_ids": [123, 456, 789, ...]  // Any number of leads
    }
    
    Returns (for 1-3 leads):
    {
        "success": true,
        "calls": [
            {"lead_id": 123, "call_sid": "CA...", "status": "initiated"},
            ...
        ]
    }
    
    Returns (for >3 leads):
    {
        "success": true,
        "message": "הופעלו 100 שיחות בתור (3 במקביל)",
        "run_id": 123,
        "queued": 100,
        "mode": "bulk_queue"
    }
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני הפעלת שיחות יוצאות"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    lead_ids = data.get("lead_ids", [])
    project_id = data.get("project_id")  # Optional project_id for tracking
    
    if not lead_ids or not isinstance(lead_ids, list):
        return jsonify({"error": "יש לבחור לפחות ליד אחד"}), 400
    
    # Validate project_id if provided
    if project_id and not _validate_project_access(project_id, tenant_id):
        return jsonify({"error": "פרויקט לא נמצא"}), 404
    
    # ✅ FIX: If more than 3 leads, use bulk queue system with concurrency control
    # This ensures only 3 calls run in parallel, and as each completes, the next one starts
    if len(lead_ids) > MAX_OUTBOUND_CALLS_PER_BUSINESS:
        log.info(f"📞 Starting bulk queue for {len(lead_ids)} leads (concurrency={MAX_OUTBOUND_CALLS_PER_BUSINESS})")
        return _start_bulk_queue(tenant_id, lead_ids, project_id=project_id)
    
    # For 1-3 leads, use immediate parallel start (original behavior)
    allowed, error_msg = check_call_limits(tenant_id, len(lead_ids))
    if not allowed:
        return jsonify({"error": error_msg}), 429
    
    try:
        leads = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id
        ).all()
        
        if len(leads) != len(lead_ids):
            return jsonify({"error": "לא נמצאו כל הלידים שנבחרו"}), 404
        
        from_phone = get_business_phone(tenant_id)
        if not from_phone:
            return jsonify({"error": "מספר טלפון של העסק לא מוגדר"}), 400
        
        business = Business.query.get(tenant_id)
        business_name = business.name if business else "העסק"
        
        host = get_public_host()
        
        results = []
        
        for lead in leads:
            if not lead.phone_e164:
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead.full_name,
                    "status": "failed",
                    "error": "אין מספר טלפון לליד"
                })
                continue
            
            # Normalize phone number to E.164 format
            normalized_phone = normalize_israeli_phone(lead.phone_e164)
            log.info(f"📞 Phone normalization: {lead.phone_e164} -> {normalized_phone}")
            
            try:
                call_log = CallLog()
                call_log.business_id = tenant_id
                call_log.lead_id = lead.id
                call_log.from_number = from_phone
                call_log.to_number = normalized_phone  # Use normalized phone
                call_log.direction = "outbound"
                call_log.status = "initiated"
                call_log.call_status = "initiated"
                # 🔥 NAME SSOT: Store lead name for NAME_ANCHOR system
                call_log.customer_name = _get_lead_display_name(lead)
                # 🎯 PROJECT TRACKING: Associate call with project if provided
                if project_id:
                    call_log.project_id = project_id
                db.session.add(call_log)
                db.session.flush()
                
                lead_name = lead.full_name or "לקוח"
                
                # 🔥 SSOT: Use centralized outbound call service (prevents duplicates + saves cost)
                from server.services.twilio_outbound_service import create_outbound_call
                
                result = create_outbound_call(
                    to_phone=normalized_phone,
                    from_phone=from_phone,
                    business_id=tenant_id,
                    host=host,
                    lead_id=lead.id,
                    business_name=business_name,
                    lead_name=lead_name
                )
                
                call_sid = result["call_sid"]
                is_duplicate = result.get("is_duplicate", False)
                
                if is_duplicate:
                    log.warning(f"⚠️ [DEDUP] Skipping duplicate call for lead={lead.id}")
                    continue
                
                call_log.call_sid = call_sid
                call_log.status = "ringing"
                call_log.call_status = "ringing"
                db.session.commit()
                
                log.info(f"📞 Outbound call started: lead={lead.id}, call_sid={call_sid}")
                
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead_name,
                    "call_sid": call_sid,
                    "status": "initiated"
                })
            
            except Exception as e:
                log.error(f"Failed to start call to lead {lead.id}: {e}")
                db.session.rollback()
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead.full_name,
                    "status": "failed",
                    "error": str(e)
                })
        
        successful_calls = [r for r in results if r.get("status") == "initiated"]
        
        return jsonify({
            "success": len(successful_calls) > 0,
            "message": f"הופעלו {len(successful_calls)} שיחות מתוך {len(lead_ids)}",
            "calls": results
        })
        
    except Exception as e:
        log.error(f"Error starting outbound calls: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"שגיאה בהפעלת השיחות: {str(e)}"}), 500


@outbound_bp.route("/api/outbound_calls/jobs/<int:job_id>/status", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_outbound_job_status(job_id: int):
    """
    Get real-time status of an outbound call queue job (OutboundCallRun)
    
    Returns:
    {
        "job_id": 123,
        "status": "running",
        "total": 45,
        "processed": 12,
        "success": 10,
        "failed": 2,
        "in_progress": 3,
        "queued": 30,
        "progress_pct": 26.7,
        "can_cancel": true,
        "cancel_requested": false
    }
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can view any job
            pass
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        run = OutboundCallRun.query.get(job_id)
        
        if not run:
            return jsonify({"error": "תור לא נמצא"}), 404
        
        # Verify access if not system admin
        if tenant_id and run.business_id != tenant_id:
            return jsonify({"error": "אין גישה לתור זה"}), 403
        
        # Calculate processed count
        processed = run.completed_count + run.failed_count
        
        # Calculate progress percentage
        progress_pct = 0
        if run.total_leads > 0:
            progress_pct = round((processed / run.total_leads) * 100, 1)
        
        # Can cancel if running or queued
        can_cancel = run.status in ('running', 'queued') and not run.cancel_requested
        
        return jsonify({
            "job_id": run.id,
            "status": run.status,
            "total": run.total_leads,
            "processed": processed,
            "success": run.completed_count,
            "failed": run.failed_count,
            "in_progress": run.in_progress_count,
            "queued": run.queued_count,
            "progress_pct": progress_pct,
            "can_cancel": can_cancel,
            "cancel_requested": run.cancel_requested,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        })
        
    except Exception as e:
        log.error(f"Error getting job status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "שגיאה בקבלת מצב התור"}), 500


@outbound_bp.route("/api/outbound_calls/jobs/<int:job_id>/cancel", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def cancel_outbound_job(job_id: int):
    """
    Request cancellation of an outbound call queue job/run
    
    🔒 SECURITY: Enforces business isolation - users can only cancel runs for their business
    
    Sets cancel_requested=True. The worker will:
    1. Stop starting new calls
    2. Mark remaining queued jobs as cancelled
    3. Set run status to cancelled
    
    Returns:
    {
        "success": true,
        "message": "בקשת ביטול נשלחה"
    }
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can cancel any job
            pass
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        run = OutboundCallRun.query.get(job_id)
        
        if not run:
            return jsonify({"error": "תור לא נמצא"}), 404
        
        # 🔒 SECURITY: Verify access if not system admin
        if tenant_id and run.business_id != tenant_id:
            # 🔒 SECURITY: Log potential cross-business access attempt
            log.warning(f"[SECURITY] User from business {tenant_id} attempted to cancel run {job_id} which belongs to business {run.business_id}")
            return jsonify({"error": "אין גישה לתור זה"}), 403
        
        # 🔒 SECURITY: Double-check business_id matches (defensive programming)
        if tenant_id:
            if run.business_id != tenant_id:
                log.error(f"[SECURITY] Business ID mismatch in cancel: run.business_id={run.business_id} != tenant_id={tenant_id}")
                return jsonify({"error": "אין גישה לתור זה"}), 403
        
        # Check if already cancelled or completed
        if run.status in ('cancelled', 'completed', 'failed', 'stopped'):
            return jsonify({
                "success": False,
                "message": f"התור כבר במצב {run.status}"
            }), 400
        
        # 🔒 STATE MACHINE: Set cancel_requested flag
        run.cancel_requested = True
        run.updated_at = datetime.utcnow()
        db.session.commit()
        
        log.info(f"📞 [business_id={run.business_id}] Cancellation requested for run {job_id} by business {tenant_id or 'system_admin'}")
        
        return jsonify({
            "success": True,
            "message": "בקשת ביטול נשלחה - התור יופסק בקרוב"
        })
        
    except Exception as e:
        log.error(f"Error cancelling job: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": "שגיאה בביטול התור"}), 500


@outbound_bp.route("/api/outbound_calls/jobs/active", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_active_outbound_job():
    """
    Get the currently active outbound call job for this business
    
    Returns the most recent job that is in 'running' or 'queued' status.
    Used by frontend to restore progress bar after page refresh.
    
    Returns:
    {
        "job_id": 123,
        "status": "running",
        ...same fields as get_outbound_job_status...
    }
    
    Or 404 if no active job found
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        # Find most recent active run for this business
        run = OutboundCallRun.query.filter(
            OutboundCallRun.business_id == tenant_id,
            OutboundCallRun.status.in_(['running', 'queued'])
        ).order_by(OutboundCallRun.created_at.desc()).first()
        
        if not run:
            return jsonify({"error": "אין תור פעיל"}), 404
        
        # Calculate processed count
        processed = run.completed_count + run.failed_count
        
        # Calculate progress percentage
        progress_pct = 0
        if run.total_leads > 0:
            progress_pct = round((processed / run.total_leads) * 100, 1)
        
        # Can cancel if running or queued
        can_cancel = run.status in ('running', 'queued') and not run.cancel_requested
        
        return jsonify({
            "job_id": run.id,
            "status": run.status,
            "total": run.total_leads,
            "processed": processed,
            "success": run.completed_count,
            "failed": run.failed_count,
            "in_progress": run.in_progress_count,
            "queued": run.queued_count,
            "progress_pct": progress_pct,
            "can_cancel": can_cancel,
            "cancel_requested": run.cancel_requested,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        })
        
    except Exception as e:
        log.error(f"Error getting active job: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "שגיאה בקבלת תור פעיל"}), 500


@outbound_bp.route("/api/outbound_calls/templates", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def create_outbound_template():
    """
    Create a new outbound call template
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני יצירת תבנית"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    prompt_text = data.get("prompt_text", "").strip()
    greeting_template = data.get("greeting_template", "").strip()
    
    if not name:
        return jsonify({"error": "שם התבנית חובה"}), 400
    
    if not prompt_text:
        return jsonify({"error": "הנחיות לשיחה חובה"}), 400
    
    try:
        template = OutboundCallTemplate()
        template.business_id = tenant_id
        template.name = name
        template.description = description
        template.prompt_text = prompt_text
        template.greeting_template = greeting_template
        template.is_active = True
        db.session.add(template)
        db.session.commit()
        
        log.info(f"✅ Created outbound template: id={template.id}, name={name}")
        
        return jsonify({
            "success": True,
            "template": {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "prompt_text": template.prompt_text,
                "greeting_template": template.greeting_template
            }
        }), 201
        
    except Exception as e:
        log.error(f"Error creating template: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה ביצירת התבנית"}), 500


@outbound_bp.route("/api/outbound_calls/templates/<int:template_id>", methods=["DELETE"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def delete_outbound_template(template_id: int):
    """
    Soft delete (deactivate) an outbound call template
    """
    from flask import session
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני מחיקת תבנית"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        template = OutboundCallTemplate.query.filter_by(
            id=template_id,
            business_id=tenant_id
        ).first()
        
        if not template:
            return jsonify({"error": "תבנית לא נמצאה"}), 404
        
        template.is_active = False
        db.session.commit()
        
        return jsonify({"success": True, "message": "התבנית נמחקה"})
        
    except Exception as e:
        log.error(f"Error deleting template: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה במחיקת התבנית"}), 500


# ========================================================
# BUILD 182: Outbound Import Leads API
# ייבוא לידים מקובץ CSV לשיחות יוצאות
# ========================================================

MAX_IMPORTED_LEADS_PER_BUSINESS = 5000


@outbound_bp.route("/api/outbound/import-leads", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def import_outbound_leads():
    """
    BUILD 182: Import leads from CSV for outbound calls
    
    Accepts CSV/Excel/JSON and tries to auto-map columns. Only phone is required.
    Maximum 5000 leads per business total.
    
    Returns:
    {
        "success": true,
        "list_id": 123,
        "imported_count": 50,
        "skipped_count": 2,
        "errors_sample": ["שורה 3: טלפון לא תקין"],
        "mapping": {"phone": "טלפון", "name": "שם", "method": "header|content|fallback"}
    }
    """
    import csv
    import io
    from flask import session
    from server.models_sql import OutboundLeadList
    from typing import Any
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני ייבוא לידים"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        # Count existing imported leads for this business
        existing_count = Lead.query.filter_by(
            tenant_id=tenant_id,
            source="imported_outbound"
        ).count()

        # -----------------------------
        # Forgiving parsing + auto-mapping
        # -----------------------------
        header_synonyms = {
            "phone": [
                "phone", "phone_number", "mobile", "cell", "tel", "telephone",
                "טלפון", "נייד", "מספר", "מס טלפון", "מספר טלפון"
            ],
            "name": [
                "name", "full_name", "full name", "customer", "client",
                "שם", "שם מלא", "לקוח"
            ],
            "city": ["city", "address", "עיר", "כתובת"],
            "notes": ["notes", "comment", "comments", "remark", "הערות", "הערה"],
        }

        def _norm_header(h: str) -> str:
            return re.sub(r"\s+", " ", (h or "").strip().lower())

        def _looks_like_header_cell(cell: str) -> bool:
            c = (cell or "").strip()
            if not c:
                return False
            # headers are usually short and do not contain many digits
            digits = sum(ch.isdigit() for ch in c)
            letters = sum(ch.isalpha() for ch in c)
            return digits == 0 and (letters > 0 or len(c) <= 20)

        def _decode_bytes(raw: bytes) -> str:
            for enc in ("utf-8-sig", "utf-8", "cp1255", "iso-8859-8"):
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            # last resort
            return raw.decode("utf-8", errors="replace")

        def _strip_phone_chars(s: str) -> str:
            return re.sub(r"[^\d+]", "", (s or "").strip())

        def _normalize_phone_forgiving(raw_phone: str) -> str | None:
            """
            Forgiving phone normalization.
            Returns E.164-like string (e.g. +9725XXXXXXXX) or None if invalid.
            """
            if not raw_phone:
                return None

            cleaned = _strip_phone_chars(raw_phone)
            if not cleaned:
                return None

            # If starts with + and not Israeli, accept if it's plausibly E.164
            if cleaned.startswith("+") and not cleaned.startswith("+972"):
                digits_only = re.sub(r"\D", "", cleaned)
                if 10 <= len(digits_only) <= 15:
                    return cleaned  # keep as provided (+country...)
                return None

            digits = re.sub(r"\D", "", cleaned)

            # Israeli: +972XXXXXXXXX / 972XXXXXXXXX
            if digits.startswith("972"):
                national = digits[3:]
                # some exports include leading 0 after 972 -> strip it
                if national.startswith("0"):
                    national = national[1:]
                if 8 <= len(national) <= 10:
                    return "+972" + national
                return None

            # Israeli local: 0XXXXXXXX (landline 9) / 05XXXXXXXX (mobile 10)
            if digits.startswith("0"):
                national = digits[1:]
                if 8 <= len(national) <= 9:
                    return "+972" + national
                return None

            # Missing leading 0 (common in exports)
            # Mobile without 0: 5XXXXXXXX (9 digits)
            if len(digits) == 9 and digits.startswith("5"):
                return "+972" + digits
            # Landline without 0: 2/3/4/8/9 + 7 digits (8 digits total)
            if len(digits) == 8 and digits[0] in "23489":
                return "+972" + digits

            return None

        def _is_phone_like(value: Any) -> bool:
            if value is None:
                return False
            v = str(value).strip()
            if not v:
                return False
            return _normalize_phone_forgiving(v) is not None

        def _guess_phone_col(data_rows: list[list[str]]) -> int | None:
            if not data_rows:
                return None
            col_count = max(len(r) for r in data_rows)
            if col_count == 0:
                return None
            sample = data_rows[:200]
            best_idx = None
            best_ratio = 0.0
            for i in range(col_count):
                values = [r[i] if i < len(r) else "" for r in sample]
                non_empty = [v for v in values if str(v).strip()]
                if not non_empty:
                    continue
                phone_like = sum(1 for v in non_empty if _is_phone_like(v))
                ratio = phone_like / max(1, len(non_empty))
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = i
            # Accept if at least half looks like phone OR it's the only plausible column
            if best_idx is not None and best_ratio >= 0.35:
                return best_idx
            # fallback: if only 2 columns, pick the more phone-like one even if ratio is low
            if col_count == 2:
                scores = []
                for i in range(2):
                    values = [r[i] if i < len(r) else "" for r in sample]
                    non_empty = [v for v in values if str(v).strip()]
                    phone_like = sum(1 for v in non_empty if _is_phone_like(v))
                    scores.append(phone_like)
                return 0 if scores[0] >= scores[1] else 1
            return best_idx

        def _guess_name_col(data_rows: list[list[str]], phone_idx: int | None) -> int | None:
            if not data_rows:
                return None
            col_count = max(len(r) for r in data_rows)
            if col_count == 0:
                return None
            sample = data_rows[:200]
            best_idx = None
            best_score = -1.0
            for i in range(col_count):
                if phone_idx is not None and i == phone_idx:
                    continue
                values = [str(r[i]).strip() if i < len(r) and r[i] is not None else "" for r in sample]
                non_empty = [v for v in values if v]
                if not non_empty:
                    continue
                # "name-like": mostly letters/spaces, not phone-like, short-ish
                name_like = 0
                for v in non_empty:
                    if _is_phone_like(v):
                        continue
                    if len(v) > 60:
                        continue
                    if any(ch.isalpha() for ch in v):
                        name_like += 1
                score = name_like / max(1, len(non_empty))
                if score > best_score:
                    best_score = score
                    best_idx = i
            # If only 2 cols and phone col exists, assume the other is name
            if best_idx is None and col_count == 2 and phone_idx is not None:
                return 1 - phone_idx
            return best_idx

        def _find_header_index(headers: list[str], target: str) -> int | None:
            syns = {_norm_header(s) for s in header_synonyms.get(target, [])}
            for i, h in enumerate(headers):
                if _norm_header(h) in syns:
                    return i
            return None

        def _auto_name_from_phone(normalized_phone: str) -> str:
            digits_only = re.sub(r"\D", "", normalized_phone or "")
            last4 = digits_only[-4:] if len(digits_only) >= 4 else ""
            return f"ליד {last4}" if last4 else "ליד חדש"

        def _parse_rows_from_request() -> tuple[list[list[str]], dict[str, Any]]:
            """
            Returns (table_rows, meta)
            - table_rows: list of rows (each row is list of strings), including header row if present.
            - meta: parsing metadata (filename, kind)
            """
            # JSON array support
            if request.is_json:
                payload = request.get_json(silent=True)
                if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
                    payload_rows = payload.get("rows")
                    meta = {"kind": "json", "filename": None, "list_name": payload.get("list_name")}
                else:
                    payload_rows = payload
                    meta = {"kind": "json", "filename": None, "list_name": None}

                if not isinstance(payload_rows, list):
                    raise ValueError("JSON חייב להיות מערך של שורות (array) או אובייקט עם rows")

                # If it's a list of dicts, convert to a table with headers
                if payload_rows and isinstance(payload_rows[0], dict):
                    keys: list[str] = []
                    seen = set()
                    for item in payload_rows[:1000]:
                        if not isinstance(item, dict):
                            continue
                        for k in item.keys():
                            if k not in seen:
                                seen.add(k)
                                keys.append(str(k))
                    header = keys
                    out: list[list[str]] = [header]
                    for item in payload_rows:
                        if not isinstance(item, dict):
                            continue
                        out.append([str(item.get(k, "")).strip() if item.get(k) is not None else "" for k in header])
                    return out, meta

                # If it's list-of-lists, assume it's already a table
                out_rows: list[list[str]] = []
                for item in payload_rows:
                    if isinstance(item, list):
                        out_rows.append([str(v).strip() if v is not None else "" for v in item])
                    else:
                        # scalar -> single-column
                        out_rows.append([str(item).strip()])
                return out_rows, meta

            # Multipart file upload
            if 'file' not in request.files:
                raise ValueError("לא נבחר קובץ")

            file = request.files['file']
            if not file or file.filename == '':
                raise ValueError("לא נבחר קובץ")

            filename = file.filename or ""
            lower = filename.lower()
            raw = file.read()

            if lower.endswith(".csv"):
                content = _decode_bytes(raw)
                reader = csv.reader(io.StringIO(content))
                rows = [[(c or "").strip() for c in r] for r in reader]
                return rows, {"kind": "csv", "filename": filename, "list_name": request.form.get('list_name')}

            if lower.endswith(".xlsx"):
                try:
                    import openpyxl  # type: ignore
                except Exception:
                    raise ValueError("קובץ Excel (.xlsx) נתמך רק אם openpyxl מותקן בשרת")

                wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
                ws = wb.active
                rows = []
                for r in ws.iter_rows(values_only=True):
                    rows.append([str(v).strip() if v is not None else "" for v in r])
                return rows, {"kind": "xlsx", "filename": filename, "list_name": request.form.get('list_name')}

            raise ValueError("יש להעלות קובץ CSV או Excel (.xlsx) או לשלוח JSON")

        table_rows, parse_meta = _parse_rows_from_request()
        # Remove fully empty rows
        table_rows = [r for r in table_rows if any((c or "").strip() for c in r)]
        if not table_rows:
            return jsonify({"error": "הקובץ ריק או לא מכיל שורות"}), 400

        # Decide if first row is header
        first_row = table_rows[0]
        first_has_digits = any(any(ch.isdigit() for ch in (c or "")) for c in first_row)
        has_header = False
        if not first_has_digits:
            # if it looks like header-ish text in most cells, treat as header
            headerish = sum(1 for c in first_row if _looks_like_header_cell(c))
            has_header = headerish >= max(1, int(len(first_row) * 0.5))

        headers = first_row if has_header else [f"col_{i+1}" for i in range(max(len(r) for r in table_rows))]
        data_rows = table_rows[1:] if has_header else table_rows

        # Normalize row lengths
        col_count = max(len(headers), *(len(r) for r in data_rows)) if data_rows else len(headers)
        headers = (headers + [""] * col_count)[:col_count]
        padded_rows: list[list[str]] = []
        for r in data_rows:
            rr = (r + [""] * col_count)[:col_count]
            padded_rows.append(rr)

        # Mapping: by header first, then content, then fallback
        phone_idx = _find_header_index(headers, "phone") if has_header else None
        name_idx = _find_header_index(headers, "name") if has_header else None
        city_idx = _find_header_index(headers, "city") if has_header else None
        notes_idx = _find_header_index(headers, "notes") if has_header else None

        mapping_method = "header" if phone_idx is not None else "content"
        if phone_idx is None:
            phone_idx = _guess_phone_col(padded_rows)
        if name_idx is None:
            name_idx = _guess_name_col(padded_rows, phone_idx)

        # Fallback for 2 columns: assume name+phone but still validate phone-like
        if phone_idx is None and col_count == 2:
            # pick the more phone-like one
            phone_idx = _guess_phone_col(padded_rows)
            name_idx = 1 - phone_idx if phone_idx is not None else 0
            mapping_method = "fallback"

        rows_to_import: list[dict[str, Any]] = []
        errors: list[str] = []
        errors_sample: list[str] = []

        def _add_error(msg: str) -> None:
            errors.append(msg)
            if len(errors_sample) < 20:
                errors_sample.append(msg)

        # Row numbers: +1 for header line, +1 to make 1-based
        base_row_number = 2 if has_header else 1
        for idx, row in enumerate(padded_rows):
            row_num = base_row_number + idx

            raw_phone = row[phone_idx] if phone_idx is not None and phone_idx < len(row) else ""
            normalized_phone = _normalize_phone_forgiving(raw_phone)
            if not normalized_phone:
                if str(raw_phone).strip():
                    _add_error(f"שורה {row_num}: טלפון לא תקין - {raw_phone}")
                else:
                    _add_error(f"שורה {row_num}: חסר טלפון")
                continue

            raw_name = row[name_idx].strip() if name_idx is not None and name_idx < len(row) else ""
            name = raw_name if raw_name else _auto_name_from_phone(normalized_phone)
            city = row[city_idx].strip() if city_idx is not None and city_idx < len(row) else None
            notes = row[notes_idx].strip() if notes_idx is not None and notes_idx < len(row) else None

            rows_to_import.append({
                "name": name,
                "phone": normalized_phone,
                "city": city,
                "notes": notes,
            })
        
        # Check 5000 limit
        if existing_count + len(rows_to_import) > MAX_IMPORTED_LEADS_PER_BUSINESS:
            available = MAX_IMPORTED_LEADS_PER_BUSINESS - existing_count
            return jsonify({
                "error": f"לא ניתן לייבא יותר מ-{MAX_IMPORTED_LEADS_PER_BUSINESS} לידים ברשימת השיחות היוצאות. יש לך מקום ל-{available} לידים נוספים."
            }), 400
        
        if len(rows_to_import) == 0:
            # Keep 400 only when we truly couldn't extract a single valid phone
            return jsonify({
                "error": "לא נמצאו טלפונים תקינים לייבוא",
                "errors_sample": errors_sample,
                "errors": errors_sample,  # backwards-compat for existing UI
            }), 400
        
        # Create the import list
        list_name = (parse_meta or {}).get("list_name") or f"ייבוא {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        outbound_list = OutboundLeadList()
        outbound_list.tenant_id = tenant_id
        outbound_list.name = list_name
        outbound_list.file_name = (parse_meta or {}).get("filename") or "import"
        outbound_list.total_leads = len(rows_to_import)
        db.session.add(outbound_list)
        db.session.flush()  # Get the list ID
        
        # Import leads
        imported_count = 0
        for row_data in rows_to_import:
            # Split name into first/last
            name_parts = row_data['name'].split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            lead = Lead()
            lead.tenant_id = tenant_id
            lead.first_name = first_name
            lead.last_name = last_name
            lead.phone_e164 = row_data['phone']
            lead.notes = row_data['notes']
            lead.source = "imported_outbound"
            lead.outbound_list_id = outbound_list.id
            lead.status = "new"
            db.session.add(lead)
            imported_count += 1
        
        db.session.commit()
        
        log.info(f"✅ Imported {imported_count} leads for business {tenant_id}, list_id={outbound_list.id}")
        
        return jsonify({
            "success": True,
            "list_id": outbound_list.id,
            "list_name": list_name,
            "imported_count": imported_count,
            "skipped_count": len(errors),
            "errors_sample": errors_sample,
            "errors": errors_sample,  # keep existing UI contract
            "mapping": {
                "phone": headers[phone_idx] if phone_idx is not None and phone_idx < len(headers) else None,
                "name": headers[name_idx] if name_idx is not None and name_idx < len(headers) else None,
                "method": mapping_method,
                "has_header": has_header,
                "kind": (parse_meta or {}).get("kind"),
            }
        })
        
    except Exception as e:
        log.error(f"Error importing leads: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        # Some parsing errors should be user-facing 400
        msg = str(e) or "שגיאה בייבוא הלידים"
        if any(s in msg for s in ["לא נבחר קובץ", "CSV", "Excel", "JSON", "ריק"]):
            return jsonify({"error": msg}), 400
        return jsonify({"error": f"שגיאה בייבוא הלידים: {msg}"}), 500


@outbound_bp.route("/api/outbound/import-leads", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_imported_leads():
    """
    BUILD 182: Get imported leads for outbound calls
    
    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    - list_id: Optional filter by list ID
    - search: Optional search query
    - statuses[]: Optional multi-status filter (e.g., ?statuses[]=new&statuses[]=contacted)
    
    Returns:
    {
        "total": 1234,
        "limit": 5000,
        "current_count": 1234,
        "page": 1,
        "page_size": 50,
        "items": [...]
    }
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"items": [], "total": 0, "limit": MAX_IMPORTED_LEADS_PER_BUSINESS, "message": "בחר עסק לצפייה"})
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        page = max(1, int(request.args.get('page', 1)))
        # 🔥 FIX: Increase max page size to 10,000 for project creation
        page_size = min(10000, max(1, int(request.args.get('page_size', 50))))
        list_id = request.args.get('list_id', type=int)
        search = request.args.get('search', '').strip()
        statuses_filter = request.args.getlist('statuses[]')  # ✅ Multi-status filter
        
        # ✅ Validate status filter values against allowed statuses
        # Sanitize: only allow alphanumeric, underscore, dash (prevent injection)
        if statuses_filter:
            statuses_filter = [
                s for s in statuses_filter 
                if s and STATUS_FILTER_PATTERN.match(s) and len(s) <= 64
            ]
        
        # Build query
        query = Lead.query.filter_by(
            tenant_id=tenant_id,
            source="imported_outbound"
        )
        
        if list_id:
            query = query.filter_by(outbound_list_id=list_id)
        
        # ✅ Status filter: Support multi-status filtering with case-insensitive matching
        if statuses_filter:
            query = query.filter(func.lower(Lead.status).in_([s.lower() for s in statuses_filter]))
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term),
                    Lead.phone_e164.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Paginate
        leads = query.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        items = []
        for lead in leads:
            items.append({
                "id": lead.id,
                "name": lead.full_name,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "phone": lead.phone_e164,
                "status": lead.status,
                "notes": lead.notes,
                "list_id": lead.outbound_list_id,
                "created_at": lead.created_at.isoformat() if lead.created_at else None
            })
        
        return jsonify({
            "total": total,
            "limit": MAX_IMPORTED_LEADS_PER_BUSINESS,
            "current_count": total,
            "page": page,
            "page_size": page_size,
            "items": items
        })
        
    except Exception as e:
        log.error(f"Error fetching imported leads: {e}")
        return jsonify({"error": "שגיאה בטעינת הלידים"}), 500


@outbound_bp.route("/api/outbound/import-leads/<int:lead_id>", methods=["DELETE"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def delete_imported_lead(lead_id: int):
    """
    BUILD 182: Delete a single imported lead
    
    Only allows deletion of leads with source="imported_outbound"
    Regular CRM leads cannot be deleted from this endpoint.
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני מחיקת ליד"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=tenant_id
        ).first()
        
        if not lead:
            return jsonify({"error": "ליד לא נמצא"}), 404
        
        # Only allow deletion of imported leads
        if lead.source != "imported_outbound":
            return jsonify({"error": "ניתן למחוק רק לידים מיובאים מרשימת שיחות יוצאות"}), 403
        
        db.session.delete(lead)
        db.session.commit()
        
        log.info(f"🗑️ Deleted imported lead {lead_id} for business {tenant_id}")
        
        return jsonify({"success": True, "message": "הליד נמחק בהצלחה"})
        
    except Exception as e:
        log.error(f"Error deleting imported lead: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה במחיקת הליד"}), 500


@outbound_bp.route("/api/outbound/import-leads/bulk-delete", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def bulk_delete_imported_leads():
    """
    BUILD 182: Bulk delete imported leads - uses RQ worker for batch processing
    
    Request body:
    {
        "lead_ids": [1, 2, 3] OR
        "delete_all": true (delete all imported leads)
    }
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני מחיקה"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    delete_all = data.get('delete_all', False)
    lead_ids = data.get('lead_ids', [])
    
    if not delete_all and not lead_ids:
        return jsonify({"error": "לא נבחרו לידים למחיקה"}), 400
    
    user = session.get('user', {})
    
    # 🔥 USE BULK GATE: Check if enqueue is allowed
    try:
        import redis
        REDIS_URL = os.getenv('REDIS_URL')
        redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
        
        if redis_conn:
            from server.services.bulk_gate import get_bulk_gate
            bulk_gate = get_bulk_gate(redis_conn)
            
            if bulk_gate:
                # Check if enqueue is allowed
                allowed, reason = bulk_gate.can_enqueue(
                    business_id=tenant_id,
                    operation_type='delete_imported_leads',
                    user_id=user.get('id')
                )
                
                if not allowed:
                    return jsonify({"error": reason}), 429
    except Exception as e:
        log.warning(f"BulkGate check failed (proceeding anyway): {e}")
    
    try:
        # Count total leads to delete
        if delete_all:
            total = Lead.query.filter_by(
                tenant_id=tenant_id,
                source="imported_outbound"
            ).count()
        else:
            total = Lead.query.filter(
                Lead.id.in_(lead_ids),
                Lead.tenant_id == tenant_id,
                Lead.source == "imported_outbound"
            ).count()
        
        if total == 0:
            return jsonify({"error": "לא נמצאו לידים למחיקה"}), 404
        
        # Create BackgroundJob record
        from server.models_sql import BackgroundJob
        from rq import Queue
        import redis
        
        bg_job = BackgroundJob()
        bg_job.business_id = tenant_id
        bg_job.requested_by_user_id = user.get('id')
        bg_job.job_type = 'delete_imported_leads'
        bg_job.status = 'queued'
        bg_job.total = total
        bg_job.processed = 0
        bg_job.succeeded = 0
        bg_job.failed_count = 0
        bg_job.cursor = json.dumps({
            'delete_all': delete_all,
            'lead_ids': lead_ids,
            'last_id': 0
        })
        db.session.add(bg_job)
        db.session.commit()
        
        # Enqueue to RQ maintenance queue
        REDIS_URL = os.getenv('REDIS_URL')
        if REDIS_URL:
            redis_conn = redis.from_url(REDIS_URL)
            queue = Queue('maintenance', connection=redis_conn)
            
            # Acquire lock and record enqueue BEFORE actually enqueuing
            if redis_conn:
                try:
                    from server.services.bulk_gate import get_bulk_gate
                    bulk_gate = get_bulk_gate(redis_conn)
                    
                    if bulk_gate:
                        # Acquire lock for this operation
                        lock_acquired = bulk_gate.acquire_lock(
                            business_id=tenant_id,
                            operation_type='delete_imported_leads',
                            job_id=bg_job.id
                        )
                        
                        # Record the enqueue
                        bulk_gate.record_enqueue(
                            business_id=tenant_id,
                            operation_type='delete_imported_leads'
                        )
                except Exception as e:
                    log.warning(f"BulkGate lock/record failed (proceeding anyway): {e}")
            
            # Import and enqueue the job function
            from server.jobs.delete_imported_leads_job import delete_imported_leads_batch_job
            rq_job = queue.enqueue(
                delete_imported_leads_batch_job,
                bg_job.id,
                job_timeout='30m',
                job_id=f"delete_imported_leads_{bg_job.id}"
            )
            
            log.info(f"🚀 Enqueued RQ job for delete imported leads, job_id={bg_job.id}, rq_job_id={rq_job.id}")
        else:
            log.warning(f"⚠️ REDIS_URL not set, cannot enqueue delete job")
            bg_job.status = 'failed'
            bg_job.last_error = 'Redis not configured'
            db.session.commit()
            return jsonify({"error": "Job queue not available"}), 503
        
        return jsonify({
            "success": True,
            "message": f"נוצרה משימת מחיקה עבור {total} לידים",
            "job_id": bg_job.id,
            "total_leads": total
        }), 202  # 202 Accepted - processing in background
        
    except Exception as e:
        log.error(f"Error creating bulk delete job: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה ביצירת משימת מחיקה"}), 500


@outbound_bp.route("/api/outbound/import-lists", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_import_lists():
    """
    BUILD 182: Get all import lists for the business
    """
    from flask import session
    from server.models_sql import OutboundLeadList
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"lists": []})
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        lists = OutboundLeadList.query.filter_by(
            tenant_id=tenant_id
        ).order_by(OutboundLeadList.created_at.desc()).all()
        
        result = []
        for lst in lists:
            # Count current leads in list
            lead_count = Lead.query.filter_by(
                tenant_id=tenant_id,
                outbound_list_id=lst.id
            ).count()
            
            result.append({
                "id": lst.id,
                "name": lst.name,
                "file_name": lst.file_name,
                "total_leads": lst.total_leads,
                "current_leads": lead_count,
                "created_at": lst.created_at.isoformat() if lst.created_at else None
            })
        
        return jsonify({"lists": result})
        
    except Exception as e:
        log.error(f"Error fetching import lists: {e}")
        return jsonify({"error": "שגיאה בטעינת רשימות הייבוא"}), 500


@outbound_bp.route("/api/outbound/bulk-enqueue", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def bulk_enqueue_outbound_calls():
    """
    Bulk enqueue outbound calls with concurrency control
    
    Request body:
    {
        "lead_ids": [1, 2, 3, ...],
        "concurrency": 3,
        "outbound_list_id": 12 (optional)
    }
    
    Returns:
    {
        "run_id": "123",
        "queued": 500
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun, OutboundCallJob
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני הפעלת שיחות"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    lead_ids = data.get("lead_ids", [])
    concurrency = data.get("concurrency", 3)
    outbound_list_id = data.get("outbound_list_id")
    project_id = data.get("project_id")  # Optional project_id for tracking
    
    if not lead_ids or not isinstance(lead_ids, list):
        return jsonify({"error": "יש לבחור לפחות ליד אחד"}), 400
    
    # Validate concurrency
    if concurrency < 1 or concurrency > 10:
        return jsonify({"error": "מספר שיחות במקביל חייב להיות בין 1 ל-10"}), 400
    
    # Validate project_id if provided
    if project_id and not _validate_project_access(project_id, tenant_id):
        return jsonify({"error": "פרויקט לא נמצא"}), 404
    
    user = session.get('user', {})
    
    # 🔥 USE BULK GATE: Check if enqueue is allowed
    try:
        import redis
        REDIS_URL = os.getenv('REDIS_URL')
        redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
        
        if redis_conn:
            from server.services.bulk_gate import get_bulk_gate
            bulk_gate = get_bulk_gate(redis_conn)
            
            if bulk_gate:
                # Check if enqueue is allowed
                allowed, reason = bulk_gate.can_enqueue(
                    business_id=tenant_id,
                    operation_type='enqueue_outbound_calls',
                    user_id=user.get('id')
                )
                
                if not allowed:
                    return jsonify({"error": reason}), 429
    except Exception as e:
        log.warning(f"BulkGate check failed (proceeding anyway): {e}")
    
    try:
        # Verify all leads belong to this tenant
        leads = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id
        ).all()
        
        if len(leads) != len(lead_ids):
            return jsonify({"error": "לא נמצאו כל הלידים שנבחרו"}), 404
        
        # 🔒 SECURITY: Create run with proper audit trail
        run = OutboundCallRun()
        run.business_id = tenant_id
        run.created_by_user_id = user.get('id')  # Audit trail
        run.outbound_list_id = outbound_list_id
        run.concurrency = concurrency
        run.total_leads = len(lead_ids)
        run.queued_count = len(lead_ids)
        run.cursor_position = 0  # Start at beginning
        run.status = "pending"  # Start as pending, worker will update to running when processing starts
        db.session.add(run)
        db.session.flush()
        
        # 🔒 SECURITY: Create jobs with business_id for isolation
        for lead_id in lead_ids:
            job = OutboundCallJob()
            job.run_id = run.id
            job.lead_id = lead_id
            job.business_id = tenant_id  # Business isolation
            job.status = "queued"
            # 🔥 NAME SSOT: Store lead name for NAME_ANCHOR system
            lead_obj = next((l for l in leads if l.id == lead_id), None)
            if lead_obj:
                job.lead_name = _get_lead_display_name(lead_obj)
            # 🎯 PROJECT TRACKING: Associate job with project if provided
            if project_id:
                job.project_id = project_id
            db.session.add(job)
        
        db.session.commit()
        
        log.info(f"✅ Created bulk call run {run.id} with {len(lead_ids)} leads, concurrency={concurrency}, project_id={project_id}")
        
        # Create BackgroundJob record and enqueue to RQ
        from server.models_sql import BackgroundJob
        from rq import Queue
        import redis
        
        # 🔒 CHECK: Look for existing active job to avoid unique constraint violation
        # The idx_background_jobs_unique_active constraint prevents multiple active jobs
        # (status in 'queued', 'running', 'paused') of the same type per business
        existing_job = BackgroundJob.query.filter_by(
            business_id=tenant_id,
            job_type='enqueue_outbound_calls'
        ).filter(
            BackgroundJob.status.in_(['queued', 'running', 'paused'])
        ).first()
        
        if existing_job:
            # Check if job is stale (stuck for more than 10 minutes without heartbeat)
            now = datetime.utcnow()
            stale_threshold = timedelta(minutes=10)
            
            # Determine if job is stale based on heartbeat or created_at
            last_activity = existing_job.heartbeat_at or existing_job.created_at
            is_stale = (now - last_activity) > stale_threshold
            
            if is_stale:
                # Mark stale job as failed and proceed with new job
                log.warning(f"⚠️ Found stale background job {existing_job.id} (status={existing_job.status}, last_activity={last_activity}). Marking as failed.")
                existing_job.status = 'failed'
                existing_job.last_error = 'Job marked as stale - exceeded timeout without heartbeat'
                existing_job.finished_at = now
                db.session.commit()
            else:
                # Active job exists, cannot create new one
                log.error(f"❌ Active background job {existing_job.id} already exists for business {tenant_id}")
                db.session.rollback()
                return jsonify({
                    "error": "תור שיחות פעיל כבר קיים. אנא המתן לסיום התור הנוכחי או צור קשר עם התמיכה.",
                    "active_job_id": existing_job.id,
                    "active_job_status": existing_job.status
                }), 409  # 409 Conflict
        
        bg_job = BackgroundJob()
        bg_job.business_id = tenant_id
        bg_job.requested_by_user_id = user.get('id')
        bg_job.job_type = 'enqueue_outbound_calls'
        bg_job.status = 'queued'
        bg_job.total = len(lead_ids)
        bg_job.processed = 0
        bg_job.succeeded = 0
        bg_job.failed_count = 0
        bg_job.cursor = json.dumps({
            'run_id': run.id,
            'last_id': 0
        })
        db.session.add(bg_job)
        db.session.commit()
        
        # Enqueue to RQ default queue (for call processing)
        REDIS_URL = os.getenv('REDIS_URL')
        if REDIS_URL:
            redis_conn = redis.from_url(REDIS_URL)
            queue = Queue('default', connection=redis_conn)
            
            # Acquire lock and record enqueue BEFORE actually enqueuing
            if redis_conn:
                try:
                    from server.services.bulk_gate import get_bulk_gate
                    bulk_gate = get_bulk_gate(redis_conn)
                    
                    if bulk_gate:
                        # Acquire lock for this operation
                        lock_acquired = bulk_gate.acquire_lock(
                            business_id=tenant_id,
                            operation_type='enqueue_outbound_calls',
                            job_id=bg_job.id
                        )
                        
                        # Record the enqueue
                        bulk_gate.record_enqueue(
                            business_id=tenant_id,
                            operation_type='enqueue_outbound_calls'
                        )
                except Exception as e:
                    log.warning(f"BulkGate lock/record failed (proceeding anyway): {e}")
            
            # Import and enqueue the job function
            from server.jobs.enqueue_outbound_calls_job import enqueue_outbound_calls_batch_job
            rq_job = queue.enqueue(
                enqueue_outbound_calls_batch_job,
                bg_job.id,
                job_timeout='60m',  # Longer timeout for calls
                job_id=f"outbound_calls_{bg_job.id}"
            )
            
            log.info(f"🚀 Enqueued RQ job for outbound calls, job_id={bg_job.id}, rq_job_id={rq_job.id}")
        else:
            log.warning(f"⚠️ REDIS_URL not set, cannot enqueue outbound calls job")
            bg_job.status = 'failed'
            bg_job.last_error = 'Redis not configured'
            run.status = 'failed'
            db.session.commit()
            return jsonify({"error": "Job queue not available"}), 503
        
        return jsonify({
            "success": True,
            "run_id": run.id,
            "job_id": bg_job.id,
            "queued": len(lead_ids)
        }), 202  # 202 Accepted - processing in background
        
    except Exception as e:
        log.error(f"Error creating bulk call run: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"שגיאה ביצירת הרצה: {str(e)}"}), 500


@outbound_bp.route("/api/outbound/runs/<int:run_id>", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_run_status(run_id: int):
    """
    Get status of bulk call run
    
    🔒 SECURITY: Enforces business isolation - users can only see runs for their business
    
    Returns:
    {
        "run_id": 123,
        "status": "running",
        "queued": 450,
        "in_progress": 3,
        "completed": 47,
        "failed": 0,
        "cursor_position": 47,
        "last_error": null
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can view any run, get tenant from run
            run = OutboundCallRun.query.get(run_id)
            if not run:
                return jsonify({"error": "הרצה לא נמצאה"}), 404
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    else:
        # 🔒 SECURITY: Regular user - MUST verify run belongs to their tenant
        run = OutboundCallRun.query.filter_by(
            id=run_id,
            business_id=tenant_id
        ).first()
        
        if not run:
            # 🔒 SECURITY: Log potential cross-business access attempt
            log.warning(f"[SECURITY] User from business {tenant_id} attempted to access run {run_id} which doesn't exist or belongs to different business")
            return jsonify({"error": "הרצה לא נמצאה"}), 404
        
        # 🔒 SECURITY: Double-check business_id matches (defensive programming)
        if run.business_id != tenant_id:
            log.error(f"[SECURITY] Business ID mismatch in get_run_status: run.business_id={run.business_id} != tenant_id={tenant_id}")
            return jsonify({"error": "הרצה לא נמצאה"}), 404
    
    return jsonify({
        "run_id": run.id,
        "status": run.status,
        "queued": run.queued_count,
        "in_progress": run.in_progress_count,
        "completed": run.completed_count,
        "failed": run.failed_count,
        "cursor_position": run.cursor_position or 0,
        "last_error": run.last_error,
        "total_leads": run.total_leads,
        "concurrency": run.concurrency,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "can_cancel": run.status in ('pending', 'running') and not run.cancel_requested,
        "cancel_requested": run.cancel_requested
    })


@outbound_bp.route("/api/outbound/stop-queue", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def stop_queue():
    """
    Stop an active bulk call queue/run
    
    🔒 SECURITY: Enforces business isolation - users can only stop runs for their business
    
    Request body:
    {
        "run_id": 123
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can stop any run
            pass
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "נתונים חסרים"}), 400
    
    run_id = data.get('run_id')
    if not run_id:
        return jsonify({"error": "חסר run_id"}), 400
    
    try:
        # 🔒 SECURITY: Get run and verify it belongs to tenant if not system admin
        if tenant_id:
            run = OutboundCallRun.query.filter_by(
                id=run_id,
                business_id=tenant_id
            ).first()
            
            if not run:
                # 🔒 SECURITY: Log potential cross-business access attempt
                log.warning(f"[SECURITY] User from business {tenant_id} attempted to stop run {run_id} which doesn't exist or belongs to different business")
                return jsonify({"error": "הרצה לא נמצאה"}), 404
            
            # 🔒 SECURITY: Double-check business_id matches (defensive programming)
            if run.business_id != tenant_id:
                log.error(f"[SECURITY] Business ID mismatch: run.business_id={run.business_id} != tenant_id={tenant_id}")
                return jsonify({"error": "הרצה לא נמצאה"}), 404
        else:
            run = OutboundCallRun.query.get(run_id)
            if not run:
                return jsonify({"error": "הרצה לא נמצאה"}), 404
        
        # Check if already stopped/completed
        if run.status in ('stopped', 'completed', 'cancelled', 'failed'):
            return jsonify({
                "success": True,
                "message": f"התור כבר הסתיים (סטטוס: {run.status})",
                "cancelled_jobs": 0
            })
        
        # 🔒 STATE MACHINE: Mark as stopped and set ended_at + cancel_requested
        run.status = "stopped"
        run.cancel_requested = True  # Also set cancel flag so worker detects stop
        run.ended_at = datetime.utcnow()
        run.completed_at = datetime.utcnow()  # Legacy field
        
        # 🔒 SECURITY: Cancel all queued jobs - only for this business
        # Use raw SQL for performance with large queues
        cancelled_count = db.session.execute(text("""
            UPDATE outbound_call_jobs 
            SET status='cancelled',
                error_message='Queue stopped by user',
                completed_at=NOW()
            WHERE run_id=:run_id 
                AND business_id=:business_id
                AND status='queued'
        """), {"run_id": run_id, "business_id": run.business_id}).rowcount
        
        # 🔒 STATE MACHINE: Update run counters to reflect reality
        # Move queued jobs to failed count (they won't run)
        run.failed_count += cancelled_count
        run.queued_count = 0
        
        # Note: Jobs in 'calling' or 'dialing' state will complete naturally
        # We don't forcefully terminate active calls
        
        db.session.commit()
        
        log.info(f"✅ [business_id={run.business_id}] Stopped queue run {run_id}: cancelled {cancelled_count} queued jobs")
        
        return jsonify({
            "success": True,
            "message": f"התור נעצר ({cancelled_count} שיחות בוטלו, שיחות פעילות יסתיימו)",
            "cancelled_jobs": cancelled_count
        })
        
    except Exception as e:
        log.error(f"Error stopping queue {run_id}: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": "שגיאה בעצירת התור"}), 500


@outbound_bp.route("/api/outbound/bulk/active", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_active_bulk_run():
    """
    Get active bulk call run for the current business
    
    Returns:
    {
        "active": true/false,
        "run": {
            "run_id": 123,
            "status": "running",
            "queued": 450,
            "in_progress": 3,
            "completed": 47,
            "failed": 0,
            "total_leads": 500,
            "concurrency": 3
        }
    }
    or
    {
        "active": false
    }
    """
    from flask import session
    from server.models_sql import OutboundCallRun
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        # 🔥 FIX: Proper "active run" definition per user requirements
        # A run is active ONLY if:
        # 1. status = 'running' (not queued/stopped/completed)
        # 2. created within last 30 minutes (prevents ancient stuck runs)
        # 3. Has actual activity (queued > 0 OR in_progress > 0)
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        
        active_run = OutboundCallRun.query.filter(
            OutboundCallRun.business_id == tenant_id,
            OutboundCallRun.status == 'running',
            OutboundCallRun.created_at >= cutoff_time,
            db.or_(
                OutboundCallRun.queued_count > 0,
                OutboundCallRun.in_progress_count > 0
            )
        ).order_by(OutboundCallRun.created_at.desc()).first()
        
        if not active_run:
            return jsonify({"active": False})
        
        return jsonify({
            "active": True,
            "run": {
                "run_id": active_run.id,
                "status": active_run.status,
                "queued": active_run.queued_count,
                "in_progress": active_run.in_progress_count,
                "completed": active_run.completed_count,
                "failed": active_run.failed_count,
                "total_leads": active_run.total_leads,
                "concurrency": active_run.concurrency,
                "created_at": active_run.created_at.isoformat() if active_run.created_at else None
            }
        })
        
    except Exception as e:
        log.error(f"Error getting active bulk run: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "שגיאה בקבלת מידע"}), 500


@outbound_bp.route("/api/outbound/recent-calls", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_recent_calls():
    """
    Get recent outbound calls, sorted by most recent first
    
    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    - status: Optional status filter
    - search: Optional search query (phone or lead name)
    - run_id: Optional filter by specific run
    
    Returns:
    {
        "total": 123,
        "page": 1,
        "page_size": 50,
        "items": [
            {
                "call_sid": "CA...",
                "to_number": "+972...",
                "lead_id": 123,
                "lead_name": "John Doe",
                "status": "completed",
                "started_at": "2024-01-01T12:00:00Z",
                "ended_at": "2024-01-01T12:05:00Z",
                "duration": 300,
                "recording_url": "https://...",
                "recording_sid": "RE...",
                "transcript": "...",
                "summary": "..."
            }
        ]
    }
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({
                "items": [], 
                "total": 0, 
                "page": 1, 
                "page_size": 50,
                "message": "בחר עסק לצפייה בשיחות"
            })
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        page = max(1, int(request.args.get('page', 1)))
        # 🔥 FIX: Increase max page size to 10,000 for better UI experience
        page_size = min(10000, max(1, int(request.args.get('page_size', 50))))
        status_filter = request.args.get('status', '').strip()
        search = request.args.get('search', '').strip()
        run_id = request.args.get('run_id', type=int)
        
        # Build query for outbound calls
        query = CallLog.query.filter_by(
            business_id=tenant_id,
            direction="outbound"
        )
        
        # Filter by run_id if provided
        if run_id:
            from server.models_sql import OutboundCallJob
            # Get call_log_ids from jobs in this run
            job_call_ids = db.session.query(OutboundCallJob.call_log_id).filter_by(
                run_id=run_id
            ).filter(
                OutboundCallJob.call_log_id.isnot(None)
            ).all()
            call_log_ids = [cid[0] for cid in job_call_ids]
            if call_log_ids:
                query = query.filter(CallLog.id.in_(call_log_ids))
            else:
                # No calls for this run yet
                return jsonify({
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size
                })
        
        # Status filter
        if status_filter and STATUS_FILTER_PATTERN.match(status_filter):
            query = query.filter(func.lower(CallLog.call_status) == status_filter.lower())
        
        # Search filter
        if search:
            # Join with Lead to search by name
            query = query.outerjoin(Lead, CallLog.lead_id == Lead.id)
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    CallLog.to_number.ilike(search_term),
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Sort by most recent first (created_at is when call record was created, which is when call started)
        query = query.order_by(CallLog.created_at.desc())
        
        # Paginate
        calls = query.offset((page - 1) * page_size).limit(page_size).all()
        
        # Format response
        items = []
        for call in calls:
            # Get lead info if available
            lead_name = None
            lead_status = None
            if call.lead_id:
                lead = Lead.query.get(call.lead_id)
                if lead:
                    lead_name = lead.full_name
                    lead_status = lead.status
            
            # ✅ Enrich with recording status
            recording_status = None
            recording_run_id = None
            recording_run = RecordingRun.query.filter_by(call_sid=call.call_sid).order_by(RecordingRun.created_at.desc()).first()
            
            if recording_run:
                recording_status = recording_run.status  # Use RecordingRun status
                recording_run_id = recording_run.id
            elif call.recording_url:
                recording_status = 'completed'  # Has URL means completed
            elif call.recording_sid:
                recording_status = 'processing'  # Has SID but no URL yet
            
            items.append({
                "call_sid": call.call_sid,
                "to_number": call.to_number,
                "lead_id": call.lead_id,
                "lead_name": lead_name,
                "lead_status": lead_status,
                "status": call.call_status,
                "started_at": call.created_at.isoformat() if call.created_at else None,
                "ended_at": call.updated_at.isoformat() if call.updated_at and call.updated_at != call.created_at else None,
                "duration": call.duration,
                "recording_url": call.recording_url,
                "recording_sid": call.recording_sid,
                "recording_status": recording_status,
                "recording_run_id": recording_run_id,
                "transcript": call.final_transcript or call.transcription,
                "summary": call.summary
            })
        
        return jsonify({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        })
        
    except Exception as e:
        log.error(f"Error fetching recent calls: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "שגיאה בטעינת השיחות האחרונות"}), 500


@outbound_bp.route("/api/inbound/recent-calls", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_inbound')
def get_recent_inbound_calls():
    """
    Get recent inbound calls, sorted by most recent first
    
    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    - status: Optional status filter
    - search: Optional search query (phone or lead name)
    
    Returns:
    {
        "total": 123,
        "page": 1,
        "page_size": 50,
        "items": [
            {
                "call_sid": "CA...",
                "to_number": "+972...",
                "lead_id": 123,
                "lead_name": "John Doe",
                "lead_status": "new",
                "status": "completed",
                "started_at": "2024-01-01T12:00:00Z",
                "ended_at": "2024-01-01T12:05:00Z",
                "duration": 300,
                "recording_url": "https://...",
                "recording_sid": "RE...",
                "transcript": "...",
                "summary": "..."
            }
        ]
    }
    """
    from flask import session
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({
                "items": [], 
                "total": 0, 
                "page": 1, 
                "page_size": 50,
                "message": "בחר עסק לצפייה בשיחות"
            })
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    try:
        page = max(1, int(request.args.get('page', 1)))
        # 🔥 FIX: Increase max page size to 10,000 for better UI experience
        page_size = min(10000, max(1, int(request.args.get('page_size', 50))))
        status_filter = request.args.get('status', '').strip()
        search = request.args.get('search', '').strip()
        
        # Build query for inbound calls only
        query = CallLog.query.filter_by(
            business_id=tenant_id,
            direction="inbound"
        )
        
        # Status filter
        if status_filter and STATUS_FILTER_PATTERN.match(status_filter):
            query = query.filter(func.lower(CallLog.call_status) == status_filter.lower())
        
        # Search filter
        if search:
            # Join with Lead to search by name
            query = query.outerjoin(Lead, CallLog.lead_id == Lead.id)
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    CallLog.to_number.ilike(search_term),
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Sort by most recent first (created_at is when call record was created, which is when call started)
        query = query.order_by(CallLog.created_at.desc())
        
        # Paginate
        calls = query.offset((page - 1) * page_size).limit(page_size).all()
        
        # Format response
        items = []
        for call in calls:
            # Get lead info if available
            lead_name = None
            lead_status = None
            if call.lead_id:
                lead = Lead.query.get(call.lead_id)
                if lead:
                    lead_name = lead.full_name
                    lead_status = lead.status
            
            # ✅ Enrich with recording status
            recording_status = None
            recording_run_id = None
            recording_run = RecordingRun.query.filter_by(call_sid=call.call_sid).order_by(RecordingRun.created_at.desc()).first()
            
            if recording_run:
                recording_status = recording_run.status  # Use RecordingRun status
                recording_run_id = recording_run.id
            elif call.recording_url:
                recording_status = 'completed'  # Has URL means completed
            elif call.recording_sid:
                recording_status = 'processing'  # Has SID but no URL yet
            
            items.append({
                "call_sid": call.call_sid,
                "to_number": call.to_number,
                "lead_id": call.lead_id,
                "lead_name": lead_name,
                "lead_status": lead_status,
                "status": call.call_status,
                "started_at": call.created_at.isoformat() if call.created_at else None,
                "ended_at": call.updated_at.isoformat() if call.updated_at and call.updated_at != call.created_at else None,
                "duration": call.duration,
                "recording_url": call.recording_url,
                "recording_sid": call.recording_sid,
                "recording_status": recording_status,
                "recording_run_id": recording_run_id,
                "transcript": call.final_transcript or call.transcription,
                "summary": call.summary
            })
        
        return jsonify({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        })
        
    except Exception as e:
        log.error(f"Error fetching recent inbound calls: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "שגיאה בטעינת השיחות הנכנסות האחרונות"}), 500


def fill_queue_slots_for_job(job_id: int):
    """
    Called when a call completes - tries to fill available slots in the queue
    This is the event-driven approach instead of polling
    """
    from server.app_factory import get_process_app
    from server.models_sql import OutboundCallRun, OutboundCallJob, Lead, Business, CallLog
    
    app = get_process_app()
    
    with app.app_context():
        try:
            # Get the job and run
            job = OutboundCallJob.query.get(job_id)
            if not job:
                log.warning(f"[FillSlots] Job {job_id} not found")
                return
            
            run = OutboundCallRun.query.get(job.run_id)
            if not run or run.status != "running":
                log.info(f"[FillSlots] Run {job.run_id} not running, skipping")
                return
            
            log.info(f"[FillSlots] Filling slots for run {run.id} after job {job_id} completed")
            
            # Get business details
            business = Business.query.get(run.business_id)
            if not business or not business.phone_e164:
                log.error(f"[FillSlots] Business {run.business_id} has no phone")
                return
            
            from_phone = business.phone_e164
            business_name = business.name or "העסק"
            
            # 🔒 CRITICAL: Verify host is available for webhooks (fail fast if missing)
            try:
                host = get_public_host()
                log.info(f"[FillSlots] Run {run.id}: public_host={host} (for Twilio webhooks)")
            except RuntimeError as e:
                log.error(f"[FillSlots] Run {run.id} FAILED: {e}")
                run.status = "failed"
                run.last_error = "No public host configured for webhooks"
                db.session.commit()
                return
            
            # 🔒 CRITICAL: Check BUSINESS-LEVEL active outbound calls, not just this run
            # This prevents multiple runs or mixed direct+bulk calls from exceeding limit
            from server.services.call_limiter import count_active_outbound_calls, MAX_OUTBOUND_CALLS_PER_BUSINESS
            
            # Check how many active calls THIS RUN has (include both "dialing" and "calling")
            # 🔥 FIX: Must count "dialing" jobs too, otherwise we start too many calls in parallel
            active_in_run = OutboundCallJob.query.filter(
                OutboundCallJob.run_id == run.id,
                OutboundCallJob.status.in_(["dialing", "calling"])
            ).count()
            
            # 🔒 BUSINESS-LEVEL LIMIT: Check total active outbound calls for this business
            business_active_outbound = count_active_outbound_calls(run.business_id)
            
            # Fill available slots (respect BOTH run concurrency AND business limit)
            while active_in_run < run.concurrency and business_active_outbound < MAX_OUTBOUND_CALLS_PER_BUSINESS:
                # Get next queued job
                next_job = OutboundCallJob.query.filter_by(
                    run_id=run.id,
                    status="queued"
                ).order_by(OutboundCallJob.id).first()
                
                if not next_job:
                    # No more jobs queued
                    if active_in_run == 0:
                        # All done!
                        run.status = "completed"
                        run.completed_at = datetime.utcnow()
                        db.session.commit()
                        log.info(f"[FillSlots] Run {run.id} completed - all calls finished")
                    break
                
                # Start this call
                try:
                    lead = Lead.query.get(next_job.lead_id)
                    if not lead or not lead.phone_e164:
                        next_job.status = "failed"
                        next_job.error_message = "אין מספר טלפון לליד"
                        next_job.completed_at = datetime.utcnow()
                        run.failed_count += 1
                        run.queued_count -= 1
                        db.session.commit()
                        continue
                    
                    # 🔒 ATOMIC LOCKING: Acquire lock before dialing
                    # This prevents duplicate calls from retry/concurrency/timeout scenarios
                    lock_token = str(uuid.uuid4())
                    
                    # Atomic UPDATE: Only proceed if status='queued' AND twilio_call_sid IS NULL AND dial_lock_token IS NULL
                    result = db.session.execute(text("""
                        UPDATE outbound_call_jobs 
                        SET status='dialing', 
                            dial_started_at=NOW(), 
                            dial_lock_token=:lock_token
                        WHERE id=:job_id 
                            AND status='queued' 
                            AND twilio_call_sid IS NULL
                            AND dial_lock_token IS NULL
                    """), {"job_id": next_job.id, "lock_token": lock_token})
                    
                    db.session.commit()
                    
                    # Check if we acquired the lock
                    if result.rowcount == 0:
                        # Someone else already started this call or it's no longer queued
                        log.warning(f"[FillSlots] Job {next_job.id} already being processed, skipping")
                        continue
                    
                    # Successfully acquired lock, proceed with call
                    run.in_progress_count += 1
                    run.queued_count -= 1
                    db.session.commit()
                    
                    # Normalize phone
                    normalized_phone = normalize_israeli_phone(lead.phone_e164)
                    
                    # Create call log
                    call_log = CallLog()
                    call_log.business_id = run.business_id
                    call_log.lead_id = lead.id
                    call_log.from_number = from_phone
                    call_log.to_number = normalized_phone
                    call_log.direction = "outbound"
                    call_log.status = "initiated"
                    call_log.call_status = "initiated"
                    db.session.add(call_log)
                    db.session.flush()
                    
                    next_job.call_log_id = call_log.id
                    db.session.commit()
                    
                    # 🔥 SSOT: Use centralized outbound call service
                    from server.services.twilio_outbound_service import create_outbound_call
                    
                    # 🔥 NAME SSOT: Extract lead name
                    lead_name = _get_lead_display_name(lead)
                    
                    try:
                        result = create_outbound_call(
                            to_phone=normalized_phone,
                            from_phone=from_phone,
                            business_id=run.business_id,
                            host=host,
                            lead_id=lead.id,
                            job_id=next_job.id,
                            business_name=business_name,
                            lead_name=lead_name
                        )
                        
                        call_sid = result["call_sid"]
                        is_duplicate = result.get("is_duplicate", False)
                        
                        if is_duplicate:
                            log.warning(f"[FillSlots] [DEDUP] Duplicate call detected for job {next_job.id}, skipping")
                            continue
                        
                        # 🔒 ATOMIC UPDATE: Update with Twilio call SID only if lock token matches
                        update_result = db.session.execute(text("""
                            UPDATE outbound_call_jobs 
                            SET twilio_call_sid=:twilio_sid, 
                                call_sid=:twilio_sid,
                                status='calling',
                                started_at=NOW()
                            WHERE id=:job_id 
                                AND dial_lock_token=:lock_token
                        """), {
                            "job_id": next_job.id, 
                            "twilio_sid": call_sid, 
                            "lock_token": lock_token
                        })
                        
                        if update_result.rowcount == 0:
                            log.error(f"[FillSlots] Lock token mismatch for job {next_job.id}, call may be duplicate")
                        
                        call_log.call_sid = call_sid
                        db.session.commit()
                        
                        log.info(f"[FillSlots] Started call for lead {lead.id}, job {next_job.id}, call_sid={call_sid}")
                        active_in_run += 1
                        business_active_outbound += 1
                        
                    except Exception as twilio_error:
                        # 🔒 DEDUPLICATION: Handle Twilio timeout/exception
                        log.error(f"[FillSlots] Twilio error for job {next_job.id}: {twilio_error}")
                        
                        # Check if call was actually created despite the error
                        db.session.refresh(next_job)
                        if not next_job.twilio_call_sid:
                            # Call was not created - reset to queued for retry
                            result = db.session.execute(text("""
                                UPDATE outbound_call_jobs 
                                SET status='queued',
                                    dial_lock_token=NULL,
                                    dial_started_at=NULL
                                WHERE id=:job_id 
                                    AND twilio_call_sid IS NULL
                                    AND dial_lock_token=:lock_token
                            """), {"job_id": next_job.id, "lock_token": lock_token})
                            
                            run.in_progress_count -= 1
                            run.queued_count += 1
                            db.session.commit()
                        
                        raise twilio_error
                    
                except Exception as e:
                    log.error(f"[FillSlots] Error starting call for job {next_job.id}: {e}")
                    # Only mark as failed if we don't have a call SID
                    db.session.refresh(next_job)
                    if not next_job.twilio_call_sid:
                        next_job.status = "failed"
                        next_job.error_message = str(e)
                        next_job.completed_at = datetime.utcnow()
                        run.in_progress_count = max(0, run.in_progress_count - 1)
                        run.failed_count += 1
                        db.session.commit()
                    
        except Exception as e:
            log.error(f"[FillSlots] Error in fill_queue_slots_for_job: {e}")
            import traceback
            traceback.print_exc()


def process_bulk_call_run(run_id: int):
    """
    Background worker to process bulk call run
    Respects concurrency limits and processes queue
    
    🔒 STATE MACHINE: pending → running → completed/cancelled/failed
    🔒 SECURITY: Enforces business isolation throughout processing
    """
    from server.app_factory import get_process_app
    from server.models_sql import OutboundCallRun, OutboundCallJob, Lead, Business, CallLog
    import time
    import socket
    
    app = get_process_app()
    
    with app.app_context():
        try:
            # 🔒 CLEANUP: Reset any stuck jobs and runs from previous failures
            cleanup_stuck_dialing_jobs()
            cleanup_stuck_runs()
            
            run = OutboundCallRun.query.get(run_id)
            if not run:
                log.error(f"Run {run_id} not found")
                return
            
            # 🔒 STATE MACHINE: Update from pending to running and set started_at
            worker_id = f"{socket.gethostname()}:{os.getpid()}"
            
            if run.status == "pending":
                run.status = "running"
                run.started_at = datetime.utcnow()
                
                # 🔒 WORKER LOCK: Set worker lock with hostname+pid
                run.locked_by_worker = worker_id
                run.lock_ts = datetime.utcnow()
                db.session.commit()
                
                log.info(f"[BulkCall] Run {run_id} started by worker {worker_id} with concurrency={run.concurrency}")
            else:
                # 🔒 WORKER LOCK: Update lock fields when resuming
                run.locked_by_worker = worker_id
                run.lock_ts = datetime.utcnow()
                db.session.commit()
                log.info(f"[BulkCall] Resuming run {run_id} with worker {worker_id}, concurrency={run.concurrency}")
            
            # Get business details
            business = Business.query.get(run.business_id)
            if not business or not business.phone_e164:
                run.status = "failed"
                run.ended_at = datetime.utcnow()
                run.last_error = "מספר טלפון של העסק לא מוגדר"
                db.session.commit()
                return
            
            from_phone = business.phone_e164
            business_name = business.name or "העסק"
            
            # 🔒 CRITICAL: Verify host is available for webhooks (fail fast if missing)
            try:
                host = get_public_host()
                log.info(f"[BulkCall] Run {run_id}: public_host={host} (for Twilio webhooks)")
            except RuntimeError as e:
                log.error(f"[BulkCall] Run {run_id} FAILED: {e}")
                run.status = "failed"
                run.ended_at = datetime.utcnow()
                run.last_error = "No public host configured for webhooks"
                db.session.commit()
                return
            
            # 🔒 CRITICAL: Import business-level limiter to prevent exceeding 3 calls per business
            from server.services.call_limiter import count_active_outbound_calls, MAX_OUTBOUND_CALLS_PER_BUSINESS
            # 🔥 SEMAPHORE: Import Redis-based semaphore for hard 3-concurrent limit
            from server.services.outbound_semaphore import try_acquire_slot, release_slot
            
            # Process jobs in queue
            while True:
                # 🔒 STATE MACHINE: Check if queue was stopped or cancellation requested
                db.session.refresh(run)
                
                # 🔒 WORKER HEARTBEAT: Update lock timestamp to show worker is alive
                run.lock_ts = datetime.utcnow()
                run.updated_at = datetime.utcnow()
                db.session.commit()
                
                # 🔒 CANCEL CHECK: Check if user requested cancellation BEFORE processing next call
                if run.cancel_requested and run.status != "cancelled":
                    log.info(f"[BulkCall] Run {run_id} cancellation requested, stopping...")
                    
                    # 🔒 SECURITY: Mark all queued jobs as cancelled - only for this business
                    result = db.session.execute(text("""
                        UPDATE outbound_call_jobs 
                        SET status='failed',
                            error_message='Cancelled by user',
                            completed_at=NOW()
                        WHERE run_id=:run_id 
                            AND business_id=:business_id
                            AND status='queued'
                    """), {"run_id": run_id, "business_id": run.business_id})
                    
                    cancelled_count = result.rowcount
                    
                    # 🔒 STATE MACHINE: Update run status to cancelled
                    run.status = "cancelled"
                    run.ended_at = datetime.utcnow()
                    run.completed_at = datetime.utcnow()  # Legacy field
                    run.queued_count = 0
                    run.failed_count += cancelled_count
                    db.session.commit()
                    
                    log.info(f"[BulkCall] Run {run_id} cancelled - marked {cancelled_count} jobs as cancelled")
                    break
                
                if run.status in ("stopping", "stopped", "cancelled"):
                    log.info(f"[BulkCall] Run {run_id} was stopped (status={run.status}), exiting")
                    # 🔒 STATE MACHINE: Mark as stopped if it was in stopping state
                    if run.status == "stopping":
                        run.status = "stopped"
                        run.ended_at = datetime.utcnow()
                        db.session.commit()
                    break
                
                # Get next queued job
                next_job = OutboundCallJob.query.filter_by(
                    run_id=run_id,
                    status="queued"
                ).order_by(OutboundCallJob.id).first()
                
                if next_job:
                    # 🔥 SEMAPHORE: Try to acquire slot before starting call
                    # This enforces hard limit of 3 concurrent calls per business
                    acquired, status = try_acquire_slot(run.business_id, next_job.id)
                    
                    if not acquired:
                        if status == "queued":
                            # Redis queue is full, wait for slot to free up
                            log.debug(f"[BulkCall] Waiting for slot to free up, sleeping 1s")
                            time.sleep(1)
                            continue
                        elif status == "already_queued":
                            # 🔥 FIX: Job is already in Redis queue waiting for a slot
                            # Don't skip - wait for it to be processed by release_slot
                            log.debug(f"[BulkCall] Job {next_job.id} already in Redis queue, waiting for slot to free up")
                            time.sleep(1)
                            continue
                        elif status == "inflight":
                            # This job is already being processed by another worker
                            log.warning(f"[BulkCall] Job {next_job.id} already inflight, skipping")
                            continue
                        # else: error_fallback or no_redis - proceed anyway
                    
                    # Start this call with finally block to ensure slot release
                    try:
                        lead = Lead.query.get(next_job.lead_id)
                        if not lead or not lead.phone_e164:
                            next_job.status = "failed"
                            next_job.error_message = "אין מספר טלפון לליד"
                            next_job.completed_at = datetime.utcnow()
                            run.failed_count += 1
                            run.queued_count -= 1
                            db.session.commit()
                            continue
                        
                        # 🔒 ATOMIC LOCKING: Generate unique lock token for this call
                        lock_token = str(uuid.uuid4())
                        
                        # Atomic UPDATE: Only proceed if status='queued' AND twilio_call_sid IS NULL AND dial_lock_token IS NULL
                        result = db.session.execute(text("""
                            UPDATE outbound_call_jobs 
                            SET status='dialing', 
                                dial_started_at=NOW(), 
                                dial_lock_token=:lock_token
                            WHERE id=:job_id 
                                AND status='queued' 
                                AND twilio_call_sid IS NULL
                                AND dial_lock_token IS NULL
                        """), {"job_id": next_job.id, "lock_token": lock_token})
                        
                        db.session.commit()
                        
                        # Check if we acquired the lock
                        if result.rowcount == 0:
                            # Someone else already started this call or it's no longer queued
                            log.warning(f"[BulkCall] Job {next_job.id} already being processed, skipping")
                            continue
                        
                        # Successfully acquired lock, proceed with call
                        run.in_progress_count += 1
                        run.queued_count -= 1
                        db.session.commit()
                        
                        # Normalize phone
                        normalized_phone = normalize_israeli_phone(lead.phone_e164)
                        
                        # Create call log
                        call_log = CallLog()
                        call_log.business_id = run.business_id
                        call_log.lead_id = lead.id
                        call_log.from_number = from_phone
                        call_log.to_number = normalized_phone
                        call_log.direction = "outbound"
                        call_log.status = "initiated"
                        call_log.call_status = "initiated"
                        # 🔥 NAME SSOT: Store lead name for NAME_ANCHOR system
                        call_log.customer_name = _get_lead_display_name(lead)
                        # 🎯 PROJECT TRACKING: Associate call with project if job has project_id
                        if next_job.project_id:
                            call_log.project_id = next_job.project_id
                        db.session.add(call_log)
                        db.session.flush()
                        
                        next_job.call_log_id = call_log.id
                        db.session.commit()
                        
                        # Initiate Twilio call
                        # 🔥 SSOT: Use centralized outbound call service
                        from server.services.twilio_outbound_service import create_outbound_call
                        
                        # 🔥 NAME SSOT: Extract lead name
                        lead_name = _get_lead_display_name(lead)
                        
                        try:
                            result = create_outbound_call(
                                to_phone=normalized_phone,
                                from_phone=from_phone,
                                business_id=run.business_id,
                                host=host,
                                lead_id=lead.id,
                                job_id=next_job.id,
                                business_name=business_name,
                                lead_name=lead_name
                            )
                            
                            call_sid = result["call_sid"]
                            is_duplicate = result.get("is_duplicate", False)
                            
                            if is_duplicate:
                                log.warning(f"[BulkCall] [DEDUP] Duplicate call detected for job {next_job.id}, skipping")
                                continue
                            
                            # 🔒 ATOMIC UPDATE: Update with Twilio call SID only if lock token matches
                            update_result = db.session.execute(text("""
                                UPDATE outbound_call_jobs 
                                SET twilio_call_sid=:twilio_sid, 
                                    call_sid=:twilio_sid,
                                    status='calling',
                                    started_at=NOW()
                                WHERE id=:job_id 
                                    AND dial_lock_token=:lock_token
                            """), {
                                "job_id": next_job.id, 
                                "twilio_sid": call_sid, 
                                "lock_token": lock_token
                            })
                            
                            # 🔥 FIX: Only log error if lock token actually mismatched (rowcount == 0)
                            if update_result.rowcount == 0:
                                log.error(f"[BulkCall] Lock token mismatch for job {next_job.id}, call may be duplicate")
                                # Call was created but we lost the lock - log warning but continue
                                # Twilio will handle the duplicate via their idempotency
                            
                            call_log.call_sid = call_sid
                            db.session.commit()
                            
                            log.info(f"[BulkCall] Started call for lead {lead.id}, job {next_job.id}, call_sid={call_sid}")
                            
                            # 🔒 FIX: Add small delay after starting each call to prevent race conditions
                            # This ensures database status updates propagate before checking active count again
                            time.sleep(0.5)  # 500ms delay to prevent starting too many calls at once
                            
                        except Exception as twilio_error:
                            # 🔒 DEDUPLICATION: Handle Twilio timeout/exception
                            # Don't retry if we already have a twilio_call_sid (call may have succeeded)
                            log.error(f"[BulkCall] Twilio error for job {next_job.id}: {twilio_error}")
                            
                            # Check if call was actually created despite the error
                            db.session.refresh(next_job)
                            if next_job.twilio_call_sid:
                                # Call was created successfully despite error
                                log.info(f"[BulkCall] Call created despite error for job {next_job.id}")
                                raise twilio_error
                            else:
                                # Call was not created - reset to queued for retry (but only if no call SID)
                                result = db.session.execute(text("""
                                    UPDATE outbound_call_jobs 
                                    SET status='queued',
                                        dial_lock_token=NULL,
                                        dial_started_at=NULL
                                    WHERE id=:job_id 
                                        AND twilio_call_sid IS NULL
                                        AND dial_lock_token=:lock_token
                                """), {"job_id": next_job.id, "lock_token": lock_token})
                                
                                run.in_progress_count -= 1
                                run.queued_count += 1
                                db.session.commit()
                                
                                log.warning(f"[BulkCall] Reset job {next_job.id} to queued for retry")
                                raise twilio_error
                        
                    except Exception as e:
                        log.error(f"[BulkCall] Error starting call for job {next_job.id}: {e}")
                        # Only mark as failed if we don't have a call SID (meaning call didn't start)
                        db.session.refresh(next_job)
                        if not next_job.twilio_call_sid:
                            next_job.status = "failed"
                            next_job.error_message = str(e)
                            next_job.completed_at = datetime.utcnow()
                            run.in_progress_count = max(0, run.in_progress_count - 1)
                            run.failed_count += 1
                            run.last_error = str(e)[:500]
                            db.session.commit()
                    finally:
                        # 🔥 CRITICAL: Release semaphore slot if call never started
                        # If call started successfully, webhook will release the slot when call ends
                        # Only release here if we failed before call actually started (no twilio_call_sid)
                        try:
                            db.session.refresh(next_job)
                            if not next_job.twilio_call_sid:
                                # Call never started - release slot now
                                from server.services.outbound_semaphore import release_slot
                                next_job_id = release_slot(run.business_id, next_job.id)
                                if next_job_id:
                                    log.info(f"[SEMAPHORE] Released slot for failed job {next_job.id}, next job {next_job_id} can proceed")
                                else:
                                    log.info(f"[SEMAPHORE] Released slot for failed job {next_job.id}, no jobs waiting")
                            # else: Call started, webhook will release the slot when it ends
                        except Exception as e:
                            log.error(f"[SEMAPHORE] Error releasing slot: {e}")
                            # Don't raise - we're in cleanup
                else:
                    # No more queued jobs - check if we're done
                    active_jobs_count = OutboundCallJob.query.filter(
                        OutboundCallJob.run_id == run_id,
                        OutboundCallJob.status.in_(["dialing", "calling"])
                    ).count()
                    
                    if active_jobs_count == 0:
                        # 🔒 STATE MACHINE: All done - mark as completed
                        run.status = "completed"
                        run.ended_at = datetime.utcnow()
                        run.completed_at = datetime.utcnow()  # Legacy field
                        run.cursor_position = run.total_leads  # Processed all
                        db.session.commit()
                        log.info(f"[BulkCall] Run {run_id} completed: {run.completed_count} succeeded, {run.failed_count} failed")
                        break
                    else:
                        # Wait for active calls to complete
                        time.sleep(2)
                
                # 🔒 CURSOR: Update cursor position after processing
                completed_jobs = OutboundCallJob.query.filter(
                    OutboundCallJob.run_id == run_id,
                    OutboundCallJob.status.in_(["completed", "failed", "cancelled"])
                ).count()
                run.cursor_position = completed_jobs
                db.session.commit()  # Persist cursor position
                
                # Refresh run to get latest counts
                db.session.refresh(run)
            
        except Exception as e:
            log.error(f"[BulkCall] Error in run {run_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # 🔒 STATE MACHINE: Mark run as failed on unexpected error
            try:
                run = OutboundCallRun.query.get(run_id)
                if run:
                    run.status = "failed"
                    run.ended_at = datetime.utcnow()
                    run.last_error = str(e)[:500]
                    db.session.commit()
            except:
                pass


def cleanup_stuck_dialing_jobs():
    """
    Cleanup jobs stuck in 'dialing' or 'calling' status
    
    This handles edge cases where:
    - calls.create succeeded but UPDATE with call_sid failed
    - Process crashed between acquiring lock and creating call
    - System restart left jobs in active state
    
    🔒 CRITICAL: Reset ALL stuck jobs on startup to prevent blocking new calls
    
    NOTE: This function assumes it's called from within an app context
    (either during app startup or from a request handler)
    """
    from server.models_sql import OutboundCallJob
    
    # 🔥 FIX: Don't call get_process_app() - assume we're already in app context
    # This prevents circular dependency when called from create_app()
    try:
        # 🔥 FIX: On startup, reset ALL jobs stuck in 'dialing' state
        # Don't wait 5 minutes - clean immediately to prevent blocking
        result_dialing = db.session.execute(text("""
            UPDATE outbound_call_jobs 
            SET status='failed',
                error_message='System restart - job was stuck in dialing state',
                completed_at=NOW()
            WHERE status='dialing'
                AND twilio_call_sid IS NULL
        """))
        
        # 🔥 FIX: Also reset jobs in 'calling' state that are old (>10 minutes)
        # These are likely calls that ended but webhook never arrived
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)
        result_calling = db.session.execute(text("""
            UPDATE outbound_call_jobs 
            SET status='failed',
                error_message='Call timeout - no status update received',
                completed_at=NOW()
            WHERE status='calling'
                AND started_at < :cutoff_time
        """), {"cutoff_time": cutoff_time})
        
        db.session.commit()
        
        total_cleaned = result_dialing.rowcount + result_calling.rowcount
        if total_cleaned > 0:
            log.info(f"[CLEANUP] ✅ Reset {result_dialing.rowcount} stuck 'dialing' jobs and {result_calling.rowcount} stuck 'calling' jobs")
        
        return total_cleaned
        
    except Exception as e:
        log.error(f"[CLEANUP] Error cleaning up stuck jobs: {e}")
        db.session.rollback()
        return 0


def cleanup_stuck_runs():
    """
    🔥 CRITICAL: Cleanup runs stuck in 'running' status with TTL-based heartbeat check
    
    This prevents "ghost active queue" bug where old runs from before a crash/restart
    continue showing as active even though no actual processing is happening.
    
    A run is considered stuck if:
    - status = 'running' 
    - lock_ts > TTL_MINUTES ago (no heartbeat from worker)
    - OR queued_count = 0 AND in_progress_count = 0 (nothing actually running)
    
    🔒 TTL-BASED RECLAIM: Uses lock_ts (heartbeat) instead of updated_at
    - Workers update lock_ts every iteration (heartbeat)
    - If lock_ts is stale (> 5 minutes), worker is considered dead
    - Run is marked as 'failed' with proper error message
    
    NOTE: This function assumes it's called from within an app context
    (typically during app startup or from a periodic cleanup task)
    """
    from server.models_sql import OutboundCallRun
    
    # 🔒 TTL for worker heartbeat: 5 minutes
    TTL_MINUTES = 5
    
    try:
        # Mark runs as failed if heartbeat is stale (worker died)
        heartbeat_cutoff = datetime.utcnow() - timedelta(minutes=TTL_MINUTES)
        
        # Also check updated_at as fallback (for runs started before this fix)
        updated_cutoff = datetime.utcnow() - timedelta(minutes=30)
        
        result = db.session.execute(text("""
            UPDATE outbound_call_runs 
            SET status='failed',
                ended_at=NOW(),
                completed_at=NOW(),
                last_error=CONCAT('Worker timeout - no heartbeat from ', locked_by_worker, ' since ', lock_ts)
            WHERE status='running'
                AND (
                    -- 🔒 PRIMARY: Check heartbeat (lock_ts)
                    (lock_ts IS NOT NULL AND lock_ts < :heartbeat_cutoff)
                    -- Fallback: Old updated_at check
                    OR (lock_ts IS NULL AND updated_at < :updated_cutoff)
                    -- Empty queue (nothing to process)
                    OR (queued_count = 0 AND in_progress_count = 0)
                )
        """), {
            "heartbeat_cutoff": heartbeat_cutoff,
            "updated_cutoff": updated_cutoff
        })
        
        db.session.commit()
        
        cleaned_count = result.rowcount
        if cleaned_count > 0:
            log.warning(f"[CLEANUP] ⚠️  Reclaimed {cleaned_count} stuck runs (TTL-based heartbeat check, TTL={TTL_MINUTES}min)")
        
        return cleaned_count
        
    except Exception as e:
        log.error(f"[CLEANUP] Error cleaning up stuck runs: {e}")
        db.session.rollback()
        return 0


@outbound_bp.route("/api/outbound/cleanup-stuck-jobs", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def cleanup_stuck_jobs_endpoint():
    """
    Manually trigger cleanup of jobs stuck in 'dialing' status
    
    This is useful for recovering from crashes or network issues.
    Jobs stuck in 'dialing' for >5 minutes without call_sid are reset to 'queued'.
    
    Rate limited to 1 request per minute per business to prevent abuse.
    Note: Rate limit is per-worker/process. In multi-worker setups, each worker
    enforces its own limit. This is acceptable for this use case.
    """
    from flask import session
    from datetime import datetime, timedelta
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            # System admin can clean up across all tenants
            pass
        else:
            return jsonify({"error": "אין גישה לעסק"}), 403
    
    # Rate limiting: Check if cleanup was called in the last minute
    # This is per-worker, which is acceptable for this admin endpoint
    cache_key = f"cleanup_last_call_{tenant_id or 'all'}"
    from server.stream_state import stream_registry
    last_call = stream_registry.get_metadata('global', cache_key)
    
    if last_call:
        last_call_time = datetime.fromisoformat(last_call)
        if datetime.utcnow() - last_call_time < timedelta(minutes=1):
            seconds_remaining = 60 - (datetime.utcnow() - last_call_time).seconds
            return jsonify({
                "error": f"יש להמתין {seconds_remaining} שניות לפני ניקוי נוסף",
                "retry_after": seconds_remaining
            }), 429
    
    try:
        count = cleanup_stuck_dialing_jobs()
        
        # Update last call time
        stream_registry.set_metadata('global', cache_key, datetime.utcnow().isoformat())
        
        log.info(f"✅ Cleanup completed: {count} jobs reset to queued")
        
        return jsonify({
            "success": True,
            "cleaned_count": count,
            "message": f"נוקו {count} משימות תקועות"
        })
        
    except Exception as e:
        log.error(f"Error in cleanup endpoint: {e}")
        return jsonify({"error": "שגיאה בניקוי משימות"}), 500


@outbound_bp.route("/api/outbound/leads/export", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calls_outbound')
def export_leads_by_status():
    """
    Export leads filtered by status to CSV format
    
    Query params:
    - status_id: Status name/ID to filter by (required)
    - format: Export format (csv only for now, default: csv)
    
    Returns:
    CSV file with leads data including status information
    
    Filename format: outbound_leads_status_<statusId>_<statusName>_<YYYY-MM-DD>.csv
    """
    from flask import session, Response
    import csv
    import io
    from server.models_sql import LeadStatus
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני ייצוא"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    # Get parameters
    status_name = request.args.get('status_id', '').strip()
    export_format = request.args.get('format', 'csv').lower()
    
    if not status_name:
        return jsonify({"error": "חסר פרמטר status_id"}), 400
    
    if export_format != 'csv':
        return jsonify({"error": "נתמך רק פורמט CSV כרגע"}), 400
    
    # Validate status name (security)
    if not STATUS_FILTER_PATTERN.match(status_name) or len(status_name) > 64:
        return jsonify({"error": "שם סטטוס לא תקין"}), 400
    
    try:
        # Get status info for proper labeling
        status_obj = LeadStatus.query.filter_by(
            tenant_id=tenant_id,
            name=status_name.lower()
        ).first()
        
        status_label = status_obj.label if status_obj else status_name
        
        # Query leads with this status for this tenant
        leads = Lead.query.filter_by(
            tenant_id=tenant_id,
            status=status_name.lower()
        ).order_by(Lead.created_at.desc()).all()
        
        # Get last call information for each lead
        lead_call_info = {}
        if leads:
            lead_ids = [lead.id for lead in leads]
            # Get most recent call for each lead
            recent_calls = db.session.query(
                CallLog.lead_id,
                func.max(CallLog.created_at).label('last_call_at')
            ).filter(
                CallLog.lead_id.in_(lead_ids),
                CallLog.business_id == tenant_id
            ).group_by(CallLog.lead_id).all()
            
            for lead_id, last_call_at in recent_calls:
                # Get the actual call record to get status
                call = CallLog.query.filter_by(
                    lead_id=lead_id,
                    business_id=tenant_id
                ).order_by(CallLog.created_at.desc()).first()
                
                lead_call_info[lead_id] = {
                    'last_call_at': last_call_at,
                    'last_call_status': call.call_status if call else None
                }
        
        # Create CSV in memory
        output = io.StringIO()
        
        # Use UTF-8 with BOM for Excel Hebrew compatibility
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'status_id',
            'status_name',
            'lead_id',
            'full_name',
            'phone',
            'email',
            'created_at',
            'last_call_at',
            'last_call_status',
            'source',
            'notes'
        ])
        
        # Write lead rows
        for lead in leads:
            call_info = lead_call_info.get(lead.id, {})
            
            writer.writerow([
                status_name.lower(),
                status_label,
                lead.id,
                lead.full_name or '',
                lead.phone_e164 or '',
                lead.email or '',
                lead.created_at.isoformat() if lead.created_at else '',
                call_info.get('last_call_at').isoformat() if call_info.get('last_call_at') else '',
                call_info.get('last_call_status') or '',
                lead.source or '',
                lead.notes or ''
            ])
        
        # Get CSV content with UTF-8 BOM
        csv_content = '\ufeff' + output.getvalue()
        output.close()
        
        # Generate filename
        today = datetime.now().strftime('%Y-%m-%d')
        # Sanitize status name for filename (remove special chars)
        safe_status_name = re.sub(r'[^a-zA-Z0-9_-]', '', status_name)
        filename = f"outbound_leads_status_{safe_status_name}_{today}.csv"
        
        log.info(f"📊 Exporting {len(leads)} leads with status '{status_name}' for tenant {tenant_id}")
        
        # Return CSV file
        return Response(
            csv_content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        log.error(f"Error exporting leads by status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"שגיאה בייצוא: {str(e)}"}), 500


# ═══════════════════════════════════════════════════════════════════════
# API COMPATIBILITY LAYER - Aliases for Frontend
# ═══════════════════════════════════════════════════════════════════════
# 🔥 PURPOSE: Frontend expects specific endpoint names after refactor to Runs
# These aliases map old endpoint names to new implementations

@outbound_bp.route("/api/inbound/recent", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_inbound')
def get_inbound_recent_alias():
    """
    ✅ COMPATIBILITY ALIAS: Maps /api/inbound/recent → /api/inbound/recent-calls
    
    Frontend expects this endpoint after refactor to CallLog/RecordingRun.
    This ensures no 404 errors in UI.
    """
    return get_recent_inbound_calls()


@outbound_bp.route("/api/inbound/calls/counts", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_inbound')
def get_inbound_counts_alias():
    """
    ✅ COMPATIBILITY ALIAS: Maps /api/inbound/calls/counts → /api/inbound_calls/counts
    
    Frontend expects this endpoint for call counters.
    """
    return get_inbound_call_counts_endpoint()


@outbound_bp.route("/api/outbound/recent", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calls_outbound')
def get_outbound_recent_alias():
    """
    ✅ COMPATIBILITY ALIAS: Maps /api/outbound/recent → /api/outbound/recent-calls
    
    Frontend expects this endpoint after refactor to CallLog/OutboundCallRun.
    """
    return get_recent_calls()


# Note: /api/outbound/bulk/active already exists at line 2035 (no alias needed)
