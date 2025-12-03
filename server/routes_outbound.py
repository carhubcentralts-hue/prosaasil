"""
BUILD 174: Outbound Calls API Routes
שיחות יוצאות - API להתחלת שיחות AI יוצאות ללידים

Endpoints:
- POST /api/outbound_calls/start - Start outbound calls to leads
- GET /api/outbound_calls/templates - Get outbound call templates
- GET /api/outbound_calls/counts - Get current active call counts
"""
import os
import logging
from flask import Blueprint, jsonify, request, g
from server.models_sql import db, CallLog, Lead, Business, OutboundCallTemplate, BusinessSettings
from server.auth_api import require_api_auth
from server.services.call_limiter import check_call_limits, get_call_counts, MAX_TOTAL_CALLS_PER_BUSINESS, MAX_OUTBOUND_CALLS_PER_BUSINESS
from twilio.rest import Client

log = logging.getLogger(__name__)

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
    
    settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
    if settings and settings.phone_number:
        return settings.phone_number
    
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
            
            try:
                call_log = CallLog()
                call_log.business_id = tenant_id
                call_log.lead_id = lead.id
                call_log.from_number = from_phone
                call_log.to_number = lead.phone_e164
                call_log.direction = "outbound"
                call_log.status = "initiated"
                call_log.call_status = "initiated"
                db.session.add(call_log)
                db.session.flush()
                
                lead_name = lead.full_name or "לקוח"
                
                webhook_url = f"https://{host}/webhook/outbound_call"
                webhook_url += f"?call_id={call_log.id}"
                webhook_url += f"&lead_id={lead.id}"
                webhook_url += f"&lead_name={lead_name}"
                webhook_url += f"&business_id={tenant_id}"
                webhook_url += f"&business_name={business_name}"
                
                client = get_twilio_client()
                
                twilio_call = client.calls.create(
                    to=lead.phone_e164,
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
