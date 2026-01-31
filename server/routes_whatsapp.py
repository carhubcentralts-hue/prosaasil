import os, requests, logging, csv, io, json, threading
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session, g, current_app
from server.extensions import csrf
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.db import db
from server.models_sql import WhatsAppConversationState, LeadReminder, Business, User
from server.services.whatsapp_session_service import update_session_activity
from server.agent_tools.phone_utils import normalize_phone
import logging

logger = logging.getLogger(__name__)


whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/api/whatsapp')
internal_whatsapp_bp = Blueprint('internal_whatsapp', __name__, url_prefix='/api/internal/whatsapp')
BAILEYS_BASE = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
INT_SECRET   = os.getenv('INTERNAL_SECRET')
log = logging.getLogger(__name__)

# 🔥 FIX: Default fallback message for when business greeting is not available
DEFAULT_FALLBACK_MESSAGE = "תודה על הפנייה. נציג יחזור אליך בהקדם."

# BUILD 136: REMOVED hardcoded business_1 - now uses tenant_id_from_ctx() dynamically
# Helper function to get tenant-specific auth directory
def get_auth_dir(tenant_id: str) -> tuple:
    """Get auth directory paths for specific tenant"""
    auth_dir = os.path.join(os.getcwd(), "storage", "whatsapp", tenant_id, "auth")
    qr_txt = os.path.join(auth_dir, "qr_code.txt")
    creds = os.path.join(auth_dir, "creds.json")
    os.makedirs(auth_dir, exist_ok=True)  # Ensure directory exists
    return auth_dir, qr_txt, creds

def mask_secret_for_logging(secret: str) -> str:
    """
    Mask a secret for secure logging using first 7 + last 2 characters
    
    Examples:
        'wh_n8n_business_six_secret_12345' -> 'wh_n8n_...45'
        'short' -> 'sho...'
        'abc' -> '***'
        '' -> '***'
    
    This allows debugging without exposing the full secret.
    """
    if not secret:
        return "***"
    
    # For secrets longer than 9 chars: first 7 + last 2
    if len(secret) > 9:
        return secret[:7] + "..." + secret[-2:]
    # For secrets 4-9 chars: first 3 + ...
    elif len(secret) > 3:
        return secret[:3] + "..."
    # For very short secrets: just ***
    else:
        return "***"


# REMOVED: _send_whatsapp_message_background function
# This functionality has been moved to send_whatsapp_message_job in server/jobs/
# See server/jobs/send_whatsapp_message_job.py for the RQ-based implementation


def tenant_id_from_ctx():
    """
    BUILD 136: SECURE tenant resolution - only from session/auth, NO query params
    
    🔒 SECURITY: Prevents cross-tenant access by ignoring business_id query parameter
    unless the user is system_admin with explicit permission.
    """
    from flask import request, abort, session
    import logging
    log = logging.getLogger(__name__)
    
    # Get current user from session
    user = session.get('al_user', {})
    user_role = user.get('role')
    
    # BUILD 136: Only system_admin can override business_id via query params
    query_business_id = request.args.get('business_id', type=int)
    if query_business_id:
        if user_role != 'system_admin':
            log.error(f"❌ SECURITY: Non-admin user tried to access business_id={query_business_id}")
            abort(403, description="Permission denied - only system_admin can specify business_id")
        # system_admin can access any business
        business_id = query_business_id
        log.info(f"✅ system_admin accessing business_id={business_id}")
    else:
        # Get from session/auth (regular users)
        # Check for impersonation first, then get from user object
        business_id = session.get('impersonated_tenant_id') or user.get('business_id')
    
    # 🔒 SECURITY: NO FALLBACK - require explicit business context
    if not business_id:
        log.error("❌ REJECTED: Missing business_id in request context")
        abort(401, description="Business context required - please login")
    
    # Return in business_X format (as expected by Baileys)
    return f'business_{business_id}'

def _headers():
    return {'X-Internal-Secret': INT_SECRET, 'Content-Type': 'application/json'}

@whatsapp_bp.route('/status', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
@require_api_auth()  # BUILD 136: AUTHENTICATION REQUIRED - prevents cross-tenant snooping
def status():
    """
    ✅ FIX (Problem 2.1): Single source of truth for WhatsApp connection status
    
    Always check real-time status from Baileys service to ensure accurate reporting.
    Only report "connected" if Baileys confirms: connection=open AND authPaired=true AND canSend=true
    """
    try:
        # BUILD 136: Get tenant from AUTHENTICATED session (secure)
        t = tenant_id_from_ctx()
        _, qr_txt, creds = get_auth_dir(t)
        
        # 🔥 FIX (Problem 2.1): ALWAYS query Baileys for real-time status first
        # Don't rely on file existence alone - files may be stale
        try:
            r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/status", headers=_headers(), timeout=5)
            if r.status_code == 200:
                baileys_data = r.json()
                
                # ✅ FIX (Problem 2): "truly_connected" now REQUIRES canSend=True
                # If canSend=False, the connection is NOT usable and needs QR rescan
                # This fixes the issue where truly_connected=True but canSend=False (zombie state)
                is_connected = baileys_data.get("connected", False)
                is_auth_paired = baileys_data.get("authPaired", False)
                can_send = baileys_data.get("canSend", False)
                has_qr = baileys_data.get("hasQR", False)
                
                # ✅ FIX: True connection REQUIRES all three: socket + auth + canSend
                # Without canSend, the connection is NOT ready for sending messages
                truly_connected = is_connected and is_auth_paired and can_send
                
                # ✅ FIX: User needs QR rescan if:
                # 1. Not truly connected (missing canSend or auth)
                # 2. OR explicit QR available
                # 3. OR zombie state (connected + authPaired but canSend=False)
                zombie_state = is_connected and is_auth_paired and not can_send
                needs_qr = (not truly_connected) or has_qr or zombie_state
                
                health_info = {
                    "connected": truly_connected,
                    "hasQR": has_qr,
                    "qr_required": needs_qr,  # ✅ FIX: Always true when canSend=False
                    "needs_qr": needs_qr,  # ✅ FIX: UI should show "לא מחובר - צריך QR"
                    "canSend": can_send,
                    "authPaired": is_auth_paired,
                    "sessionState": baileys_data.get("sessionState", "unknown"),
                    "pushName": baileys_data.get("pushName", ""),
                    "reconnectAttempts": baileys_data.get("reconnectAttempts", 0),
                    "reason": "WA_NOT_READY_CAN_SEND_FALSE" if zombie_state else None  # ✅ FIX: Clear error reason
                }
                
                log.info(f"[WA_STATUS] tenant={t} truly_connected={truly_connected} (connected={is_connected}, authPaired={is_auth_paired}, canSend={can_send})")
                
                # Add session age if connected
                if truly_connected and os.path.exists(creds):
                    import time
                    creds_mtime = os.path.getmtime(creds)
                    session_age_seconds = int(time.time() - creds_mtime)
                    health_info["session_age"] = session_age_seconds
                    health_info["session_age_human"] = f"{session_age_seconds // 3600}h {(session_age_seconds % 3600) // 60}m"
                
                # Try to get last message timestamp from DB
                try:
                    from server.models_sql import WhatsAppMessage
                    business_id = int(t.split('_')[1]) if '_' in t else None
                    if business_id:
                        last_msg = WhatsAppMessage.query.filter_by(
                            business_id=business_id
                        ).order_by(WhatsAppMessage.created_at.desc()).first()
                        
                        if last_msg:
                            health_info["last_message_ts"] = last_msg.created_at.isoformat()
                            from datetime import datetime
                            time_since = (datetime.utcnow() - last_msg.created_at).total_seconds()
                            health_info["last_message_age"] = int(time_since)
                            health_info["last_message_age_human"] = f"{int(time_since // 60)}m ago"
                except Exception as db_err:
                    log.warning(f"[WA_STATUS] Could not fetch last message: {db_err}")
                
                return jsonify(health_info), 200
        except requests.exceptions.Timeout:
            log.warning(f"[WA_STATUS] Baileys timeout for tenant={t}")
            # Fall back to file-based check, but mark as potentially stale
            pass
        except requests.exceptions.ConnectionError:
            log.warning(f"[WA_STATUS] Baileys connection error for tenant={t}")
            # Fall back to file-based check
            pass
        except Exception as baileys_err:
            log.warning(f"[WA_STATUS] Baileys error for tenant={t}: {baileys_err}")
            # Fall back to file-based check
            pass
        
        # Fallback: File-based check (but mark as potentially stale)
        has_qr = os.path.exists(qr_txt)
        connected = os.path.exists(creds) and not has_qr
        
        health_info = {
            "connected": connected,
            "hasQR": has_qr,
            "qr_required": has_qr,
            "warning": "Baileys service unavailable - status may be stale",
            "session_age": None,
            "last_message_ts": None
        }
        
        log.warning(f"[WA_STATUS] tenant={t} using fallback file check: connected={connected} hasQR={has_qr}")
        return jsonify(health_info), 200
        
    except Exception as e:
        log.error(f"[WA_STATUS] Error: {e}")
        return jsonify({
            "connected": False,
            "hasQR": False,
            "qr_required": False,
            "error": str(e)
        }), 200

@whatsapp_bp.route('/qr', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
@require_api_auth()  # BUILD 136: AUTHENTICATION REQUIRED - prevents QR code theft
def qr():
    """BUILD 136: SECURE multi-tenant QR - each business sees only its own QR code"""
    try:
        # BUILD 136: Get tenant from AUTHENTICATED session (secure)
        t = tenant_id_from_ctx()
        _, qr_txt, _ = get_auth_dir(t)
        
        # Check file for this specific tenant ONLY
        if os.path.exists(qr_txt):
            with open(qr_txt, "r", encoding="utf-8") as f:
                qr_text = f.read().strip()
            if qr_text:
                return jsonify({"dataUrl": None, "qrText": qr_text}), 200
        
        # If no file, try Baileys API
        r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/qr", headers=_headers(), timeout=10)
        if r.status_code == 404:
            return jsonify({"dataUrl": None, "qrText": None}), 200
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"dataUrl": None, "qrText": None}), 200

@whatsapp_bp.route('/start', methods=['POST'])
@csrf.exempt
@require_api_auth()  # BUILD 168.3: Auth required to prevent unauthorized session starts
def start():
    """B4) תמיד JSON ב-/api/whatsapp/start - לפי ההוראות המדויקות
    הוא מפעיל את Baileys session אם עדיין לא רץ.
    """
    t = tenant_id_from_ctx()
    try:
        # קריאה פנימית ל-Baileys (עם INTERNAL_SECRET)
        r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/start", headers=_headers(), timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        # אם Baileys לא עונה, נחזיר OK (כי הוא כבר רץ)
        return jsonify({"ok": True}), 200

@whatsapp_bp.route('/reset', methods=['POST'])
@csrf.exempt
@require_api_auth()  # BUILD 168.3: Auth required to prevent unauthorized session resets
def reset():
    """Reset WhatsApp session for authenticated business"""
    t = tenant_id_from_ctx()
    try:
        r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/reset", headers=_headers(), timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        log.error(f"WhatsApp reset failed: {e}")
        return jsonify({"error": "Reset failed"}), 500

@whatsapp_bp.route('/disconnect', methods=['POST'])
@csrf.exempt
@require_api_auth()  # BUILD 168.3: Auth required to prevent unauthorized disconnects
def disconnect():
    """Disconnect WhatsApp session for authenticated business"""
    t = tenant_id_from_ctx()
    try:
        r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/disconnect", headers=_headers(), timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        log.error(f"WhatsApp disconnect failed: {e}")
        return jsonify({"error": "Disconnect failed"}), 500


# === BUILD 150: AI Active/Inactive Toggle for Customer Service ===

