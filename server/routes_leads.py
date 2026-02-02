"""
Leads CRM API routes - Monday/HubSpot/Salesforce style
Modern lead management with Kanban board support, reminders, and activity tracking
"""
from flask import Blueprint, jsonify, request, session, g, send_file
from server.models_sql import Lead, LeadActivity, LeadReminder, LeadMergeCandidate, LeadNote, LeadAttachment, User, Business, CallLog, Contract, ContactIdentity, WhatsAppConversation, CallSession, CRMTask, Appointment, OutboundCallJob, WhatsAppBroadcastRecipient, LeadStatusHistory
from server.db import db
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from datetime import datetime, timezone, timedelta
from sqlalchemy import or_, and_, func, desc
from sqlalchemy.orm import joinedload
import logging
import os
import json
import uuid
from werkzeug.utils import secure_filename

# Timezone handling - prefer zoneinfo (Python 3.9+), fallback to pytz

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    ZONEINFO_AVAILABLE = True
except ImportError:
    ZONEINFO_AVAILABLE = False

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

if not ZONEINFO_AVAILABLE and not PYTZ_AVAILABLE:
    logging.warning("Neither zoneinfo nor pytz available - using fixed UTC+2 offset")

# Import status webhook service
from server.services.status_webhook_service import dispatch_lead_status_webhook

# Import push notification dispatcher
from server.services.notifications.dispatcher import dispatch_push_for_reminder

# Import psycopg2 for database error handling
try:
    import psycopg2.errors
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logging.warning("psycopg2 not available - some error handling may be limited")

# Background job stale threshold - jobs stuck longer than this are marked as failed
BACKGROUND_JOB_STALE_THRESHOLD_MINUTES = 10


def check_and_handle_duplicate_background_job(job_type: str, business_id: int, error_message: str, return_existing: bool = False):
    """
    Check for existing active background job and handle it appropriately.
    
    This function prevents duplicate key violations on the idx_background_jobs_unique_active
    constraint by checking for existing active jobs before creating a new one.
    
    Args:
        job_type: The type of background job (e.g., 'delete_leads')
        business_id: The business ID
        error_message: Hebrew error message to show user if active job exists
        return_existing: If True, return existing job instead of error (for idempotency)
        
    Returns:
        tuple: (can_proceed: bool, response: dict or None, status_code: int or None)
        - If can_proceed is True, caller should create the new job
        - If can_proceed is False and return_existing is True, response contains existing job_id
        - If can_proceed is False and return_existing is False, caller should return error
    """
    from server.models_sql import BackgroundJob
    
    # 🔒 CHECK: Look for existing active job to avoid unique constraint violation
    # The idx_background_jobs_unique_active constraint prevents multiple active jobs
    # (status in 'queued', 'running', 'paused') of the same type per business
    existing_job = BackgroundJob.query.filter_by(
        business_id=business_id,
        job_type=job_type
    ).filter(
        BackgroundJob.status.in_(['queued', 'running', 'paused'])
    ).first()
    
    if not existing_job:
        # No existing job, safe to proceed
        return (True, None, None)
    
    # Check if job is stale (stuck for more than threshold without heartbeat)
    now = datetime.utcnow()
    stale_threshold = timedelta(minutes=BACKGROUND_JOB_STALE_THRESHOLD_MINUTES)
    
    # Determine if job is stale based on heartbeat or created_at
    last_activity = existing_job.heartbeat_at or existing_job.created_at
    is_stale = (now - last_activity) > stale_threshold
    
    if is_stale:
        # Mark stale job as failed and allow new job to be created
        logger.warning(f"⚠️ Found stale background job {existing_job.id} (status={existing_job.status}, last_activity={last_activity}). Marking as failed.")
        existing_job.status = 'failed'
        existing_job.last_error = 'Job marked as stale - exceeded timeout without heartbeat'
        existing_job.finished_at = now
        db.session.commit()
        return (True, None, None)
    else:
        # Active job exists
        if return_existing:
            # 🔁 IDEMPOTENCY: Return existing job instead of error
            logger.info(f"🔁 Active background job {existing_job.id} already exists for business {business_id} - returning existing job (idempotent)")
            response = {
                "success": True,
                "message": f"Job already exists",
                "job_id": existing_job.id,
                "status": existing_job.status,
                "total_leads": existing_job.total,
                "existing": True
            }
            return (False, response, 202)
        else:
            # Return error (legacy behavior)
            logger.error(f"❌ Active background job {existing_job.id} already exists for business {business_id}")
            db.session.rollback()
            error_response = {
                "error": error_message,
                "active_job_id": existing_job.id,
                "active_job_status": existing_job.status,
                "success": False
            }
            return (False, error_response, 409)

log = logging.getLogger(__name__)

leads_bp = Blueprint("leads_bp", __name__)

def localize_datetime_to_israel(dt):
    """
    Convert a naive datetime (assumed to be in Israel time) to timezone-aware datetime.
    
    This fixes the issue where naive datetimes are sent to the client and interpreted as UTC,
    causing a 2-hour offset for Israel timezone (or 3 hours during DST).
    
    Uses Python's built-in zoneinfo (preferred), falls back to pytz if needed.
    
    Args:
        dt: datetime object (naive or aware)
    
    Returns:
        timezone-aware datetime in Asia/Jerusalem timezone
    """
    if dt is None:
        return None
    
    # Method 1: Use zoneinfo (Python 3.9+, built-in, handles DST automatically)
    if ZONEINFO_AVAILABLE:
        israel_tz = ZoneInfo('Asia/Jerusalem')
        
        # If already timezone-aware, convert to Israel timezone
        if dt.tzinfo is not None:
            return dt.astimezone(israel_tz)
        
        # If naive, assume it's already in Israel time and add timezone info
        # Note: We use replace() because the datetime is ALREADY in Israel local time
        # (it comes from the database stored as naive Israel time).
        # This is the correct approach for zoneinfo - it doesn't have a localize() method.
        # During DST transitions (the "ambiguous hour"), replace() uses fold=0 by default,
        # which assumes standard time. This is acceptable for our use case since:
        # 1. Users schedule reminders, not during the 1-hour DST transition
        # 2. The 1-hour ambiguity happens once a year at 2 AM
        # 3. Even if a reminder falls in that hour, 1-hour error is minimal
        return dt.replace(tzinfo=israel_tz)
    
    # Method 2: Use pytz (third-party, handles DST automatically)
    if PYTZ_AVAILABLE:
        israel_tz = pytz.timezone('Asia/Jerusalem')
        
        # If already timezone-aware, convert to Israel timezone
        if dt.tzinfo is not None:
            return dt.astimezone(israel_tz)
        
        # If naive, assume it's already in Israel time and localize it
        # Note: pytz requires localize() for naive datetimes, not replace()
        # During DST transitions, is_dst=None will raise an exception for ambiguous times,
        # which is safer than guessing. In practice, reminder times are user-scheduled
        # and unlikely to fall exactly in the DST transition hour.
        try:
            return israel_tz.localize(dt, is_dst=None)
        except Exception as e:
            # If we hit a DST transition issue, fall back to assuming DST is active
            logging.warning(f"DST ambiguity for {dt}, assuming DST is active: {e}")
            return israel_tz.localize(dt, is_dst=True)
    
    # Method 3: Fallback - use fixed offset (does NOT handle DST)
    # This is a last resort and will be incorrect during DST periods
    # Israel Standard Time is UTC+2, Israel Daylight Time is UTC+3
    # For a proper fix without zoneinfo/pytz, we'd need to implement DST rules manually
    logging.warning("Using fixed UTC+2 offset - will be incorrect during DST periods")
    if dt.tzinfo is None:
        israel_offset = timezone(timedelta(hours=2))
        return dt.replace(tzinfo=israel_offset)
    return dt


def normalize_source(source: str) -> str:
    """
    Normalize lead source to only 'phone' or 'whatsapp'
    All phone-related sources (call, realtime_phone, phone_call, etc.) become 'phone'
    All WhatsApp-related sources become 'whatsapp'
    """
    if not source:
        return 'phone'
    
    source_lower = source.lower().strip()
    
    phone_sources = {'call', 'phone', 'phone_call', 'realtime_phone', 'ai_agent', 'form', 'manual'}
    whatsapp_sources = {'whatsapp', 'wa', 'whats_app'}
    
    if source_lower in whatsapp_sources:
        return 'whatsapp'
    
    return 'phone'

def get_current_user():
    """
    BUILD 141 FIX: Get current user from g.user (populated by @require_api_auth)
    
    IMPORTANT: This relies on @require_api_auth decorator populating g.user
    """
    # Priority 1: Use g.user if available (set by @require_api_auth)
    if hasattr(g, 'user') and g.user:
        return g.user
    
    # Priority 2: Fallback to session - try both keys for compatibility
    return session.get('user') or session.get('al_user')

def get_current_tenant():
    """
    BUILD 143 FIX: Prioritize g.tenant (set by @require_api_auth) before session checks
    
    This ensures owner/admin/agent users get their tenant from the decorator,
    while system_admin can still use impersonation via session.
    """
    # Priority 1: Use g.tenant if available (set by @require_api_auth) - MOST RELIABLE
    if hasattr(g, 'tenant') and g.tenant:
        log.info(f"✅ get_current_tenant(): Using g.tenant={g.tenant}")
        return g.tenant
    
    # Priority 2: Check if impersonating (for system_admin)
    if session.get('impersonating') and session.get('impersonated_tenant_id'):
        tenant = session['impersonated_tenant_id']
        log.info(f"✅ get_current_tenant(): Impersonating tenant_id={tenant}")
        return tenant
    
    # Priority 3: Fallback to impersonated session WITHOUT flag (backward compat)
    impersonated_id = session.get('impersonated_tenant_id')
    if impersonated_id:
        log.info(f"✅ get_current_tenant(): Using impersonated_tenant_id={impersonated_id}")
        return impersonated_id
    
    # Priority 4: Get from user session - try both session keys
    user = session.get('user') or session.get('al_user')
    if user and user.get('business_id'):
        log.info(f"✅ get_current_tenant(): Using user.business_id={user.get('business_id')}")
        return user.get('business_id')
    
    # No tenant found - OK for system_admin, error for others
    user_role = user.get('role') if user else None
    if user_role == 'system_admin':
        log.info(f"✅ get_current_tenant(): system_admin with no tenant (OK)")
        return None
    
    log.error(f"❌ get_current_tenant(): No tenant found! g.tenant={getattr(g, 'tenant', None)}, impersonated={impersonated_id}, user={user}")
    return None

