import os, requests, logging, csv, io
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session, g, current_app
from server.extensions import csrf
from server.auth_api import require_api_auth
from server.db import db
from server.models_sql import WhatsAppConversationState, LeadReminder, Business, User
from server.services.whatsapp_session_service import update_session_activity

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/api/whatsapp')
internal_whatsapp_bp = Blueprint('internal_whatsapp', __name__, url_prefix='/api/internal/whatsapp')
BAILEYS_BASE = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
INT_SECRET   = os.getenv('INTERNAL_SECRET')
log = logging.getLogger(__name__)

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
    Mask a secret for secure logging using SHA256 hash
    Returns first 6 characters of SHA256 hash for identification without exposing the secret
    """
    if not secret:
        return "***"
    import hashlib
    secret_hash = hashlib.sha256(secret.encode('utf-8')).hexdigest()
    return secret_hash[:6]  # First 6 chars of hash for log identification

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
    ✅ FIX: Enhanced WhatsApp connection status with health details
    Returns: connected, session_age, last_message_ts, qr_required, active_phone
    """
    try:
        # BUILD 136: Get tenant from AUTHENTICATED session (secure)
        t = tenant_id_from_ctx()
        _, qr_txt, creds = get_auth_dir(t)
        
        # Check files for this specific tenant ONLY
        has_qr = os.path.exists(qr_txt)
        connected = os.path.exists(creds) and not has_qr
        
        # ✅ FIX: Add more health information
        health_info = {
            "connected": connected,
            "hasQR": has_qr,
            "qr_required": has_qr,
            "session_age": None,
            "last_message_ts": None,
            "active_phone": None
        }
        
        # Get session age from file timestamp
        if connected and os.path.exists(creds):
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
                    # Calculate time since last message
                    from datetime import datetime
                    time_since = (datetime.utcnow() - last_msg.created_at).total_seconds()
                    health_info["last_message_age"] = int(time_since)
                    health_info["last_message_age_human"] = f"{int(time_since // 60)}m ago"
        except Exception as db_err:
            log.warning(f"[WA_STATUS] Could not fetch last message: {db_err}")
        
        if has_qr or connected:
            log.info(f"[WA_STATUS] tenant={t} connected={connected} hasQR={has_qr} session_age={health_info.get('session_age')}")
            return jsonify(health_info), 200
        
        # If no files, try Baileys API
        r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/status", headers=_headers(), timeout=15)
        baileys_data = r.json()
        
        # Merge Baileys response with our health info
        health_info.update(baileys_data)
        
        log.info(f"[WA_STATUS] tenant={t} baileys_response={baileys_data}")
        return jsonify(health_info), r.status_code
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
        print(f"Error fetching conversation: {e}")
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
        
        print(f"🏢 BUSINESS RESOLUTION: tenant_id={tenant_id} → business_id={business_id} (status={status})", flush=True)
        
        # 🔥 Get business name for clear logging
        from server.models_sql import Business
        business = Business.query.filter_by(id=business_id).first() if business_id else None
        business_name = business.name if business else "UNKNOWN"
        print(f"🏢 BUSINESS: {business_name} (ID={business_id})", flush=True)
        
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
        overall_start = time.time()
        
        wa_service = get_whatsapp_service(tenant_id=tenant_id)  # MULTI-TENANT: Pass tenant_id for correct WhatsApp session
        processed_count = 0
        
        for msg in messages:
            msg_start = time.time()
            try:
                # Extract message details
                from_number = msg.get('key', {}).get('remoteJid', '').replace('@s.whatsapp.net', '')
                message_text = msg.get('message', {}).get('conversation', '') or \
                              msg.get('message', {}).get('extendedTextMessage', {}).get('text', '')
                
                if not from_number or not message_text:
                    continue
                
                # 🔥 CRITICAL FIX: Check if this is our OWN message echoing back!
                # Sometimes Baileys sends bot's outbound messages back as "incoming"
                # 🔥 BUILD 180: Check both 'out' and 'outbound' for backwards compatibility
                recent_outbound = WhatsAppMessage.query.filter(
                    WhatsAppMessage.business_id == business_id,
                    WhatsAppMessage.to_number == from_number,
                    WhatsAppMessage.direction.in_(['out', 'outbound'])
                ).order_by(WhatsAppMessage.created_at.desc()).first()
                
                if recent_outbound:
                    from datetime import datetime, timedelta
                    time_diff = datetime.utcnow() - recent_outbound.created_at
                    # If we sent a similar message in the last 30 seconds, skip
                    if time_diff < timedelta(seconds=30):
                        # Check if message content is similar (our response echoing)
                        if recent_outbound.body and message_text in recent_outbound.body:
                            print(f"🚫 LOOP PREVENTED: Ignoring echo of our own message to {from_number}", flush=True)
                            log.warning(f"🚫 Ignoring bot echo: {message_text[:50]}...")
                            continue
                        # Also skip if message looks like AI response (Hebrew AI phrases)
                        ai_markers = ['אני כאן', 'כדי לעזור', 'תיאום פגישות', 'אשמח לעזור', 'שלום', 'ברוכים הבאים']
                        if any(marker in message_text for marker in ai_markers) and len(message_text) > 50:
                            print(f"🚫 LOOP PREVENTED: Ignoring AI-like message: {message_text[:50]}...", flush=True)
                            log.warning(f"🚫 Skipping AI-like message (possible echo)")
                            continue
                
                log.info(f"[WA-INCOMING] biz={business_id}, from={from_number}, text={message_text[:50]}...")
                
                # ✅ FIX: Use correct CustomerIntelligence class with validated business_id
                ci_service = CustomerIntelligence(business_id=business_id)
                customer, lead, was_created = ci_service.find_or_create_customer_from_whatsapp(
                    phone_number=from_number,
                    message_text=message_text
                )
                
                action = "created" if was_created else "updated"
                log.info(f"✅ {action} customer/lead for {from_number}")
                
                # ✅ Check if message already exists (prevent duplicates from webhook retries)
                # 🔥 BUILD 180: Check both 'in' and 'inbound' for backwards compatibility
                existing_msg = WhatsAppMessage.query.filter(
                    WhatsAppMessage.business_id == business_id,
                    WhatsAppMessage.to_number == from_number,
                    WhatsAppMessage.body == message_text,
                    WhatsAppMessage.direction.in_(['in', 'inbound'])
                ).order_by(WhatsAppMessage.created_at.desc()).first()
                
                # Skip if same message was received in last 10 seconds (webhook retry)
                if existing_msg:
                    from datetime import datetime, timedelta
                    if (datetime.utcnow() - existing_msg.created_at) < timedelta(seconds=10):
                        log.warning(f"⚠️ Duplicate message detected, skipping: {message_text[:50]}...")
                        continue
                
                # Save incoming message to DB
                wa_msg = WhatsAppMessage()
                wa_msg.business_id = business_id
                wa_msg.to_number = from_number
                wa_msg.body = message_text
                wa_msg.message_type = 'text'
                wa_msg.direction = 'in'  # 🔥 BUILD 180: Consistent 'in'/'out' values
                wa_msg.provider = 'baileys'
                wa_msg.status = 'received'
                db.session.add(wa_msg)
                db.session.commit()
                
                # ✅ BUILD 162: Track session for auto-summary generation
                try:
                    update_session_activity(
                        business_id=business_id,
                        customer_wa_id=from_number,
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
                        phone_number=from_number,
                        message_text=message_text,
                        message_id=wa_msg.id,
                        business_id=business_id  # ✅ FIX: Pass correct business_id
                    )
                    if appointment_result.get('appointment_created'):
                        appointment_created = True
                        log.info(f"📅 Appointment created for {from_number}: {appointment_result.get('appointment_id')}")
                except Exception as e:
                    log.warning(f"⚠️ Appointment check failed: {e}")
                
                # ✅ BUILD 152: Check if AI is enabled for this conversation
                ai_enabled = True  # Default to enabled
                try:
                    from server.models_sql import WhatsAppConversationState
                    conv_state = WhatsAppConversationState.query.filter_by(
                        business_id=business_id,
                        phone=from_number
                    ).first()
                    if conv_state:
                        ai_enabled = conv_state.ai_active
                        log.info(f"[WA-INCOMING] AI state for {from_number}: {'enabled' if ai_enabled else 'DISABLED'}")
                except Exception as e:
                    log.warning(f"[WA-WARN] Could not check AI state: {e}")
                
                # If AI is disabled, skip AI response generation
                if not ai_enabled:
                    log.info(f"[WA-INCOMING] AI disabled for {from_number} - skipping AI response")
                    msg_duration = time.time() - msg_start
                    log.info(f"[WA-INCOMING] Message saved (no AI response) in {msg_duration:.2f}s")
                    continue
                
                # ✅ BUILD 122: Load conversation history for AI context (10 messages)
                previous_messages = []
                try:
                    recent_msgs = WhatsAppMessage.query.filter_by(
                        business_id=business_id,
                        to_number=from_number
                    ).order_by(WhatsAppMessage.created_at.desc()).limit(10).all()
                    
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
                try:
                    db.session.rollback()
                except:
                    pass
                
                ai_start = time.time()
                response_text = None
                
                from server.services.ai_service import get_ai_service
                ai_service = get_ai_service()
                
                try:
                    ai_response = ai_service.generate_response_with_agent(
                        message=message_text,
                        business_id=business_id,
                        context={
                            'phone': from_number,
                            'customer_name': customer.name if customer else None,
                            'lead_status': lead.status if lead else None,
                            'previous_messages': previous_messages,  # ✅ זיכרון שיחה - 10 הודעות!
                            'appointment_created': appointment_created  # ✅ BUILD 93: הפגישה נקבעה!
                        },
                        channel='whatsapp',
                        customer_phone=from_number,
                        customer_name=customer.name if customer else None
                    )
                    print(f"🔍 DEBUG: ai_response type={type(ai_response)}, value={str(ai_response)[:100]}...", flush=True)
                    
                    # ✅ FIX: Handle dict response (text + actions) vs plain string
                    if isinstance(ai_response, dict):
                        response_text = ai_response.get('text', '')
                        actions = ai_response.get('actions', [])
                        print(f"🎯 Agent returned {len(actions)} actions with response", flush=True)
                    else:
                        response_text = str(ai_response)
                        print(f"🎯 Agent returned string response", flush=True)
                    
                    ai_duration = time.time() - ai_start
                    print(f"✅ Agent response ({ai_duration:.2f}s): {str(response_text)[:50]}...", flush=True)
                except Exception as e:
                    print(f"⚠️ Agent failed, trying regular AI response: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    
                    # ✅ BUILD 170.1: Fallback to regular AI (which uses DB prompt!)
                    try:
                        response_text = ai_service.generate_response(
                            message=message_text,
                            business_id=business_id,
                            context={
                                'phone': from_number,
                                'customer_name': customer.name if customer else None,
                                'previous_messages': previous_messages
                            },
                            channel='whatsapp'
                        )
                        print(f"✅ Fallback AI response: {str(response_text)[:50]}...", flush=True)
                    except Exception as e2:
                        print(f"⚠️ Regular AI also failed: {e2}", flush=True)
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
                            return jsonify({"status": "ok", "skipped": True}), 200
                
                # Send response via Baileys
                send_start = time.time()
                log.info(f"[WA-OUTGOING] biz={business_id}, to={from_number}, text={str(response_text)[:50]}...")
                
                send_result = wa_service.send_message(
                    to=f"{from_number}@s.whatsapp.net",
                    message=response_text,
                    tenant_id=tenant_id  # MULTI-TENANT: Route to correct WhatsApp session
                )
                
                send_duration = time.time() - send_start
                log.info(f"[WA-OUTGOING] send_result={send_result.get('status')}, duration={send_duration:.2f}s")
                
                if send_result.get('status') == 'sent':
                    # Save outgoing message
                    out_msg = WhatsAppMessage()
                    out_msg.business_id = business_id
                    out_msg.to_number = from_number
                    out_msg.body = response_text
                    out_msg.message_type = 'text'
                    out_msg.direction = 'out'  # 🔥 BUILD 180: Consistent 'in'/'out' values
                    out_msg.provider = 'baileys'
                    out_msg.status = 'sent'
                    db.session.add(out_msg)
                    db.session.commit()
                    
                    # ✅ BUILD 162: Track session for outgoing message
                    try:
                        update_session_activity(
                            business_id=business_id,
                            customer_wa_id=from_number,
                            direction="out",
                            provider="baileys"
                        )
                    except Exception as e:
                        log.warning(f"⚠️ Session tracking (out) failed: {e}")
                    
                    log.info(f"[WA-OUTGOING] Sent to {from_number} successfully")
                    processed_count += 1
                
                msg_duration = time.time() - msg_start
                log.info(f"[WA-INCOMING] Message processed in {msg_duration:.2f}s")
                
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
    """שליחת הודעה ידנית מנציג - Agent Takeover"""
    data = request.get_json(force=True)
    
    to_number = data.get('to')
    message = data.get('message')
    
    # 🔒 SECURITY: business_id from authenticated session via get_business_id()
    from server.routes_crm import get_business_id
    
    business_id = get_business_id()
    
    if not to_number or not message:
        return {"ok": False, "error": "missing_required_fields"}, 400
    
    try:
        # שליחת הודעה דרך WhatsApp provider
        from server.whatsapp_provider import get_whatsapp_service
        
        # MULTI-TENANT: Create tenant_id from business_id
        if not business_id:
            return {"ok": False, "error": "no_business_id"}, 400
        tenant_id = f"business_{business_id}"
        
        try:
            wa_service = get_whatsapp_service(tenant_id=tenant_id)
        except Exception as e:
            log.error(f"[WA-SEND] Failed to get WhatsApp service: {e}")
            return {"ok": False, "error": f"whatsapp_service_unavailable: {str(e)}"}, 503
        
        # התאמת פורמט המספר (אם נדרש)
        formatted_number = to_number
        if '@' not in formatted_number:
            formatted_number = f"{to_number}@s.whatsapp.net"
        
        try:
            send_result = wa_service.send_message(formatted_number, message, tenant_id=tenant_id)
        except Exception as e:
            log.error(f"[WA-SEND] Send message failed: {e}")
            return {"ok": False, "error": f"send_failed: {str(e)}"}, 500
        
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
                wa_msg.body = message
                wa_msg.message_type = 'text'
                wa_msg.direction = 'out'  # 🔥 BUILD 180: Consistent 'in'/'out' values
                wa_msg.provider = send_result.get('provider', 'unknown')
                wa_msg.provider_message_id = send_result.get('sid') or send_result.get('message_id')
                wa_msg.status = db_status
                
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
    ✅ FIX BUILD 200+: Reliable webhook endpoint for external services (n8n)
    
    This endpoint allows external services to send WhatsApp messages without
    session authentication, using a webhook secret instead.
    
    Key Requirements:
    1. Resolve business_id from X-Webhook-Secret header (NO defaults!)
    2. Webhook must NOT use provider="auto" - explicit baileys only
    3. Internal base URL must be http://baileys:3300 (Docker network)
    4. Pre-send health check: GET {BAILEYS_BASE_URL}/status
    5. Return proof response with provider/message_id
    
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
    
    # ✅ 1) Get and validate webhook secret from header (case-insensitive)
    webhook_secret = request.headers.get('X-Webhook-Secret')
    if not webhook_secret:
        webhook_secret = request.headers.get('x-webhook-secret')
    
    if not webhook_secret:
        log.error(f"[WA_WEBHOOK] Missing X-Webhook-Secret header from {request.remote_addr}")
        return jsonify({
            "ok": False, 
            "error_code": "missing_webhook_secret",
            "message": "X-Webhook-Secret header is required"
        }), 401
    
    # ✅ 2) Resolve business from webhook secret (NO DEFAULT FALLBACK!)
    business = Business.query.filter_by(webhook_secret=webhook_secret).first()
    
    if not business:
        secret_hash = mask_secret_for_logging(webhook_secret)
        log.error(f"[WA_WEBHOOK] Invalid webhook secret: secret_hash={secret_hash}, ip={request.remote_addr}")
        return jsonify({
            "ok": False, 
            "error_code": "invalid_webhook_secret",
            "message": "Invalid webhook secret - no matching business found"
        }), 401
    
    business_id = business.id
    
    # ✅ 3) Enhanced logging - prove business resolution
    secret_hash = mask_secret_for_logging(webhook_secret)
    log.info(f"[WA_WEBHOOK] secret_hash={secret_hash}, resolved_business_id={business_id}, resolved_business_name={business.name}, provider={business.whatsapp_provider}")
    
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
        reminder.due_at = datetime.utcnow()  # Due immediately
        reminder.note = "חיבור הווטסאפ נותק - יש להיכנס להגדרות ולחבר מחדש"
        reminder.description = "חיבור הווטסאפ לעסק נותק. יש להיכנס להגדרות WhatsApp ולסרוק את קוד ה-QR מחדש כדי להתחבר."
        reminder.channel = 'ui'
        reminder.priority = 'high'
        reminder.reminder_type = 'system_whatsapp_disconnect'
        reminder.created_by = owner.id if owner else None
        
        db.session.add(reminder)
        db.session.commit()
        
        log.info(f"[WHATSAPP_STATUS] ✅ Created disconnect notification for business_id={business_id}")
        
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
        
        for reminder in reminders:
            reminder.completed_at = datetime.utcnow()
        
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


@whatsapp_bp.route('/broadcasts', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def create_broadcast():
    """
    Create a new WhatsApp broadcast campaign
    ✅ FIX: Enhanced validation and logging per problem statement requirements
    """
    try:
        from server.routes_crm import get_business_id
        from server.models_sql import WhatsAppBroadcast, WhatsAppBroadcastRecipient, Lead
        import json
        
        business_id = get_business_id()
        user = session.get('al_user') or session.get('user', {})
        user_id = user.get('id')
        
        # ✅ FIX: Log incoming request for debugging
        log.info(f"[WA_BROADCAST] Incoming request from business_id={business_id}, user={user_id}")
        log.info(f"[WA_BROADCAST] Form keys: {list(request.form.keys())}")
        log.info(f"[WA_BROADCAST] Files: {list(request.files.keys())}")
        
        # Parse form data
        provider = request.form.get('provider', 'meta')
        message_type = request.form.get('message_type', 'template')
        template_id = request.form.get('template_id')
        template_name = request.form.get('template_name')
        message_text = request.form.get('message_text', '')
        audience_source = request.form.get('audience_source', 'legacy')  # NEW: leads, import-list, csv, or legacy
        statuses_json = request.form.get('statuses', '[]')
        lead_ids_json = request.form.get('lead_ids', '[]')  # NEW: Direct lead IDs
        import_list_id = request.form.get('import_list_id')  # NEW: Import list ID
        
        # ✅ FIX: Support multiple field names for backwards compatibility (recipients, lead_ids, phones)
        # Frontend might send different field names
        if not lead_ids_json or lead_ids_json == '[]':
            lead_ids_json = request.form.get('recipients', '[]')
        if not lead_ids_json or lead_ids_json == '[]':
            lead_ids_json = request.form.get('phones', '[]')
        
        log.info(f"[WA_BROADCAST] audience_source={audience_source}, provider={provider}, message_type={message_type}")
        log.info(f"[WA_BROADCAST] lead_ids_json={lead_ids_json[:100]}...")
        log.info(f"[WA_BROADCAST] statuses_json={statuses_json}")
        
        # Parse JSON parameters
        try:
            statuses = json.loads(statuses_json)
        except:
            statuses = []
        
        try:
            lead_ids = json.loads(lead_ids_json)
        except:
            lead_ids = []
        
        # ✅ FIX BUILD 200+: Enhanced diagnostic logging per requirements
        # Log incoming keys to understand what frontend sends
        incoming_keys = list(request.form.keys())
        log.info(f"[WA_BROADCAST] incoming_keys={incoming_keys}")
        
        # Get recipients based on audience source
        recipients = []
        
        # ✅ FIX: Track diagnostics for better error messages
        diagnostics = {
            'audience_source': audience_source,
            'lead_ids_count': len(lead_ids),
            'statuses_count': len(statuses),
            'has_csv': 'csv_file' in request.files,
            'import_list_id': import_list_id,
            'incoming_keys': incoming_keys
        }
        
        # NEW: Direct lead selection from system
        if audience_source == 'leads' and lead_ids:
            log.info(f"[WA_BROADCAST] Loading {len(lead_ids)} leads from system")
            leads = Lead.query.filter(
                Lead.tenant_id == business_id,
                Lead.id.in_(lead_ids),
                Lead.phone_e164.isnot(None)
            ).all()
            
            log.info(f"[WA_BROADCAST] Found {len(leads)} leads with phone numbers")
            
            for lead in leads:
                if lead.phone_e164:
                    recipients.append({
                        'phone': lead.phone_e164,
                        'lead_id': lead.id
                    })
        
        # NEW: Import list selection
        elif audience_source == 'import-list' and import_list_id:
            log.info(f"[WA_BROADCAST] Loading leads from import_list_id={import_list_id}")
            leads = Lead.query.filter(
                Lead.tenant_id == business_id,
                Lead.outbound_list_id == int(import_list_id),
                Lead.phone_e164.isnot(None)
            ).all()
            
            log.info(f"[WA_BROADCAST] Found {len(leads)} leads in import list")
            
            for lead in leads:
                if lead.phone_e164:
                    recipients.append({
                        'phone': lead.phone_e164,
                        'lead_id': lead.id
                    })
        
        # CSV file upload
        elif audience_source == 'csv' or (not audience_source or audience_source == 'legacy'):
            # Legacy: From CRM filters (statuses) - backward compatibility
            if statuses:
                log.info(f"[WA_BROADCAST] Loading leads with statuses: {statuses}")
                leads = Lead.query.filter(
                    Lead.tenant_id == business_id,
                    Lead.status.in_(statuses),
                    Lead.phone_e164.isnot(None)
                ).all()
                
                log.info(f"[WA_BROADCAST] Found {len(leads)} leads with statuses {statuses}")
                
                for lead in leads:
                    if lead.phone_e164:
                        recipients.append({
                            'phone': lead.phone_e164,
                            'lead_id': lead.id
                        })
            
            # From CSV file (with validation)
            csv_file = request.files.get('csv_file')
            if csv_file:
                log.info(f"[WA_BROADCAST] Processing CSV file: {csv_file.filename}")
                # Validate file size (max 5MB)
                MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
                csv_file.seek(0, 2)  # Seek to end
                file_size = csv_file.tell()
                csv_file.seek(0)  # Seek back to start
                
                if file_size > MAX_FILE_SIZE:
                    log.error(f"[WA_BROADCAST] CSV file too large: {file_size} bytes")
                    return jsonify({
                        'success': False,
                        'message': 'קובץ גדול מדי (מקסימום 5MB)'
                    }), 400
                
                # Read and parse CSV with row limit
                MAX_ROWS = 10000  # Max 10,000 recipients
                try:
                    stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
                    csv_reader = csv.DictReader(stream)
                    
                    row_count = 0
                    for row in csv_reader:
                        row_count += 1
                        if row_count > MAX_ROWS:
                            log.warning(f"[WA_BROADCAST] CSV row limit exceeded: {row_count} > {MAX_ROWS}")
                            break
                        
                        phone = row.get('phone', '').strip()
                        if phone:
                            recipients.append({
                                'phone': phone,
                                'lead_id': None
                            })
                    
                    log.info(f"[WA_BROADCAST] Loaded {len(recipients)} recipients from CSV")
                except Exception as csv_err:
                    log.error(f"[WA_BROADCAST] CSV parsing error: {csv_err}")
                    return jsonify({
                        'success': False,
                        'message': 'שגיאה בקריאת קובץ CSV'
                    }), 400
        
        # ✅ FIX BUILD 200+: Log recipient counts BEFORE normalization
        log.info(f"[WA_BROADCAST] recipients_count={len(recipients)}, lead_ids_count={len(lead_ids) if lead_ids else 0}, phones_count={len([r for r in recipients if r.get('phone')])}")
        
        # ✅ FIX: Enhanced error message with diagnostics
        if len(recipients) == 0:
            error_details = {
                'missing_field': None,
                'selection_count': 0,
                'business_id': business_id,
                'diagnostics': diagnostics
            }
            
            # Determine what's missing
            if audience_source == 'leads':
                error_details['missing_field'] = 'lead_ids'
                error_details['selection_count'] = len(lead_ids)
                error_msg = f'לא נמצאו נמענים. בחרת {len(lead_ids)} לידים אבל לא נמצאו מספרי טלפון תקינים.'
            elif audience_source == 'import-list':
                error_details['missing_field'] = 'import_list_id'
                error_msg = 'לא נמצאו נמענים ברשימת הייבוא. ייתכן שהרשימה ריקה או שאין מספרי טלפון.'
            elif audience_source == 'csv':
                error_details['missing_field'] = 'csv_file'
                error_msg = 'לא נמצאו נמענים בקובץ ה-CSV. וודא שיש עמודת "phone" עם מספרים תקינים.'
            else:
                error_details['missing_field'] = 'statuses or csv_file'
                error_msg = 'לא נמצאו נמענים. יש לבחור סטטוסים, רשימת ייבוא או להעלות קובץ CSV.'
            
            log.error(f"[WA_BROADCAST] No recipients found: {error_details}")
            
            # ✅ FIX BUILD 200+: Return clear error with expected_one_of format
            return jsonify({
                'ok': False,
                'error_code': 'missing_recipients',
                'expected_one_of': ['recipients', 'phones', 'lead_ids'],
                'got_keys': incoming_keys,
                'message': error_msg,
                'details': error_details
            }), 400
        
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
        broadcast.audience_filter = {'statuses': statuses}
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
        
        # Trigger background worker to process the broadcast
        try:
            import threading
            from server.services.broadcast_worker import process_broadcast
            
            # Run in background thread
            thread = threading.Thread(
                target=process_broadcast,
                args=(broadcast.id,),
                daemon=True
            )
            thread.start()
            log.info(f"🚀 [WA_BROADCAST] Started worker thread for broadcast_id={broadcast.id}")
        except Exception as worker_err:
            log.error(f"❌ [WA_BROADCAST] Failed to start worker: {worker_err}")
            # Don't fail the request - campaign is created, worker can be triggered manually
        
        # ✅ FIX: Return proof of queuing (never return success without queued_count > 0)
        return jsonify({
            'success': True,
            'broadcast_id': broadcast.id,
            'queued_count': len(normalized_recipients),
            'total_recipients': len(normalized_recipients),
            'sent_count': 0,  # Will be updated as broadcast progresses
            'job_id': f"broadcast_{broadcast.id}",  # For tracking
            'message': f'תפוצה נוצרה עם {len(normalized_recipients)} נמענים'
        }), 201
        
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
    Get real-time status of a broadcast campaign
    """
    try:
        from server.routes_crm import get_business_id
        from server.models_sql import WhatsAppBroadcast, WhatsAppBroadcastRecipient
        
        business_id = get_business_id()
        
        broadcast = WhatsAppBroadcast.query.filter_by(
            id=broadcast_id,
            business_id=business_id
        ).first_or_404()
        
        # Get detailed recipient status
        recipients = WhatsAppBroadcastRecipient.query.filter_by(
            broadcast_id=broadcast_id
        ).all()
        
        recipient_details = []
        for r in recipients:
            recipient_details.append({
                'phone': r.phone,
                'status': r.status,
                'error': r.error_message,
                'sent_at': r.sent_at.isoformat() if r.sent_at else None
            })
        
        creator = User.query.get(broadcast.created_by) if broadcast.created_by else None
        
        return jsonify({
            'id': broadcast.id,
            'name': broadcast.name or f'תפוצה #{broadcast.id}',
            'provider': broadcast.provider,
            'status': broadcast.status,
            'total_recipients': broadcast.total_recipients,
            'sent_count': broadcast.sent_count,
            'failed_count': broadcast.failed_count,
            'created_at': broadcast.created_at.isoformat() if broadcast.created_at else None,
            'created_by': creator.name if creator else 'לא ידוע',
            'recipients': recipient_details
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching broadcast status: {e}")
        return jsonify({'error': str(e)}), 500