@whatsapp_bp.route('/ai-state', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def set_ai_state():
    """Toggle AI active/inactive for a specific WhatsApp conversation"""
    from server.routes_crm import get_business_id
    
    data = request.get_json() or {}
    phone = data.get('phone')
    active = data.get('active', True)
    
    if not phone:
        return jsonify({"success": False, "error": "Missing phone number"}), 400
    
    business_id = get_business_id()
    user_id = getattr(g, 'user', {}).get('id') if hasattr(g, 'user') else None
    
    try:
        # Find or create state record
        state = WhatsAppConversationState.query.filter_by(
            business_id=business_id,
            phone=phone
        ).first()
        
        if state:
            state.ai_active = active
            state.updated_by = user_id
        else:
            state = WhatsAppConversationState()
            state.business_id = business_id
            state.phone = phone
            state.ai_active = active
            state.updated_by = user_id
            db.session.add(state)
        
        db.session.commit()
        log.info(f"✅ AI state for {phone}: {'active' if active else 'inactive'} (business {business_id})")
        return jsonify({"success": True, "ai_active": active})
    except Exception as e:
        db.session.rollback()
        log.error(f"❌ Failed to set AI state: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@whatsapp_bp.route('/ai-state', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_ai_state():
    """Get AI active/inactive state for a specific WhatsApp conversation"""
    from server.routes_crm import get_business_id
    
    phone = request.args.get('phone')
    if not phone:
        return jsonify({"success": False, "error": "Missing phone number"}), 400
    
    business_id = get_business_id()
    
    state = WhatsAppConversationState.query.filter_by(
        business_id=business_id,
        phone=phone
    ).first()
    
    # Default to active if no state record exists
    ai_active = state.ai_active if state else True
    return jsonify({"success": True, "ai_active": ai_active})


# ✅ BUILD 170: Add toggle-ai endpoint for frontend compatibility
@whatsapp_bp.route('/toggle-ai', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def toggle_ai():
    """Toggle AI on/off for a specific WhatsApp conversation - frontend compatibility"""
    from server.routes_crm import get_business_id
    
    data = request.get_json() or {}
    phone_number = data.get('phone_number') or data.get('phone')
    ai_enabled = data.get('ai_enabled', True)
    
    if not phone_number:
        return jsonify({"success": False, "error": "Missing phone_number"}), 400
    
    # Normalize phone number
    phone = phone_number.replace('+', '').strip()
    
    business_id = get_business_id()
    user_id = getattr(g, 'user', {}).get('id') if hasattr(g, 'user') else None
    
    try:
        state = WhatsAppConversationState.query.filter_by(
            business_id=business_id,
            phone=phone
        ).first()
        
        if state:
            state.ai_active = ai_enabled
            state.updated_by = user_id
        else:
            state = WhatsAppConversationState()
            state.business_id = business_id
            state.phone = phone
            state.ai_active = ai_enabled
            state.updated_by = user_id
            db.session.add(state)
        
        db.session.commit()
        log.info(f"✅ AI toggled for {phone}: {'enabled' if ai_enabled else 'disabled'} (business {business_id})")
        return jsonify({"success": True, "ai_enabled": ai_enabled})
    except Exception as e:
        db.session.rollback()
        log.error(f"❌ Failed to toggle AI: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def is_ai_active_for_conversation(business_id: int, phone: str) -> bool:
    """Helper function to check if AI should respond to this conversation
    
    Used by WhatsApp message handlers to determine if AI should auto-respond.
    Returns True (AI active) by default if no state is set.
    """
    try:
        state = WhatsAppConversationState.query.filter_by(
            business_id=business_id,
            phone=phone
        ).first()
        return state.ai_active if state else True
    except Exception as e:
        log.error(f"Error checking AI state for {phone}: {e}")
        return True  # Default to active on error


# === שלב 3: JSON יציב ו-commit/rollback ===
from server.utils.api_guard import api_handler

# === שלב 1: השלמת 3 routes ש-UI מבקש (תואם ל-WhatsAppPage.jsx) ===
from server.models_sql import WhatsAppMessage, Customer
from sqlalchemy import func

@whatsapp_bp.route('/contacts', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def api_wa_contacts():
    # 🔒 SECURITY: business_id from authenticated session via get_business_id()
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    
    # Get unique WhatsApp conversations (simulating WhatsAppConversation with WhatsAppMessage)
    convs = db.session.query(
        WhatsAppMessage.to_number,
        func.max(WhatsAppMessage.created_at).label('last_message_at'),
        func.count(WhatsAppMessage.id).label('message_count')
    ).filter_by(business_id=business_id).group_by(
        WhatsAppMessage.to_number
    ).order_by(func.max(WhatsAppMessage.created_at).desc()).limit(20).all()
    
    out = []
    for c in convs:
        # Try to get customer name from Customer table
        customer = Customer.query.filter_by(business_id=business_id, phone_e164=c.to_number).first()
        customer_name = customer.name if customer else c.to_number
        
        out.append({
            "id": c.to_number,  # Use phone number as ID since no conversation table
            "customer_phone": c.to_number,
            "customer_name": customer_name,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        })
    return jsonify({"contacts": out}), 200

@whatsapp_bp.route('/messages', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def api_wa_messages():
    contact_id = request.args.get("contact_id")  # This is the phone number
    if not contact_id:
        return jsonify({"error":"missing contact_id"}), 400
    
    # 🔒 SECURITY: business_id from authenticated session via get_business_id()
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    
    msgs = WhatsAppMessage.query.filter_by(
        business_id=business_id,
        to_number=contact_id
    ).order_by(WhatsAppMessage.created_at.asc()).all()
    
    return jsonify({"messages":[{
        "id": m.id,
        "text": m.body,
        "type": m.message_type,
        "direction": m.direction,
        "ts": m.created_at.isoformat() if m.created_at else None,
        "platform": m.provider,
    } for m in msgs]}), 200


@whatsapp_bp.route('/messages/<phone_number>', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def api_wa_messages_by_phone(phone_number):
    """Get WhatsApp messages by phone number path parameter"""
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    
    clean_phone = phone_number.replace('+', '').replace('@s.whatsapp.net', '').replace('%2B', '')
    
    msgs = WhatsAppMessage.query.filter_by(
        business_id=business_id,
        to_number=clean_phone
    ).order_by(WhatsAppMessage.created_at.asc()).all()
    
    return jsonify({"messages":[{
        "id": m.id,
        "text": m.body,
        "type": m.message_type,
        "direction": m.direction,
        "ts": m.created_at.isoformat() if m.created_at else None,
        "platform": m.provider,
    } for m in msgs]}), 200

@whatsapp_bp.route('/conversation/<phone_number>', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_conversation(phone_number):
    """
    Get WhatsApp conversation for a specific phone number
    Returns messages in format expected by WhatsAppChat component
    """
    try:
        # 🔒 SECURITY: business_id from authenticated session via get_business_id()
        from server.routes_crm import get_business_id
        
        business_id = get_business_id()
        
        # Clean phone number (remove + and @s.whatsapp.net)
        clean_phone = phone_number.replace('+', '').replace('@s.whatsapp.net', '')
        
        # Get all messages for this phone number
        msgs = WhatsAppMessage.query.filter_by(
            business_id=business_id,
            to_number=clean_phone
        ).order_by(WhatsAppMessage.created_at.asc()).all()
        
        # Format messages for frontend
        formatted_messages = []
        for m in msgs:
            # 🔥 BUILD 180: Normalize direction to 'in' or 'out'
            # Backend sometimes saves 'inbound'/'outbound', normalize for frontend
            direction = m.direction or 'in'
            if direction in ['outbound', 'out']:
                direction = 'out'
            else:
                direction = 'in'
            
            formatted_messages.append({
                "id": str(m.id),
                "direction": direction,  # 'in' or 'out'
                "content_text": m.body or "",
                "sent_at": m.created_at.isoformat() if m.created_at else None,
                "status": m.status or "sent",
                "provider": m.provider or "baileys"
            })
        
        # Get last message timestamp
        last_message_at = msgs[-1].created_at.isoformat() if msgs else None
        
        return jsonify({
            "id": clean_phone,
            "phone_number": clean_phone,
            "messages": formatted_messages,
            "total_messages": len(formatted_messages),
            "last_message_at": last_message_at
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "id": phone_number,
            "phone_number": phone_number,
            "messages": [],
            "total_messages": 0,
            "last_message_at": None
        }), 200  # Return empty conversation instead of error

@whatsapp_bp.route('/stats', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def api_wa_stats():
    # 🔒 SECURITY: business_id from authenticated session via get_business_id()
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    
    # Count unique conversations
    total_convs = db.session.query(WhatsAppMessage.to_number).filter_by(
        business_id=business_id
    ).distinct().count()
    
    # Count total messages
    total_msgs = WhatsAppMessage.query.filter_by(business_id=business_id).count()
    
    return jsonify({
        "total_conversations": total_convs, 
        "total_messages": total_msgs
    }), 200

# === שלב 3: דוגמה לשמירת פרומפטים עם api_handler ===
from server.models_sql import Business, BusinessSettings

@whatsapp_bp.route('/prompts/<int:business_id>', methods=['POST'])
@api_handler
def save_whatsapp_prompt(business_id):
    """שמירת פרומפט וואטסאפ לעסק - דוגמה לשימוש ב-api_handler"""
    data = request.get_json(force=True)
    
    business = Business.query.filter_by(id=business_id).first()
    if not business:
        return {"ok": False, "error": "business_not_found"}, 404
    
    # 🔥 BUILD 186 FIX: Handle missing columns gracefully - continue with new settings
    settings = None
    try:
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
    except Exception as db_err:
        import logging
        logging.warning(f"⚠️ Could not load settings for {business_id} (DB schema issue): {db_err}")
        # Continue - will create new settings row below
    
    # 🔥 BUILD 186 FIX: Wrap entire save in try-except for schema mismatch resilience
    import logging
    try:
        if not settings:
            settings = BusinessSettings()
            settings.tenant_id = business_id
            db.session.add(settings)
        
        settings.ai_prompt = data.get('whatsapp_prompt', '')
        db.session.commit()
    except Exception as commit_err:
        db.session.rollback()
        logging.error(f"❌ Failed to save WhatsApp prompt for {business_id} (likely DB schema issue): {commit_err}")
        return {"ok": False, "error": "save_failed", "message": "Database schema mismatch - please run migrations"}, 500
    
    # ✅ CRITICAL: Invalidate AI service cache after prompt update
    try:
        from server.services.ai_service import invalidate_business_cache
        invalidate_business_cache(business_id)
        logging.info(f"🔥 AI cache invalidated for business {business_id} after WhatsApp prompt update")
    except Exception as cache_error:
        logging.error(f"❌ Failed to invalidate AI cache: {cache_error}")
    
    return {"ok": True, "id": business_id, "prompt_length": len(settings.ai_prompt)}

@whatsapp_bp.route('/webhook/incoming', methods=['POST'])
@csrf.exempt
def baileys_webhook():
    """🔴 CRITICAL: Webhook from Baileys for incoming WhatsApp messages"""
    import logging
    log = logging.getLogger(__name__)
    
    try:
        # Verify internal secret
        if request.headers.get('X-Internal-Secret') != INT_SECRET:
            log.warning("[WA-ERROR] Unauthorized webhook request")
            return jsonify({"error": "unauthorized"}), 401
        
        data = request.get_json()
        tenant_id = data.get('tenantId')
        if not tenant_id:
            log.error("[WA-ERROR] No tenantId in webhook payload - cannot process!")
            return jsonify({"error": "missing_tenant_id"}), 400
        payload = data.get('payload', {})
        messages = payload.get('messages', [])
        
        log.info(f"[WA-INCOMING] biz={tenant_id}, msg_count={len(messages)}")
        
        if not messages:
            return jsonify({"ok": True, "processed": 0}), 200
        
        # Process each incoming message
        from server.services.customer_intelligence import CustomerIntelligence
        from server.whatsapp_provider import get_whatsapp_service
        
        # ✅ BUILD 91: Multi-tenant - חכם! זיהוי business לפי tenantId
        from server.services.business_resolver import resolve_business_with_fallback
        business_id, status = resolve_business_with_fallback('whatsapp', tenant_id)
        
        # Get business name for clear logging (only on error)
        from server.models_sql import Business
        business = Business.query.filter_by(id=business_id).first() if business_id else None
        business_name = business.name if business else "UNKNOWN"
        
        if status == 'found':
            log.info(f"[WA-INCOMING] Resolved biz={business_id} from tenant={tenant_id}")
        else:
            log.warning(f"[WA-INCOMING] Fallback biz={business_id} ({status}) for tenant={tenant_id}")
        
        # ✅ Ensure business_id is valid
        if not business_id:
            log.error(f"[WA-ERROR] No valid business_id found for tenant={tenant_id}")
            return jsonify({"ok": False, "error": "no_business"}), 400
        
        # ✅ BUILD 92: Process messages IMMEDIATELY (no threading) - זריזות מקסימלית!
        import time
        from datetime import datetime, timedelta
        overall_start = time.time()
        
        wa_service = get_whatsapp_service(tenant_id=tenant_id)  # MULTI-TENANT: Pass tenant_id for correct WhatsApp session
        processed_count = 0
        
        for msg in messages:
            msg_start = time.time()
            try:
                # 🔥 CRITICAL FIX: Extract FULL remoteJid - DO NOT strip domain!
                # Android messages may come from @lid, @g.us (groups), or other formats
                # We must reply to the EXACT remoteJid we received
                remote_jid = msg.get('key', {}).get('remoteJid', '')
                
                # 🔥 LID FIX: Enhanced logging for incoming message identification
                message_id = msg.get('key', {}).get('id', '')
                from_me = msg.get('key', {}).get('fromMe', False)
                log.info(f"[WA-INCOMING] 🔵 Incoming chat_jid={remote_jid}, message_id={message_id}, from_me={from_me}")
                
                # 🔥 CRITICAL FIX: Skip messages from bot itself (fromMe=true)
                # The bot should ONLY process messages from users, not its own messages
                if from_me:
                    log.info(f"[WA-SKIP] Ignoring message from bot itself (fromMe=true)")
                    continue
                
                # 🔥 BUG FIX: Create safe identifier for logging/DB from remoteJid
                # This prevents NameError when logging unknown message formats
                from_identifier = remote_jid.replace('@', '_').replace('.', '_') if remote_jid else 'unknown'
                
                # 🔥 CRITICAL: Skip NON-PRIVATE messages - bot ONLY responds to private 1-on-1 chats!
                # Groups: @g.us
                # Broadcast lists: @broadcast
                # Newsletters/Channels: @newsletter
                # Status updates: status@broadcast
                if (remote_jid.endswith('@g.us') or 
                    remote_jid.endswith('@broadcast') or 
                    remote_jid.endswith('@newsletter') or
                    'status@broadcast' in remote_jid):
                    log.info(f"[WA-SKIP] Ignoring non-private message from {remote_jid} - bot only responds to private chats")
                    continue
                
                # 🔥 FIX #3 & #6: Extract phone number with proper normalization and LID support
                # remoteJid can be:
                # - Standard: 972501234567@s.whatsapp.net
                # - LID (Android/Business): 82399031480511@lid
                # - Participant (Groups): phone@s.whatsapp.net as participant
                from_number_e164 = None
                customer_external_id = None
                remote_jid_alt = None  # Alternative JID for proper reply routing
                phone_raw = None  # Raw phone for debugging
                push_name = None  # WhatsApp display name
                
                # 🆕 Extract pushName for name saving
                push_name = msg.get('pushName', '')
                if push_name and push_name.lower() not in ['unknown', '']:
                    log.debug(f"[WA-INCOMING] Extracted pushName: {push_name}")
                
                # 🔥 FIX #3: Check for participant (sender_pn) first - this is the preferred reply address
                participant = msg.get('key', {}).get('participant')
                if participant and participant.endswith('@s.whatsapp.net'):
                    remote_jid_alt = participant
                    log.debug(f"[WA-LID] Found participant (sender_pn): {participant}")
                
                if remote_jid.endswith('@s.whatsapp.net'):
                    # Standard WhatsApp user - extract and normalize phone
                    phone_raw = remote_jid.replace('@s.whatsapp.net', '')
                    from_number_e164 = normalize_phone(phone_raw)
                    
                    if from_number_e164:
                        log.debug(f"[WA-INCOMING] Standard JID - phone normalized: {phone_raw} -> {from_number_e164}")
                        phone_for_ai_check = from_number_e164
                    else:
                        # Invalid phone format - treat as external ID
                        log.warning(f"[WA-INCOMING] Could not normalize phone from standard JID: {remote_jid}")
                        customer_external_id = remote_jid
                        phone_for_ai_check = remote_jid
                        
                elif remote_jid.endswith('@lid'):
                    # 🔥 FIX #3: LID JID - DO NOT extract phone from LID!
                    # LID is NOT a phone number - it's an internal WhatsApp identifier
                    push_name = msg.get('pushName', 'Unknown')
                    log.info(f"[WA-INCOMING] @lid JID detected: {remote_jid}, pushName={push_name}")
                    
                    # Store LID as external ID for this conversation
                    customer_external_id = remote_jid
                    
                    # 🔥 FIX #3: Try to extract phone from participant/sender_pn if available
                    if remote_jid_alt:
                        phone_raw = remote_jid_alt.replace('@s.whatsapp.net', '')
                        from_number_e164 = normalize_phone(phone_raw)
                        if from_number_e164:
                            log.info(f"[WA-LID] Extracted phone from participant: {from_number_e164}")
                        else:
                            log.warning(f"[WA-LID] Could not normalize phone from participant: {remote_jid_alt}")
                    else:
                        log.info(f"[WA-LID] No participant field - using @lid as external_id only")
                    
                    phone_for_ai_check = customer_external_id  # Use LID for AI state
                    
                else:
                    # 🔥 FIX #6: Other non-standard JID - store as external ID
                    push_name = msg.get('pushName', 'Unknown')
                    log.warning(f"[WA-INCOMING] Non-standard JID {remote_jid}, pushName={push_name}")
                    customer_external_id = remote_jid
                    phone_for_ai_check = remote_jid
                
                log.info(f"[WA-INCOMING] Processed JIDs: remoteJid={(remote_jid or '')[:30]}, "
                        f"remoteJidAlt={(remote_jid_alt or '')[:30]}, "
                        f"phone_e164={from_number_e164}, external_id={(customer_external_id or '')[:30]}")
                
                # 🔥 ANDROID FIX: Support ALL message formats (iPhone + Android)
                # Different devices send messages in different formats:
                # - iPhone: usually uses 'conversation'
                # - Android: uses 'conversation', 'extendedTextMessage', or 'imageMessage' with caption
                message_obj = msg.get('message', {})
                message_text = None
                
                # Try all possible text locations (order matters - most common first)
                if not message_text and message_obj.get('conversation'):
                    message_text = message_obj.get('conversation')
                    log.debug(f"[WA-PARSE] Found text in 'conversation'")
                
                if not message_text and message_obj.get('extendedTextMessage'):
                    message_text = message_obj.get('extendedTextMessage', {}).get('text', '')
                    log.debug(f"[WA-PARSE] Found text in 'extendedTextMessage'")
                
                # 🔥 ANDROID FIX: Handle image/video/document messages with captions
                if not message_text and message_obj.get('imageMessage'):
                    message_text = message_obj.get('imageMessage', {}).get('caption', '[תמונה]')
                    log.debug(f"[WA-PARSE] Found caption in 'imageMessage'")
                
                if not message_text and message_obj.get('videoMessage'):
                    message_text = message_obj.get('videoMessage', {}).get('caption', '[וידאו]')
                    log.debug(f"[WA-PARSE] Found caption in 'videoMessage'")
                
                if not message_text and message_obj.get('documentMessage'):
                    message_text = message_obj.get('documentMessage', {}).get('caption', '[מסמך]')
                    log.debug(f"[WA-PARSE] Found caption in 'documentMessage'")
                
                # 🔥 ANDROID FIX: Handle audio messages
                if not message_text and message_obj.get('audioMessage'):
                    message_text = '[הודעה קולית]'
                    log.debug(f"[WA-PARSE] Found 'audioMessage'")
                
                # 🔥 FIX D: Don't crash on empty/unknown message formats - just skip gracefully
                if not message_text:
                    available_keys = list(message_obj.keys()) if message_obj else []
                    if available_keys:
                        log.info(f"[WA-SKIP] Unknown message format from {from_identifier} (remoteJid={remote_jid}), available keys: {available_keys}")
                        log.debug(f"[WA-PARSE] Full message object: {str(message_obj)[:200]}...")
                        # Try to extract ANY text from ANY key as last resort
                        for key in available_keys:
                            if isinstance(message_obj[key], dict):
                                if 'text' in message_obj[key]:
                                    message_text = message_obj[key]['text']
                                    log.info(f"[WA-PARSE] Found text in '{key}.text'")
                                    break
                                if 'caption' in message_obj[key]:
                                    message_text = message_obj[key]['caption']
                                    log.info(f"[WA-PARSE] Found text in '{key}.caption'")
                                    break
                    else:
                        # Empty message object - skip without error
                        log.info(f"[WA-SKIP] Empty message object from {remote_jid} - skipping gracefully")
                        continue
                
                # 🔥 FIX D: If still no message text after all attempts, skip gracefully (don't crash)
                if not remote_jid or not message_text:
                    log.info(f"[WA-SKIP] Missing remote_jid={bool(remote_jid)} or message_text={bool(message_text)} - skipping message")
                    continue
                
                # 🔥 CRITICAL FIX: Check if this is our OWN message echoing back!
                # Sometimes Baileys sends bot's outbound messages back as "incoming"
                # 🔥 BUILD 180: Check both 'out' and 'outbound' for backwards compatibility
                # 🔥 FIX: Only check for EXACT match, not substring, to avoid false positives
                recent_outbound = WhatsAppMessage.query.filter(
                    WhatsAppMessage.business_id == business_id,
                    WhatsAppMessage.to_number == from_number_e164,
                    WhatsAppMessage.direction.in_(['out', 'outbound'])
                ).order_by(WhatsAppMessage.created_at.desc()).first()
                
                if recent_outbound:
                    from datetime import datetime, timedelta
                    time_diff = datetime.utcnow() - recent_outbound.created_at
                    # If we sent the EXACT SAME message in the last 10 seconds, skip (likely echo)
                    # 🔥 FIX: Changed from 30s to 10s and from substring to exact match
                    if time_diff < timedelta(seconds=10):
                        # Check if message content is EXACTLY the same (exact echo)
                        # 🔥 FIX: Changed from "message_text in recent_outbound.body" to equality check
                        if recent_outbound.body and message_text.strip() == recent_outbound.body.strip():
                            logger.info(f"🚫 LOOP PREVENTED: Ignoring exact echo of our own message to {from_number_e164}")
                            log.warning(f"🚫 Ignoring bot echo (exact match): {message_text[:50]}...")
                            continue
                
                log.info(f"[WA-INCOMING] biz={business_id}, from={from_number_e164}, remoteJid={remote_jid}, text={message_text[:50]}...")
                
                # 🔥 FIX #3: Calculate reply_jid - prefer @s.whatsapp.net over @lid
                reply_jid = remote_jid  # Default: use remoteJid
                if remote_jid_alt and remote_jid_alt.endswith('@s.whatsapp.net'):
                    # Prefer participant/sender_pn if it's a standard WhatsApp number
                    reply_jid = remote_jid_alt
                    log.info(f"[WA-REPLY] 🎯 Using remote_jid_alt (participant) as reply target: {reply_jid}")
                elif remote_jid:
                    log.info(f"[WA-REPLY] 🎯 Using remote_jid as reply target: {reply_jid}")
                
                # 🔥 LID FIX: Log clear message for LID handling
                if remote_jid.endswith('@lid'):
                    if reply_jid != remote_jid:
                        log.info(f"[WA-LID] ✅ LID message: incoming={remote_jid}, reply_to={reply_jid} (using participant)")
                    else:
                        log.info(f"[WA-LID] ⚠️ LID message: incoming={remote_jid}, reply_to={reply_jid} (no participant available)")
                
                # ✅ BUILD 200: Use ContactIdentityService for unified lead management
                # This prevents duplicates across WhatsApp and Phone channels
                from server.services.contact_identity_service import ContactIdentityService
                from datetime import datetime
                
                # Prepare timestamp
                msg_timestamp = None
                if timestamp_ms:
                    try:
                        msg_timestamp = datetime.fromtimestamp(int(timestamp_ms))
                    except (ValueError, TypeError):
                        msg_timestamp = datetime.utcnow()
                else:
                    msg_timestamp = datetime.utcnow()
                
                # Get or create lead using unified contact identity service
                lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
                    business_id=business_id,
                    remote_jid=remote_jid,
                    push_name=push_name,
                    message_text=message_text,
                    wa_message_id=baileys_message_id,
                    ts=msg_timestamp
                )
                
                log.info(f"✅ Lead resolved: lead_id={lead.id}, phone={lead.phone_e164 or 'N/A'}, jid={remote_jid[:30]}...")
                
                # Get customer for backwards compatibility (if exists)
                from server.models_sql import Customer
                customer = Customer.query.filter_by(
                    business_id=business_id,
                    phone_e164=lead.phone_e164
                ).first() if lead.phone_e164 else None
                
                # Extract message_id from Baileys message structure
                # This is critical for deduplication (same message_id = same message)
                baileys_message_id = msg.get('key', {}).get('id', '')
                jid = msg.get('key', {}).get('remoteJid', '')
                timestamp_ms = msg.get('messageTimestamp', 0)
                
                # ✅ Check if message already exists (prevent duplicates from webhook retries)
                # 🔥 ENHANCED: Triple-check deduplication with message_id + jid + timestamp
                # This prevents:
                # 1. Webhook retries (same message_id)
                # 2. Multiple delivery attempts (same jid + timestamp)
                # 3. Content duplication (same body + phone within 10s)
                existing_msg = None
                
                # First check: message_id (most reliable)
                if baileys_message_id:
                    existing_msg = WhatsAppMessage.query.filter(
                        WhatsAppMessage.business_id == business_id,
                        WhatsAppMessage.provider_message_id == baileys_message_id
                    ).first()
                    
                    if existing_msg:
                        log.info(f"⚠️ Duplicate by message_id: {baileys_message_id}")
                        continue
                
                # Second check: jid + timestamp (for messages without message_id)
                if not existing_msg and jid and timestamp_ms:
                    # Allow 1-second tolerance for timestamp matching
                    timestamp_dt = datetime.utcfromtimestamp(timestamp_ms)
                    time_tolerance = timedelta(seconds=1)
                    
                    existing_msg = WhatsAppMessage.query.filter(
                        WhatsAppMessage.business_id == business_id,
                        WhatsAppMessage.to_number == from_number_e164,
                        WhatsAppMessage.created_at >= timestamp_dt - time_tolerance,
                        WhatsAppMessage.created_at <= timestamp_dt + time_tolerance,
                        WhatsAppMessage.direction.in_(['in', 'inbound'])
                    ).first()
                    
                    if existing_msg:
                        log.info(f"⚠️ Duplicate by jid+timestamp: {jid} @ {timestamp_ms}")
                        continue
                
                # Third check: body content + phone within 10 seconds (fallback)
                if not existing_msg:
                    existing_msg = WhatsAppMessage.query.filter(
                        WhatsAppMessage.business_id == business_id,
                        WhatsAppMessage.to_number == from_number_e164,
                        WhatsAppMessage.body == message_text,
                        WhatsAppMessage.direction.in_(['in', 'inbound'])
                    ).order_by(WhatsAppMessage.created_at.desc()).first()
                    
                    # Skip if same message was received in last 10 seconds (webhook retry)
                    if existing_msg:
                        if (datetime.utcnow() - existing_msg.created_at) < timedelta(seconds=10):
                            log.warning(f"⚠️ Duplicate by content within 10s: {message_text[:50]}...")
                            continue
                
                # Save incoming message to DB with message_id for deduplication
                # Use ON CONFLICT DO NOTHING pattern for race condition protection
                wa_msg = WhatsAppMessage()
                wa_msg.business_id = business_id
                wa_msg.to_number = from_number_e164  # E.164 format for database consistency
                wa_msg.body = message_text
                wa_msg.message_type = 'text'
                wa_msg.direction = 'in'  # 🔥 BUILD 180: Consistent 'in'/'out' values
                wa_msg.provider = 'baileys'
                wa_msg.status = 'received'
                wa_msg.provider_message_id = baileys_message_id if baileys_message_id else None
                
                try:
                    db.session.add(wa_msg)
                    db.session.commit()
                except Exception as integrity_err:
                    # Handle race condition: another thread/instance inserted same message_id
                    db.session.rollback()
                    if baileys_message_id and 'unique' in str(integrity_err).lower():
                        log.info(f"⚠️ Message already saved by another process: {baileys_message_id}")
                        continue
                    else:
                        # Unexpected error - re-raise
                        raise
                
                # ✅ BUILD 162: Track session for auto-summary generation
                try:
                    update_session_activity(
                        business_id=business_id,
                        customer_wa_id=from_number_e164,
                        direction="in",
                        provider="baileys"
                    )
                except Exception as e:
                    log.warning(f"⚠️ Session tracking failed: {e}")
                
                # ✅ BUILD 93: Check for appointment request FIRST
                appointment_created = False
                try:
                    from server.whatsapp_appointment_handler import process_incoming_whatsapp_message
                    # ✅ BUILD 100.13: Pass business_id to appointment handler
                    appointment_result = process_incoming_whatsapp_message(
                        phone_number=from_number_e164,
                        message_text=message_text,
                        message_id=wa_msg.id,
                        business_id=business_id  # ✅ FIX: Pass correct business_id
                    )
                    if appointment_result.get('appointment_created'):
                        appointment_created = True
                        log.info(f"📅 Appointment created for {from_number_e164}: {appointment_result.get('appointment_id')}")
                except Exception as e:
                    log.warning(f"⚠️ Appointment check failed: {e}")
                
                # ✅ BUILD 152: Check if AI is enabled for this conversation
                # 🔥 FIX: Use phone_for_ai_check (remoteJid) instead of from_number_e164 for @lid messages
                ai_enabled = True  # Default to enabled
                try:
                    from server.models_sql import WhatsAppConversationState
                    # Use phone_for_ai_check if available, otherwise use from_number_e164
                    check_phone = phone_for_ai_check if 'phone_for_ai_check' in locals() else from_number_e164
                    
                    if not check_phone:
                        log.warning(f"[WA-INCOMING] No phone identifier for AI check - defaulting to enabled")
                        ai_enabled = True  # Explicitly set to True
                    else:
                        conv_state = WhatsAppConversationState.query.filter_by(
                            business_id=business_id,
                            phone=check_phone
                        ).first()
                        if conv_state:
                            ai_enabled = conv_state.ai_active
                            log.info(f"[WA-INCOMING] 🤖 AI state for {check_phone}: {'✅ ENABLED' if ai_enabled else '❌ DISABLED'}")
                        else:
                            ai_enabled = True  # Explicitly set to True when no state found
                            log.info(f"[WA-INCOMING] 🤖 No AI state found for {check_phone} - defaulting to ENABLED")
                except Exception as e:
                    ai_enabled = True  # Explicitly set to True on error
                    log.warning(f"[WA-WARN] Could not check AI state: {e}")
                
                # If AI is disabled, send a basic acknowledgment instead of silence
                # 🔥 FIX: Bot should ALWAYS respond, even if AI is disabled
                if not ai_enabled:
                    log.info(f"[WA-INCOMING] AI disabled for {check_phone if 'check_phone' in locals() else from_number_e164} - sending basic acknowledgment")
                    
                    # Try to get business greeting as fallback response
                    try:
                        from server.models_sql import Business
                        business = Business.query.get(business_id)
                        if business:
                            # Use whatsapp_greeting first, then greeting_message, then default
                            response_text = business.whatsapp_greeting or business.greeting_message or DEFAULT_FALLBACK_MESSAGE
                        else:
                            response_text = DEFAULT_FALLBACK_MESSAGE
                    except Exception as e:
                        log.warning(f"[WA-WARN] Could not fetch business greeting: {e}")
                        response_text = DEFAULT_FALLBACK_MESSAGE
                    
                    # 🔥 FIX: Validate response is not empty or whitespace
                    if not response_text or response_text.isspace():
                        response_text = DEFAULT_FALLBACK_MESSAGE
                    
                    # Send the basic acknowledgment
                    log.info(f"[WA-OUTGOING] 📤 Sending basic ack to jid={reply_jid}, text={str(response_text)[:50]}...")
                    
                    try:
                        from server.services.jobs import enqueue_job
                        from server.jobs.send_whatsapp_message_job import send_whatsapp_message_job
                        
                        job = enqueue_job(
                            queue_name='default',
                            func=send_whatsapp_message_job,
                            business_id=business_id,
                            tenant_id=tenant_id,
                            remote_jid=reply_jid,
                            response_text=response_text,
                            wa_msg_id=wa_msg.id,
                            timeout=60,
                            retry=2,
                            description=f"Send WhatsApp basic ack to {reply_jid[:15]}"
                        )
                        log.info(f"[WA-OUTGOING] ✅ Basic ack job enqueued: {job.id[:8]}")
                        processed_count += 1
                    except Exception as enqueue_error:
                        log.error(f"[WA-OUTGOING] ❌ Failed to enqueue basic ack: {enqueue_error}")
                    
                    msg_duration = time.time() - msg_start
                    log.info(f"[WA-INCOMING] Basic ack sent (AI disabled) in {msg_duration:.2f}s")
                    continue
                
                # ✅ FIX: Load conversation history for AI context (12 messages for better context)
                # Increased from 10 to 12 to match AI service limit and prevent context loss
                previous_messages = []
                try:
                    recent_msgs = WhatsAppMessage.query.filter_by(
                        business_id=business_id,
                        to_number=from_number_e164
                    ).order_by(WhatsAppMessage.created_at.desc()).limit(12).all()
                    
                    # Format as conversation (reversed to chronological order)
                    # 🔥 BUILD 180: Handle both 'in'/'inbound' and 'out'/'outbound' for backwards compatibility
                    for msg_hist in reversed(recent_msgs):
                        if msg_hist.direction in ['in', 'inbound']:
                            previous_messages.append(f"לקוח: {msg_hist.body}")
                        else:
                            previous_messages.append(f"עוזר: {msg_hist.body}")  # ✅ כללי - לא hardcoded!
                    
                    log.info(f"📚 Loaded {len(previous_messages)} previous messages for context")
                except Exception as e:
                    log.warning(f"⚠️ Could not load conversation history: {e}")
                
                # ✅ BUILD 119: Generate AI response with Agent SDK (real actions!)
                # ✅ BUILD 170.1: Improved error handling - use DB prompt even on fallback!
                # 🔥 BUILD 170.1: Clear any poisoned DB session before AI call!
                # 🔥 FIX: Add explicit logging to show AgentKit is about to be invoked
                log.info(f"[WA-AI-READY] ✅ Message passed all filters, invoking AgentKit now!")
                log.info(f"[WA-AI-READY] Parameters: business_id={business_id}, lead_id={lead.id}, from={from_number_e164}, jid={remote_jid[:30]}")
                try:
                    db.session.rollback()
                except:
                    pass
                
                ai_start = time.time()
                response_text = None
                
                from server.services.ai_service import get_ai_service
                ai_service = get_ai_service()
                
                # 🔥 BUILD 200 DEBUG: Log state before AI call
                log.info(f"[WA-AI-START] About to call AI for jid={remote_jid[:30]}, lead_id={lead.id}")
                
                try:
                    ai_response = ai_service.generate_response_with_agent(
                        message=message_text,
                        business_id=business_id,
                        context={
                            'phone': from_number_e164,  # E.164 for CRM
                            'remote_jid': remote_jid,  # 🔥 CRITICAL: Original JID for replies
                            'customer_name': customer.name if customer else None,
                            'lead_status': lead.status if lead else None,
                            'previous_messages': previous_messages,  # ✅ זיכרון שיחה - 10 הודעות!
                            'appointment_created': appointment_created  # ✅ BUILD 93: הפגישה נקבעה!
                        },
                        channel='whatsapp',
                        customer_phone=from_number_e164,
                        customer_name=customer.name if customer else None
                    )
                    
                    # Handle dict response (text + actions) vs plain string
                    if isinstance(ai_response, dict):
                        response_text = ai_response.get('text', '')
                        actions = ai_response.get('actions', [])
                    else:
                        response_text = str(ai_response)
                    
                    ai_duration = time.time() - ai_start
                    log.info(f"[WA-AI-SUCCESS] AI generated response in {ai_duration:.2f}s, length={len(response_text) if response_text else 0}")
                except Exception as e:
                    logger.error(f"⚠️ Agent failed, trying regular AI response: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # ✅ BUILD 170.1: Fallback to regular AI (which uses DB prompt!)
                    try:
                        response_text = ai_service.generate_response(
                            message=message_text,
                            business_id=business_id,
                            context={
                                'phone': from_number_e164,  # E.164 for CRM
                                'remote_jid': remote_jid,  # 🔥 CRITICAL: Original JID for replies
                                'customer_name': customer.name if customer else None,
                                'previous_messages': previous_messages
                            },
                            channel='whatsapp'
                        )
                    except Exception as e2:
                        logger.error(f"⚠️ Regular AI also failed: {e2}")
                        # ✅ Last resort - use business whatsapp_greeting or greeting_message
                        try:
                            from server.models_sql import Business
                            business = Business.query.get(business_id)
                            if business:
                                # Use whatsapp_greeting first, then greeting_message, then name
                                response_text = business.whatsapp_greeting or business.greeting_message or f"{business.name}" if business.name else ""
                            else:
                                response_text = None  # Don't send if no business
                        except:
                            response_text = None  # Don't send on error
                        
                        # 🔥 Guard: Don't send empty messages
                        if not response_text or not response_text.strip():
                            log.warning(f"⚠️ No fallback response available - skipping send")
                            continue
                
                # 🔥 BUILD 200 DEBUG: Log before sending
                log.info(f"[WA-SEND-DEBUG] reply_jid={reply_jid[:30]}, response_text_length={len(response_text) if response_text else 0}")
                
                # 🔥 CRITICAL: Verify response_text is not empty before sending
                if not response_text or response_text.isspace():
                    log.error(f"[WA-ERROR] ❌ AgentKit returned empty response! Cannot send empty message.")
                    # Try to send a fallback message instead of silence
                    try:
                        from server.models_sql import Business
                        business = Business.query.get(business_id)
                        if business:
                            response_text = business.whatsapp_greeting or business.greeting_message or DEFAULT_FALLBACK_MESSAGE
                        else:
                            response_text = DEFAULT_FALLBACK_MESSAGE
                        log.warning(f"[WA-WARN] Using fallback response: {response_text[:50]}...")
                    except Exception as e:
                        log.error(f"[WA-ERROR] Could not fetch fallback: {e}")
                        log.error(f"[WA-ERROR] Skipping message - cannot send empty response")
                        continue
                
                # 🔥 CRITICAL FIX: Send response to ORIGINAL remoteJid, not reconstructed @s.whatsapp.net
                # This ensures Android messages with @lid, @g.us, etc. get proper replies
                # 🔥 LID FIX: Use reply_jid (which prefers @s.whatsapp.net over @lid)
                log.info(f"[WA-OUTGOING] 📤 Sending AI reply to jid={reply_jid}, text={str(response_text)[:50]}...")
                log.info(f"[WA-OUTGOING] 🤖 AgentKit successfully generated response, now enqueueing send job")
                
                # 🔥 REMOVED THREADING: Use RQ job for WhatsApp sending
                # This ensures proper retry, error handling, and no thread proliferation
                try:
                    from server.services.jobs import enqueue_job
                    from server.jobs.send_whatsapp_message_job import send_whatsapp_message_job
                    
                    # 🔥 BUILD 200 DEBUG: Log parameters before enqueue
                    log.info(f"[WA-ENQUEUE-DEBUG] business_id={business_id}, tenant_id={tenant_id}, reply_jid={reply_jid[:30]}, msg_length={len(response_text)}")
                    
                    job = enqueue_job(
                        queue_name='default',
                        func=send_whatsapp_message_job,
                        business_id=business_id,
                        tenant_id=tenant_id,
                        remote_jid=reply_jid,  # 🔥 LID FIX: Use reply_jid instead of remote_jid
                        response_text=response_text,
                        wa_msg_id=wa_msg.id,
                        timeout=60,
                        retry=2,
                        description=f"Send WhatsApp to {reply_jid[:15]}"
                    )
                    log.info(f"[WA-OUTGOING] ✅ Job enqueued: {job.id[:8]} for message {wa_msg.id}, target={reply_jid[:20]}")
                    log.info(f"[WA-SUCCESS] ✅✅✅ FULL FLOW COMPLETED: webhook → AgentKit → sendMessage queued ✅✅✅")
                except Exception as enqueue_error:
                    log.error(f"[WA-OUTGOING] ❌ Failed to enqueue WhatsApp send: {enqueue_error}")
                    # Fall back to synchronous send if enqueue fails
                    log.warning(f"[WA-OUTGOING] Falling back to synchronous send to {reply_jid[:20]}")
                    send_whatsapp_message_job(business_id, tenant_id, reply_jid, response_text, wa_msg.id)  # 🔥 LID FIX: Use reply_jid
                
                # Mark as processed immediately (actual sending happens in background)
                processed_count += 1
                
                msg_duration = time.time() - msg_start
                log.info(f"[WA-INCOMING] Message queued for background send in {msg_duration:.2f}s")
                
            except Exception as e:
                import traceback
                log.error(f"[WA-ERROR] Processing message failed: {e}")
                log.error(f"[WA-ERROR] Traceback: {traceback.format_exc()}")
        
        overall_duration = time.time() - overall_start
        log.info(f"[WA-INCOMING] Total processing: {overall_duration:.2f}s for {len(messages)} message(s)")
        
        processed = processed_count
        
        return jsonify({"ok": True, "processed": processed}), 200
        
    except Exception as e:
        import traceback
        log.error(f"[WA-ERROR] Baileys webhook error: {e}")
        log.error(f"[WA-ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@whatsapp_bp.route('/send', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@api_handler
def send_manual_message():
    """✅ UNIFIED: Send WhatsApp message - same logic as CRM thread endpoint"""
    import time
    start_time = time.time()
    
    data = request.get_json(force=True)
    
    to_number = data.get('to')
    message = data.get('message')
    attachment_id = data.get('attachment_id')  # Optional media attachment
    lead_id = data.get('lead_id')  # ✅ NEW: Optional lead_id to lookup reply_jid from Lead model (most reliable JID for Baileys)
    
    # 🔒 SECURITY: business_id from authenticated session via get_business_id()
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    
    if not to_number or (not message and not attachment_id):
        return {"ok": False, "error": "missing_required_fields"}, 400
    
    # Ensure we have either message text or attachment, but warn if caption is missing for media
    if attachment_id and not message:
        log.warning(f"[WA-SEND] Sending media without caption to {to_number}")
    
    try:
        # שליחת הודעה דרך WhatsApp provider
        from server.whatsapp_provider import get_whatsapp_service
        from server.utils.whatsapp_utils import normalize_whatsapp_to
        from server.models_sql import Lead
        
        # MULTI-TENANT: Create tenant_id from business_id
        if not business_id:
            return {"ok": False, "error": "no_business_id"}, 400
        tenant_id = f"business_{business_id}"
        
        # ✅ NEW: Lookup lead for reply_jid if lead_id provided
        lead_phone = None
        lead_reply_jid = None
        if lead_id:
            try:
                lead = db.session.query(Lead).filter_by(
                    id=lead_id,
                    business_id=business_id
                ).first()
                if lead:
                    lead_phone = lead.phone_e164
                    lead_reply_jid = lead.reply_jid
                    log.debug(f"[WA-SEND] Found lead {lead_id}: phone={lead_phone}, reply_jid={lead_reply_jid}")
            except Exception as e:
                log.warning(f"[WA-SEND] Could not lookup lead {lead_id}: {e}")
        
        # ✅ UNIFIED: Use centralized normalization function
        try:
            formatted_number, jid_source = normalize_whatsapp_to(
                to=to_number,
                lead_phone=lead_phone,
                lead_reply_jid=lead_reply_jid,
                lead_id=lead_id,
                business_id=business_id
            )
            log.info(f"[WA-SEND] from_page=whatsapp_send normalized_to={formatted_number} source={jid_source} lead_id={lead_id} business_id={business_id}")
        except ValueError as e:
            log.error(f"[WA-SEND] Normalization failed: {e}")
            return {"ok": False, "error": str(e)}, 400
        
        try:
            wa_service = get_whatsapp_service(tenant_id=tenant_id)
        except Exception as e:
            log.error(f"[WA-SEND] Failed to get WhatsApp service: {e}")
            return {"ok": False, "error": f"whatsapp_service_unavailable: {str(e)}"}, 503
        
        # Handle media attachment if provided
        message_type = 'text'
        media_url = None
        
        if attachment_id:
            from server.models_sql import Attachment
            from server.services.attachment_service import get_attachment_service
            
            # Validate attachment belongs to business and is WhatsApp-compatible
            attachment = db.session.query(Attachment).filter_by(
                id=attachment_id,
                business_id=business_id,
                is_deleted=False
            ).first()
            
            if not attachment:
                return {"ok": False, "error": "attachment_not_found"}, 404
            
            if not attachment.channel_compatibility.get('whatsapp', False):
                return {"ok": False, "error": "attachment_not_compatible_with_whatsapp"}, 400
            
            # Generate signed URL for media
            attachment_service = get_attachment_service()
            media_url = attachment_service.generate_signed_url(
                attachment.id,
                attachment.storage_path,
                ttl_minutes=60
            )
            
            # Determine media type from mime
            if attachment.mime_type.startswith('image/'):
                message_type = 'image'
            elif attachment.mime_type.startswith('video/'):
                message_type = 'video'
            elif attachment.mime_type.startswith('audio/'):
                message_type = 'audio'
            elif attachment.mime_type == 'application/pdf':
                message_type = 'document'
            else:
                message_type = 'document'  # Default to document for other types
            
            log.info(f"[WA-SEND] Sending {message_type} attachment: {attachment.filename_original}")
        
        # ✅ FAST-FAIL: Send with timeout handling for better UX
        try:
            if media_url:
                # Send media message - use send_media method
                send_result = wa_service.send_media(
                    formatted_number,
                    media_url,
                    caption=message or '',  # Optional caption
                    tenant_id=tenant_id
                )
            else:
                # Send text message
                send_result = wa_service.send_message(formatted_number, message, tenant_id=tenant_id)
                
            # ✅ Log timing for SLOW_API detection
            elapsed = time.time() - start_time
            if elapsed > 5.0:
                log.warning(f"SLOW_API: POST /api/whatsapp/send took {elapsed:.2f}s")
            else:
                log.info(f"[WA-SEND] Request completed in {elapsed:.2f}s")
                
        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start_time
            log.error(f"[WA-SEND] Timeout after {elapsed:.2f}s: {e}")
            # ✅ Fast fail - don't let timeout hang for 20 seconds
            return {"ok": False, "error": "send_timeout", "elapsed": elapsed}, 504
        except Exception as e:
            elapsed = time.time() - start_time
            log.error(f"[WA-SEND] Send message failed after {elapsed:.2f}s: {e}")
            
            # ✅ Check if this is a Baileys 500 error - fail fast
            error_str = str(e).lower()
            if '500' in error_str or 'service unavailable' in error_str:
                log.error(f"[WA-SEND] Baileys 500 error detected - failing fast")
                return {"ok": False, "error": "provider_error_500", "elapsed": elapsed}, 503
            
            return {"ok": False, "error": f"send_failed: {str(e)}", "elapsed": elapsed}, 500
        
        if not send_result:
            return {"ok": False, "error": "empty_response_from_provider"}, 500
        
        # 🔥 FIX BUILD 181: Accept multiple success states from Twilio/Baileys
        # Providers return: 'sent', 'queued', 'accepted', or just a message_id/sid
        provider_status = send_result.get('status', '')
        success_statuses = {'sent', 'queued', 'accepted', 'delivered'}
        has_message_id = send_result.get('sid') or send_result.get('message_id')
        is_success = provider_status in success_statuses or has_message_id
        
        if is_success:
            # שמירת ההודעה בבסיס הנתונים
            clean_number = to_number.replace('@s.whatsapp.net', '')
            # Normalize status for DB storage
            db_status = provider_status if provider_status in success_statuses else 'sent'
            try:
                wa_msg = WhatsAppMessage()
                wa_msg.business_id = business_id
                wa_msg.to_number = clean_number
                wa_msg.body = message or ''  # Caption or empty if media-only
                wa_msg.message_type = message_type  # 'text', 'image', 'video', 'audio', 'document'
                wa_msg.direction = 'out'  # 🔥 BUILD 180: Consistent 'in'/'out' values
                wa_msg.provider = send_result.get('provider', 'unknown')
                wa_msg.provider_message_id = send_result.get('sid') or send_result.get('message_id')
                wa_msg.status = db_status
                
                # Store media URL if attachment was sent
                if media_url:
                    wa_msg.media_url = media_url
                
                db.session.add(wa_msg)
                db.session.commit()
                
                # ✅ BUILD 162: Track session for manual message
                try:
                    update_session_activity(
                        business_id=business_id,
                        customer_wa_id=clean_number,
                        direction="out",
                        provider=send_result.get('provider', 'baileys')
                    )
                except Exception as e:
                    log.warning(f"⚠️ Session tracking (manual) failed: {e}")
                    
            except Exception as db_error:
                log.error(f"[WA-SEND] DB save failed (message was sent): {db_error}")
                db.session.rollback()
                # Message was sent even if DB failed - still return success
                return {
                    "ok": True, 
                    "message_id": None,
                    "provider": send_result.get('provider'),
                    "status": db_status,
                    "warning": "message_sent_but_db_save_failed"
                }
            
            return {
                "ok": True, 
                "message_id": wa_msg.id,
                "provider": send_result.get('provider'),
                "status": db_status
            }
        else:
            error_msg = send_result.get('error', 'send_failed')
            log.error(f"[WA-SEND] Provider returned error status '{provider_status}': {error_msg}")
            return {
                "ok": False, 
                "error": error_msg
            }, 500
            
    except Exception as e:
        log.error(f"[WA-SEND] Unexpected error: {e}")
        import traceback
        log.error(f"[WA-SEND] Traceback: {traceback.format_exc()}")
        db.session.rollback()  # 🔥 FIX: Always rollback on error to prevent session poisoning
        return {"ok": False, "error": str(e)}, 500


# ============================================================================
# 🔗 WEBHOOK: Send endpoint for external services (n8n, Zapier, etc.)
# ============================================================================

@whatsapp_bp.route('/webhook/send', methods=['POST'])
@csrf.exempt
def send_via_webhook():
    """
    ✅ FIX BUILD 200+: Bulletproof webhook endpoint for external services (n8n)
    
    This endpoint allows external services to send WhatsApp messages without
    session authentication, using a webhook secret instead.
    
    Key Requirements:
    1. Resolve business_id from X-Webhook-Secret header (NO defaults!)
    2. Support multiple header variants (X-Webhook-Secret, x-webhook-secret, X_WEBHOOK_SECRET)
    3. Normalize secret values (strip whitespace, quotes)
    4. Enhanced diagnostic logging (masked secrets, lengths, DB info)
    5. Fail-fast query (no defaults, no fallback)
    
    Usage:
        POST /api/whatsapp/webhook/send
        Headers:
            Content-Type: application/json
            X-Webhook-Secret: <business-specific-secret-from-db>
        Body:
            {
                "to": "+972501234567",
                "message": "Hello World"
            }
    
    Setup:
        1. Set webhook_secret in Business table for each business
        2. Configure n8n to use this endpoint with the business-specific secret
        3. Set BAILEYS_BASE_URL=http://baileys:3300 (Docker network)
    """
    from server.models_sql import WhatsAppMessage, Business
    
    # ✅ 1) Get webhook secret from multiple header variants (case-insensitive, underscore support)
    # Support: X-Webhook-Secret, x-webhook-secret, X_WEBHOOK_SECRET
    raw_secret = (
        request.headers.get('X-Webhook-Secret') or
        request.headers.get('x-webhook-secret') or
        request.headers.get('X_WEBHOOK_SECRET') or
        ""
    )
    
    # ✅ 2) Track which headers are present for diagnostics
    headers_seen = {
        'X-Webhook-Secret': 'X-Webhook-Secret' in request.headers,
        'x-webhook-secret': 'x-webhook-secret' in request.headers,
        'X_WEBHOOK_SECRET': 'X_WEBHOOK_SECRET' in request.headers
    }
    
    has_header = bool(raw_secret)
    raw_len = len(raw_secret) if raw_secret else 0
    
    if not has_header:
        log.error(f"[WA_WEBHOOK] Missing webhook secret header from {request.remote_addr}")
        log.error(f"[WA_WEBHOOK] headers_seen={headers_seen}, has_header={has_header}")
        return jsonify({
            "ok": False, 
            "error_code": "missing_webhook_secret",
            "message": "X-Webhook-Secret header is required",
            "headers_seen": headers_seen
        }), 401
    
    # ✅ 3) Normalize secret value - strip whitespace and quotes
    # Remove leading/trailing: whitespace, newlines, single quotes, double quotes
    webhook_secret = raw_secret.strip().strip('"').strip("'").strip()
    clean_len = len(webhook_secret)
    
    # ✅ 4) Enhanced diagnostic logging (without exposing full secret)
    masked_secret = mask_secret_for_logging(webhook_secret)
    
    log.info(f"[WA_WEBHOOK] has_header={has_header}, raw_len={raw_len}, clean_len={clean_len}, masked_secret={masked_secret}")
    log.info(f"[WA_WEBHOOK] headers_seen={headers_seen}")
    
    # ✅ 5) Get DB connection info for diagnostics (without exposing password)
    try:
        from server.db import db
        db_url = str(db.engine.url)
        # Extract just the host (hide password)
        db_host = db.engine.url.host if hasattr(db.engine.url, 'host') else 'unknown'
        db_name = db.engine.url.database if hasattr(db.engine.url, 'database') else 'unknown'
        log.info(f"[WA_WEBHOOK] db_host={db_host}, db_name={db_name}")
        
        # Count businesses with webhook_secret set
        business_count_with_secret = Business.query.filter(Business.webhook_secret.isnot(None)).count()
        log.info(f"[WA_WEBHOOK] business_count_with_secret={business_count_with_secret}")
    except Exception as db_info_err:
        log.warning(f"[WA_WEBHOOK] Could not get DB info: {db_info_err}")
    
    # ✅ 6) Fail-fast query - NO DEFAULT FALLBACK
    business = Business.query.filter(Business.webhook_secret == webhook_secret).first()
    
    if not business:
        # Log failure with diagnostics
        log.error(f"[WA_WEBHOOK] Invalid webhook secret")
        log.error(f"[WA_WEBHOOK] has_header={has_header}, raw_len={raw_len}, clean_len={clean_len}")
        log.error(f"[WA_WEBHOOK] masked_secret={masked_secret}, ip={request.remote_addr}")
        log.error(f"[WA_WEBHOOK] headers_seen={headers_seen}")
        
        return jsonify({
            "ok": False, 
            "error_code": "invalid_webhook_secret",
            "message": "Invalid webhook secret - no matching business found",
            "diagnostics": {
                "has_header": has_header,
                "raw_len": raw_len,
                "clean_len": clean_len,
                "headers_seen": headers_seen
            }
        }), 401
    
    business_id = business.id
    
    # ✅ 7) Enhanced logging - prove business resolution with masked secrets
    # Mask the secret from DB too for comparison
    masked_db_secret = mask_secret_for_logging(business.webhook_secret or "")
    
    log.info(f"[WA_WEBHOOK] ✅ MATCHED: masked_request={masked_secret}, masked_db={masked_db_secret}")
    log.info(f"[WA_WEBHOOK] resolved_business_id={business_id}, resolved_business_name={business.name}, provider={business.whatsapp_provider}")
    
    # ✅ 4) Get data
    try:
        data = request.get_json(force=True)
    except Exception as e:
        log.error(f"[WA_WEBHOOK] Invalid JSON: {e}")
        return jsonify({
            "ok": False, 
            "error_code": "invalid_json",
            "message": "Request body must be valid JSON"
        }), 400
    
    to_number = data.get('to')
    message = data.get('message')
    
    # ✅ 5) Validate required fields
    if not to_number:
        return jsonify({
            "ok": False, 
            "error_code": "missing_to",
            "message": "Field 'to' is required (phone number)"
        }), 400
    
    if not message:
        return jsonify({
            "ok": False, 
            "error_code": "missing_message",
            "message": "Field 'message' is required"
        }), 400
    
    # ✅ 6) Resolve provider from business (use business.whatsapp_provider, default to baileys)
    provider_resolved = business.whatsapp_provider if business.whatsapp_provider in ['baileys', 'meta'] else 'baileys'
    
    tenant_id = f"business_{business_id}"
    
    # ✅ 7) Verify base URL is internal (Docker network) - NOT external domain
    baileys_base = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
    if baileys_base.startswith('https://prosaas.pro') or 'prosaas.pro' in baileys_base:
        log.error(f"[WA_WEBHOOK] ERROR: BAILEYS_BASE_URL contains external domain: {baileys_base}")
        log.error("[WA_WEBHOOK] CRITICAL: Must use Docker internal URL: http://baileys:3300")
        return jsonify({
            "ok": False,
            "error_code": "invalid_base_url",
            "message": "BAILEYS_BASE_URL must be internal Docker URL (http://baileys:3300), not external domain"
        }), 500
    
    log.info(f"[WA_WEBHOOK] Using base_url={baileys_base}, tenant_id={tenant_id}")
    
    # ✅ 8) Pre-send health check - verify WhatsApp is actually connected
    try:
        import requests
        headers = {'X-Internal-Secret': os.getenv('INTERNAL_SECRET', '')}
        
        # Check tenant-specific status (not just service health)
        status_url = f"{baileys_base}/whatsapp/{tenant_id}/status"
        log.info(f"[WA_WEBHOOK] Checking connection status: {status_url}")
        
        status_resp = requests.get(status_url, headers=headers, timeout=3)
        
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            connected = status_data.get('connected', False)
            has_qr = status_data.get('hasQR', False)
            active_phone = status_data.get('active_phone')
            last_seen = status_data.get('last_message_ts')
            
            log.info(f"[WA_WEBHOOK] Connection status: connected={connected}, active_phone={active_phone}, hasQR={has_qr}, last_seen={last_seen}")
            
            if not connected or has_qr:
                # Not actually connected - return 503 (not 500!)
                return jsonify({
                    "ok": False,
                    "error_code": "wa_not_connected",
                    "provider": provider_resolved,
                    "status_snapshot": {
                        "connected": connected,
                        "hasQR": has_qr,
                        "active_phone": active_phone,
                        "checked_at": datetime.utcnow().isoformat()
                    },
                    "message": "WhatsApp is not connected. Please scan QR code in settings."
                }), 503
        else:
            # Status check failed
            log.error(f"[WA_WEBHOOK] Status check failed: {status_resp.status_code}")
            return jsonify({
                "ok": False,
                "error_code": "wa_status_check_failed",
                "provider": provider_resolved,
                "message": f"WhatsApp status check failed: {status_resp.status_code}"
            }), 503
            
    except requests.exceptions.Timeout:
        log.error("[WA_WEBHOOK] Status check timeout")
        return jsonify({
            "ok": False,
            "error_code": "wa_status_timeout",
            "provider": provider_resolved,
            "message": "WhatsApp status check timeout - service may be down"
        }), 503
    except Exception as health_err:
        log.error(f"[WA_WEBHOOK] Health check error: {health_err}")
        return jsonify({
            "ok": False,
            "error_code": "wa_health_check_failed",
            "provider": provider_resolved,
            "message": f"WhatsApp health check failed: {str(health_err)}"
        }), 503
    
    # ✅ 9) Send message using WhatsApp provider (SYNCHRONOUS for debugging)
    try:
        from server.whatsapp_provider import get_whatsapp_service
        
        try:
            wa_service = get_whatsapp_service(tenant_id=tenant_id)
        except Exception as e:
            log.error(f"[WA_WEBHOOK] Failed to get WhatsApp service: {e}")
            return jsonify({
                "ok": False, 
                "error_code": "whatsapp_service_unavailable",
                "provider": provider_resolved,
                "message": f"WhatsApp service unavailable: {str(e)}"
            }), 503
        
        # Format phone number
        formatted_number = to_number
        if '@' not in formatted_number:
            formatted_number = f"{to_number}@s.whatsapp.net"
        
        log.info(f"[WA_WEBHOOK] Sending message to {formatted_number} via {provider_resolved}")
        
        # Send message (SYNCHRONOUS - no queue for debugging)
        try:
            send_result = wa_service.send_message(formatted_number, message, tenant_id=tenant_id)
            log.info(f"[WA_WEBHOOK] Send result: {send_result}")
        except Exception as e:
            log.error(f"[WA_WEBHOOK] Send failed: {type(e).__name__}: {str(e)}")
            return jsonify({
                "ok": False, 
                "error_code": "send_failed",
                "provider": provider_resolved,
                "message": f"Failed to send message: {str(e)}"
            }), 500
        
        if not send_result:
            return jsonify({
                "ok": False, 
                "error_code": "empty_response",
                "provider": provider_resolved,
                "message": "No response from provider"
            }), 500
        
        # Check success
        provider_status = send_result.get('status', '')
        success_statuses = {'sent', 'queued', 'accepted', 'delivered'}
        has_message_id = send_result.get('sid') or send_result.get('message_id')
        is_success = provider_status in success_statuses or has_message_id
        
        if is_success:
            # Save to database
            clean_number = to_number.replace('@s.whatsapp.net', '')
            db_status = provider_status if provider_status in success_statuses else 'sent'
            
            message_db_id = None
            provider_message_id = send_result.get('sid') or send_result.get('message_id')
            
            try:
                wa_msg = WhatsAppMessage()
                wa_msg.business_id = business_id
                wa_msg.to_number = clean_number
                wa_msg.body = message
                wa_msg.message_type = 'text'
                wa_msg.direction = 'out'
                wa_msg.provider = send_result.get('provider', provider_resolved)
                wa_msg.provider_message_id = provider_message_id
                wa_msg.status = db_status
                
                db.session.add(wa_msg)
                db.session.commit()
                
                message_db_id = wa_msg.id
                log.info(f"[WA_WEBHOOK] ✅ Message sent successfully: db_id={message_db_id}, provider_msg_id={provider_message_id}")
                
            except Exception as db_error:
                log.error(f"[WA_WEBHOOK] DB save failed: {db_error}")
                db.session.rollback()
                # Message was sent even if DB failed
            
            # ✅ 10) Return proof response with full details
            return jsonify({
                "ok": True,
                "provider": send_result.get('provider', provider_resolved),
                "message_id": provider_message_id,
                "db_id": message_db_id,
                "delivered": True,
                "status": db_status
            }), 200
        else:
            error_msg = send_result.get('error', 'send_failed')
            log.error(f"[WA_WEBHOOK] Provider error: {error_msg}")
            return jsonify({
                "ok": False,
                "error_code": error_msg,
                "provider": provider_resolved,
                "message": f"Provider failed to send: {error_msg}"
            }), 500
    
    except Exception as e:
        log.error(f"[WA_WEBHOOK] Unexpected error: {e}")
        import traceback
        log.error(f"[WA_WEBHOOK] Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return jsonify({
            "ok": False, 
            "error_code": "internal_error",
            "provider": provider_resolved if 'provider_resolved' in locals() else 'baileys',
            "message": str(e)
        }), 500


# ============================================================================
# 🤖 BUILD 152: Toggle AI per WhatsApp conversation
# ============================================================================

@whatsapp_bp.route('/toggle-ai', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@api_handler
def toggle_ai_for_conversation():
    """Toggle AI on/off for a specific WhatsApp conversation"""
    import logging
    log = logging.getLogger(__name__)
    
    data = request.get_json(force=True)
    phone_number = data.get('phone_number')
    ai_enabled = data.get('ai_enabled')
    
    if phone_number is None or ai_enabled is None:
        return {"success": False, "error": "missing_required_fields"}, 400
    
    # Get business_id from authenticated session
    from server.routes_crm import get_business_id
    business_id = get_business_id()
    
    if not business_id:
        return {"success": False, "error": "no_business_id"}, 400
    
    try:
        from server.models_sql import WhatsAppConversationState
        
        # Normalize phone number (remove + if present)
        phone = phone_number.replace('+', '').strip()
        
        # Find or create state record
        state = WhatsAppConversationState.query.filter_by(
            business_id=business_id,
            phone=phone
        ).first()
        
        if not state:
            state = WhatsAppConversationState()
            state.business_id = business_id
            state.phone = phone
            db.session.add(state)
        
        # Update AI state
        state.ai_active = bool(ai_enabled)
        # 🔥 FIX: g.user is a dict, not an object - use .get() instead of .id
        state.updated_by = g.user.get('id') if hasattr(g, 'user') and g.user else None
        
        db.session.commit()
        
        log.info(f"[WA-AI-TOGGLE] biz={business_id}, phone={phone}, ai_active={state.ai_active}")
        
        return {
            "success": True,
            "ai_enabled": state.ai_active,
            "phone_number": phone
        }
        
    except Exception as e:
        log.error(f"[WA-ERROR] Failed to toggle AI: {e}")
        db.session.rollback()
        return {"success": False, "error": str(e)}, 500


@whatsapp_bp.route('/ai-state/<phone_number>', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@api_handler
def get_ai_state_for_conversation(phone_number):
    """Get AI state for a specific WhatsApp conversation"""
    from server.routes_crm import get_business_id
    business_id = get_business_id()
    
    if not business_id:
        return {"success": False, "error": "no_business_id"}, 400
    
    try:
        from server.models_sql import WhatsAppConversationState
        
        # Normalize phone number
        phone = phone_number.replace('+', '').strip()
        
        state = WhatsAppConversationState.query.filter_by(
            business_id=business_id,
            phone=phone
        ).first()
        
        # Default to AI enabled if no state record exists
        ai_enabled = state.ai_active if state else True
        
        return {
            "success": True,
            "ai_enabled": ai_enabled,
            "phone_number": phone
        }
        
    except Exception as e:
        import logging
        logging.error(f"[WA-ERROR] Failed to get AI state: {e}")
        return {"success": False, "error": str(e)}, 500


# ============================================================================
# 🔔 BUILD 151: Internal WhatsApp Status Webhook
# ============================================================================

def validate_internal_secret():
    """Validate internal secret header for internal-only endpoints"""
    secret = request.headers.get('X-Internal-Secret')
    return secret and secret == INT_SECRET

def _create_whatsapp_disconnect_notification(business_id: int):
    """
    🔔 BUILD 151: Create a system notification when WhatsApp disconnects
    Uses LeadReminder with type='system_whatsapp_disconnect' so it flows through
    the existing notification system.
    
    Also dispatches push notifications to business owners.
    """
    try:
        # Check if notification already exists (prevent duplicates)
        existing = LeadReminder.query.filter_by(
            tenant_id=business_id,
            reminder_type='system_whatsapp_disconnect',
            completed_at=None
        ).first()
        
        if existing:
            log.info(f"[WHATSAPP_STATUS] Disconnect notification already exists for business_id={business_id}")
            return
        
        # Find business owner to associate notification
        owner = User.query.filter_by(business_id=business_id, role='owner').first()
        
        # Create the notification reminder
        reminder = LeadReminder()
        reminder.tenant_id = business_id
        reminder.lead_id = None  # System notification - not related to a lead
        # 🔥 FIX: Use local time for due_at (immediate system notification)
        reminder.due_at = datetime.now()  # Due immediately
        reminder.note = "חיבור הווטסאפ נותק - יש להיכנס להגדרות ולחבר מחדש"
        reminder.description = "חיבור הווטסאפ לעסק נותק. יש להיכנס להגדרות WhatsApp ולסרוק את קוד ה-QR מחדש כדי להתחבר."
        reminder.channel = 'ui'
        reminder.priority = 'high'
        reminder.reminder_type = 'system_whatsapp_disconnect'
        reminder.created_by = owner.id if owner else None
        
        db.session.add(reminder)
        db.session.commit()
        
        log.info(f"[WHATSAPP_STATUS] ✅ Created disconnect notification for business_id={business_id}")
        
        # 🔔 Push notification dispatch to business owners/admins
        try:
            from server.services.notifications.dispatcher import dispatch_push_to_business_owners
            dispatch_push_to_business_owners(
                business_id=business_id,
                notification_type='whatsapp_disconnect',
                title='⚠️ חיבור WhatsApp נותק',
                body='יש להיכנס להגדרות ולחבר מחדש את WhatsApp',
                url='/app/settings',
                entity_id=str(business_id)
            )
            log.info(f"[WHATSAPP_STATUS] 📱 Dispatched push notification for WhatsApp disconnect")
        except Exception as push_error:
            log.warning(f"[WHATSAPP_STATUS] ⚠️ Push notification dispatch failed (non-critical): {push_error}")
        
    except Exception as e:
        log.error(f"[WHATSAPP_STATUS] ❌ Failed to create disconnect notification: {e}")
        db.session.rollback()

def _clear_whatsapp_disconnect_notification(business_id: int):
    """
    🔔 BUILD 151: Clear/complete the disconnect notification when WhatsApp reconnects
    """
    try:
        reminders = LeadReminder.query.filter_by(
            tenant_id=business_id,
            reminder_type='system_whatsapp_disconnect',
            completed_at=None
        ).all()
        
        if not reminders:
            log.info(f"[WHATSAPP_STATUS] No active disconnect notifications to clear for business_id={business_id}")
            return
        
        # 🔥 FIX: Use local time for completed_at
        for reminder in reminders:
            reminder.completed_at = datetime.now()
        
        db.session.commit()
        log.info(f"[WHATSAPP_STATUS] ✅ Cleared {len(reminders)} disconnect notification(s) for business_id={business_id}")
        
    except Exception as e:
        log.error(f"[WHATSAPP_STATUS] ❌ Failed to clear disconnect notifications: {e}")
        db.session.rollback()

@whatsapp_bp.route('/admin/migrate-sessions', methods=['POST'])
@require_api_auth(['system_admin'])
@api_handler
def migrate_whatsapp_sessions():
    """Admin endpoint: Create sessions from existing messages for summaries
    
    This is a one-time migration to populate the sessions table from
    existing WhatsApp messages. Only system_admin can run this.
    """
    try:
        from server.services.whatsapp_session_service import migrate_existing_messages_to_sessions
        result = migrate_existing_messages_to_sessions()
        return {"ok": True, "result": result}
    except Exception as e:
        log.error(f"[WA-ADMIN] Migration error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}, 500


@csrf.exempt
@internal_whatsapp_bp.route('/status-webhook', methods=['POST'])
def whatsapp_status_webhook():
    """
    🔔 BUILD 151: Internal webhook to handle WhatsApp connection status changes
    Called by Baileys service when connection status changes.
    Creates/clears notification reminders for business owners.
    """
    try:
        # 1) Validate internal secret
        if not validate_internal_secret():
            log.error("[WHATSAPP_STATUS] ❌ Unauthorized request - invalid internal secret")
            return jsonify({"error": "unauthorized"}), 401
        
        # 2) Parse request
        data = request.get_json() or {}
        tenant_id = data.get('tenant_id')  # e.g., "business_1"
        status = data.get('status')  # "connected" or "disconnected"
        reason = data.get('reason')  # optional: "logged_out", etc.
        
        if not tenant_id or status not in ('connected', 'disconnected'):
            log.error(f"[WHATSAPP_STATUS] Invalid payload: tenant_id={tenant_id}, status={status}")
            return jsonify({"error": "invalid_payload"}), 400
        
        # 3) Extract business_id from tenant_id (business_1 -> 1)
        try:
            if tenant_id.startswith('business_'):
                business_id = int(tenant_id.split('_')[1])
            else:
                business_id = int(tenant_id)
        except (ValueError, IndexError):
            log.error(f"[WHATSAPP_STATUS] Cannot parse business_id from tenant_id={tenant_id}")
            return jsonify({"error": "invalid_tenant_id"}), 400
        
        # 4) Verify business exists
        business = Business.query.get(business_id)
        if not business:
            log.warning(f"[WHATSAPP_STATUS] Unknown business_id={business_id} (tenant_id={tenant_id})")
            return jsonify({"ok": True}), 200  # Don't error - just ignore
        
        log.info(f"[WHATSAPP_STATUS] 📬 Received status={status} for business_id={business_id} (reason={reason})")
        
        # 5) Create or clear notification based on status
        if status == 'disconnected':
            _create_whatsapp_disconnect_notification(business_id)
        else:  # connected
            _clear_whatsapp_disconnect_notification(business_id)
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        log.error(f"[WHATSAPP_STATUS] ❌ Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 🔵 Meta WhatsApp Cloud API Webhook
# ============================================================================

META_WA_VERIFY_TOKEN = os.getenv("META_WA_VERIFY_TOKEN")

@whatsapp_bp.route('/webhook/meta', methods=['GET', 'POST'])
@csrf.exempt
def meta_webhook():
    """
    Meta WhatsApp Cloud API Webhook
    
    GET: Webhook verification (Meta sends challenge)
    POST: Incoming messages from Meta WhatsApp Cloud API
    """
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        log.info(f"[META-WA-WEBHOOK] Verification request: mode={mode}")
        
        if mode == 'subscribe' and token and token == META_WA_VERIFY_TOKEN:
            log.info("[META-WA-WEBHOOK] ✅ Webhook verified successfully")
            return challenge, 200
        
        log.warning("[META-WA-WEBHOOK] ❌ Webhook verification failed")
        return "Forbidden", 403
    
    try:
        data = request.get_json(silent=True) or {}
        log.info(f"[META-WA-WEBHOOK] Received payload: {str(data)[:200]}...")
        
        entries = data.get('entry', [])
        if not entries:
            return "OK", 200
        
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                
                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id')
                display_phone = metadata.get('display_phone_number')
                
                messages = value.get('messages', [])
                for msg in messages:
                    from_number = msg.get('from', '')
                    msg_type = msg.get('type', 'text')
                    
                    if msg_type == 'text':
                        body = msg.get('text', {}).get('body', '')
                    elif msg_type in ['image', 'video', 'audio', 'document']:
                        media = msg.get(msg_type, {})
                        body = media.get('caption', f'[{msg_type.upper()}]')
                    else:
                        body = f'[{msg_type.upper()}]'
                    
                    if not from_number or not body:
                        continue
                    
                    from server.services.business_resolver import resolve_business_by_meta_phone
                    business_id = resolve_business_by_meta_phone(display_phone or phone_number_id)
                    
                    if not business_id:
                        log.warning(f"[META-WA-WEBHOOK] No business found for phone_number_id={phone_number_id}")
                        continue
                    
                    business = Business.query.get(business_id)
                    if not business:
                        log.warning(f"[META-WA-WEBHOOK] Business {business_id} not found in DB")
                        continue
                    
                    log.info(f"[META-WA-WEBHOOK] Processing message from {from_number} for business {business.name}")
                    
                    from server.services.whatsapp_gateway import handle_incoming_whatsapp_message
                    result = handle_incoming_whatsapp_message(
                        provider="meta",
                        business=business,
                        from_number=from_number,
                        to_number=display_phone or phone_number_id,
                        body=body,
                        raw_payload=msg,
                        message_type=msg_type
                    )
                    
                    if result.get('ai_enabled', False):
                        _process_meta_ai_response(business, from_number, body)
        
        return "OK", 200
        
    except Exception as e:
        log.error(f"[META-WA-WEBHOOK] Error processing: {e}")
        import traceback
        traceback.print_exc()
        return "OK", 200


def _process_meta_ai_response(business, from_number: str, user_message: str):
    """Generate and send AI response for Meta WhatsApp message"""
    try:
        from server.services.ai_service import get_ai_response
        from server.services.whatsapp_gateway import send_whatsapp_message
        
        response_text = get_ai_response(
            business_id=business.id,
            user_message=user_message,
            channel='whatsapp'
        )
        
        if response_text:
            send_whatsapp_message(business, from_number, response_text)
            log.info(f"[META-WA-WEBHOOK] AI response sent to {from_number[:8]}...")
    except Exception as e:
        log.error(f"[META-WA-WEBHOOK] AI response failed: {e}")


# ============================================================================
# 🔵 WhatsApp Test Endpoint (Unified Gateway)
# ============================================================================

@whatsapp_bp.route('/test', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def whatsapp_test():
    """
    Send a test WhatsApp message via the unified gateway
    
    Uses the business's configured whatsapp_provider (baileys or meta)
    """
    from server.routes_crm import get_business_id
    from server.services.whatsapp_gateway import send_whatsapp_message
    
    business_id = get_business_id()
    if not business_id:
        return jsonify({"success": False, "error": "no_business_id"}), 400
    
    business = Business.query.get(business_id)
    if not business:
        return jsonify({"success": False, "error": "business_not_found"}), 404
    
    data = request.get_json(force=True)
    to = data.get('to')
    text = data.get('text', 'היי, זו הודעת בדיקה מ-ProSaaS')
    
    if not to:
        return jsonify({"success": False, "error": "missing_to"}), 400
    
    tenant_id = f"business_{business_id}"
    
    result = send_whatsapp_message(business, to, text, tenant_id=tenant_id)
    
    success = result.get('status') == 'sent'
    return jsonify({
        "success": success,
        "provider": result.get('provider'),
        "message_id": result.get('message_id') or result.get('sid'),
        "error": result.get('error') if not success else None
    }), 200 if success else 500


# ============================================================================
# 🔵 WhatsApp Provider Update Endpoint
# ============================================================================

@whatsapp_bp.route('/provider', methods=['PUT'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def update_provider():
    """
    Update WhatsApp provider for the current business
    
    Body: { "provider": "baileys" | "meta" }
    """
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    if not business_id:
        return jsonify({"success": False, "error": "no_business_id"}), 400
    
    business = Business.query.get(business_id)
    if not business:
        return jsonify({"success": False, "error": "business_not_found"}), 404
    
    data = request.get_json(force=True)
    provider = data.get('provider')
    
    if provider not in ('baileys', 'meta'):
        return jsonify({"success": False, "error": "invalid_provider"}), 400
    
    try:
        business.whatsapp_provider = provider
        db.session.commit()
        
        log.info(f"[WHATSAPP] Updated provider to '{provider}' for business_id={business_id}")
        
        return jsonify({
            "success": True,
            "provider": provider,
            "message": f"ספק WhatsApp עודכן ל-{provider}"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        log.error(f"[WHATSAPP] Error updating provider: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# 🔵 WhatsApp Provider Info Endpoint
# ============================================================================

@whatsapp_bp.route('/provider-info', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_provider_info():
    """
    Get WhatsApp provider information for the current business
    
    Returns provider type, connection status, and configuration
    """
    from server.routes_crm import get_business_id
    from server.services.whatsapp_gateway import get_whatsapp_provider_info
    
    business_id = get_business_id()
    if not business_id:
        return jsonify({"success": False, "error": "no_business_id"}), 400
    
    business = Business.query.get(business_id)
    if not business:
        return jsonify({"success": False, "error": "business_not_found"}), 404
    
    info = get_whatsapp_provider_info(business)
    
    return jsonify({
        "success": True,
        **info
    }), 200


# ============================================================================
# 🔵 BUILD 162: Active Chats / Session Tracking Endpoints
# ============================================================================

@whatsapp_bp.route('/active-chats', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_active_chats():
    """
    Get list of active WhatsApp conversations
    
    Returns count and list of open sessions
    """
    from server.routes_crm import get_business_id
    from server.services.whatsapp_session_service import get_active_chats_count, get_active_chats as get_chats_list
    
    business_id = get_business_id()
    if not business_id:
        return jsonify({"success": False, "error": "no_business_id"}), 400
    
    count = get_active_chats_count(int(business_id))
    chats = get_chats_list(int(business_id), limit=50)
    
    return jsonify({
        "success": True,
        "count": count,
        "chats": chats
    }), 200


@whatsapp_bp.route('/process-stale-sessions', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin'])
def trigger_stale_session_processing():
    """
    Manually trigger stale session processing (for testing/admin)
    
    Finds sessions inactive > 15 minutes and generates summaries
    """
    from server.services.whatsapp_session_service import process_stale_sessions
    
    processed = process_stale_sessions()
    
    return jsonify({
        "success": True,
        "processed": processed,
        "message": f"Processed {processed} stale sessions"
    }), 200


@whatsapp_bp.route('/summaries', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def get_whatsapp_summaries():
    """
    Get all WhatsApp conversation summaries for the business
    
    Returns list of leads with their last WhatsApp summary
    """
    from server.routes_crm import get_business_id
    from server.models_sql import Lead
    
    business_id = get_business_id()
    if not business_id:
        return jsonify({"success": False, "error": "no_business_id"}), 400
    
    leads = Lead.query.filter(
        Lead.tenant_id == int(business_id),
        Lead.whatsapp_last_summary.isnot(None),
        Lead.whatsapp_last_summary != ''
    ).order_by(Lead.whatsapp_last_summary_at.desc()).limit(50).all()
    
    summaries = []
    for lead in leads:
        summaries.append({
            "id": lead.id,
            "lead_name": lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "לקוח לא ידוע",
            "phone": lead.phone_e164 or lead.phone or "",
            "summary": lead.whatsapp_last_summary,
            "summary_at": lead.whatsapp_last_summary_at.isoformat() if lead.whatsapp_last_summary_at else None
        })
    
    return jsonify({
        "success": True,
        "summaries": summaries
    }), 200

# === WhatsApp Broadcast Endpoints ===

@whatsapp_bp.route('/templates', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_templates():
    """
    Get WhatsApp templates from Meta Cloud API
    Only for Meta provider
    """
    try:
        from server.routes_crm import get_business_id
        business_id = get_business_id()
        
        # Get Meta WhatsApp credentials from business settings
        business = Business.query.get(business_id)
        if not business:
            return jsonify({'templates': []}), 200
        
        # Check if Meta Cloud API is configured
        meta_phone_id = os.getenv('META_PHONE_NUMBER_ID')
        meta_token = os.getenv('META_ACCESS_TOKEN')
        
        if not meta_phone_id or not meta_token:
            log.warning("Meta Cloud API not configured - no templates available")
            return jsonify({'templates': []}), 200
        
        # Fetch templates from Meta API
        # GET /v18.0/{WABA_ID}/message_templates
        waba_id = os.getenv('META_WABA_ID')
        if not waba_id:
            return jsonify({'templates': []}), 200
        
        url = f"https://graph.facebook.com/v18.0/{waba_id}/message_templates"
        headers = {
            'Authorization': f'Bearer {meta_token}'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            templates = data.get('data', [])
            
            return jsonify({
                'templates': [{
                    'id': t.get('id'),
                    'name': t.get('name'),
                    'status': t.get('status'),
                    'language': t.get('language'),
                    'category': t.get('category'),
                    'components': t.get('components', [])
                } for t in templates]
            }), 200
        else:
            log.error(f"Failed to fetch templates from Meta: {response.status_code} {response.text}")
            return jsonify({'templates': []}), 200
            
    except Exception as e:
        log.error(f"Error fetching templates: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'templates': []}), 200


@whatsapp_bp.route('/broadcasts', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_broadcasts():
    """
    ✅ FIX BUILD 200+: Get broadcast campaign history
    
    REQUIREMENT: Never return 500 - always return {ok:true, campaigns:[]} even if empty/no table
    """
    try:
        from server.routes_crm import get_business_id
        from server.models_sql import WhatsAppBroadcast
        
        business_id = get_business_id()
        
        # ✅ FIX: Try to get broadcasts, but handle table not existing gracefully
        broadcasts = []
        try:
            broadcasts = WhatsAppBroadcast.query.filter_by(
                business_id=business_id
            ).order_by(WhatsAppBroadcast.created_at.desc()).limit(50).all()
        except Exception as db_err:
            # ✅ Table might not exist yet (fresh install) - return empty list
            log.warning(f"[WA_CAMPAIGNS] DB query failed (table may not exist): {db_err}")
            # Don't raise - just return empty
            broadcasts = []
        
        campaigns = []
        for broadcast in broadcasts:
            try:
                creator = User.query.get(broadcast.created_by) if broadcast.created_by else None
                campaigns.append({
                    'id': broadcast.id,
                    'name': broadcast.name or f'תפוצה #{broadcast.id}',
                    'provider': broadcast.provider,
                    'template_id': broadcast.template_id,
                    'message_text': broadcast.message_text,
                    'total_recipients': broadcast.total_recipients,
                    'sent_count': broadcast.sent_count,
                    'failed_count': broadcast.failed_count,
                    'status': broadcast.status,
                    'created_at': broadcast.created_at.isoformat() if broadcast.created_at else None,
                    'created_by': creator.name if creator else 'לא ידוע'
                })
            except Exception as item_err:
                # Skip this broadcast if there's an error serializing it
                log.warning(f"[WA_CAMPAIGNS] Error serializing broadcast {broadcast.id}: {item_err}")
                continue
        
        # ✅ ALWAYS return success with campaigns list (even if empty)
        return jsonify({
            'ok': True,
            'campaigns': campaigns
        }), 200
        
    except Exception as e:
        # ✅ Even on catastrophic error, return empty list (not 500!)
        log.error(f"[WA_CAMPAIGNS] Error loading campaigns: {e}")
        log.error(f"[WA_CAMPAIGNS] error_code: campaigns_load_failed")
        import traceback
        log.error(f"[WA_CAMPAIGNS] Traceback: {traceback.format_exc()}")
        
        # Return empty list instead of 500
        return jsonify({
            'ok': True,
            'campaigns': [],
            'warning': 'Failed to load campaigns - check logs'
        }), 200


def normalize_phone(phone_str) -> str:
    """
    Normalize phone number to E.164 format (or cleaned format)
    Returns None if invalid
    
    Examples:
        '972-52-1234567' -> '972521234567'
        '052 123 4567' -> '0521234567'
        'invalid' -> None
    """
    if not phone_str:
        return None
    
    # Convert to string and strip whitespace
    phone = str(phone_str).strip()
    
    # Remove common separators
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    # Basic validation: must be at least 8 digits and only contain digits (and optional leading +)
    if phone.startswith('+'):
        phone = phone[1:]
    
    if not phone.isdigit() or len(phone) < 8:
        return None
    
    return phone


def parse_csv_phones(csv_file) -> list:
    """
    Parse phone numbers from CSV file
    Returns list of normalized phone numbers
    """
    phones = []
    try:
        # Read CSV content
        content = csv_file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Parse CSV
        csv_file.seek(0)  # Reset file pointer
        reader = csv.DictReader(io.StringIO(content))
        
        for row in reader:
            # Try to find phone field (case insensitive)
            phone = None
            for key in row.keys():
                if key.lower() in ['phone', 'telephone', 'mobile', 'number', 'tel', 'טלפון']:
                    phone = row[key]
                    break
            
            # If no phone column found, try first column
            if not phone and row:
                phone = list(row.values())[0]
            
            normalized = normalize_phone(phone)
            if normalized:
                phones.append(normalized)
    except Exception as e:
        log.error(f"[parse_csv_phones] Error: {e}")
    
    return phones


def is_empty_value(value) -> bool:
    """
    Helper function: Check if a value is considered empty for recipient extraction
    
    Args:
        value: The value to check (can be str, list, or None)
    
    Returns:
        bool: True if value is empty, False otherwise
    
    Returns True for:
    - None
    - Empty string or whitespace-only string
    - String literals '[]', 'null', 'None'
    - Empty lists
    
    Example:
        >>> is_empty_value(None)
        True
        >>> is_empty_value([])
        True
        >>> is_empty_value('[]')
        True
        >>> is_empty_value([1, 2, 3])
        False
    """
    if not value:
        return True
    if isinstance(value, str) and value.strip() in ['', '[]', 'null', 'None']:
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def extract_phones_simplified(payload, files, business_id):
    """
    🔥 SIMPLIFIED recipient resolution - accept phones from ANYWHERE!
    
    Per requirements: "Don't complicate it! Just make it so that to send a broadcast,
    all that's needed is to have a phone marked!"
    
    Extract phone numbers from ANY source:
    1. Direct phones (phones/recipients/selected_phones/to - any format)
    2. lead_ids → fetch phones from DB
    3. csv_file → parse phones  
    4. statuses → query leads by status
    5. message_text → extract phones from text
    
    Returns list of normalized phone numbers (deduplicated)
    """
    phones = []
    
    log.info(f"[WA_BROADCAST] 🔍 Starting SIMPLIFIED phone extraction for business_id={business_id}")
    log.info(f"[WA_BROADCAST] Payload keys: {list(payload.keys())}")
    log.info(f"[WA_BROADCAST] Files keys: {list(files.keys())}")
    log.info(f"[WA_BROADCAST] Full payload: {str(payload)[:500]}")
    
    # 🔥 STRATEGY: Try EVERY possible field name and format
    # Don't skip anything - if it looks like a phone, accept it!
    
    # 1) Try ALL possible direct phone field names
    phone_field_names = ['phones', 'recipients', 'selected_phones', 'to', 'phone_numbers', 
                         'numbers', 'contacts', 'phone', 'phoneNumbers']
    
    for field_name in phone_field_names:
        raw_value = payload.get(field_name)
        if not raw_value:
            continue
            
        log.info(f"[WA_BROADCAST] Found {field_name}={str(raw_value)[:200]}")
        
        # Parse the value - it could be a string, list, or JSON string
        parsed_phones = []
        
        if isinstance(raw_value, str):
            # Try JSON parse first
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, list):
                    parsed_phones = parsed
                elif isinstance(parsed, str):
                    # JSON string containing a single phone
                    parsed_phones = [parsed]
            except:
                # Not JSON - could be CSV or single phone
                if ',' in raw_value:
                    # CSV format
                    parsed_phones = [x.strip() for x in raw_value.split(',') if x.strip()]
                else:
                    # Single phone
                    parsed_phones = [raw_value.strip()] if raw_value.strip() else []
        
        elif isinstance(raw_value, list):
            parsed_phones = raw_value
        
        # Normalize and add phones
        for p in parsed_phones:
            # Convert to string if needed
            p_str = str(p).strip() if p else ''
            if p_str:
                normalized = normalize_phone(p_str)
                if normalized:
                    phones.append(normalized)
                    log.info(f"[WA_BROADCAST] ✅ Extracted phone: {p_str} → {normalized}")
    
    log.info(f"[WA_BROADCAST] After direct extraction: {len(phones)} phones")
    
    # 2) Try lead_ids - fetch from DB
    lead_id_field_names = ['lead_ids', 'leadIds', 'leads', 'lead_id']
    for field_name in lead_id_field_names:
        lead_ids = payload.get(field_name)
        if not lead_ids:
            continue
        
        log.info(f"[WA_BROADCAST] Found {field_name}={str(lead_ids)[:200]}")
        
        # Parse lead IDs
        parsed_ids = []
        if isinstance(lead_ids, str):
            try:
                parsed_ids = json.loads(lead_ids)
            except:
                # Try CSV
                parsed_ids = [int(x.strip()) for x in lead_ids.split(',') if x.strip().isdigit()]
        elif isinstance(lead_ids, list):
            parsed_ids = [int(x) for x in lead_ids if str(x).isdigit()]
        
        if parsed_ids:
            from server.models_sql import Lead
            log.info(f"[WA_BROADCAST] Querying DB for {len(parsed_ids)} lead IDs")
            
            db_phones = (
                Lead.query
                .with_entities(Lead.phone_e164)
                .filter(Lead.tenant_id == business_id, Lead.id.in_(parsed_ids))
                .all()
            )
            
            for p_tuple in db_phones:
                if p_tuple[0]:
                    normalized = normalize_phone(p_tuple[0])
                    if normalized:
                        phones.append(normalized)
                        log.info(f"[WA_BROADCAST] ✅ From lead: {p_tuple[0]} → {normalized}")
            
            log.info(f"[WA_BROADCAST] Found {len(db_phones)} phones from {len(parsed_ids)} lead_ids")
            break  # Found lead_ids, no need to check other field names
    
    log.info(f"[WA_BROADCAST] After lead_ids: {len(phones)} phones")
    
    # 3) Try CSV file upload
    if 'csv_file' in files:
        log.info(f"[WA_BROADCAST] Processing CSV file")
        csv_phones = parse_csv_phones(files['csv_file'])
        phones.extend(csv_phones)
        log.info(f"[WA_BROADCAST] Found {len(csv_phones)} phones from CSV")
    
    log.info(f"[WA_BROADCAST] After CSV: {len(phones)} phones")
    
    # 4) Try statuses - query by status
    status_field_names = ['statuses', 'status', 'lead_statuses']
    for field_name in status_field_names:
        statuses = payload.get(field_name)
        if not statuses:
            continue
        
        log.info(f"[WA_BROADCAST] Found {field_name}={str(statuses)[:200]}")
        
        # Parse statuses
        parsed_statuses = []
        if isinstance(statuses, str):
            try:
                parsed_statuses = json.loads(statuses)
            except:
                # Try CSV
                parsed_statuses = [x.strip() for x in statuses.split(',') if x.strip()]
        elif isinstance(statuses, list):
            parsed_statuses = statuses
        
        if parsed_statuses:
            from server.models_sql import Lead
            log.info(f"[WA_BROADCAST] Querying DB for statuses={parsed_statuses}")
            
            db_phones = (
                Lead.query
                .with_entities(Lead.phone_e164)
                .filter(Lead.tenant_id == business_id, Lead.status.in_(parsed_statuses))
                .all()
            )
            
            for p_tuple in db_phones:
                if p_tuple[0]:
                    normalized = normalize_phone(p_tuple[0])
                    if normalized:
                        phones.append(normalized)
            
            log.info(f"[WA_BROADCAST] Found {len(db_phones)} phones from statuses")
            break  # Found statuses, no need to check other field names
    
    log.info(f"[WA_BROADCAST] After statuses: {len(phones)} phones")
    
    # 5) 🔥 LAST RESORT: Try to extract phones from message_text or any other text field
    # Look for phone numbers in ANY string field
    import re
    phone_pattern = re.compile(r'\+?\d[\d\s\-\(\)]{7,}')  # Match phone-like patterns
    
    for key, value in payload.items():
        if isinstance(value, str) and len(value) < 1000:  # Don't process huge strings
            matches = phone_pattern.findall(value)
            for match in matches:
                normalized = normalize_phone(match)
                if normalized:
                    phones.append(normalized)
                    log.info(f"[WA_BROADCAST] ✅ Extracted from {key}: {match} → {normalized}")
    
    # Deduplicate and sort
    phones = sorted(set(p for p in phones if p))
    
    log.info(f"[WA_BROADCAST] 🏁 FINAL: {len(phones)} unique phones extracted")
    if phones:
        log.info(f"[WA_BROADCAST] Sample phones: {phones[:3]}")
    
    return phones


@whatsapp_bp.route('/broadcasts', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def create_broadcast():
    """
    Create a new WhatsApp broadcast campaign
    ✅ FIX: Enhanced validation and logging per problem statement requirements
    🔥 FIX: Handle both JSON and form-data requests
    """
    try:
        from server.routes_crm import get_business_id
        from server.models_sql import WhatsAppBroadcast, WhatsAppBroadcastRecipient, Lead
        import json
        
        business_id = get_business_id()
        user = session.get('al_user') or session.get('user', {})
        user_id = user.get('id')
        
        # 🔥 USE BULK GATE: Check if enqueue is allowed
        try:
            # ✅ Use unified jobs wrapper for BulkGate
            from server.services.jobs import get_redis
            redis_conn = get_redis()
            
            from server.services.bulk_gate import get_bulk_gate
            bulk_gate = get_bulk_gate(redis_conn)
            
            if bulk_gate:
                # Check if enqueue is allowed
                allowed, reason = bulk_gate.can_enqueue(
                    business_id=business_id,
                    operation_type='broadcast_whatsapp',
                    user_id=user_id
                )
                
                if not allowed:
                    return jsonify({"ok": False, "error": reason}), 429
        except Exception as e:
            logger.warning(f"BulkGate check failed (proceeding anyway): {e}")
        
        # ✅ FIX: Log incoming request for debugging
        log.info(f"[WA_BROADCAST] Incoming request from business_id={business_id}, user={user_id}")
        log.info(f"[WA_BROADCAST] Content-Type: {request.content_type}")
        log.info(f"[WA_BROADCAST] Form keys: {list(request.form.keys())}")
        log.info(f"[WA_BROADCAST] Files: {list(request.files.keys())}")
        
        # 🔥 SIMPLIFIED: Build a unified payload from ALL possible sources
        # Merge JSON, form, and query params - accept data from ANYWHERE!
        payload_dict = {}
        
        # 1) Try JSON body
        try:
            json_data = request.get_json(silent=True) or {}
            if json_data:
                payload_dict.update(json_data)
                log.info(f"[WA_BROADCAST] Found JSON data with keys: {list(json_data.keys())}")
        except:
            pass
        
        # 2) Try form data
        if request.form:
            payload_dict.update(dict(request.form))
            log.info(f"[WA_BROADCAST] Found form data with keys: {list(request.form.keys())}")
        
        # 3) Try query parameters
        if request.args:
            payload_dict.update(dict(request.args))
            log.info(f"[WA_BROADCAST] Found query params with keys: {list(request.args.keys())}")
        
        # 4) Get metadata fields (with defaults)
        provider = payload_dict.get('provider', 'meta')
        message_type = payload_dict.get('message_type', 'text')  # Default to 'text' for simplicity
        template_id = payload_dict.get('template_id')
        template_name = payload_dict.get('template_name')
        message_text = payload_dict.get('message_text', '')
        audience_source = payload_dict.get('audience_source', 'manual')
        
        # ✅ FIX: Convert attachment_id to int (comes as string from FormData)
        attachment_id = payload_dict.get('attachment_id')
        if attachment_id:
            try:
                attachment_id = int(attachment_id)
            except (ValueError, TypeError):
                log.warning(f"[WA_BROADCAST] Invalid attachment_id: {attachment_id}")
                attachment_id = None
        
        log.info(f"[WA_BROADCAST] provider={provider}, message_type={message_type}, audience_source={audience_source}, attachment_id={attachment_id}")
        log.info(f"[WA_BROADCAST] message_text preview: {message_text[:100] if message_text else 'none'}")
        
        # Validate attachment if provided
        media_url = None
        if attachment_id:
            from server.models_sql import Attachment
            from server.services.attachment_service import get_attachment_service
            
            attachment = db.session.query(Attachment).filter_by(
                id=attachment_id,
                business_id=business_id,
                is_deleted=False
            ).first()
            
            if not attachment:
                return jsonify({
                    'ok': False,
                    'error': 'attachment_not_found',
                    'message': 'הקובץ שנבחר לא נמצא'
                }), 404
            
            if not attachment.channel_compatibility.get('broadcast', False):
                return jsonify({
                    'ok': False,
                    'error': 'attachment_not_compatible',
                    'message': f'הקובץ {attachment.filename_original} לא נתמך בתפוצות WhatsApp'
                }), 400
            
            # Generate signed URL for media
            attachment_service = get_attachment_service()
            media_url = attachment_service.generate_signed_url(
                attachment.id,
                attachment.storage_path,
                ttl_minutes=1440  # 24 hours for broadcasts
            )
            
            # Determine message type from mime if not explicitly set
            if message_type == 'text' and attachment.mime_type:
                if attachment.mime_type.startswith('image/'):
                    message_type = 'image'
                elif attachment.mime_type.startswith('video/'):
                    message_type = 'video'
                elif attachment.mime_type.startswith('audio/'):
                    message_type = 'audio'
                elif attachment.mime_type == 'application/pdf':
                    message_type = 'document'
            
            log.info(f"[WA_BROADCAST] Using media attachment: {attachment.filename_original} ({message_type})")
        
        # 🔥 SIMPLIFIED RECIPIENT RESOLUTION - Accept phones from ANYWHERE!
        log.info(f"[WA_BROADCAST] Using SIMPLIFIED recipient resolver (accepts phones from ANY source)")
        
        # Extract phones using simplified resolver
        phones = extract_phones_simplified(payload_dict, request.files, business_id)
        
        # Convert phones to recipient objects
        recipients = [{'phone': phone, 'lead_id': None} for phone in phones]
        
        log.info(f"[WA_BROADCAST] Resolved {len(recipients)} unique recipients")
        
        # ✅ FIX: Enhanced error message with diagnostics and clearer guidance
        if len(recipients) == 0:
            error_details = {
                'error_code': 'NO_RECIPIENTS',
                'business_id': business_id,
                'payload_keys': list(payload_dict.keys()),
                'form_keys': list(request.form.keys()),
                'files_keys': list(request.files.keys()),
                'args_keys': list(request.args.keys())
            }
            
            log.error(f"[WA_BROADCAST] No recipients found: {error_details}")
            
            # 🔥 CLEARER ERROR MESSAGE per requirements
            error_msg = '''
לא נמצאו נמענים! אפשר לשלוח תפוצה באחת מהדרכים הבאות:
1. העבר מספרי טלפון ישירות (phones=[...])
2. העבר מזהי לידים (lead_ids=[...])  
3. העלה קובץ CSV עם מספרי טלפון
4. בחר סטטוסים של לידים (statuses=[...])
5. הדבק מספרי טלפון בהודעה עצמה

דוגמה: {"phones": ["+972501234567", "+972521234567"], "message_text": "שלום"}
            '''.strip()
            
            return jsonify({
                'ok': False,
                'error_code': 'NO_RECIPIENTS',
                'message': error_msg,
                'details': error_details
            }), 400  # Use 400 instead of 422 for simpler handling
        
        # Limit total recipients
        MAX_RECIPIENTS = 10000
        if len(recipients) > MAX_RECIPIENTS:
            log.error(f"[WA_BROADCAST] Too many recipients: {len(recipients)} > {MAX_RECIPIENTS}")
            return jsonify({
                'success': False,
                'message': f'יותר מדי נמענים (מקסימום {MAX_RECIPIENTS})'
            }), 400
        
        # ✅ FIX: Normalize phone numbers to E.164 format with validation
        import re
        normalized_recipients = []
        invalid_phones = []
        
        for recipient in recipients:
            phone = recipient['phone']
            # Remove all non-digits
            phone_digits = re.sub(r'\D', '', phone)
            
            # Validate minimum length
            if len(phone_digits) < 9:
                invalid_phones.append({'phone': phone, 'reason': 'too_short'})
                continue
            
            # Ensure it starts with +
            if not phone.startswith('+'):
                # Assume Israeli number if doesn't start with country code
                if phone_digits.startswith('972'):
                    phone = '+' + phone_digits
                elif phone_digits.startswith('0'):
                    phone = '+972' + phone_digits[1:]
                else:
                    # If no country code and doesn't start with 0, assume Israeli mobile
                    phone = '+972' + phone_digits
            else:
                phone = '+' + phone_digits
            
            # Final E.164 validation (must start with + and have 10-15 digits)
            if not re.match(r'^\+\d{10,15}$', phone):
                invalid_phones.append({'phone': recipient['phone'], 'reason': 'invalid_format'})
                continue
            
            normalized_recipients.append({
                'phone': phone,
                'lead_id': recipient.get('lead_id')
            })
        
        log.info(f"[WA_BROADCAST] Normalized {len(normalized_recipients)} phones, invalid={len(invalid_phones)}")
        
        # ✅ FIX BUILD 200+: Log normalized count with sample
        sample_phones = [r['phone'] for r in normalized_recipients[:3]]
        log.info(f"[WA_BROADCAST] normalized_count={len(normalized_recipients)} sample={sample_phones}")
        
        # ✅ ENHANCEMENT 5: Report invalid recipients count
        if invalid_phones:
            log.warning(f"[WA_BROADCAST] Invalid phones: {invalid_phones[:5]}...")  # Log first 5
        
        # If all phones are invalid, return error with details
        if len(normalized_recipients) == 0 and len(invalid_phones) > 0:
            return jsonify({
                'ok': False,
                'error_code': 'all_phones_invalid',
                'message': 'כל המספרים שנבחרו לא תקינים',
                'invalid_recipients_count': len(invalid_phones),
                'details': {
                    'invalid_phones': invalid_phones[:10]  # Return first 10 for debugging
                }
            }), 400
        
        # Create broadcast campaign
        broadcast = WhatsAppBroadcast()
        broadcast.business_id = business_id
        broadcast.provider = provider
        broadcast.message_type = message_type
        broadcast.template_id = template_id
        broadcast.template_name = template_name
        broadcast.message_text = message_text
        
        # Build audience_filter with media info and raw request
        audience_filter_data = {
            'raw_request': dict(payload_dict) if payload_dict else {}
        }
        
        # Add media info if attachment provided
        if media_url:
            audience_filter_data['media_url'] = media_url
            audience_filter_data['attachment_id'] = attachment_id
        
        broadcast.audience_filter = audience_filter_data
        broadcast.total_recipients = len(normalized_recipients)
        broadcast.created_by = user_id
        broadcast.status = 'pending'
        
        db.session.add(broadcast)
        db.session.flush()  # Get the ID
        
        log.info(f"[WA_BROADCAST] Created broadcast campaign {broadcast.id}")
        
        # Create recipient records
        for recipient in normalized_recipients:
            br = WhatsAppBroadcastRecipient()
            br.broadcast_id = broadcast.id
            br.business_id = business_id
            br.phone = recipient['phone']
            br.lead_id = recipient.get('lead_id')
            br.status = 'queued'
            db.session.add(br)
        
        db.session.commit()
        
        log.info(f"✅ [WA_BROADCAST] broadcast_id={broadcast.id} total={len(normalized_recipients)} queued={len(normalized_recipients)}")
        
        # ✅ SSOT: Enqueue RQ job with broadcast_id directly (no BackgroundJob)
        try:
            from rq import Queue
            import redis
            
            # Enqueue to RQ broadcasts queue
            REDIS_URL = os.getenv('REDIS_URL')
            if not REDIS_URL:
                log.error(f"❌ [WA_BROADCAST] REDIS_URL not set, cannot enqueue broadcast job")
                broadcast.status = 'failed'
                db.session.commit()
                return jsonify({
                    'success': False,
                    'message': 'Redis not configured - cannot process broadcast'
                }), 503
            
            # ✅ Use unified jobs wrapper
            from server.services.jobs import enqueue, get_redis
            
            # Get Redis for BulkGate
            redis_conn = get_redis()
            
            # Acquire lock and record enqueue BEFORE actually enqueuing
            try:
                from server.services.bulk_gate import get_bulk_gate
                bulk_gate = get_bulk_gate(redis_conn)
                
                if bulk_gate:
                    # Acquire lock for this operation
                    lock_acquired = bulk_gate.acquire_lock(
                        business_id=business_id,
                        operation_type='broadcast_whatsapp',
                        job_id=broadcast.id
                    )
                    
                    # Record the enqueue
                    bulk_gate.record_enqueue(
                        business_id=business_id,
                        operation_type='broadcast_whatsapp'
                    )
            except Exception as e:
                log.warning(f"BulkGate lock/record failed (proceeding anyway): {e}")
            
            # Import and enqueue the job function with broadcast_id
            from server.jobs.broadcast_job import process_broadcast_job
            rq_job = enqueue(
                'broadcasts',
                process_broadcast_job,
                broadcast.id,
                business_id=business_id,
                run_id=broadcast.id,
                job_id=f"broadcast_{broadcast.id}",
                timeout=1800,  # 30 minutes
                ttl=3600
            )
            
            log.info(f"🚀 [WA_BROADCAST] Enqueued RQ job for broadcast_id={broadcast.id}, rq_job_id={rq_job.id}")
                
        except Exception as worker_err:
            log.error(f"❌ [WA_BROADCAST] Failed to enqueue job: {worker_err}")
            import traceback
            traceback.print_exc()
            # Mark broadcast as failed if enqueue fails
            broadcast.status = 'failed'
            db.session.commit()
            return jsonify({
                'success': False,
                'message': f'Failed to enqueue broadcast: {str(worker_err)}'
            }), 500
        
        # ✅ FIX: Return success only AFTER successful enqueue validation
        return jsonify({
            'success': True,
            'broadcast_id': broadcast.id,
            'queued_count': len(normalized_recipients),
            'total_recipients': len(normalized_recipients),
            'sent_count': 0,  # Will be updated as broadcast progresses
            'message': f'תפוצה נוצרה עם {len(normalized_recipients)} נמענים'
        }), 202  # 202 Accepted - processing in background
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error creating broadcast: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@whatsapp_bp.route('/broadcasts/<int:broadcast_id>', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_broadcast_status(broadcast_id):
    """
    Get real-time status of a broadcast campaign with detailed recipient information
    """
    try:
        from server.routes_crm import get_business_id
        from server.models_sql import WhatsAppBroadcast, WhatsAppBroadcastRecipient, Lead
        
        business_id = get_business_id()
        
        broadcast = WhatsAppBroadcast.query.filter_by(
            id=broadcast_id,
            business_id=business_id
        ).first_or_404()
        
        # ✅ FIX: Detect stale broadcasts and auto-mark as failed
        # Wrapped in try-except to ensure status can still be returned even if auto-marking fails
        STALE_THRESHOLD_SECONDS = 5 * 60  # 5 minutes
        
        if broadcast.status == 'running':
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Use updated_at as heartbeat (broadcasts update this field on progress)
            last_activity = broadcast.updated_at or broadcast.started_at or broadcast.created_at
            
            # Ensure timezone-aware
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            
            seconds_since_update = int((now - last_activity).total_seconds())
            
            if seconds_since_update > STALE_THRESHOLD_SECONDS:
                try:
                    log.warning(f"⚠️ STALE BROADCAST DETECTED: broadcast_id={broadcast.id}, business_id={business_id}, "
                               f"seconds_since_update={seconds_since_update}")
                    
                    # Re-check status before marking (prevent race condition with worker)
                    broadcast = WhatsAppBroadcast.query.filter_by(id=broadcast_id).with_for_update().first()
                    if broadcast and broadcast.status == 'running':
                        # Auto-mark as failed to prevent stuck progress bars
                        broadcast.status = 'failed'
                        broadcast.completed_at = now
                        db.session.commit()
                        log.info(f"✅ Auto-marked stale broadcast as failed: broadcast_id={broadcast.id}")
                    else:
                        # Status changed (worker completed it), just rollback
                        db.session.rollback()
                except Exception as e:
                    log.error(f"Failed to auto-mark stale broadcast as failed: {e}")
                    db.session.rollback()
                    # Continue to return current status even if auto-marking failed
        
        # Get detailed recipient status (paginated)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        status_filter = request.args.get('status')  # optional filter: sent, failed, queued
        
        recipients_query = WhatsAppBroadcastRecipient.query.filter_by(
            broadcast_id=broadcast_id
        )
        
        # Apply status filter if provided
        if status_filter:
            recipients_query = recipients_query.filter_by(status=status_filter)
        
        # Paginate
        recipients_paginated = recipients_query.paginate(page=page, per_page=per_page, error_out=False)
        
        recipient_details = []
        for r in recipients_paginated.items:
            # Try to get lead name if available
            lead_name = None
            if r.lead_id:
                lead = Lead.query.get(r.lead_id)
                if lead:
                    lead_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
            
            recipient_details.append({
                'phone': r.phone,
                'lead_name': lead_name,
                'status': r.status,
                'error': r.error_message,
                'sent_at': r.sent_at.isoformat() if r.sent_at else None,
                'delivered_at': r.delivered_at.isoformat() if r.delivered_at else None
            })
        
        creator = User.query.get(broadcast.created_by) if broadcast.created_by else None
        stopper = User.query.get(broadcast.stopped_by) if hasattr(broadcast, 'stopped_by') and broadcast.stopped_by else None
        
        return jsonify({
            'id': broadcast.id,
            'name': broadcast.name or f'תפוצה #{broadcast.id}',
            'provider': broadcast.provider,
            'status': broadcast.status,
            'cancel_requested': broadcast.cancel_requested if hasattr(broadcast, 'cancel_requested') else False,
            'total_recipients': broadcast.total_recipients,
            'processed_count': broadcast.processed_count if hasattr(broadcast, 'processed_count') else (broadcast.sent_count + broadcast.failed_count),
            'sent_count': broadcast.sent_count,
            'failed_count': broadcast.failed_count,
            'cancelled_count': broadcast.cancelled_count if hasattr(broadcast, 'cancelled_count') else 0,
            'created_at': broadcast.created_at.isoformat() if broadcast.created_at else None,
            'started_at': broadcast.started_at.isoformat() if hasattr(broadcast, 'started_at') and broadcast.started_at else None,
            'completed_at': broadcast.completed_at.isoformat() if hasattr(broadcast, 'completed_at') and broadcast.completed_at else None,
            'updated_at': broadcast.updated_at.isoformat() if hasattr(broadcast, 'updated_at') and broadcast.updated_at else None,  # ✅ FIX: Add for frontend staleness detection
            'created_by': creator.name if creator else 'לא ידוע',
            'stopped_by': stopper.name if stopper else None,
            'recipients': recipient_details,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': recipients_paginated.total,
                'pages': recipients_paginated.pages
            }
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching broadcast status: {e}")
        return jsonify({'error': str(e)}), 500


@whatsapp_bp.route('/broadcasts/<int:broadcast_id>/stop', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def stop_broadcast(broadcast_id):
    """
    Stop a running broadcast campaign by setting cancel_requested flag
    ✅ Real cancel: Sets cancel_requested for worker to respect
    """
    try:
        from server.routes_crm import get_business_id
        from server.models_sql import WhatsAppBroadcast
        
        business_id = get_business_id()
        user = session.get('al_user') or session.get('user', {})
        user_id = user.get('id')
        
        broadcast = WhatsAppBroadcast.query.filter_by(
            id=broadcast_id,
            business_id=business_id
        ).first_or_404()
        
        # Check if broadcast can be cancelled
        if broadcast.status not in ['queued', 'running']:
            return jsonify({
                'success': False,
                'message': f'לא ניתן לעצור תפוצה עם סטטוס {broadcast.status}'
            }), 400
        
        # ✅ Real cancel: Set cancel_requested flag for worker to respect
        broadcast.cancel_requested = True
        if hasattr(broadcast, 'stopped_by'):
            broadcast.stopped_by = user_id
        if hasattr(broadcast, 'stopped_at'):
            broadcast.stopped_at = datetime.utcnow()
        
        db.session.commit()
        
        log.info(f"[WA_BROADCAST] broadcast_id={broadcast_id} cancel requested by user_id={user_id}")
        
        return jsonify({
            'success': True,
            'message': 'בקשת ביטול נשלחה - התפוצה תיעצר בקרוב',
            'status': broadcast.status,
            'cancel_requested': True,
            'sent_count': broadcast.sent_count,
            'failed_count': broadcast.failed_count,
            'remaining': broadcast.total_recipients - broadcast.sent_count - broadcast.failed_count
        }), 200
        
    except Exception as e:
        log.error(f"Error stopping broadcast: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================================================
# WHATSAPP MANUAL TEMPLATES API - Custom text templates for broadcasts
# ========================================================================

def get_current_business_id_wa():
    """Get current business ID from authenticated user"""
    if hasattr(g, 'tenant') and g.tenant:
        return g.tenant
    
    # Try session
    user = session.get('al_user') or session.get('user', {})
    return user.get('business_id')


@whatsapp_bp.route('/manual-templates', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('whatsapp_inbox')
def list_manual_templates():
    """🔥 FIX F: List all WhatsApp manual templates for the current business
    
    Handles missing table gracefully - returns empty list if table doesn't exist
    """
    try:
        business_id = get_current_business_id_wa()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        from sqlalchemy import text as sa_text
        
        # 🔥 FIX F: Try to query templates, but handle missing table gracefully
        try:
            result = db.session.execute(
                sa_text("""
                    SELECT id, name, message_text, is_active, created_at, updated_at
                    FROM whatsapp_manual_templates
                    WHERE business_id = :business_id AND is_active = TRUE
                    ORDER BY created_at DESC
                """),
                {"business_id": business_id}
            ).fetchall()
            
            templates = []
            for row in result:
                templates.append({
                    'id': row[0],
                    'name': row[1],
                    'message_text': row[2],
                    'is_active': row[3],
                    'created_at': row[4].isoformat() if row[4] else None,
                    'updated_at': row[5].isoformat() if row[5] else None
                })
            
            return jsonify({'ok': True, 'templates': templates}), 200
            
        except Exception as db_err:
            # 🔥 FIX F: Table might not exist - return empty list gracefully
            log.warning(f"[WA_MANUAL_TEMPLATES] Could not load templates (table may not exist): {db_err}")
            return jsonify({'ok': True, 'templates': [], 'warning': 'Templates table not available'}), 200
        
    except Exception as e:
        log.exception("[WA_MANUAL_TEMPLATES] Failed to list templates")
        # 🔥 FIX F: Always return gracefully, never 500
        return jsonify({'ok': True, 'templates': [], 'error': str(e)}), 200


@whatsapp_bp.route('/manual-templates', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def create_manual_template():
    """Create a new WhatsApp manual template"""
    try:
        business_id = get_current_business_id_wa()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json() or {}
        
        name = data.get('name', '').strip()
        message_text = data.get('message_text', '').strip()
        
        if not name:
            return jsonify({'ok': False, 'error': 'Template name is required'}), 400
        if not message_text:
            return jsonify({'ok': False, 'error': 'Template message text is required'}), 400
        
        # Get current user ID
        user = session.get('al_user') or session.get('user', {})
        user_id = user.get('id')
        
        from sqlalchemy import text as sa_text
        
        result = db.session.execute(
            sa_text("""
                INSERT INTO whatsapp_manual_templates 
                (business_id, name, message_text, created_by_user_id, is_active, created_at, updated_at)
                VALUES (:business_id, :name, :message_text, :user_id, TRUE, NOW(), NOW())
                RETURNING id, created_at
            """),
            {
                "business_id": business_id,
                "name": name,
                "message_text": message_text,
                "user_id": user_id
            }
        )
        row = result.fetchone()
        db.session.commit()
        
        log.info(f"[WA_MANUAL_TEMPLATES] Created template: id={row[0]}, name={name}, business_id={business_id}")
        
        return jsonify({
            'ok': True,
            'template': {
                'id': row[0],
                'name': name,
                'message_text': message_text,
                'created_at': row[1].isoformat() if row[1] else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        log.exception("[WA_MANUAL_TEMPLATES] Failed to create template")
        return jsonify({'ok': False, 'error': str(e)}), 500


@whatsapp_bp.route('/manual-templates/<int:template_id>', methods=['PATCH'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def update_manual_template(template_id: int):
    """Update a WhatsApp manual template"""
    try:
        business_id = get_current_business_id_wa()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json() or {}
        
        from sqlalchemy import text as sa_text
        
        # Check template exists
        existing = db.session.execute(
            sa_text("SELECT id FROM whatsapp_manual_templates WHERE id = :id AND business_id = :business_id"),
            {"id": template_id, "business_id": business_id}
        ).fetchone()
        
        if not existing:
            return jsonify({'ok': False, 'error': 'Template not found'}), 404
        
        # Allowlist of updatable fields
        ALLOWED_FIELDS = {'name', 'message_text', 'is_active'}
        
        updates = []
        params = {"id": template_id, "business_id": business_id}
        
        for field in ALLOWED_FIELDS:
            if field in data:
                if field == 'is_active':
                    updates.append(f"{field} = :{field}")
                    params[field] = bool(data[field])
                else:
                    updates.append(f"{field} = :{field}")
                    params[field] = str(data[field]).strip()
        
        if not updates:
            return jsonify({'ok': False, 'error': 'No fields to update'}), 400
        
        updates.append("updated_at = NOW()")
        
        db.session.execute(
            sa_text(f"""
                UPDATE whatsapp_manual_templates
                SET {', '.join(updates)}
                WHERE id = :id AND business_id = :business_id
            """),
            params
        )
        db.session.commit()
        
        log.info(f"[WA_MANUAL_TEMPLATES] Updated template: id={template_id}, business_id={business_id}")
        
        return jsonify({'ok': True, 'message': 'Template updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        log.exception("[WA_MANUAL_TEMPLATES] Failed to update template")
        return jsonify({'ok': False, 'error': str(e)}), 500


@whatsapp_bp.route('/manual-templates/<int:template_id>', methods=['DELETE'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
def delete_manual_template(template_id: int):
    """Delete (soft-delete) a WhatsApp manual template"""
    try:
        business_id = get_current_business_id_wa()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        from sqlalchemy import text as sa_text
        
        result = db.session.execute(
            sa_text("""
                UPDATE whatsapp_manual_templates
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = :id AND business_id = :business_id
                RETURNING id
            """),
            {"id": template_id, "business_id": business_id}
        )
        row = result.fetchone()
        db.session.commit()
        
        if not row:
            return jsonify({'ok': False, 'error': 'Template not found'}), 404
        
        log.info(f"[WA_MANUAL_TEMPLATES] Deleted template: id={template_id}, business_id={business_id}")
        
        return jsonify({'ok': True, 'message': 'Template deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        log.exception("[WA_MANUAL_TEMPLATES] Failed to delete template")
        return jsonify({'ok': False, 'error': str(e)}), 500