def require_auth():
    """
    BUILD 136 DEPRECATED: Use @require_api_auth() decorator instead
    
    This function is kept for backward compatibility but should not be used
    in new code. Use @require_api_auth() which properly sets g.user and g.tenant
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    return None

def check_lead_access(lead_id):
    """Check if current user can access lead"""
    user = get_current_user()
    if not user:
        return False
    
    # ✅ FIX: system_admin can access ALL leads
    if user.get('role') == 'system_admin':
        lead = Lead.query.filter_by(id=lead_id).first()
        return lead is not None
    
    # Business-level roles (owner, admin, agent): check tenant
    tenant_id = get_current_tenant()
    if not tenant_id:
        return False
    
    lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
    return lead is not None

def create_activity(lead_id, activity_type, payload, created_by=None):
    """Helper to create lead activity record"""
    activity = LeadActivity()
    activity.lead_id = lead_id
    activity.type = activity_type
    activity.payload = payload
    activity.created_by = created_by
    activity.at = datetime.utcnow()
    db.session.add(activity)

def ensure_default_statuses_exist(business_id):
    """Ensure default statuses exist for business - shared seeding logic"""
    from server.models_sql import LeadStatus
    
    # Check if statuses already exist
    existing_statuses = LeadStatus.query.filter_by(
        business_id=business_id,
        is_active=True
    ).count()
    
    if existing_statuses > 0:
        return  # Already seeded
    
    # Default Hebrew statuses with auto-status support - ALWAYS lowercase canonical names
    default_statuses = [
        {'name': 'new', 'label': 'חדש', 'color': 'bg-blue-100 text-blue-800', 'is_default': True},
        {'name': 'attempting', 'label': 'בניסיון קשר', 'color': 'bg-yellow-100 text-yellow-800'},
        {'name': 'no_answer', 'label': 'לא ענה', 'color': 'bg-gray-100 text-gray-800'},
        {'name': 'contacted', 'label': 'נוצר קשר', 'color': 'bg-purple-100 text-purple-800'},
        {'name': 'interested', 'label': 'מעוניין', 'color': 'bg-green-100 text-green-800'},
        {'name': 'follow_up', 'label': 'חזרה', 'color': 'bg-orange-100 text-orange-800'},
        {'name': 'not_relevant', 'label': 'לא רלוונטי', 'color': 'bg-red-100 text-red-800'},
        {'name': 'qualified', 'label': 'מוכשר', 'color': 'bg-teal-100 text-teal-800'},
        {'name': 'won', 'label': 'זכיה', 'color': 'bg-emerald-100 text-emerald-800', 'is_system': True},
        {'name': 'lost', 'label': 'אובדן', 'color': 'bg-rose-100 text-rose-800', 'is_system': True},
        {'name': 'unqualified', 'label': 'לא מוכשר', 'color': 'bg-slate-100 text-slate-800', 'is_system': True}
    ]
    
    for index, status_data in enumerate(default_statuses):
        status = LeadStatus()
        status.business_id = business_id
        status.name = status_data['name']  # Already lowercase canonical
        status.label = status_data['label']
        status.color = status_data['color']
        status.order_index = index
        status.is_default = status_data.get('is_default', False)
        status.is_system = status_data.get('is_system', False)
        db.session.add(status)
    
    db.session.commit()

def get_default_status_for_business(business_id):
    """Get default status for business with fallback to 'new'"""
    from server.models_sql import LeadStatus
    
    # Ensure default statuses exist first
    ensure_default_statuses_exist(business_id)
    
    # Get the default status
    default_status = LeadStatus.query.filter_by(
        business_id=business_id,
        is_active=True,
        is_default=True
    ).first()
    
    if default_status:
        return default_status.name  # Return canonical lowercase name
    
    # Fallback: if no default found, return 'new' (should not happen after seeding)
    log.warning(f"No default status found for business {business_id}, using fallback 'new'")
    return 'new'

def get_valid_statuses_for_business(business_id):
    """Get valid statuses for business, with guaranteed seeding"""
    from server.models_sql import LeadStatus
    
    # Ensure default statuses exist first
    ensure_default_statuses_exist(business_id)
    
    # Get statuses (guaranteed to exist now)
    statuses = LeadStatus.query.filter_by(
        business_id=business_id,
        is_active=True
    ).all()
    
    return [s.name for s in statuses]  # Return canonical lowercase names

# === LEAD MANAGEMENT ENDPOINTS ===

@leads_bp.route("/api/leads", methods=["GET"])
@require_api_auth()
@require_page_access('crm_leads')
def list_leads():
    """List leads with filtering and pagination"""
    
    try:
        user = get_current_user()
        is_system_admin = user.get('role') == 'system_admin' if user else False
        
        # BUILD 135: ONLY system_admin can see ALL leads
        if is_system_admin:
            # System admin sees all leads across all businesses
            query = Lead.query
        else:
            # BUILD 135: owner/admin/agent see only their tenant's leads
            tenant_id = get_current_tenant()
            if not tenant_id:
                return jsonify({"error": "No tenant access"}), 403
            query = Lead.query.filter_by(tenant_id=tenant_id)
        
        # Parse query parameters
        status_filter = request.args.get('status', '')
        statuses_filter = request.args.getlist('statuses[]')  # Multi-status filter
        source_filter = request.args.get('source', '')
        owner_filter = request.args.get('owner', '')
        outbound_list_id = request.args.get('outbound_list_id', '')
        direction_filter = request.args.get('direction', '')  # inbound|outbound|all
        q_filter = request.args.get('q', '')  # Search query
        from_date = request.args.get('from', '')
        to_date = request.args.get('to', '')
        page = int(request.args.get('page', 1))
        # 🔥 FIX: Increase max page size to 10,000 for project creation
        # This allows fetching all leads for a project (up to 10,000 limit)
        page_size = min(int(request.args.get('pageSize', 50)), 10000)  # Max 10,000 per page
        
        # Apply filters
        if statuses_filter:
            # ✅ NEW: Multi-status filter (case-insensitive)
            query = query.filter(func.lower(Lead.status).in_([s.lower() for s in statuses_filter]))
        elif status_filter:
            # ✅ FIXED: Case-insensitive status filtering for legacy compatibility
            query = query.filter(func.lower(Lead.status) == status_filter.lower())
        
        if source_filter:
            if source_filter == 'phone':
                phone_sources = ['call', 'phone', 'phone_call', 'realtime_phone', 'ai_agent', 'form', 'manual']
                query = query.filter(Lead.source.in_(phone_sources))
            elif source_filter == 'whatsapp':
                whatsapp_sources = ['whatsapp', 'wa', 'whats_app']
                query = query.filter(Lead.source.in_(whatsapp_sources))
        
        if owner_filter:
            query = query.filter(Lead.owner_user_id == owner_filter)
        
        if outbound_list_id:
            query = query.filter(Lead.outbound_list_id == int(outbound_list_id))
        
        if direction_filter and direction_filter != 'all':
            # Filter by call direction (inbound/outbound)
            query = query.filter(Lead.last_call_direction == direction_filter)
        
        if q_filter:
            # ✅ BUILD 170: Search only by name or phone number (partial match)
            # Remove email from search, phone partial match works (e.g., "075" finds any number containing "075")
            search_term = f"%{q_filter}%"
            query = query.filter(
                or_(
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term),
                    Lead.phone_e164.ilike(search_term)
                )
            )
        
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                query = query.filter(Lead.created_at >= from_dt)
            except ValueError:
                pass
        
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                query = query.filter(Lead.created_at <= to_dt)
            except ValueError:
                pass
        
        # Order by created_at DESC for faster sorting (indexed column)
        # BUILD 174: Performance optimization - avoid ORDER BY on multiple columns
        query = query.order_by(Lead.created_at.desc())
        
        # Pagination - BUILD 174: Optimize count query
        offset = (page - 1) * page_size
        
        # Use a lighter count query - only count IDs (faster)
        count_query = query.with_entities(Lead.id)
        total = count_query.count()
        
        # Fetch leads with pagination
        leads = query.offset(offset).limit(page_size).all()
        
        # Format response
        items = []
        for lead in leads:
            items.append({
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "full_name": lead.full_name,
                "phone_e164": lead.phone_e164,
                "display_phone": lead.display_phone,
                "email": lead.email,
                "gender": lead.gender,
                "status": lead.status,
                "source": normalize_source(lead.source),
                "owner_user_id": lead.owner_user_id,
                "outbound_list_id": lead.outbound_list_id,
                "last_call_direction": lead.last_call_direction,
                "summary": lead.summary,
                "tags": lead.tags or [],
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
                "last_contact_at": lead.last_contact_at.isoformat() if lead.last_contact_at else None
            })
        
        return jsonify({
            "items": items,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        # 🔒 DB RESILIENCE: Catch schema mismatch errors (e.g., missing last_call_direction column)
        db.session.rollback()
        if PSYCOPG2_AVAILABLE and (isinstance(e, psycopg2.errors.UndefinedColumn) or 'last_call_direction does not exist' in str(e)):
            log.error(f"❌ Database schema mismatch: last_call_direction column missing. Please run migrations. Error: {e}")
            return jsonify({
                "error": "Database schema outdated",
                "message": "Please run database migrations to add missing columns",
                "details": "Column 'last_call_direction' does not exist in leads table"
            }), 500
        # Re-raise other exceptions
        log.error(f"❌ Unexpected error in list_leads: {e}")
        raise

@leads_bp.route("/api/leads", methods=["POST"])
@require_api_auth()  # BUILD 137: Use proper decorator that sets g.user and g.tenant
def create_lead():
    """Create new lead manually"""
    try:
        log.info(f"🔵 CREATE LEAD - Starting request")
        
        tenant_id = get_current_tenant()
        log.info(f"🔵 CREATE LEAD - tenant_id: {tenant_id}")
        if not tenant_id:
            log.error(f"🔴 CREATE LEAD - No tenant access")
            return jsonify({"error": "No tenant access"}), 403
        
        data = request.get_json()
        log.info(f"🔵 CREATE LEAD - Received data: {data}")
        if not data:
            log.error(f"🔴 CREATE LEAD - No JSON data")
            return jsonify({"error": "JSON data required"}), 400
        
        # 🔥 FIX: Normalize phone number to E.164 format if provided
        raw_phone = data.get('phone_e164')
        if raw_phone:
            from server.agent_tools.phone_utils import normalize_il_phone
            normalized_phone = normalize_il_phone(raw_phone)
            if normalized_phone:
                data['phone_e164'] = normalized_phone
                log.info(f"📞 Normalized phone: {raw_phone} → {normalized_phone}")
            else:
                log.warning(f"⚠️ Could not normalize phone: {raw_phone}")
        
        # Validate required fields
        if not data.get('first_name') and not data.get('phone_e164'):
            log.error(f"🔴 CREATE LEAD - Missing required fields")
            return jsonify({"error": "Either first_name or phone_e164 is required"}), 400
        
        # Check for duplicates if phone provided - UPDATE instead of error
        if data.get('phone_e164'):
            existing = Lead.query.filter_by(
                tenant_id=tenant_id,
                phone_e164=data['phone_e164']
            ).first()
            if existing:
                log.info(f"🟡 CREATE LEAD - Found existing lead with phone {data['phone_e164']}, updating instead")
                
                # Update existing lead with new data
                if data.get('first_name'):
                    existing.first_name = data['first_name']
                if data.get('last_name'):
                    existing.last_name = data['last_name']
                if data.get('email'):
                    existing.email = data['email']
                if data.get('notes'):
                    # Append new notes to existing ones
                    if existing.notes:
                        existing.notes = existing.notes + "\n\n---\n\n" + data['notes']
                    else:
                        existing.notes = data['notes']
                
                # Update status if provided and valid
                if data.get('status'):
                    valid_statuses = get_valid_statuses_for_business(tenant_id)
                    normalized_status = data['status'].lower().strip()
                    if normalized_status in valid_statuses:
                        existing.status = normalized_status
                
                # Update tags if provided
                if data.get('tags'):
                    existing.tags = list(set((existing.tags or []) + data['tags']))
                
                existing.updated_at = datetime.utcnow()
                
                # Create activity for update
                user = get_current_user()
                create_activity(
                    existing.id,
                    "lead_updated",
                    {
                        "method": "duplicate_prevention",
                        "updated_by": user.get('email', 'unknown') if user else 'unknown',
                        "fields_updated": [k for k in ['first_name', 'last_name', 'email', 'notes', 'status', 'tags'] if data.get(k)]
                    },
                    user.get('id') if user else None
                )
                
                db.session.commit()
                log.info(f"✅ CREATE LEAD - Updated existing lead ID: {existing.id}")
                
                return jsonify({
                    "lead": {
                        "id": existing.id,
                        "first_name": existing.first_name,
                        "last_name": existing.last_name,
                        "full_name": existing.full_name,
                        "phone_e164": existing.phone_e164,
                        "email": existing.email,
                        "status": existing.status,
                        "source": existing.source,
                        "created_at": existing.created_at.isoformat(),
                        "updated_at": existing.updated_at.isoformat() if existing.updated_at else None
                    },
                    "updated": True
                }), 200
        
        # Create new lead
        user = get_current_user()
        log.info(f"🔵 CREATE LEAD - User: {user.get('email') if user else 'None'}")
        
        # ✅ FIXED: Use actual default status from database, not hardcoded 'new'
        log.info(f"🔵 CREATE LEAD - Getting valid statuses for tenant {tenant_id}")
        valid_statuses = get_valid_statuses_for_business(tenant_id)
        log.info(f"🔵 CREATE LEAD - Valid statuses: {valid_statuses}")
        
        default_status = get_default_status_for_business(tenant_id)  # Get actual default from DB
        log.info(f"🔵 CREATE LEAD - Default status: {default_status}")
        
        # Normalize provided status to canonical lowercase
        provided_status = data.get('status')
        if provided_status:
            normalized_status = provided_status.lower().strip()
            if normalized_status in valid_statuses:
                default_status = normalized_status
            else:
                log.error(f"🔴 CREATE LEAD - Invalid status: {provided_status}")
                return jsonify({
                    "error": f"Invalid status '{provided_status}'. Valid options: {', '.join(valid_statuses)}"
                }), 400
        
        log.info(f"🔵 CREATE LEAD - Creating lead object")
        lead = Lead()
        lead.tenant_id = tenant_id
        lead.first_name = data.get('first_name')
        lead.last_name = data.get('last_name')
        lead.phone_e164 = data.get('phone_e164')
        lead.email = data.get('email')
        lead.source = data.get('source', 'manual')
        lead.status = default_status  # Always canonical lowercase
        lead.owner_user_id = data.get('owner_user_id') or (user.get('id') if user else None)
        lead.tags = data.get('tags', [])
        lead.notes = data.get('notes')
        
        log.info(f"🔵 CREATE LEAD - Adding to session")
        db.session.add(lead)
        db.session.flush()  # Get ID
        log.info(f"🔵 CREATE LEAD - Lead ID: {lead.id}")
        
        # Create activity
        log.info(f"🔵 CREATE LEAD - Creating activity")
        create_activity(
            lead.id,
            "lead_created",
            {
                "method": "manual",
                "created_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
        
        log.info(f"🔵 CREATE LEAD - Committing to DB")
        db.session.commit()
        
        log.info(f"✅ CREATE LEAD - Success! Lead ID: {lead.id}")
        # ✅ FIX: Return lead wrapped in {lead: {...}} to match frontend expectations
        return jsonify({
            "lead": {
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "full_name": lead.full_name,
                "phone_e164": lead.phone_e164,
                "email": lead.email,
                "status": lead.status,
                "source": normalize_source(lead.source),
                "created_at": lead.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        log.error(f"🔴 CREATE LEAD - Exception: {e}")
        import traceback
        log.error(f"🔴 CREATE LEAD - Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to create lead: {str(e)}"}), 500

@leads_bp.route("/api/leads/<int:lead_id>", methods=["GET"])
@require_api_auth()  # BUILD 137: Added missing decorator
def get_lead_detail(lead_id):
    """Get detailed lead information with activities and reminders"""
    try:
        # BUILD 137: Authentication handled by @require_api_auth() decorator
        
        if not check_lead_access(lead_id):
            return jsonify({"error": "Lead not found or access denied"}), 404
        
        # Get lead with related data
        lead = Lead.query.filter_by(id=lead_id).first()
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        
        # Get reminders
        reminders = LeadReminder.query.filter_by(lead_id=lead_id).order_by(LeadReminder.due_at).all()
        
        # Get recent activities
        activities = LeadActivity.query.filter_by(lead_id=lead_id).order_by(desc(LeadActivity.at)).limit(50).all()
        
        # Format reminders safely
        formatted_reminders = []
        for r in reminders:
            try:
                formatted_reminders.append({
                    "id": r.id,
                    "due_at": localize_datetime_to_israel(r.due_at).isoformat() if r.due_at else None,
                    "note": r.note,
                    "channel": r.channel,
                    "delivered_at": localize_datetime_to_israel(r.delivered_at).isoformat() if r.delivered_at else None,
                    "completed_at": localize_datetime_to_israel(r.completed_at).isoformat() if r.completed_at else None
                })
            except Exception as e:
                log.error(f"Error formatting reminder {r.id}: {e}")
                continue
        
        # Format activities safely
        formatted_activities = []
        for a in activities:
            try:
                formatted_activities.append({
                    "id": a.id,
                    "type": a.type,
                    "payload": a.payload if a.payload is not None else {},
                    "at": a.at.isoformat() if a.at else None,
                    "created_by": a.created_by
                })
            except Exception as e:
                log.error(f"Error formatting activity {a.id}: {e}")
                continue
        
        # Format response
        response = {
            "id": lead.id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "full_name": lead.full_name,
            "phone_e164": lead.phone_e164,
            "display_phone": lead.display_phone,
            "email": lead.email,
            "gender": lead.gender,
            "status": lead.status,
            "source": normalize_source(lead.source),
            "external_id": lead.external_id,
            "owner_user_id": lead.owner_user_id,
            "tags": lead.tags or [],
            "notes": lead.notes,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            "last_contact_at": lead.last_contact_at.isoformat() if lead.last_contact_at else None,
            "tenant_id": lead.tenant_id,
            
            "reminders": formatted_reminders,
            "activity": formatted_activities
        }
        
        return jsonify(response)
    except Exception as e:
        log.error(f"Error getting lead detail for lead {lead_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@leads_bp.route("/api/leads/<int:lead_id>", methods=["PATCH"])
@require_api_auth()  # BUILD 137: Added missing decorator
def update_lead(lead_id):
    """Update lead information"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    # 🔥 FIX: Normalize phone number to E.164 format if provided
    if 'phone_e164' in data and data['phone_e164']:
        from server.agent_tools.phone_utils import normalize_il_phone
        raw_phone = data['phone_e164']
        normalized_phone = normalize_il_phone(raw_phone)
        if normalized_phone:
            data['phone_e164'] = normalized_phone
            log.info(f"📞 Normalized phone: {raw_phone} → {normalized_phone}")
        else:
            log.warning(f"⚠️ Could not normalize phone: {raw_phone}")
    
    lead = Lead.query.filter_by(id=lead_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
        
    user = get_current_user()
    
    # Track changes for activity log
    changes = {}
    
    # Update allowed fields
    updateable_fields = ['first_name', 'last_name', 'phone_e164', 'email', 'gender', 'owner_user_id', 'tags', 'notes']
    
    for field in updateable_fields:
        if field in data:
            old_value = getattr(lead, field)
            new_value = data[field]
            if old_value != new_value:
                changes[field] = {"from": old_value, "to": new_value}
                setattr(lead, field, new_value)
    
    # Update timestamp
    lead.updated_at = datetime.utcnow()
    
    # Log changes
    if changes:
        create_activity(
            lead_id,
            "lead_updated",
            {
                "changes": changes,
                "updated_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
    
    db.session.commit()
    
    # ✅ FIX: Return the updated lead object so frontend can update UI
    return jsonify({
        "message": "Lead updated successfully", 
        "changes": changes,
        "lead": {
            "id": lead.id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "phone_e164": lead.phone_e164,
            "email": lead.email,
            "gender": lead.gender,
            "status": lead.status,
            "source": normalize_source(lead.source),
            "owner_user_id": lead.owner_user_id,
            "tags": lead.tags,
            "notes": lead.notes,
            "summary": lead.summary,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None
        }
    })

@leads_bp.route("/api/leads/<int:lead_id>", methods=["DELETE"])
@require_api_auth()  # BUILD 137: Added missing decorator
def delete_lead(lead_id):
    """Delete a lead"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    # ✅ Admin/Superadmin can delete any lead across tenants
    is_admin = user.get('role') in ['admin', 'superadmin']
    
    # Check access - admin can access all, regular users need tenant match
    if not is_admin and not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    lead = Lead.query.filter_by(id=lead_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    try:
        # Delete all related records to prevent foreign key constraint violations
        # Order matters: delete children before parents
        
        # 1. Delete activities and reminders (already existed)
        LeadActivity.query.filter_by(lead_id=lead_id).delete()
        LeadReminder.query.filter_by(lead_id=lead_id).delete()
        
        # 2. Delete contact identities (already existed)
        ContactIdentity.query.filter_by(lead_id=lead_id).delete()
        
        # 3. Delete WhatsApp conversations (FIX: Foreign key constraint violation)
        WhatsAppConversation.query.filter_by(lead_id=lead_id).delete()
        
        # 4. Delete call sessions
        CallSession.query.filter_by(lead_id=lead_id).delete()
        
        # 5. Delete CRM tasks
        CRMTask.query.filter_by(lead_id=lead_id).delete()
        
        # 6. Delete lead merge candidates (both as source and duplicate)
        LeadMergeCandidate.query.filter_by(lead_id=lead_id).delete()
        LeadMergeCandidate.query.filter_by(duplicate_lead_id=lead_id).delete()
        
        # 7. Delete outbound call jobs
        OutboundCallJob.query.filter_by(lead_id=lead_id).delete()
        
        # 8. Delete lead status history (handle missing table gracefully)
        try:
            LeadStatusHistory.query.filter_by(lead_id=lead_id).delete()
        except Exception as lsh_err:
            err_str = str(lsh_err).lower()
            if 'undefinedtable' in err_str or 'does not exist' in err_str or 'lead_status_history' in err_str:
                log.warning(f"⚠️ LeadStatusHistory delete skipped (table does not exist)")
            else:
                raise
        
        # 9. Nullify foreign keys in related tables (instead of deleting them)
        # These records should remain even if lead is deleted
        CallLog.query.filter_by(lead_id=lead_id).update({'lead_id': None})
        Contract.query.filter_by(lead_id=lead_id).update({'lead_id': None})
        Appointment.query.filter_by(lead_id=lead_id).update({'lead_id': None})
        
        # 🔥 FIX 1: Nullify WhatsApp broadcast recipient references (preserve broadcast history)
        WhatsAppBroadcastRecipient.query.filter_by(lead_id=lead_id).update({'lead_id': None})
        
        # 10. Delete the lead itself
        # Note: LeadNote, LeadAttachment, ScheduledMessagesQueue have CASCADE delete
        db.session.delete(lead)
        db.session.commit()
        
        log.info(f"✅ Lead {lead_id} deleted by {user.get('role')} user {user.get('email')}")
    except Exception as e:
        db.session.rollback()
        log.error(f"❌ Failed to delete lead {lead_id}: {str(e)}")
        return jsonify({"error": f"Failed to delete lead: {str(e)}"}), 500
    
    return jsonify({"message": "Lead deleted successfully"}), 200

@leads_bp.route("/api/leads/<int:lead_id>/status", methods=["POST", "PATCH"])
@require_api_auth()  # BUILD 137: Added missing decorator
def update_lead_status(lead_id):
    """Update lead status (for Kanban board)"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"error": "Status is required"}), 400
    
    new_status = data['status']
    
    lead = Lead.query.filter_by(id=lead_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    # ✅ FIXED: Get valid statuses with guaranteed seeding - no more race condition
    valid_statuses = get_valid_statuses_for_business(lead.tenant_id)
    
    # ✅ FIXED: Always normalize to canonical lowercase - no more TitleCase writes
    original_status = new_status
    normalized_status = new_status.lower().strip()
    
    # Find exact match in valid statuses (all are lowercase canonical)
    if normalized_status not in valid_statuses:
        return jsonify({
            "error": f"Invalid status '{original_status}'. Valid options: {', '.join(valid_statuses)}"
        }), 400
    
    # Always use the canonical lowercase name
    new_status = normalized_status
        
    old_status = lead.status
    
    if old_status != new_status:
        lead.status = new_status
        lead.updated_at = datetime.utcnow()
        
        # Log status change
        user = get_current_user()
        create_activity(
            lead_id,
            "status_change",
            {
                "from": old_status,
                "to": new_status,
                "changed_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
        
        db.session.commit()
        
        # ✅ SCHEDULED MESSAGES: Trigger scheduled WhatsApp messages for this status change
        try:
            from server.services import scheduled_messages_service
            from server.models_sql import LeadStatus
            
            # Find the status_id for the new and old statuses
            new_status_obj = LeadStatus.query.filter_by(
                business_id=lead.tenant_id,
                name=new_status
            ).first()
            
            old_status_obj = LeadStatus.query.filter_by(
                business_id=lead.tenant_id,
                name=old_status
            ).first() if old_status else None
            
            if new_status_obj:
                scheduled_messages_service.schedule_messages_for_lead_status_change(
                    business_id=lead.tenant_id,
                    lead_id=lead_id,
                    new_status_id=new_status_obj.id,
                    old_status_id=old_status_obj.id if old_status_obj else None,
                    changed_at=datetime.utcnow()
                )
        except Exception as e:
            # Log error but don't fail the status update
            logger.error(f"Failed to schedule messages for status change: {e}", exc_info=True)
        
        # Check if webhook should be dispatched
        # Client will handle user preference (always/never/ask) and call webhook dispatch endpoint
        should_dispatch = data.get('dispatch_webhook', False)
        
        if should_dispatch:
            # Dispatch webhook in background (non-blocking)
            try:
                dispatch_lead_status_webhook(
                    business_id=lead.tenant_id,
                    lead_id=lead_id,
                    old_status=old_status,
                    new_status=new_status,
                    source=data.get('source', 'lead_page'),
                    user_id=user.get('id') if user else None
                )
            except Exception as e:
                # Don't fail the status update if webhook fails
                log.error(f"Failed to dispatch status webhook for lead {lead_id}: {e}")
        
        return jsonify({"message": "Status updated successfully", "old_status": old_status, "new_status": new_status})
    
    return jsonify({"message": "Status unchanged"})

@leads_bp.route("/api/leads/<int:lead_id>/reminders", methods=["GET"])
@require_api_auth()  # BUILD 137: Added missing decorator
def get_lead_reminders(lead_id):
    """Get all reminders for a lead"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    reminders = LeadReminder.query.filter_by(lead_id=lead_id).order_by(LeadReminder.due_at.desc()).all()
    
    return jsonify({
        "reminders": [
            {
                "id": r.id,
                "lead_id": r.lead_id,
                "due_at": localize_datetime_to_israel(r.due_at).isoformat() if r.due_at else None,
                "note": r.note,
                "channel": r.channel,
                "completed_at": localize_datetime_to_israel(r.completed_at).isoformat() if r.completed_at else None,
                "created_by": r.created_by
            }
            for r in reminders
        ]
    })

@leads_bp.route("/api/leads/<int:lead_id>/activities", methods=["GET"])
@require_api_auth()  # BUILD 137: Added missing decorator
def get_lead_activities(lead_id):
    """Get all activities for a lead"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    activities = LeadActivity.query.filter_by(lead_id=lead_id).order_by(LeadActivity.at.desc()).all()
    
    return jsonify({
        "activities": [
            {
                "id": a.id,
                "lead_id": a.lead_id,
                "type": a.type,
                "at": a.at.isoformat() if a.at else None,
                "payload": a.payload,
                "user_id": a.user_id
            }
            for a in activities
        ]
    })

@leads_bp.route("/api/leads/<int:lead_id>/reminders", methods=["POST"])
@require_api_auth()  # BUILD 137: Added missing decorator
def create_reminder(lead_id):
    """Create 'חזור אליי' reminder"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    data = request.get_json()
    if not data or 'due_at' not in data:
        return jsonify({"error": "due_at is required"}), 400
    
    try:
        # 🔥 FIX: Handle both formats - with and without timezone
        due_at_str = data['due_at']
        if due_at_str.endswith('Z'):
            due_at_str = due_at_str[:-1]
        due_at = datetime.fromisoformat(due_at_str)
        # Ensure naive datetime (local Israel time)
        if due_at.tzinfo is not None:
            due_at = due_at.replace(tzinfo=None)
    except ValueError:
        return jsonify({"error": "Invalid due_at format. Use ISO format"}), 400
    
    user = get_current_user()
    tenant_id = get_current_tenant()
    
    # Get lead name for push notification
    lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
    lead_name = lead.full_name if lead else None
    
    reminder = LeadReminder()
    reminder.tenant_id = tenant_id  # Required for new schema
    reminder.lead_id = lead_id
    reminder.due_at = due_at
    reminder.note = data.get('note')
    reminder.channel = data.get('channel', 'ui')
    reminder.created_by = user.get('id') if user else None
    
    db.session.add(reminder)
    
    # Log reminder creation
    create_activity(
        lead_id,
        "reminder_created",
        {
            "due_at": due_at.isoformat(),
            "note": data.get('note'),
            "channel": data.get('channel', 'ui'),
            "created_by": user.get('email', 'unknown') if user else 'unknown'
        },
        user.get('id') if user else None
    )
    
    db.session.commit()
    
    # 🔔 Dispatch push notification for new reminder
    dispatch_push_for_reminder(
        reminder_id=reminder.id,
        tenant_id=tenant_id,
        created_by=user.get('id') if user else None,
        note=reminder.note,
        lead_name=lead_name,
        lead_id=lead_id,
        reminder_type='lead_related',
        priority='medium'
    )
    
    return jsonify({
        "id": reminder.id,
        "due_at": localize_datetime_to_israel(reminder.due_at).isoformat(),
        "note": reminder.note,
        "channel": reminder.channel,
        "message": "Reminder created successfully"
    }), 201

# === ADMIN ENDPOINTS ===
# Note: Admin leads endpoint moved to routes_admin.py to avoid duplicate route conflict
# REMOVED: Duplicate /api/admin/leads route was here - now only in routes_admin.py

@leads_bp.route("/api/leads/<int:lead_id>/move", methods=["PATCH"])
@require_api_auth()  # BUILD 137: Added missing decorator
def move_lead_in_kanban(lead_id):
    """Move lead position in Kanban board (drag & drop support)"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    # Extract move parameters
    new_status = data.get('status')
    before_id = data.get('beforeId')  # ID of lead before which to place this lead
    after_id = data.get('afterId')    # ID of lead after which to place this lead
    
    tenant_id = get_current_tenant()
    lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    # Update status if provided
    if new_status and new_status != lead.status:
        # ✅ FIXED: Use guaranteed seeding and canonical lowercase validation
        valid_statuses = get_valid_statuses_for_business(tenant_id)
        normalized_status = new_status.lower().strip()
        
        if normalized_status not in valid_statuses:
            return jsonify({"error": f"Invalid status '{new_status}'. Valid options: {', '.join(valid_statuses)}"}), 400
        
        old_status = lead.status
        lead.status = normalized_status  # Always canonical lowercase
        
        # Log status change
        user = get_current_user()
        create_activity(
            lead_id,
            "kanban_move",
            {
                "from_status": old_status,
                "to_status": new_status,
                "moved_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
        
        # ✅ SCHEDULED MESSAGES: Trigger scheduled WhatsApp messages for this status change
        try:
            from server.services import scheduled_messages_service
            from server.models_sql import LeadStatus
            
            # Find the status_id for the new and old statuses
            new_status_obj = LeadStatus.query.filter_by(
                business_id=tenant_id,
                name=normalized_status
            ).first()
            
            old_status_obj = LeadStatus.query.filter_by(
                business_id=tenant_id,
                name=old_status
            ).first() if old_status else None
            
            if new_status_obj:
                scheduled_messages_service.schedule_messages_for_lead_status_change(
                    business_id=tenant_id,
                    lead_id=lead_id,
                    new_status_id=new_status_obj.id,
                    old_status_id=old_status_obj.id if old_status_obj else None,
                    changed_at=datetime.utcnow()
                )
        except Exception as e:
            # Log error but don't fail the status update
            logger.error(f"Failed to schedule messages for kanban status change: {e}", exc_info=True)
    
    # Calculate new order_index based on before/after positioning
    new_order_index = 0
    
    if before_id or after_id:
        # Get reference leads for positioning
        if before_id:
            before_lead = Lead.query.filter_by(id=before_id, tenant_id=tenant_id).first()
            if before_lead and before_lead.status == (new_status or lead.status):
                new_order_index = before_lead.order_index - 1
        
        if after_id:
            after_lead = Lead.query.filter_by(id=after_id, tenant_id=tenant_id).first()
            if after_lead and after_lead.status == (new_status or lead.status):
                new_order_index = max(new_order_index, after_lead.order_index + 1)
    
    # If no positioning specified, put at the end of the status column
    if new_order_index == 0:
        last_lead = Lead.query.filter_by(
            tenant_id=tenant_id, 
            status=(new_status or lead.status)
        ).order_by(desc(Lead.order_index)).first()
        new_order_index = (last_lead.order_index + 100) if last_lead else 100
    
    lead.order_index = new_order_index
    lead.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        "message": "Lead moved successfully",
        "status": lead.status,
        "order_index": lead.order_index
    })

@leads_bp.route("/api/leads/<int:lead_id>/reminders/<int:reminder_id>", methods=["GET"])
@require_api_auth()  # BUILD 137: Added missing decorator
def get_reminder(lead_id, reminder_id):
    """Get specific reminder details"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    reminder = LeadReminder.query.filter_by(id=reminder_id, lead_id=lead_id).first()
    if not reminder:
        return jsonify({"error": "Reminder not found"}), 404
    
    return jsonify({
        "id": reminder.id,
        "due_at": localize_datetime_to_israel(reminder.due_at).isoformat() if reminder.due_at else None,
        "note": reminder.note,
        "channel": reminder.channel,
        "delivered_at": localize_datetime_to_israel(reminder.delivered_at).isoformat() if reminder.delivered_at else None,
        "completed_at": localize_datetime_to_israel(reminder.completed_at).isoformat() if reminder.completed_at else None,
        "created_at": localize_datetime_to_israel(reminder.created_at).isoformat() if reminder.created_at else None
    })

@leads_bp.route("/api/leads/<int:lead_id>/reminders/<int:reminder_id>", methods=["PATCH"])
@require_api_auth()  # BUILD 137: Added missing decorator
def update_reminder(lead_id, reminder_id):
    """Update or complete reminder"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    reminder = LeadReminder.query.filter_by(id=reminder_id, lead_id=lead_id).first()
    if not reminder:
        return jsonify({"error": "Reminder not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    # Update allowed fields
    if 'due_at' in data:
        try:
            # 🔥 FIX: Handle both formats - with and without timezone
            due_at_str = data['due_at']
            if due_at_str.endswith('Z'):
                due_at_str = due_at_str[:-1]
            due_at = datetime.fromisoformat(due_at_str)
            # Ensure naive datetime (local Israel time)
            reminder.due_at = due_at.replace(tzinfo=None) if due_at.tzinfo else due_at
        except ValueError:
            return jsonify({"error": "Invalid due_at format. Use ISO format"}), 400
    
    if 'note' in data:
        reminder.note = data['note']
    
    if 'completed' in data and data['completed']:
        # 🔥 FIX: Use local time for completed_at
        reminder.completed_at = datetime.now()
        
        # Log completion
        user = get_current_user()
        create_activity(
            lead_id,
            "reminder_completed",
            {
                "reminder_id": reminder_id,
                "note": reminder.note,
                "completed_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
    
    db.session.commit()
    
    return jsonify({"message": "Reminder updated successfully"})

@leads_bp.route("/api/leads/<int:lead_id>/reminders/<int:reminder_id>", methods=["DELETE"])
@require_api_auth()
@require_page_access('crm_leads')
def delete_lead_reminder(lead_id, reminder_id):
    """Delete a reminder associated with a lead"""
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    reminder = LeadReminder.query.filter_by(id=reminder_id, lead_id=lead_id).first()
    if not reminder:
        return jsonify({"error": "Reminder not found"}), 404
    
    try:
        # Store note for logging before deletion
        note = reminder.note
        
        # Delete reminder
        db.session.delete(reminder)
        db.session.commit()
        
        # Log deletion after successful commit
        user = get_current_user()
        create_activity(
            lead_id,
            "reminder_deleted",
            {
                "reminder_id": reminder_id,
                "note": note,
                "deleted_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
        
        return jsonify({"message": "Reminder deleted successfully"})
    except Exception as e:
        db.session.rollback()
        log.error(f"Error deleting reminder {reminder_id}: {e}")
        return jsonify({"error": "Failed to delete reminder"}), 500


@leads_bp.route("/api/reminders/due", methods=["GET"])
@require_api_auth()  # BUILD 137: Added missing decorator
def get_due_reminders():
    """Get all due and overdue reminders for notifications"""
    
    # Use existing auth pattern
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403

    # 🔥 FIX: Get current time in local Israel time
    now = datetime.now()
    
    # Query for due reminders (not completed, due time has passed)
    # Use left join to support reminders without lead_id
    due_reminders = db.session.query(LeadReminder, Lead).outerjoin(
        Lead, LeadReminder.lead_id == Lead.id
    ).filter(
        LeadReminder.tenant_id == tenant_id,  # Business scope via direct tenant ownership
        LeadReminder.completed_at.is_(None),  # Not completed
        LeadReminder.due_at <= now  # Due or overdue
    ).order_by(LeadReminder.due_at.asc()).all()

    # Build response with lead context
    reminders_data = []
    for reminder, lead in due_reminders:
        reminders_data.append({
            "id": reminder.id,
            "lead_id": reminder.lead_id,
            "lead_name": lead.full_name if lead else None,
            "lead_phone": lead.display_phone if lead else None,
            "due_at": localize_datetime_to_israel(reminder.due_at).isoformat(),
            "note": reminder.note,
            "channel": reminder.channel,
            "overdue_minutes": int((now - reminder.due_at).total_seconds() / 60) if reminder.due_at < now else 0,
            "created_at": localize_datetime_to_israel(reminder.created_at).isoformat()
        })

    return jsonify({
        "reminders": reminders_data,
        "total_count": len(reminders_data),
        "overdue_count": len([r for r in reminders_data if r["overdue_minutes"] > 0])
    })

@leads_bp.route("/api/notifications", methods=["GET"])
@require_api_auth()  # BUILD 142 FINAL FIX
def get_notifications():
    """Get task notifications categorized by urgency (overdue, today, soon)"""
    try:
        tenant_id = get_current_tenant()
        user = get_current_user()
        user_id = user.get('id') if user else None
        is_system_admin = user.get('role') == 'system_admin' if user else False
        
        logger.info(f"🔔 /api/notifications - tenant_id={tenant_id}, user_id={user_id}, is_system_admin={is_system_admin}")
        
        # If no tenant and NOT system_admin, return empty
        if not tenant_id and not is_system_admin:
            logger.warning(f"⚠️ Non-admin user with no tenant - returning empty notifications")
            return jsonify({
                "notifications": [],
                "overdue": [],
                "today": [],
                "soon": []
            })
        
        # system_admin with no tenant sees ALL reminders across all businesses
        if is_system_admin and not tenant_id:
            logger.info(f"✅ system_admin viewing ALL notifications (no tenant filter)")
            # Continue without tenant filter
        
        from datetime import timedelta
        from sqlalchemy import and_, cast, Date, or_
        
        # 🔥 FIX: Use local Israel time instead of UTC
        # Since reminders are stored as naive datetime in local Israel time,
        # we must compare against local time, not UTC
        now = datetime.now()  # Local Israel time (naive datetime)
        today = now.date()
        soon_threshold = now + timedelta(hours=3)
        tomorrow = today + timedelta(days=1)
        
        # 🔥 FIX: Only show reminders that are due (past or today), not future reminders
        # Show:
        # 1. Overdue reminders (past)
        # 2. Today's reminders
        # 3. System notifications (always show)
        # Don't show: Future reminders
        query = db.session.query(LeadReminder, Lead).outerjoin(
            Lead, LeadReminder.lead_id == Lead.id
        ).filter(
            LeadReminder.completed_at.is_(None),
            or_(
                LeadReminder.due_at <= tomorrow,  # Past, today, or early tomorrow
                and_(
                    LeadReminder.reminder_type.isnot(None),
                    LeadReminder.reminder_type.like('system_%')  # Always show system notifications
                )
            )
        )
        
        # Add tenant filter (business scoping)
        if tenant_id:
            query = query.filter(LeadReminder.tenant_id == tenant_id)
        
        # Add user-level filter: only show notifications for current user
        # Exception: lead-related reminders (lead_id is not None) are shared within business
        if user_id and not is_system_admin:
            query = query.filter(
                or_(
                    LeadReminder.created_by == user_id,  # User's own notifications
                    LeadReminder.lead_id.isnot(None)     # Lead-related reminders are shared
                )
            )
        
        # Order by due_at to show most urgent first
        query = query.order_by(LeadReminder.due_at.asc())
        
        reminders = query.all()
        
        logger.info(f"🔔 Found {len(reminders)} reminders for user {user_id}")
    
    except Exception as e:
        import traceback
        logger.error(f"❌ ERROR in /api/notifications: {e}")
        logger.error(f"❌ STACKTRACE:\n{traceback.format_exc()}")
        
        # 🔒 FAIL-SOFT (BONUS ONLY): Handle schema mismatch errors gracefully
        # ⚠️ IMPORTANT: This is NOT a real solution - just prevents 500 errors
        # The real fix is running migrations: python -m server.db_migrate
        # 
        # Schema drift affects the ENTIRE Lead flow:
        # - Lead creation (WhatsApp, calls, forms)
        # - Lead queries and filters
        # - Customer intelligence
        # - Call direction tracking
        # 
        # This fail-soft only helps /api/notifications continue working.
        # In production with MIGRATIONS_ENFORCE=true, server won't start anyway.
        if PSYCOPG2_AVAILABLE and isinstance(e, psycopg2.errors.UndefinedColumn):
            logger.error("❌ Database schema outdated - missing column in query")
            logger.error("   ⚠️ This affects the ENTIRE Lead system, not just notifications!")
            logger.error("   Action: Run migrations with: python -m server.db_migrate")
            return jsonify({
                "notifications": [],
                "overdue": [],
                "today": [],
                "soon": [],
                "warning": "Database schema outdated. Please run migrations."
            }), 200  # Return 200 with empty data for graceful degradation
        
        # Check for UndefinedColumn in string representation (fallback)
        if 'does not exist' in str(e).lower() and 'column' in str(e).lower():
            logger.error("❌ Database schema mismatch detected")
            logger.error("   ⚠️ This affects the ENTIRE Lead system, not just notifications!")
            logger.error("   Action: Run migrations with: python -m server.db_migrate")
            return jsonify({
                "notifications": [],
                "overdue": [],
                "today": [],
                "soon": [],
                "warning": "Database schema outdated. Please run migrations."
            }), 200  # Return 200 with empty data for graceful degradation
        
        return jsonify({"error": f"Internal error: {str(e)}"}), 500
    
    notifications = []
    
    for reminder, lead in reminders:
        # FIX: Show ALL notifications with smart categorization
        # Categorize by urgency for display purposes
        category = None
        
        is_system_notification = reminder.reminder_type and reminder.reminder_type.startswith('system_')
        
        if reminder.due_at < now:
            category = "overdue"
        elif reminder.due_at.date() == today:
            category = "today"
        elif reminder.due_at <= soon_threshold:
            category = "soon"
        elif reminder.due_at.date() == tomorrow:
            category = "tomorrow"
        elif is_system_notification:
            category = "system"
        else:
            # Future notifications - still show them but mark as upcoming
            category = "upcoming"
        
        notifications.append({
            "id": str(reminder.id),
            "title": reminder.note or "משימה ללא תיאור",
            "description": reminder.description,  # BUILD 151: For system notifications
            "due_date": localize_datetime_to_israel(reminder.due_at).isoformat(),
            "category": category,
            "phone": lead.display_phone if lead else None,
            "lead_id": reminder.lead_id,
            "lead_name": lead.full_name if lead else None,
            "created_at": localize_datetime_to_israel(reminder.created_at).isoformat() if reminder.created_at else None,
            "reminder_type": reminder.reminder_type,  # BUILD 151: For system notifications
            "priority": reminder.priority  # BUILD 151: For urgency indication
        })
    
    return jsonify({
        "success": True,
        "notifications": notifications,
        "count": len(notifications)
    })

@leads_bp.route("/api/leads/bulk-delete", methods=["POST"])
@require_api_auth()  # BUILD 137: Added missing decorator
def bulk_delete_leads():
    """Bulk delete multiple leads - with proper cascade cleanup"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    user = get_current_user()
    is_system_admin = user.get('role') == 'system_admin' if user else False
    
    # BUILD 157: Always get tenant from session/g - even system_admin uses it when impersonating
    tenant_id = get_current_tenant()
    
    # BUILD 157: For non-system-admin, tenant is required
    if not is_system_admin and not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    data = request.get_json()
    if not data or 'lead_ids' not in data:
        return jsonify({"error": "lead_ids is required"}), 400
    
    lead_ids = data['lead_ids']
    
    if not isinstance(lead_ids, list) or len(lead_ids) == 0:
        return jsonify({"error": "lead_ids must be a non-empty array"}), 400
    
    log.info(f"🗑️ Bulk delete: user={user.get('email') if user else 'unknown'}, is_system_admin={is_system_admin}, tenant_id={tenant_id}, lead_ids={lead_ids}")
    
    # 🔥 USE BULK GATE: Check if enqueue is allowed
    try:
        # Get Redis connection for BulkGate via unified wrapper
        from server.services.jobs import get_redis
        redis_conn = get_redis()
        
        from server.services.bulk_gate import get_bulk_gate
        bulk_gate = get_bulk_gate(redis_conn)
        
        if bulk_gate:
            # Check if enqueue is allowed
            allowed, reason = bulk_gate.can_enqueue(
                business_id=tenant_id,
                operation_type='delete_leads_bulk',
                user_id=user.get('id') if user else None
            )
            
            if not allowed:
                return jsonify({"error": reason}), 429
    except Exception as e:
        logger.warning(f"BulkGate check failed (proceeding anyway): {e}")
    
    try:
        # Validate tenant access - ensure we have leads to process
        if tenant_id:
            # Verify all requested leads belong to this tenant
            accessible_leads = Lead.query.filter(
                Lead.id.in_(lead_ids),
                Lead.tenant_id == tenant_id
            ).all()
        else:
            # System admin without impersonation
            accessible_leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
        
        if len(accessible_leads) == 0:
            return jsonify({"error": "No leads found or access denied", "success": False}), 404
        
        # Extract business_id for BackgroundJob (use tenant or first lead's tenant)
        business_id = tenant_id if tenant_id else accessible_leads[0].tenant_id
        
        log.info(f"🗑️ Creating bulk delete job: {len(accessible_leads)} leads (tenant={business_id})")
        
        # Create BackgroundJob record
        from server.models_sql import BackgroundJob
        from rq import Queue
        import redis
        
        # 🔁 IDEMPOTENCY: Check for existing active job and return it if found (instead of error)
        # This prevents duplicate jobs from UI double-clicks or network retries
        can_proceed, response, status_code = check_and_handle_duplicate_background_job(
            job_type='delete_leads',
            business_id=business_id,
            error_message="מחיקה המונית פעילה כבר קיימת. אנא המתן לסיום המחיקה הנוכחית.",
            return_existing=True  # 🔁 Return existing job instead of error
        )
        
        if not can_proceed:
            # Return existing job (idempotent) or error
            return jsonify(response), status_code
        
        bg_job = BackgroundJob()
        bg_job.business_id = business_id
        bg_job.requested_by_user_id = user.get('id') if user else None
        bg_job.job_type = 'delete_leads'
        bg_job.status = 'queued'
        bg_job.total = len(accessible_leads)
        bg_job.processed = 0
        bg_job.succeeded = 0
        bg_job.failed_count = 0
        bg_job.cursor = json.dumps({
            'lead_ids': [lead.id for lead in accessible_leads],
            'processed_ids': []
        })
        db.session.add(bg_job)
        
        # Commit with error handling for constraint violations
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            # Check if this is a constraint violation on job_type
            error_msg = str(commit_error).lower()
            if 'chk_job_type' in error_msg or 'job_type' in error_msg:
                log.error(f"❌ Database constraint error: job_type 'delete_leads' not allowed")
                log.error(f"   This requires a database migration to update the chk_job_type constraint")
                log.error(f"   Run migrations to add 'delete_leads' to allowed job types")
                return jsonify({
                    "error": "Database migration required for bulk delete feature",
                    "details": "The background_jobs table constraint needs to be updated. Contact administrator.",
                    "success": False
                }), 503
            # Re-raise other errors
            raise
        
        # Enqueue to RQ maintenance queue using unified wrapper
        from server.services.jobs import enqueue, get_redis
        
        # Get Redis connection for bulk gate
        redis_conn = get_redis()
        
        # Acquire lock and record enqueue BEFORE actually enqueuing
        try:
            from server.services.bulk_gate import get_bulk_gate
            bulk_gate = get_bulk_gate(redis_conn)
            
            if bulk_gate:
                # Acquire lock for this operation
                lock_acquired = bulk_gate.acquire_lock(
                    business_id=business_id,
                    operation_type='delete_leads_bulk',
                    job_id=bg_job.id
                )
                
                # Record the enqueue
                bulk_gate.record_enqueue(
                    business_id=business_id,
                    operation_type='delete_leads_bulk'
                )
        except Exception as e:
            logger.warning(f"BulkGate lock/record failed (proceeding anyway): {e}")
        
        # Import and enqueue the job function
        from server.jobs.delete_leads_job import delete_leads_batch_job
        rq_job = enqueue(
            'maintenance',
            delete_leads_batch_job,
            bg_job.id,
            business_id=business_id,
            run_id=bg_job.id,
            job_id=f"delete_leads_{bg_job.id}",
            timeout=1800,  # 30 minutes
            ttl=3600
        )
        
        log.info(f"🚀 Enqueued RQ job for bulk delete, job_id={bg_job.id}, rq_job_id={rq_job.id}")
        
        return jsonify({
            "success": True,
            "message": f"Bulk delete job created for {len(accessible_leads)} leads",
            "job_id": bg_job.id,
            "total_leads": len(accessible_leads)
        }), 202  # 202 Accepted - processing in background
        
    except Exception as e:
        db.session.rollback()
        log.error(f"❌ Bulk delete error: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({"error": f"Failed to delete leads: {str(e)}", "success": False}), 500

@leads_bp.route("/api/jobs/<int:job_id>", methods=["GET"])
@require_api_auth()
def get_job_status(job_id):
    """
    Get status of a background job (delete_leads, update_leads, etc.)
    
    This endpoint is called by the UI to poll job status during bulk operations.
    
    CRITICAL: Always returns 200 OK with valid JSON, even if job not found.
    This prevents UI error toasts when polling after job completion/cleanup.
    
    Returns:
    - success: True/False
    - job_id: Job ID
    - status: Current status (queued/running/paused/completed/failed/cancelled/unknown)
    - total: Total items to process
    - processed: Items processed so far
    - succeeded: Items successfully processed
    - failed_count: Items that failed
    - percent: Completion percentage (0-100)
    - last_error: Last error message (if any)
    - created_at: When job was created
    - started_at: When job started (if started)
    - finished_at: When job finished (if finished)
    - heartbeat_at: Last heartbeat timestamp (for stale detection)
    - is_stuck: Whether job appears to be stuck
    - stuck_reason: Reason why job is considered stuck (if applicable)
    """
    from server.models_sql import BackgroundJob
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        # 🔥 CRITICAL: Return valid JSON with 200, not 403
        # UI polling should not show error toast for auth issues
        return jsonify({
            "success": True,
            "status": "unknown",
            "job_id": job_id,
            "message": "No tenant access",
            "total": 0,
            "processed": 0,
            "succeeded": 0,
            "failed_count": 0,
            "percent": 0.0
        }), 200
    
    # Load job with business_id check for multi-tenant isolation
    job = BackgroundJob.query.filter_by(
        id=job_id,
        business_id=tenant_id
    ).first()
    
    # 🔥 CRITICAL: If job not found, return neutral JSON with 200 (not 404)
    # This prevents UI error toasts when:
    # - Job was already deleted/cleaned up
    # - Job doesn't exist yet
    # - Job belongs to different tenant
    if not job:
        return jsonify({
            "success": True,
            "status": "unknown",
            "job_id": job_id,
            "job_type": "unknown",
            "message": "Job not found - may have been completed and cleaned up",
            "total": 0,
            "processed": 0,
            "succeeded": 0,
            "failed_count": 0,
            "percent": 0.0,
            "is_stuck": False
        }), 200
    
    # Check if job is stuck (no worker processing it)
    is_stuck = False
    stuck_reason = None
    
    if job.status == 'queued':
        # Job is queued but not picked up by worker
        time_in_queue = (datetime.utcnow() - job.created_at).total_seconds() if job.created_at else 0
        if time_in_queue > 60:  # Stuck in queue for more than 1 minute
            is_stuck = True
            stuck_reason = f"Job queued for {int(time_in_queue)}s but not picked up by worker. Worker may not be running or not listening to maintenance queue."
    
    elif job.status == 'running':
        # Job is running but heartbeat is stale
        if job.heartbeat_at:
            seconds_since_heartbeat = (datetime.utcnow() - job.heartbeat_at).total_seconds()
            if seconds_since_heartbeat > 120:  # No heartbeat for 2+ minutes
                is_stuck = True
                stuck_reason = f"No heartbeat for {int(seconds_since_heartbeat)}s. Worker may have crashed or database connection lost."
    
    # 🔥 ALWAYS return 200 with valid JSON
    response = {
        "success": True,
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "total": job.total,
        "processed": job.processed,
        "succeeded": job.succeeded,
        "failed_count": job.failed_count,
        "percent": job.percent,
        "last_error": job.last_error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        "is_stuck": is_stuck,
        "stuck_reason": stuck_reason
    }
    
    return jsonify(response), 200

@leads_bp.route("/api/leads/bulk", methods=["PATCH"])
@require_api_auth()  # BUILD 137: Added missing decorator
def bulk_update_leads():
    """Bulk update multiple leads - uses RQ worker for batch processing"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    data = request.get_json()
    if not data or 'lead_ids' not in data or 'updates' not in data:
        return jsonify({"error": "lead_ids and updates are required"}), 400
    
    lead_ids = data['lead_ids']
    updates = data['updates']
    
    if not isinstance(lead_ids, list) or len(lead_ids) == 0:
        return jsonify({"error": "lead_ids must be a non-empty array"}), 400
    
    user = get_current_user()
    
    # 🔥 USE BULK GATE: Check if enqueue is allowed
    try:
        # Get Redis connection for BulkGate via unified wrapper
        from server.services.jobs import get_redis
        redis_conn = get_redis()
        
        from server.services.bulk_gate import get_bulk_gate
        bulk_gate = get_bulk_gate(redis_conn)
        
        if bulk_gate:
            # Check if enqueue is allowed
            allowed, reason = bulk_gate.can_enqueue(
                business_id=tenant_id,
                operation_type='update_leads_bulk',
                user_id=user.get('id') if user else None
            )
            
            if not allowed:
                return jsonify({"error": reason}), 429
    except Exception as e:
        logger.warning(f"BulkGate check failed (proceeding anyway): {e}")
    
    # Validate access to all leads
    leads = Lead.query.filter(
        Lead.id.in_(lead_ids),
        Lead.tenant_id == tenant_id
    ).all()
    
    if len(leads) != len(lead_ids):
        return jsonify({"error": "Some leads not found or access denied"}), 404
    
    try:
        # Create BackgroundJob record
        from server.models_sql import BackgroundJob
        from rq import Queue
        import redis
        
        # Check for existing active job and handle duplicates
        can_proceed, error_response, status_code = check_and_handle_duplicate_background_job(
            job_type='update_leads',
            business_id=tenant_id,
            error_message="עדכון המוני פעיל כבר קיים. אנא המתן לסיום העדכון הנוכחי."
        )
        
        if not can_proceed:
            return jsonify(error_response), status_code
        
        bg_job = BackgroundJob()
        bg_job.business_id = tenant_id
        bg_job.requested_by_user_id = user.get('id') if user else None
        bg_job.job_type = 'update_leads'
        bg_job.status = 'queued'
        bg_job.total = len(lead_ids)
        bg_job.processed = 0
        bg_job.succeeded = 0
        bg_job.failed_count = 0
        bg_job.cursor = json.dumps({
            'lead_ids': lead_ids,
            'updates': updates,
            'user_email': user.get('email', 'unknown') if user else 'unknown',
            'user_id': user.get('id') if user else None,
            'processed_ids': []
        })
        db.session.add(bg_job)
        
        # Commit with error handling for constraint violations
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            # Check if this is a constraint violation on job_type
            error_msg = str(commit_error).lower()
            if 'chk_job_type' in error_msg or 'job_type' in error_msg:
                log.error(f"❌ Database constraint error: job_type 'update_leads' not allowed")
                log.error(f"   This requires a database migration to update the chk_job_type constraint")
                log.error(f"   Run migrations to add 'update_leads' to allowed job types")
                return jsonify({
                    "error": "Database migration required for bulk update feature",
                    "details": "The background_jobs table constraint needs to be updated. Contact administrator.",
                    "success": False
                }), 503
            # Re-raise other errors
            raise
        
        # Enqueue to RQ maintenance queue using unified wrapper
        from server.services.jobs import enqueue, get_redis
        
        # Get Redis connection for bulk gate
        redis_conn = get_redis()
        
        # Acquire lock and record enqueue BEFORE actually enqueuing
        try:
            from server.services.bulk_gate import get_bulk_gate
            bulk_gate = get_bulk_gate(redis_conn)
            
            if bulk_gate:
                # Acquire lock for this operation
                lock_acquired = bulk_gate.acquire_lock(
                    business_id=tenant_id,
                    operation_type='update_leads_bulk',
                    job_id=bg_job.id
                )
                
                # Record the enqueue
                bulk_gate.record_enqueue(
                    business_id=tenant_id,
                    operation_type='update_leads_bulk'
                )
        except Exception as e:
            logger.warning(f"BulkGate lock/record failed (proceeding anyway): {e}")
        
        # Import and enqueue the job function
        from server.jobs.update_leads_job import update_leads_batch_job
        rq_job = enqueue(
            'maintenance',
            update_leads_batch_job,
            bg_job.id,
            business_id=tenant_id,
            run_id=bg_job.id,
            job_id=f"update_leads_{bg_job.id}",
            timeout=1800,  # 30 minutes
            ttl=3600
        )
        
        log.info(f"🚀 Enqueued RQ job for bulk update, job_id={bg_job.id}, rq_job_id={rq_job.id}")
        
        return jsonify({
            "success": True,
            "message": f"Bulk update job created for {len(lead_ids)} leads",
            "job_id": bg_job.id,
            "total_leads": len(lead_ids)
        }), 202  # 202 Accepted - processing in background
        
    except Exception as e:
        db.session.rollback()
        log.error(f"❌ Bulk update error: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({"error": f"Failed to create update job: {str(e)}"}), 500

# Placeholder for WhatsApp integration - will be implemented in task 7
@leads_bp.route("/api/leads/<int:lead_id>/message/whatsapp", methods=["POST"])
@require_api_auth()  # BUILD 137: Added missing decorator
def send_whatsapp_message(lead_id):
    """Send WhatsApp message to lead"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    # WhatsApp integration is available via WhatsApp provider
    # See server/whatsapp_provider.py and server/services/whatsapp_send_service.py
    return jsonify({"message": "WhatsApp integration coming soon"}), 501

# ====================================
# General Reminders Endpoints (CRM)
# ====================================

@leads_bp.route("/api/reminders", methods=["GET"])
@require_api_auth()  # BUILD 136 FIX: Use proper decorator that sets g.user and g.tenant
def get_all_reminders():
    """Get all reminders for current business/tenant"""
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Get all reminders for this tenant (both lead-specific and general)
    reminders = LeadReminder.query.filter_by(tenant_id=tenant_id).order_by(LeadReminder.due_at.desc()).all()
    
    # Get lead names for display
    lead_names = {}
    lead_ids = [r.lead_id for r in reminders if r.lead_id]
    if lead_ids:
        leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
        lead_names = {l.id: l.full_name or f"{l.first_name or ''} {l.last_name or ''}".strip() for l in leads}
    
    return jsonify({
        "reminders": [
            {
                "id": r.id,
                "lead_id": r.lead_id,
                "lead_name": lead_names.get(r.lead_id) if r.lead_id else None,
                "due_at": localize_datetime_to_israel(r.due_at).isoformat() if r.due_at else None,
                "note": r.note,
                "description": r.description or r.note,  # BUILD 143: Use actual description
                "channel": r.channel,
                "priority": r.priority or "medium",  # BUILD 143: Use actual priority
                "reminder_type": r.reminder_type or "general",  # BUILD 143: Use actual type
                "completed_at": localize_datetime_to_israel(r.completed_at).isoformat() if r.completed_at else None,
                "created_by": r.created_by,
                "created_at": localize_datetime_to_israel(r.created_at).isoformat() if r.created_at else None
            }
            for r in reminders
        ]
    })

@leads_bp.route("/api/reminders", methods=["POST"])
@require_api_auth()  # BUILD 142 FINAL: Allow all authenticated users (owner/admin/agent)
def create_general_reminder():
    """Create a new reminder (with or without lead association)"""
    log.info(f"📝 CREATE REMINDER - Starting")
    
    tenant_id = get_current_tenant()
    log.info(f"📝 CREATE REMINDER - tenant_id={tenant_id}")
    if not tenant_id:
        log.error(f"❌ CREATE REMINDER - No tenant access")
        return jsonify({"error": "No tenant access"}), 403
    
    data = request.get_json()
    log.info(f"📝 CREATE REMINDER - data={data}")
    if not data or 'due_at' not in data or 'note' not in data:
        log.error(f"❌ CREATE REMINDER - Missing required fields: due_at={data.get('due_at')}, note={data.get('note')}")
        return jsonify({"error": "due_at and note are required"}), 400
    
    try:
        # 🔥 FIX: Handle both formats - with and without timezone
        due_at_str = data['due_at']
        if due_at_str.endswith('Z'):
            due_at_str = due_at_str[:-1]
        due_at = datetime.fromisoformat(due_at_str)
        # Ensure naive datetime (local Israel time)
        if due_at.tzinfo is not None:
            due_at = due_at.replace(tzinfo=None)
    except ValueError:
        return jsonify({"error": "Invalid due_at format. Use ISO format"}), 400
    
    # If lead_id is provided, verify access
    lead_id = data.get('lead_id')
    lead_name = None
    if lead_id:
        lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
        if not lead:
            return jsonify({"error": "Lead not found or access denied"}), 404
        lead_name = lead.full_name
    
    user = get_current_user()
    
    reminder = LeadReminder()
    reminder.tenant_id = tenant_id  # Direct tenant ownership
    reminder.lead_id = lead_id if lead_id else None  # Optional lead association
    reminder.due_at = due_at
    reminder.note = data.get('note')
    reminder.description = data.get('description')  # BUILD 143: Additional details
    reminder.channel = data.get('channel', 'ui')
    reminder.priority = data.get('priority', 'medium')  # BUILD 143: low|medium|high
    reminder.reminder_type = data.get('reminder_type', 'general')  # BUILD 143: general|lead_related
    reminder.created_by = user.get('id') if user else None
    
    db.session.add(reminder)
    
    # Log reminder creation only if associated with a lead
    if lead_id:
        create_activity(
            lead_id,
            "reminder_created",
            {
                "due_at": due_at.isoformat(),
                "note": data.get('note'),
                "channel": data.get('channel', 'ui'),
                "created_by": user.get('email', 'unknown') if user else 'unknown'
            },
            user.get('id') if user else None
        )
    
    db.session.commit()
    log.info(f"✅ CREATE REMINDER - Success! reminder_id={reminder.id}, tenant_id={tenant_id}")
    
    # 🔔 Dispatch push notification for new reminder
    dispatch_push_for_reminder(
        reminder_id=reminder.id,
        tenant_id=tenant_id,
        created_by=user.get('id') if user else None,
        note=reminder.note,
        lead_name=lead_name,
        lead_id=lead_id,
        reminder_type=reminder.reminder_type,
        priority=reminder.priority
    )
    
    return jsonify({
        "message": "Reminder created successfully",
        "reminder": {
            "id": reminder.id,
            "lead_id": reminder.lead_id,
            "due_at": reminder.due_at.isoformat(),
            "note": reminder.note
        }
    }), 201

@leads_bp.route("/api/reminders/<int:reminder_id>", methods=["PATCH"])
@require_api_auth()  # BUILD 137: Added missing decorator
def update_general_reminder(reminder_id):
    """Update or complete a general reminder"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Find reminder by ID and tenant_id for security
    reminder = LeadReminder.query.filter_by(id=reminder_id, tenant_id=tenant_id).first()
    if not reminder:
        return jsonify({"error": "Reminder not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    # Update allowed fields
    if 'due_at' in data:
        try:
            # 🔥 FIX: Handle both formats - with and without timezone
            due_at_str = data['due_at']
            if due_at_str.endswith('Z'):
                due_at_str = due_at_str[:-1]
            due_at = datetime.fromisoformat(due_at_str)
            # Ensure naive datetime (local Israel time)
            reminder.due_at = due_at.replace(tzinfo=None) if due_at.tzinfo else due_at
        except ValueError:
            return jsonify({"error": "Invalid due_at format. Use ISO format"}), 400
    
    if 'note' in data:
        reminder.note = data['note']
    
    if 'description' in data:
        reminder.note = data['description']  # Use note field for description
    
    if 'completed_at' in data:
        if data['completed_at']:
            # 🔥 FIX: Handle both formats - with and without timezone
            completed_str = data['completed_at']
            if completed_str.endswith('Z'):
                completed_str = completed_str[:-1]
            completed = datetime.fromisoformat(completed_str)
            reminder.completed_at = completed.replace(tzinfo=None) if completed.tzinfo else completed
        else:
            reminder.completed_at = None
        
        # Log completion only if associated with a lead and being marked complete
        if reminder.lead_id and data['completed_at']:
            user = get_current_user()
            create_activity(
                reminder.lead_id,
                "reminder_completed",
                {
                    "reminder_id": reminder_id,
                    "note": reminder.note,
                    "completed_by": user.get('email', 'unknown') if user else 'unknown'
                },
                user.get('id') if user else None
            )
    
    if 'completed' in data and data['completed']:
        # 🔥 FIX: Use local time for completed_at
        reminder.completed_at = datetime.now()
        
        # Log completion only if associated with a lead
        if reminder.lead_id:
            user = get_current_user()
            create_activity(
                reminder.lead_id,
                "reminder_completed",
                {
                    "reminder_id": reminder_id,
                    "note": reminder.note,
                    "completed_by": user.get('email', 'unknown') if user else 'unknown'
                },
                user.get('id') if user else None
            )
    
    db.session.commit()
    
    return jsonify({"message": "Reminder updated successfully"})

@leads_bp.route("/api/reminders/<int:reminder_id>", methods=["DELETE"])
@require_api_auth()  # BUILD 137: Added missing decorator
def delete_general_reminder(reminder_id):
    """Delete a general reminder"""
    # BUILD 137: Authentication handled by @require_api_auth() decorator
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Find reminder by ID and tenant_id for security
    reminder = LeadReminder.query.filter_by(id=reminder_id, tenant_id=tenant_id).first()
    if not reminder:
        return jsonify({"error": "Reminder not found"}), 404
    
    db.session.delete(reminder)
    db.session.commit()
    
    return jsonify({"message": "Reminder deleted successfully"})


# === LEAD NOTES API ===
# BUILD 172: Permanent notes with edit/delete and file attachments

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit

@leads_bp.route("/api/leads/<int:lead_id>/notes", methods=["GET"])
@require_api_auth()
@require_page_access('crm_leads')
def get_lead_notes(lead_id):
    """Get all notes for a lead - includes manual notes, call summaries, and system notes"""
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    notes = LeadNote.query.filter_by(lead_id=lead_id, tenant_id=tenant_id).order_by(
        LeadNote.created_at.desc()
    ).all()
    
    # 🔥 FIX: Return attachments from the JSON field, not from LeadAttachment table
    # The upload endpoint saves to the JSON field, so we need to read from there
    # CRM Context-Aware Support: Include note_type, call_id, and structured_data
    return jsonify({
        "success": True,
        "notes": [{
            "id": note.id,
            "content": note.content,
            "note_type": getattr(note, 'note_type', 'manual') or 'manual',
            "call_id": getattr(note, 'call_id', None),
            "structured_data": getattr(note, 'structured_data', None),
            "attachments": note.attachments or [],  # Use JSON field
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        } for note in notes]
    })


@leads_bp.route("/api/leads/<int:lead_id>/notes", methods=["POST"])
@require_api_auth()
@require_page_access('crm_leads')
def create_lead_note(lead_id):
    """Create a new note for a lead"""
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    data = request.get_json()
    # 🔥 FIX: Allow notes with just attachments (no text content required)
    # The frontend will send placeholder text if only files are attached
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    content = data.get('content', '').strip()
    if not content:
        # 🔥 FIX: content is NOT NULL, so use placeholder for file-only notes
        content = '📎 קבצים מצורפים'
    
    # Migration 75: Support note_type field for separating AI customer service notes from free notes
    note_type = data.get('note_type', 'manual')
    valid_note_types = {'manual', 'call_summary', 'system', 'customer_service_ai'}
    if note_type not in valid_note_types:
        note_type = 'manual'
    
    user = get_current_user()
    
    note = LeadNote()
    note.lead_id = lead_id
    note.tenant_id = tenant_id
    note.content = content
    note.note_type = note_type  # Migration 75: Set note type
    note.attachments = data.get('attachments', [])
    note.created_by = user.get('id') if user else None
    
    # 🔥 CRITICAL FIX: Mark JSON field as modified for SQLAlchemy
    if note.attachments:
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(note, 'attachments')
    
    try:
        db.session.add(note)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error(f"Error creating note: {e}")
        return jsonify({"error": "Failed to create note"}), 500
    
    return jsonify({
        "success": True,
        "note": {
            "id": note.id,
            "content": note.content,
            "note_type": note.note_type,  # Migration 75: Include note_type in response
            "attachments": note.attachments or [],
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
    }), 201


@leads_bp.route("/api/leads/<int:lead_id>/notes/<int:note_id>", methods=["PATCH"])
@require_api_auth()
@require_page_access('crm_leads')
def update_lead_note(lead_id, note_id):
    """Update an existing note"""
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    note = LeadNote.query.filter_by(id=note_id, lead_id=lead_id, tenant_id=tenant_id).first()
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    if 'content' in data:
        note.content = data['content'].strip()
    
    if 'attachments' in data:
        note.attachments = data['attachments']
        # 🔥 CRITICAL FIX: Mark JSON field as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(note, 'attachments')
    
    note.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error(f"Error updating note: {e}")
        return jsonify({"error": "Failed to update note"}), 500
    
    return jsonify({
        "success": True,
        "note": {
            "id": note.id,
            "content": note.content,
            "note_type": note.note_type,  # Migration 75: Include note_type in response
            "attachments": note.attachments or [],
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
    })


@leads_bp.route("/api/leads/<int:lead_id>/notes/<int:note_id>", methods=["DELETE"])
@require_api_auth()
@require_page_access('crm_leads')
def delete_lead_note(lead_id, note_id):
    """Delete a note"""
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    note = LeadNote.query.filter_by(id=note_id, lead_id=lead_id, tenant_id=tenant_id).first()
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    db.session.delete(note)
    db.session.commit()
    
    return jsonify({"success": True, "message": "Note deleted successfully"})


@leads_bp.route("/api/leads/<int:lead_id>/notes/<int:note_id>/upload", methods=["POST"])
@require_api_auth()
@require_page_access('crm_leads')
def upload_note_attachment(lead_id, note_id):
    """Upload file attachment to a note - max 10MB"""
    import base64
    import uuid
    import os
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    note = LeadNote.query.filter_by(id=note_id, lead_id=lead_id, tenant_id=tenant_id).first()
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Check file size
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to start
    
    if size > MAX_FILE_SIZE_BYTES:
        return jsonify({"error": f"File too large. Maximum size is 10MB"}), 400
    
    # Generate unique filename
    filename = file.filename or 'file'
    ext = os.path.splitext(filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    
    # Save to uploads directory
    uploads_dir = os.path.join(os.getcwd(), 'uploads', 'notes', str(tenant_id))
    os.makedirs(uploads_dir, exist_ok=True)
    
    file_path = os.path.join(uploads_dir, unique_name)
    file.save(file_path)
    
    # Determine file type
    file_type = 'image' if file.content_type and file.content_type.startswith('image/') else 'file'
    
    # Add to note attachments
    attachment = {
        "id": str(uuid.uuid4()),
        "name": file.filename,
        "url": f"/uploads/notes/{tenant_id}/{unique_name}",
        "type": file_type,
        "size": size
    }
    
    attachments = note.attachments or []
    attachments.append(attachment)
    note.attachments = attachments
    note.updated_at = datetime.utcnow()
    
    # 🔥 CRITICAL FIX: Mark JSON field as modified for SQLAlchemy to detect changes
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(note, 'attachments')
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "attachment": attachment
    })


@leads_bp.route("/api/leads/<int:lead_id>/notes/<int:note_id>/attachments/<attachment_id>", methods=["DELETE"])
@require_api_auth()
@require_page_access('crm_leads')
def delete_note_attachment(lead_id, note_id, attachment_id):
    """
    Delete a file attachment from a note
    - Removes attachment from note.attachments JSON field
    - Deletes file from storage
    - Validates tenant access
    """
    import os
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Get note and verify tenant access
    note = LeadNote.query.filter_by(id=note_id, lead_id=lead_id, tenant_id=tenant_id).first()
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    # Find attachment in JSON field by ID (UUID)
    attachments = note.attachments or []
    attachment_to_delete = None
    new_attachments = []
    
    for att in attachments:
        if str(att.get('id')) == str(attachment_id):
            attachment_to_delete = att
        else:
            new_attachments.append(att)
    
    if not attachment_to_delete:
        return jsonify({"error": "Attachment not found"}), 404
    
    # Delete file from storage if it exists
    url = attachment_to_delete.get('url', '')
    if url.startswith('/uploads/notes/'):
        # Extract file path from URL
        # URL format: /uploads/notes/{tenant_id}/{filename}
        file_path = os.path.join(os.getcwd(), url.lstrip('/'))
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                log.info(f"Deleted note attachment file: {file_path}")
            except Exception as e:
                log.error(f"Error deleting file {file_path}: {e}")
                # Continue with DB update even if file deletion fails
    
    # Update note with remaining attachments
    note.attachments = new_attachments
    note.updated_at = datetime.utcnow()
    
    # Mark JSON field as modified for SQLAlchemy
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(note, 'attachments')
    
    try:
        db.session.commit()
        return jsonify({"success": True, "message": "Attachment deleted successfully"})
    except Exception as e:
        db.session.rollback()
        log.error(f"Error deleting note attachment from database: {e}")
        return jsonify({"error": "Failed to delete attachment"}), 500


# ============================================================================
# ATTACHMENT ENDPOINTS - Production-ready file uploads for leads
# ============================================================================

ALLOWED_EXTENSIONS = {
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',  # Images & PDFs
    'mp3', 'wav', 'ogg', 'm4a', 'aac',  # Audio
    'mp4', 'avi', 'mov', 'webm',  # Video
    'txt', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',  # Documents
    'zip', 'rar', '7z'  # Archives
}

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal attacks"""
    # Use werkzeug's secure_filename and add additional sanitization
    safe_name = secure_filename(filename)
    # Remove any remaining path separators
    safe_name = safe_name.replace('/', '').replace('\\', '')
    # Limit length
    if len(safe_name) > 255:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:255-len(ext)] + ext
    return safe_name


@leads_bp.route("/api/leads/<int:lead_id>/attachments", methods=["POST"])
@require_api_auth()
@require_page_access('crm_leads')
def upload_lead_attachment(lead_id):
    """
    Upload file attachment for a lead
    - Validates tenant access
    - Stores file in tenant-isolated directory
    - Creates database record
    - Returns attachment metadata with download URL
    """
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Verify lead belongs to tenant
    lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    # Check file in request
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Validate file extension
    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
    
    # Check file size
    file.seek(0, 2)  # Seek to end
    size_bytes = file.tell()
    file.seek(0)  # Reset to start
    
    if size_bytes > MAX_ATTACHMENT_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {MAX_ATTACHMENT_SIZE // (1024*1024)}MB"}), 400
    
    # Sanitize and generate unique filename
    original_filename = sanitize_filename(file.filename)
    file_ext = os.path.splitext(original_filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    
    # Create tenant-isolated storage path
    storage_dir = os.path.join(os.getcwd(), 'data', 'tenants', str(tenant_id), 'leads', str(lead_id))
    os.makedirs(storage_dir, exist_ok=True)
    
    # Full file path
    file_path = os.path.join(storage_dir, unique_filename)
    storage_key = os.path.join('tenants', str(tenant_id), 'leads', str(lead_id), unique_filename)
    
    try:
        # Save file
        file.save(file_path)
        
        # Get current user
        user = get_current_user()
        user_id = user.get('id') if user else None
        
        # Create database record
        attachment = LeadAttachment()
        attachment.tenant_id = tenant_id
        attachment.lead_id = lead_id
        attachment.filename = original_filename
        attachment.content_type = file.content_type or 'application/octet-stream'
        attachment.size_bytes = size_bytes
        attachment.storage_key = storage_key
        attachment.created_by = user_id
        
        db.session.add(attachment)
        db.session.commit()
        
        return jsonify({
            "id": attachment.id,
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
            "download_url": f"/api/attachments/{attachment.id}/download",
            "created_at": attachment.created_at.isoformat() if attachment.created_at else None
        }), 201
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error uploading attachment: {e}")
        # Clean up file if database insert failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        return jsonify({"error": "Failed to upload file"}), 500


@leads_bp.route("/api/attachments/<int:attachment_id>/download", methods=["GET"])
@require_api_auth()
@require_page_access('crm_leads')
def download_attachment(attachment_id):
    """
    Download or preview an attachment
    - Validates tenant access
    - Supports both inline (preview) and attachment (download) modes
    - Query param ?download=1 forces download
    """
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Get attachment and verify tenant access
    attachment = LeadAttachment.query.filter_by(id=attachment_id, tenant_id=tenant_id).first()
    if not attachment:
        return jsonify({"error": "Attachment not found or access denied"}), 404
    
    # Build file path
    file_path = os.path.join(os.getcwd(), 'data', attachment.storage_key)
    
    # Check if file exists
    if not os.path.exists(file_path):
        log.error(f"Attachment file not found: {file_path}")
        return jsonify({"error": "File not found on server"}), 404
    
    # Determine if download or inline
    as_attachment = request.args.get('download', '0') == '1'
    
    try:
        return send_file(
            file_path,
            mimetype=attachment.content_type,
            as_attachment=as_attachment,
            download_name=attachment.filename
        )
    except Exception as e:
        log.error(f"Error serving attachment {attachment_id}: {e}")
        return jsonify({"error": "Failed to serve file"}), 500


@leads_bp.route("/api/attachments/<int:attachment_id>", methods=["DELETE"])
@require_api_auth()
@require_page_access('crm_leads')
def delete_attachment(attachment_id):
    """
    Delete an attachment
    - Removes from database
    - Removes file from storage
    - Validates tenant access
    """
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Get attachment and verify tenant access
    attachment = LeadAttachment.query.filter_by(id=attachment_id, tenant_id=tenant_id).first()
    if not attachment:
        return jsonify({"error": "Attachment not found or access denied"}), 404
    
    # Build file path
    file_path = os.path.join(os.getcwd(), 'data', attachment.storage_key)
    
    # Delete file from storage
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            log.info(f"Deleted attachment file: {file_path}")
        except Exception as e:
            log.error(f"Error deleting file {file_path}: {e}")
            # Continue with DB deletion even if file deletion fails
    
    # Delete from database
    try:
        db.session.delete(attachment)
        db.session.commit()
        return jsonify({"success": True, "message": "Attachment deleted successfully"})
    except Exception as e:
        db.session.rollback()
        log.error(f"Error deleting attachment from database: {e}")
        return jsonify({"error": "Failed to delete attachment"}), 500


@leads_bp.route("/api/leads/select-ids", methods=["POST"])
@require_api_auth()
@require_page_access('crm_leads')
def select_lead_ids():
    """
    Get lead IDs based on filter criteria (for bulk selection across pagination)
    
    Request body:
    {
        "statuses": ["no_answer_1", "no_answer_2", "no_answer_3"],
        "search": "",
        "tab": "system|active|imported",
        "source": "phone|whatsapp",
        "direction": "inbound|outbound"
    }
    
    Response:
    {
        "lead_ids": [1, 2, 3, ...],
        "count": 3
    }
    """
    try:
        user = get_current_user()
        is_system_admin = user.get('role') == 'system_admin' if user else False
        
        # BUILD 135: ONLY system_admin can see ALL leads
        if is_system_admin:
            query = Lead.query
        else:
            tenant_id = get_current_tenant()
            if not tenant_id:
                return jsonify({"error": "No tenant access"}), 403
            query = Lead.query.filter_by(tenant_id=tenant_id)
        
        # Parse request body
        data = request.get_json() or {}
        statuses_filter = data.get('statuses', [])
        search_query = data.get('search', '')
        tab = data.get('tab', 'system')
        source_filter = data.get('source', '')
        direction_filter = data.get('direction', '')
        
        # Apply status filter
        if statuses_filter:
            query = query.filter(func.lower(Lead.status).in_([s.lower() for s in statuses_filter]))
        
        # Apply tab-specific filters
        if tab == 'active':
            # Active outbound leads
            query = query.filter(Lead.last_call_direction == 'outbound')
        elif tab == 'imported':
            # Imported leads (leads with outbound_list_id)
            query = query.filter(Lead.outbound_list_id.isnot(None))
        # 'system' tab has no additional filter
        
        # Apply source filter
        if source_filter:
            if source_filter == 'phone':
                phone_sources = ['call', 'phone', 'phone_call', 'realtime_phone', 'ai_agent', 'form', 'manual']
                query = query.filter(Lead.source.in_(phone_sources))
            elif source_filter == 'whatsapp':
                whatsapp_sources = ['whatsapp', 'wa', 'whats_app']
                query = query.filter(Lead.source.in_(whatsapp_sources))
        
        # Apply direction filter
        if direction_filter and direction_filter != 'all':
            query = query.filter(Lead.last_call_direction == direction_filter)
        
        # Apply search filter
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                or_(
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term),
                    Lead.phone_e164.ilike(search_term)
                )
            )
        
        # Get only IDs (efficient query)
        lead_ids = [lead_id for (lead_id,) in query.with_entities(Lead.id).all()]
        
        return jsonify({
            "lead_ids": lead_ids,
            "count": len(lead_ids)
        })
    except Exception as e:
        log.error(f"❌ Error in select_lead_ids: {e}")


@leads_bp.route("/api/leads/export", methods=["GET"])
@require_api_auth()
@require_page_access('crm_leads')
def export_leads():
    """
    Export leads to CSV with comprehensive filtering support
    
    Supports all the same filters as list_leads:
    - status: Single status filter
    - statuses[]: Multiple status filter
    - source: Source filter (phone/whatsapp)
    - owner: Owner user ID
    - outbound_list_id: Import list ID
    - direction: Call direction (inbound/outbound/all)
    - q: Search query (name/phone)
    - from: Start date (ISO format)
    - to: End date (ISO format)
    
    Returns:
    CSV file with all lead data including status, source, owner, etc.
    """
    from flask import Response
    import csv
    import io
    
    try:
        user = get_current_user()
        is_system_admin = user.get('role') == 'system_admin' if user else False
        
        # BUILD 135: ONLY system_admin can see ALL leads
        if is_system_admin:
            # System admin sees all leads across all businesses
            query = Lead.query
            tenant_id = None
        else:
            # BUILD 135: owner/admin/agent see only their tenant's leads
            tenant_id = get_current_tenant()
            if not tenant_id:
                return jsonify({"error": "No tenant access"}), 403
            query = Lead.query.filter_by(tenant_id=tenant_id)
        
        # Parse query parameters (same as list_leads)
        status_filter = request.args.get('status', '')
        statuses_filter = request.args.getlist('statuses[]')
        source_filter = request.args.get('source', '')
        owner_filter = request.args.get('owner', '')
        outbound_list_id = request.args.get('outbound_list_id', '')
        direction_filter = request.args.get('direction', '')
        q_filter = request.args.get('q', '')
        from_date = request.args.get('from', '')
        to_date = request.args.get('to', '')
        
        # Apply filters (same logic as list_leads)
        if statuses_filter:
            query = query.filter(func.lower(Lead.status).in_([s.lower() for s in statuses_filter]))
        elif status_filter:
            query = query.filter(func.lower(Lead.status) == status_filter.lower())
        
        if source_filter:
            if source_filter == 'phone':
                phone_sources = ['call', 'phone', 'phone_call', 'realtime_phone', 'ai_agent', 'form', 'manual']
                query = query.filter(Lead.source.in_(phone_sources))
            elif source_filter == 'whatsapp':
                whatsapp_sources = ['whatsapp', 'wa', 'whats_app']
                query = query.filter(Lead.source.in_(whatsapp_sources))
        
        if owner_filter:
            query = query.filter(Lead.owner_user_id == owner_filter)
        
        if outbound_list_id:
            query = query.filter(Lead.outbound_list_id == int(outbound_list_id))
        
        if direction_filter and direction_filter != 'all':
            query = query.filter(Lead.last_call_direction == direction_filter)
        
        if q_filter:
            search_term = f"%{q_filter}%"
            query = query.filter(
                or_(
                    Lead.first_name.ilike(search_term),
                    Lead.last_name.ilike(search_term),
                    Lead.phone_e164.ilike(search_term)
                )
            )
        
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                query = query.filter(Lead.created_at >= from_dt)
            except ValueError:
                pass
        
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                query = query.filter(Lead.created_at <= to_dt)
            except ValueError:
                pass
        
        # Order by created_at DESC
        query = query.order_by(Lead.created_at.desc())
        
        # Fetch all leads (no pagination for export)
        leads = query.all()
        
        # 🔥 FIX: Load status labels from LeadStatus table (Hebrew labels)
        # Build a mapping of status name -> Hebrew label for this business
        from server.models_sql import LeadStatus, OutboundLeadList
        
        status_labels = {}
        if tenant_id:
            # Get all statuses for this business
            business_statuses = LeadStatus.query.filter_by(
                business_id=tenant_id,
                is_active=True
            ).all()
            for s in business_statuses:
                status_labels[s.name.lower()] = s.label
        
        # Fallback labels for standard statuses (if not in DB)
        fallback_labels = {
            'new': 'חדש',
            'attempting': 'מנסה ליצור קשר',
            'contacted': 'יצרנו קשר',
            'qualified': 'מתאים',
            'won': 'נצחנו',
            'lost': 'איבדנו',
            'unqualified': 'לא מתאים',
        }
        
        # 🔥 FIX: Load outbound list names (not just IDs)
        list_names = {}
        if tenant_id:
            lists = OutboundLeadList.query.filter_by(tenant_id=tenant_id).all()
            for lst in lists:
                list_names[lst.id] = lst.name
        
        # Create CSV in memory
        output = io.StringIO()
        
        # Use UTF-8 with BOM for Excel Hebrew compatibility
        writer = csv.writer(output)
        
        # 🔥 FIX: Write Hebrew headers matching UI
        writer.writerow([
            'מזהה',  # id
            'שם מלא',  # full_name
            'שם פרטי',  # first_name
            'שם משפחה',  # last_name
            'טלפון',  # phone
            'אימייל',  # email
            'סטטוס',  # status (Hebrew label)
            'מקור',  # source
            'אחראי',  # owner_user_id
            'רשימת ייבוא',  # outbound_list_name (not ID)
            'כיוון שיחה',  # last_call_direction
            'סיכום',  # summary
            'תגיות',  # tags
            'תאריך יצירה',  # created_at
            'תאריך עדכון',  # updated_at
            'מועד שיחה אחרונה'  # last_contact_at
        ])
        
        # Write lead rows
        for lead in leads:
            # 🔥 FIX: Get Hebrew status label
            status_internal = (lead.status or '').lower()
            status_display = status_labels.get(status_internal) or fallback_labels.get(status_internal) or lead.status or ''
            
            # 🔥 FIX: Get outbound list name (not just ID)
            list_name = ''
            if lead.outbound_list_id:
                list_name = list_names.get(lead.outbound_list_id, f'רשימה {lead.outbound_list_id}')
            
            # 🔥 FIX: Format dates in Hebrew-friendly format (DD/MM/YYYY HH:MM)
            def format_date(dt):
                if not dt:
                    return ''
                try:
                    return dt.strftime('%d/%m/%Y %H:%M')
                except:
                    return dt.isoformat() if dt else ''
            
            writer.writerow([
                lead.id,
                lead.full_name or '',
                lead.first_name or '',
                lead.last_name or '',
                lead.phone_e164 or '',
                lead.email or '',
                status_display,  # 🔥 FIX: Hebrew label instead of internal enum
                normalize_source(lead.source),
                lead.owner_user_id or '',
                list_name,  # 🔥 FIX: List name instead of ID
                lead.last_call_direction or '',
                lead.summary or '',
                ','.join(lead.tags or []),
                format_date(lead.created_at),
                format_date(lead.updated_at),
                format_date(lead.last_contact_at)
            ])
        
        # Get CSV content with UTF-8 BOM
        csv_content = '\ufeff' + output.getvalue()
        output.close()
        
        # Generate filename
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"leads_export_{today}.csv"
        
        log.info(f"📊 Exporting {len(leads)} leads for tenant {tenant_id} (filters: status={status_filter}, source={source_filter}, list={outbound_list_id})")
        
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
        log.error(f"Error exporting leads: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"שגיאה בייצוא: {str(e)}"}), 500

@leads_bp.route("/api/webhooks/status/dispatch", methods=["POST"])
@require_api_auth()
@require_page_access('crm_leads')
def dispatch_status_webhook():
    """
    Manually dispatch status webhook for a lead
    
    Used by frontend when user confirms they want to send webhook
    after status change.
    
    Request body:
    {
        "lead_id": 123,
        "old_status": "new",
        "new_status": "contacted",
        "source": "lead_page"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        lead_id = data.get('lead_id')
        old_status = data.get('old_status', '')
        new_status = data.get('new_status')
        source = data.get('source', 'manual')
        
        if not lead_id or not new_status:
            return jsonify({"error": "lead_id and new_status are required"}), 400
        
        # Get lead to verify access and get tenant_id
        lead = Lead.query.filter_by(id=lead_id).first()
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        
        # Check access
        user = get_current_user()
        tenant_id = get_current_tenant()
        
        # Verify user has access to this lead
        if not user.get('role') == 'system_admin' and lead.tenant_id != tenant_id:
            return jsonify({"error": "Access denied"}), 403
        
        # Dispatch webhook
        success = dispatch_lead_status_webhook(
            business_id=lead.tenant_id,
            lead_id=lead_id,
            old_status=old_status,
            new_status=new_status,
            source=source,
            user_id=user.get('id') if user else None
        )
        
        if success:
            return jsonify({"message": "Webhook dispatched successfully", "success": True})
        else:
            return jsonify({"message": "Webhook dispatch failed (check logs)", "success": False}), 500
            
    except Exception as e:
        log.error(f"Error dispatching status webhook: {e}")
        return jsonify({"error": str(e)}), 500


# ============== NEW: Lead Contracts Endpoints ==============

@leads_bp.route("/api/leads/<int:lead_id>/contracts", methods=["GET"])
@require_api_auth()
@require_page_access('crm_leads')
def get_lead_contracts(lead_id):
    """
    Get all contracts for a specific lead
    Returns contract list with status and basic info
    """
    try:
        tenant_id = get_current_tenant()
        if not tenant_id:
            return jsonify({"error": "No tenant access"}), 403
        
        # Verify lead belongs to tenant
        lead = Lead.query.filter_by(id=lead_id, tenant_id=tenant_id).first()
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        
        # Get contracts for this lead
        contracts = Contract.query.filter_by(
            lead_id=lead_id,
            business_id=tenant_id
        ).order_by(Contract.created_at.desc()).all()
        
        contracts_data = []
        for contract in contracts:
            contracts_data.append({
                'id': contract.id,
                'title': contract.title,
                'status': contract.status,
                'signer_name': contract.signer_name,
                'signer_phone': contract.signer_phone,
                'signer_email': contract.signer_email,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'signed_at': contract.signed_at.isoformat() if contract.signed_at else None
            })
        
        return jsonify({
            "success": True,
            "contracts": contracts_data
        })
        
    except Exception as e:
        log.error(f"Error fetching lead contracts: {e}")
        return jsonify({"error": str(e)}), 500
