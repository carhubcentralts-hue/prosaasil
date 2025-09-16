"""
Leads CRM API routes - Monday/HubSpot/Salesforce style
Modern lead management with Kanban board support, reminders, and activity tracking
"""
from flask import Blueprint, jsonify, request, session, g
from server.models_sql import Lead, LeadActivity, LeadReminder, LeadMergeCandidate, User, Business
from server.db import db
from datetime import datetime, timezone
from sqlalchemy import or_, and_, func, desc
from sqlalchemy.orm import joinedload
import logging

log = logging.getLogger(__name__)

leads_bp = Blueprint("leads_bp", __name__)

def get_current_user():
    """Get current user from session - consistent with auth system"""
    return session.get('al_user')

def get_current_tenant():
    """Get current tenant based on impersonation or user business"""
    user = get_current_user()
    if not user:
        return None
        
    # Check if impersonating
    if session.get('impersonating') and session.get('impersonated_tenant_id'):
        return session.get('impersonated_tenant_id')
    
    # Return user's business
    return user.get('business_id')

def require_auth():
    """Require authentication for API access"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    return None

def check_lead_access(lead_id):
    """Check if current user can access lead"""
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
    
    # Default Hebrew real estate statuses - ALWAYS lowercase canonical names
    default_statuses = [
        {'name': 'new', 'label': 'חדש', 'color': 'bg-blue-100 text-blue-800', 'is_default': True},
        {'name': 'attempting', 'label': 'בניסיון קשר', 'color': 'bg-yellow-100 text-yellow-800'},
        {'name': 'contacted', 'label': 'נוצר קשר', 'color': 'bg-purple-100 text-purple-800'},
        {'name': 'qualified', 'label': 'מוכשר', 'color': 'bg-green-100 text-green-800'},
        {'name': 'won', 'label': 'זכיה', 'color': 'bg-emerald-100 text-emerald-800', 'is_system': True},
        {'name': 'lost', 'label': 'אובדן', 'color': 'bg-red-100 text-red-800', 'is_system': True},
        {'name': 'unqualified', 'label': 'לא מוכשר', 'color': 'bg-gray-100 text-gray-800', 'is_system': True}
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
def list_leads():
    """List leads with filtering and pagination"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    # Parse query parameters
    status_filter = request.args.get('status', '')
    source_filter = request.args.get('source', '')
    owner_filter = request.args.get('owner', '')
    q_filter = request.args.get('q', '')  # Search query
    from_date = request.args.get('from', '')
    to_date = request.args.get('to', '')
    page = int(request.args.get('page', 1))
    page_size = min(int(request.args.get('pageSize', 50)), 100)  # Max 100 per page
    
    # Build query
    query = Lead.query.filter_by(tenant_id=tenant_id)
    
    # Apply filters
    if status_filter:
        # ✅ FIXED: Case-insensitive status filtering for legacy compatibility
        query = query.filter(func.lower(Lead.status) == status_filter.lower())
    
    if source_filter:
        query = query.filter(Lead.source == source_filter)
    
    if owner_filter:
        query = query.filter(Lead.owner_user_id == owner_filter)
    
    if q_filter:
        # Search in name, phone, email
        search_term = f"%{q_filter}%"
        query = query.filter(
            or_(
                Lead.first_name.ilike(search_term),
                Lead.last_name.ilike(search_term),
                Lead.phone_e164.ilike(search_term),
                Lead.email.ilike(search_term)
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
    
    # Order by Kanban board: status first, then order_index within status
    query = query.order_by(Lead.status, Lead.order_index)
    
    # Pagination
    offset = (page - 1) * page_size
    total = query.count()
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
            "status": lead.status,
            "source": lead.source,
            "owner_user_id": lead.owner_user_id,
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

@leads_bp.route("/api/leads", methods=["POST"])
def create_lead():
    """Create new lead manually"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    # Validate required fields
    if not data.get('first_name') and not data.get('phone_e164'):
        return jsonify({"error": "Either first_name or phone_e164 is required"}), 400
    
    # Check for duplicates if phone provided
    if data.get('phone_e164'):
        existing = Lead.query.filter_by(
            tenant_id=tenant_id,
            phone_e164=data['phone_e164']
        ).first()
        if existing:
            return jsonify({"error": "Lead with this phone number already exists", "existing_id": existing.id}), 409
    
    # Create lead
    user = get_current_user()
    
    # ✅ FIXED: Use actual default status from database, not hardcoded 'new'
    valid_statuses = get_valid_statuses_for_business(tenant_id)
    default_status = get_default_status_for_business(tenant_id)  # Get actual default from DB
    
    # Normalize provided status to canonical lowercase
    provided_status = data.get('status')
    if provided_status:
        normalized_status = provided_status.lower().strip()
        if normalized_status in valid_statuses:
            default_status = normalized_status
        else:
            return jsonify({
                "error": f"Invalid status '{provided_status}'. Valid options: {', '.join(valid_statuses)}"
            }), 400
    
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
    
    db.session.add(lead)
    db.session.flush()  # Get ID
    
    # Create activity
    create_activity(
        lead.id,
        "lead_created",
        {
            "method": "manual",
            "created_by": user.get('email', 'unknown') if user else 'unknown'
        },
        user.get('id') if user else None
    )
    
    db.session.commit()
    
    return jsonify({
        "id": lead.id,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.full_name,
        "phone_e164": lead.phone_e164,
        "email": lead.email,
        "status": lead.status,
        "source": lead.source,
        "created_at": lead.created_at.isoformat()
    }), 201

@leads_bp.route("/api/leads/<int:lead_id>", methods=["GET"])
def get_lead_detail(lead_id):
    """Get detailed lead information with activities and reminders"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
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
    
    # Format response
    response = {
        "id": lead.id,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.full_name,
        "phone_e164": lead.phone_e164,
        "display_phone": lead.display_phone,
        "email": lead.email,
        "status": lead.status,
        "source": lead.source,
        "external_id": lead.external_id,
        "owner_user_id": lead.owner_user_id,
        "tags": lead.tags or [],
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        "last_contact_at": lead.last_contact_at.isoformat() if lead.last_contact_at else None,
        
        "reminders": [
            {
                "id": r.id,
                "due_at": r.due_at.isoformat() if r.due_at else None,
                "note": r.note,
                "channel": r.channel,
                "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None
            } for r in reminders
        ],
        
        "activity": [
            {
                "id": a.id,
                "type": a.type,
                "payload": a.payload,
                "at": a.at.isoformat() if a.at else None,
                "created_by": a.created_by
            } for a in activities
        ]
    }
    
    return jsonify(response)

@leads_bp.route("/api/leads/<int:lead_id>", methods=["PATCH"])
def update_lead(lead_id):
    """Update lead information"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    lead = Lead.query.filter_by(id=lead_id).first()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
        
    user = get_current_user()
    
    # Track changes for activity log
    changes = {}
    
    # Update allowed fields
    updateable_fields = ['first_name', 'last_name', 'phone_e164', 'email', 'owner_user_id', 'tags', 'notes']
    
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
    
    return jsonify({"message": "Lead updated successfully", "changes": changes})

@leads_bp.route("/api/leads/<int:lead_id>/status", methods=["POST"])
def update_lead_status(lead_id):
    """Update lead status (for Kanban board)"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
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
        
        return jsonify({"message": "Status updated successfully", "old_status": old_status, "new_status": new_status})
    
    return jsonify({"message": "Status unchanged"})

@leads_bp.route("/api/leads/<int:lead_id>/reminders", methods=["GET"])
def get_lead_reminders(lead_id):
    """Get all reminders for a lead"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    reminders = LeadReminder.query.filter_by(lead_id=lead_id).order_by(LeadReminder.due_at.desc()).all()
    
    return jsonify({
        "reminders": [
            {
                "id": r.id,
                "lead_id": r.lead_id,
                "due_at": r.due_at.isoformat() if r.due_at else None,
                "note": r.note,
                "channel": r.channel,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_by": r.created_by
            }
            for r in reminders
        ]
    })

@leads_bp.route("/api/leads/<int:lead_id>/activities", methods=["GET"])
def get_lead_activities(lead_id):
    """Get all activities for a lead"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
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
def create_reminder(lead_id):
    """Create 'חזור אליי' reminder"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    data = request.get_json()
    if not data or 'due_at' not in data:
        return jsonify({"error": "due_at is required"}), 400
    
    try:
        due_at = datetime.fromisoformat(data['due_at'].replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"error": "Invalid due_at format. Use ISO format"}), 400
    
    user = get_current_user()
    
    reminder = LeadReminder()
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
    
    return jsonify({
        "id": reminder.id,
        "due_at": reminder.due_at.isoformat(),
        "note": reminder.note,
        "channel": reminder.channel,
        "message": "Reminder created successfully"
    }), 201

# === ADMIN ENDPOINTS ===
# Note: Admin leads endpoint moved to routes_admin.py to avoid duplicate route conflict
# REMOVED: Duplicate /api/admin/leads route was here - now only in routes_admin.py

@leads_bp.route("/api/leads/<int:lead_id>/move", methods=["PATCH"])
def move_lead_in_kanban(lead_id):
    """Move lead position in Kanban board (drag & drop support)"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
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
def get_reminder(lead_id, reminder_id):
    """Get specific reminder details"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    reminder = LeadReminder.query.filter_by(id=reminder_id, lead_id=lead_id).first()
    if not reminder:
        return jsonify({"error": "Reminder not found"}), 404
    
    return jsonify({
        "id": reminder.id,
        "due_at": reminder.due_at.isoformat() if reminder.due_at else None,
        "note": reminder.note,
        "channel": reminder.channel,
        "delivered_at": reminder.delivered_at.isoformat() if reminder.delivered_at else None,
        "completed_at": reminder.completed_at.isoformat() if reminder.completed_at else None,
        "created_at": reminder.created_at.isoformat() if reminder.created_at else None
    })

@leads_bp.route("/api/leads/<int:lead_id>/reminders/<int:reminder_id>", methods=["PATCH"])
def update_reminder(lead_id, reminder_id):
    """Update or complete reminder"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
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
            reminder.due_at = datetime.fromisoformat(data['due_at'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({"error": "Invalid due_at format. Use ISO format"}), 400
    
    if 'note' in data:
        reminder.note = data['note']
    
    if 'completed' in data and data['completed']:
        reminder.completed_at = datetime.utcnow()
        
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


@leads_bp.route("/api/reminders/due", methods=["GET"])
def get_due_reminders():
    """Get all due and overdue reminders for notifications"""
    
    # Use existing auth pattern
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    tenant_id = get_current_tenant()
    if not tenant_id:
        return jsonify({"error": "No tenant access"}), 403

    # Get current time and filter due reminders
    now = datetime.utcnow()
    
    # Query for due reminders (not completed, due time has passed)
    due_reminders = db.session.query(LeadReminder, Lead).join(
        Lead, LeadReminder.lead_id == Lead.id
    ).filter(
        Lead.tenant_id == tenant_id,  # Business scope
        LeadReminder.completed_at.is_(None),  # Not completed
        LeadReminder.due_at <= now  # Due or overdue
    ).order_by(LeadReminder.due_at.asc()).all()

    # Build response with lead context
    reminders_data = []
    for reminder, lead in due_reminders:
        reminders_data.append({
            "id": reminder.id,
            "lead_id": reminder.lead_id,
            "lead_name": lead.full_name,
            "lead_phone": lead.display_phone,
            "due_at": reminder.due_at.isoformat(),
            "note": reminder.note,
            "channel": reminder.channel,
            "overdue_minutes": int((now - reminder.due_at).total_seconds() / 60) if reminder.due_at < now else 0,
            "created_at": reminder.created_at.isoformat()
        })

    return jsonify({
        "reminders": reminders_data,
        "total_count": len(reminders_data),
        "overdue_count": len([r for r in reminders_data if r["overdue_minutes"] > 0])
    })

@leads_bp.route("/api/leads/bulk", methods=["PATCH"])
def bulk_update_leads():
    """Bulk update multiple leads"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
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
    
    # Validate access to all leads
    leads = Lead.query.filter(
        Lead.id.in_(lead_ids),
        Lead.tenant_id == tenant_id
    ).all()
    
    if len(leads) != len(lead_ids):
        return jsonify({"error": "Some leads not found or access denied"}), 404
    
    # Apply updates
    updated_count = 0
    user = get_current_user()
    
    for lead in leads:
        changes = {}
        
        # Update allowed fields
        for field in ['status', 'owner_user_id', 'tags']:
            if field in updates:
                old_value = getattr(lead, field)
                new_value = updates[field]
                if old_value != new_value:
                    changes[field] = {"from": old_value, "to": new_value}
                    setattr(lead, field, new_value)
        
        if changes:
            lead.updated_at = datetime.utcnow()
            updated_count += 1
            
            # Log bulk update
            create_activity(
                lead.id,
                "bulk_update",
                {
                    "changes": changes,
                    "updated_by": user.get('email', 'unknown') if user else 'unknown'
                },
                user.get('id') if user else None
            )
    
    db.session.commit()
    
    return jsonify({
        "message": f"Bulk update completed: {updated_count} leads updated",
        "updated_count": updated_count,
        "total_requested": len(lead_ids)
    })

# Placeholder for WhatsApp integration - will be implemented in task 7
@leads_bp.route("/api/leads/<int:lead_id>/message/whatsapp", methods=["POST"])
def send_whatsapp_message(lead_id):
    """Send WhatsApp message to lead"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not check_lead_access(lead_id):
        return jsonify({"error": "Lead not found or access denied"}), 404
    
    # TODO: Implement WhatsApp integration in task 7
    return jsonify({"message": "WhatsApp integration coming soon"}), 501