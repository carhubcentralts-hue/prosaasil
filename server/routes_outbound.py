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
from urllib.parse import quote  # 🔧 BUILD 177: URL encode Hebrew characters
from flask import Blueprint, jsonify, request, g
from server.models_sql import db, CallLog, Lead, Business, OutboundCallTemplate, BusinessSettings
from server.auth_api import require_api_auth
from server.services.call_limiter import check_call_limits, get_call_counts, MAX_TOTAL_CALLS_PER_BUSINESS, MAX_OUTBOUND_CALLS_PER_BUSINESS
from twilio.rest import Client

log = logging.getLogger(__name__)


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


def get_twilio_client():
    """Get Twilio REST client"""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        raise ValueError("Missing Twilio credentials")
    
    return Client(account_sid, auth_token)


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
    """Get public host for webhook URLs"""
    public_host = os.environ.get('PUBLIC_HOST', '').replace('https://', '').replace('http://', '').rstrip('/')
    if public_host:
        return public_host
    
    return os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 'localhost'


@outbound_bp.route("/api/outbound_calls/templates", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
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


@outbound_bp.route("/api/outbound_calls/start", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def start_outbound_calls():
    """
    Start outbound AI calls to selected leads.
    Uses outbound_ai_prompt from business settings.
    
    Request body:
    {
        "lead_ids": [123, 456, 789]  // 1-3 leads
    }
    
    Returns:
    {
        "success": true,
        "calls": [
            {"lead_id": 123, "call_sid": "CA...", "status": "initiated"},
            ...
        ]
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
    
    if not lead_ids or not isinstance(lead_ids, list):
        return jsonify({"error": "יש לבחור לפחות ליד אחד"}), 400
    
    if len(lead_ids) > 3:
        return jsonify({"error": "ניתן לבחור עד שלושה לידים לשיחות יוצאות במקביל"}), 400
    
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
                db.session.add(call_log)
                db.session.flush()
                
                lead_name = lead.full_name or "לקוח"
                
                # 🔧 BUILD 177: URL-encode Hebrew characters to prevent Twilio 400 errors
                webhook_url = f"https://{host}/webhook/outbound_call"
                webhook_url += f"?call_id={call_log.id}"
                webhook_url += f"&lead_id={lead.id}"
                webhook_url += f"&lead_name={quote(lead_name, safe='')}"
                webhook_url += f"&business_id={tenant_id}"
                webhook_url += f"&business_name={quote(business_name, safe='')}"
                
                client = get_twilio_client()
                
                twilio_call = client.calls.create(
                    to=normalized_phone,  # Use normalized phone
                    from_=from_phone,
                    url=webhook_url,
                    status_callback=f"https://{host}/webhook/call_status",
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    record=True
                )
                
                call_log.call_sid = twilio_call.sid
                call_log.status = "ringing"
                call_log.call_status = "ringing"
                db.session.commit()
                
                log.info(f"📞 Outbound call started: lead={lead.id}, call_sid={twilio_call.sid}")
                
                results.append({
                    "lead_id": lead.id,
                    "lead_name": lead_name,
                    "call_sid": twilio_call.sid,
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


@outbound_bp.route("/api/outbound_calls/templates", methods=["POST"])
@require_api_auth(['system_admin', 'owner', 'admin'])
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
def import_outbound_leads():
    """
    BUILD 182: Import leads from CSV for outbound calls
    
    Accepts CSV file with columns: name, phone, city (optional), notes (optional)
    Maximum 5000 leads per business total.
    
    Returns:
    {
        "success": true,
        "list_id": 123,
        "imported_count": 50,
        "skipped_count": 2,
        "errors": ["שורה 3: טלפון לא תקין"]
    }
    """
    import csv
    import io
    from datetime import datetime
    from flask import session
    from server.models_sql import OutboundLeadList
    
    tenant_id = g.get('tenant')
    
    if not tenant_id:
        user = session.get('user', {})
        if user.get('role') == 'system_admin':
            return jsonify({"error": "יש לבחור עסק לפני ייבוא לידים"}), 400
        return jsonify({"error": "אין גישה לעסק"}), 403
    
    # Check file upload
    if 'file' not in request.files:
        return jsonify({"error": "לא נבחר קובץ"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "לא נבחר קובץ"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "יש להעלות קובץ CSV בלבד"}), 400
    
    try:
        # Count existing imported leads for this business
        existing_count = Lead.query.filter_by(
            tenant_id=tenant_id,
            source="imported_outbound"
        ).count()
        
        # Read and parse CSV
        content = file.read().decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(content))
        
        # Normalize column names (support Hebrew and English)
        column_map = {
            'name': ['name', 'שם', 'full_name', 'שם מלא'],
            'phone': ['phone', 'טלפון', 'phone_number', 'מספר טלפון', 'נייד'],
            'city': ['city', 'עיר', 'address', 'כתובת'],
            'notes': ['notes', 'הערות', 'comments', 'הערה']
        }
        
        def get_column_value(row, target_col):
            """Get value for a column, checking various column name variants"""
            for col_variant in column_map.get(target_col, [target_col]):
                for key in row.keys():
                    if key.strip().lower() == col_variant.lower():
                        return row[key].strip() if row[key] else None
            return None
        
        rows_to_import = []
        errors = []
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            name = get_column_value(row, 'name')
            phone = get_column_value(row, 'phone')
            city = get_column_value(row, 'city')
            notes = get_column_value(row, 'notes')
            
            # Validate required fields
            if not name:
                errors.append(f"שורה {row_num}: חסר שם")
                continue
            
            if not phone:
                errors.append(f"שורה {row_num}: חסר טלפון")
                continue
            
            # Normalize phone number
            normalized_phone = normalize_israeli_phone(phone)
            
            # Basic phone validation
            if not normalized_phone or len(normalized_phone) < 10:
                errors.append(f"שורה {row_num}: טלפון לא תקין - {phone}")
                continue
            
            rows_to_import.append({
                'name': name,
                'phone': normalized_phone,
                'city': city,
                'notes': notes
            })
        
        # Check 5000 limit
        if existing_count + len(rows_to_import) > MAX_IMPORTED_LEADS_PER_BUSINESS:
            available = MAX_IMPORTED_LEADS_PER_BUSINESS - existing_count
            return jsonify({
                "error": f"לא ניתן לייבא יותר מ-{MAX_IMPORTED_LEADS_PER_BUSINESS} לידים ברשימת השיחות היוצאות. יש לך מקום ל-{available} לידים נוספים."
            }), 400
        
        if len(rows_to_import) == 0:
            return jsonify({
                "error": "לא נמצאו לידים תקינים לייבוא",
                "errors": errors
            }), 400
        
        # Create the import list
        list_name = request.form.get('list_name') or f"ייבוא {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        outbound_list = OutboundLeadList()
        outbound_list.tenant_id = tenant_id
        outbound_list.name = list_name
        outbound_list.file_name = file.filename
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
            "errors": errors[:20]  # Limit error messages
        })
        
    except Exception as e:
        log.error(f"Error importing leads: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"שגיאה בייבוא הלידים: {str(e)}"}), 500


@outbound_bp.route("/api/outbound/import-leads", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_imported_leads():
    """
    BUILD 182: Get imported leads for outbound calls
    
    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    - list_id: Optional filter by list ID
    - search: Optional search query
    
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
        page_size = min(100, max(1, int(request.args.get('page_size', 50))))
        list_id = request.args.get('list_id', type=int)
        search = request.args.get('search', '').strip()
        
        # Build query
        query = Lead.query.filter_by(
            tenant_id=tenant_id,
            source="imported_outbound"
        )
        
        if list_id:
            query = query.filter_by(outbound_list_id=list_id)
        
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
def bulk_delete_imported_leads():
    """
    BUILD 182: Bulk delete imported leads
    
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
    
    try:
        if data.get('delete_all'):
            # Delete all imported leads for this business
            deleted = Lead.query.filter_by(
                tenant_id=tenant_id,
                source="imported_outbound"
            ).delete()
            db.session.commit()
            
            log.info(f"🗑️ Bulk deleted {deleted} imported leads for business {tenant_id}")
            
            return jsonify({
                "success": True,
                "deleted_count": deleted,
                "message": f"נמחקו {deleted} לידים"
            })
        
        lead_ids = data.get('lead_ids', [])
        if not lead_ids:
            return jsonify({"error": "לא נבחרו לידים למחיקה"}), 400
        
        # Only delete imported leads
        deleted = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.tenant_id == tenant_id,
            Lead.source == "imported_outbound"
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        log.info(f"🗑️ Bulk deleted {deleted} imported leads for business {tenant_id}")
        
        return jsonify({
            "success": True,
            "deleted_count": deleted,
            "message": f"נמחקו {deleted} לידים"
        })
        
    except Exception as e:
        log.error(f"Error bulk deleting imported leads: {e}")
        db.session.rollback()
        return jsonify({"error": "שגיאה במחיקת הלידים"}), 500


@outbound_bp.route("/api/outbound/import-lists", methods=["GET"])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
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
