import os, requests, logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session, g, current_app
from server.extensions import csrf
from server.auth_api import require_api_auth
from server.db import db
from server.models_sql import WhatsAppConversationState, LeadReminder, Business, User

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
    """BUILD 136: SECURE multi-tenant status - each business sees only its own QR/creds"""
    try:
        # BUILD 136: Get tenant from AUTHENTICATED session (secure)
        t = tenant_id_from_ctx()
        _, qr_txt, creds = get_auth_dir(t)
        
        # Check files for this specific tenant ONLY
        has_qr = os.path.exists(qr_txt)
        connected = os.path.exists(creds) and not has_qr
        if has_qr or connected:
            return jsonify({"connected": connected, "hasQR": has_qr}), 200
        
        # If no files, try Baileys API
        r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/status", headers=_headers(), timeout=15)
        return jsonify(r.json()), r.status_code
    except:
        return jsonify({"connected": False, "hasQR": False}), 200

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
@csrf.exempt  # User already authenticated, no CSRF needed for this action
def start():
    """B4) תמיד JSON ב-/api/whatsapp/start - לפי ההוראות המדויקות
    
    הערה: endpoint זה לא דורש CSRF כי זה פעולת start פשוטה.
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
def reset():
    t = tenant_id_from_ctx()
    r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/reset", headers=_headers(), timeout=10)
    return jsonify(r.json()), r.status_code

@whatsapp_bp.route('/disconnect', methods=['POST'])
def disconnect():
    t = tenant_id_from_ctx()
    r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/disconnect", headers=_headers(), timeout=10)
    return jsonify(r.json()), r.status_code


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
            state = WhatsAppConversationState(
                business_id=business_id,
                phone=phone,
                ai_active=active,
                updated_by=user_id
            )
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
            formatted_messages.append({
                "id": str(m.id),
                "direction": m.direction,  # 'in' or 'out'
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
    
    settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
    if not settings:
        settings = BusinessSettings()
        settings.tenant_id = business_id
        db.session.add(settings)
    
    # העדכון כאן - אם יש שגיאה, api_handler יטפל
    settings.ai_prompt = data.get('whatsapp_prompt', '')
    db.session.commit()  # api_handler יעשה rollback אם נכשל
    
    # ✅ CRITICAL: Invalidate AI service cache after prompt update
    import logging
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
            log.warning("Baileys webhook: Unauthorized request")
            return jsonify({"error": "unauthorized"}), 401
        
        data = request.get_json()
        tenant_id = data.get('tenantId')
        if not tenant_id:
            log.error("❌ CRITICAL: No tenantId in webhook payload - cannot process!")
            return jsonify({"error": "missing_tenant_id"}), 400
        payload = data.get('payload', {})
        messages = payload.get('messages', [])
        
        log.info(f"📨 Baileys webhook: {len(messages)} message(s) from tenant {tenant_id}")
        
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
            log.info(f"✅ Resolved business_id={business_id} from tenantId={tenant_id}")
        else:
            log.warning(f"⚠️ Using fallback business_id={business_id} ({status}) for tenantId={tenant_id}")
        
        # ✅ Ensure business_id is valid
        if not business_id:
            log.error(f"❌ No valid business_id found for tenantId={tenant_id}")
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
                recent_outbound = WhatsAppMessage.query.filter_by(
                    business_id=business_id,
                    to_number=from_number,
                    direction='outbound'
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
                
                log.info(f"📱 Processing message from {from_number}: {message_text[:50]}...")
                
                # ✅ FIX: Use correct CustomerIntelligence class with validated business_id
                ci_service = CustomerIntelligence(business_id=business_id)
                customer, lead, was_created = ci_service.find_or_create_customer_from_whatsapp(
                    phone_number=from_number,
                    message_text=message_text
                )
                
                action = "created" if was_created else "updated"
                log.info(f"✅ {action} customer/lead for {from_number}")
                
                # ✅ Check if message already exists (prevent duplicates from webhook retries)
                existing_msg = WhatsAppMessage.query.filter_by(
                    business_id=business_id,
                    to_number=from_number,
                    body=message_text,
                    direction='inbound'
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
                wa_msg.direction = 'inbound'
                wa_msg.provider = 'baileys'
                wa_msg.status = 'received'
                db.session.add(wa_msg)
                db.session.commit()
                
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
                
                # ✅ BUILD 122: Load conversation history for AI context (10 messages)
                previous_messages = []
                try:
                    recent_msgs = WhatsAppMessage.query.filter_by(
                        business_id=business_id,
                        to_number=from_number
                    ).order_by(WhatsAppMessage.created_at.desc()).limit(10).all()
                    
                    # Format as conversation (reversed to chronological order)
                    for msg_hist in reversed(recent_msgs):
                        if msg_hist.direction == 'inbound':
                            previous_messages.append(f"לקוח: {msg_hist.body}")
                        else:
                            previous_messages.append(f"עוזר: {msg_hist.body}")  # ✅ כללי - לא hardcoded!
                    
                    log.info(f"📚 Loaded {len(previous_messages)} previous messages for context")
                except Exception as e:
                    log.warning(f"⚠️ Could not load conversation history: {e}")
                
                # ✅ BUILD 119: Generate AI response with Agent SDK (real actions!)
                try:
                    ai_start = time.time()
                    
                    from server.services.ai_service import get_ai_service
                    ai_service = get_ai_service()
                    
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
                    print(f"⚠️ Agent response failed, using fallback: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    response_text = "שלום! קיבלתי את ההודעה שלך. נציג יחזור אליך בהקדם."
                
                # Send response via Baileys
                send_start = time.time()
                log.info(f"📨 Attempting to send to {from_number} (tenant={tenant_id}): {str(response_text)[:50]}...")
                
                send_result = wa_service.send_message(
                    to=f"{from_number}@s.whatsapp.net",
                    message=response_text,
                    tenant_id=tenant_id  # MULTI-TENANT: Route to correct WhatsApp session
                )
                log.info(f"📨 send_result: {send_result}")
                
                send_duration = time.time() - send_start
                log.info(f"📤 Send duration: {send_duration:.2f}s")
                
                if send_result.get('status') == 'sent':
                    # Save outgoing message
                    out_msg = WhatsAppMessage()
                    out_msg.business_id = business_id
                    out_msg.to_number = from_number
                    out_msg.body = response_text
                    out_msg.message_type = 'text'
                    out_msg.direction = 'outbound'
                    out_msg.provider = 'baileys'
                    out_msg.status = 'sent'
                    db.session.add(out_msg)
                    db.session.commit()
                    log.info(f"✅ Sent auto-response to {from_number}")
                    processed_count += 1
                
                msg_duration = time.time() - msg_start
                log.info(f"⏱️ Message processed in {msg_duration:.2f}s")
                
            except Exception as e:
                print(f"❌ ERROR processing message: {e}", flush=True)
                import traceback
                traceback.print_exc()
                log.error(f"❌ Error processing message: {e}")
        
        overall_duration = time.time() - overall_start
        log.info(f"🏁 Total processing: {overall_duration:.2f}s for {len(messages)} message(s)")
        
        processed = processed_count
        
        return jsonify({"ok": True, "processed": processed}), 200
        
    except Exception as e:
        log.error(f"❌ Baileys webhook error: {e}")
        import traceback
        traceback.print_exc()
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
        
        wa_service = get_whatsapp_service(tenant_id=tenant_id)
        
        # התאמת פורמט המספר (אם נדרש)
        formatted_number = to_number
        if '@' not in formatted_number:
            formatted_number = f"{to_number}@s.whatsapp.net"
        
        send_result = wa_service.send_message(formatted_number, message, tenant_id=tenant_id)
        
        if send_result.get('status') == 'sent':
            # שמירת ההודעה בבסיס הנתונים
            wa_msg = WhatsAppMessage()
            wa_msg.business_id = business_id
            wa_msg.to_number = to_number.replace('@s.whatsapp.net', '')
            wa_msg.body = message
            wa_msg.message_type = 'text'
            wa_msg.direction = 'outbound'
            wa_msg.provider = send_result.get('provider', 'unknown')
            wa_msg.provider_message_id = send_result.get('sid')
            wa_msg.status = 'sent'
            
            db.session.add(wa_msg)
            db.session.commit()
            
            return {
                "ok": True, 
                "message_id": wa_msg.id,
                "provider": send_result.get('provider')
            }
        else:
            return {
                "ok": False, 
                "error": send_result.get('error', 'send_failed')
            }, 500
            
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


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
        reminder = LeadReminder(
            tenant_id=business_id,
            lead_id=None,  # System notification - not related to a lead
            due_at=datetime.utcnow(),  # Due immediately
            note="חיבור הווטסאפ נותק - יש להיכנס להגדרות ולחבר מחדש",
            description="חיבור הווטסאפ לעסק נותק. יש להיכנס להגדרות WhatsApp ולסרוק את קוד ה-QR מחדש כדי להתחבר.",
            channel='ui',
            priority='high',
            reminder_type='system_whatsapp_disconnect',
            created_by=owner.id if owner else None
        )
        
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