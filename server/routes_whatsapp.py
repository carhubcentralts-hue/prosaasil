import os, requests
from flask import Blueprint, jsonify, request
from server.extensions import csrf

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/api/whatsapp')
BAILEYS_BASE = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
INT_SECRET   = os.getenv('INTERNAL_SECRET')

# === B1) QR/סטטוס דרך Flask - tenant אחיד business_1 ===
# בדיוק כמו ב-Node: storage/whatsapp/business_1/auth
AUTH_DIR = os.path.join(os.getcwd(), "storage", "whatsapp", "business_1", "auth")  
QR_TXT   = os.path.join(AUTH_DIR, "qr_code.txt")
CREDS    = os.path.join(AUTH_DIR, "creds.json")
os.makedirs(AUTH_DIR, exist_ok=True)  # וודא שהתיקייה קיימת

def tenant_id_from_ctx():
    # B1) CRITICAL FIX: Always return 'business_1' for unified storage
    # This ensures Flask and Baileys use the same tenant path
    # בדיוק לפי ההוראות - tenant אחיד!
    return 'business_1'

def _headers():
    return {'X-Internal-Secret': INT_SECRET, 'Content-Type': 'application/json'}

@whatsapp_bp.route('/status', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
def status():
    """B4) תמיד JSON - Status route לפי ההוראות"""
    # קריאה מקבצים (tenant אחיד business_1)
    has_qr = os.path.exists(QR_TXT)
    connected = os.path.exists(CREDS) and not has_qr
    if has_qr or connected:
        return jsonify({"connected": connected, "hasQR": has_qr}), 200
    
    # אם אין קבצים, ננסה את המערכת הנוכחית
    try:
        t = tenant_id_from_ctx()
        r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/status", headers=_headers(), timeout=5)
        return jsonify(r.json()), r.status_code
    except:
        return jsonify({"connected": False, "hasQR": False}), 200

@whatsapp_bp.route('/qr', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
def qr():
    """B4) תמיד JSON - QR route לפי ההוראות"""
    # קודם נבדוק קובץ (כי Baileys מוחק מזיכרון אחרי התחברות)
    if os.path.exists(QR_TXT):
        with open(QR_TXT, "r", encoding="utf-8") as f:
            qr_text = f.read().strip()
        if qr_text:  # יש QR בקובץ
            return jsonify({"dataUrl": None, "qrText": qr_text}), 200
    
    # אם אין בקובץ, ננסה לקבל מBaileys
    t = tenant_id_from_ctx()
    try:
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


# === שלב 3: JSON יציב ו-commit/rollback ===
from server.utils.api_guard import api_handler

# === שלב 1: השלמת 3 routes ש-UI מבקש (תואם ל-WhatsAppPage.jsx) ===
from server.models_sql import WhatsAppMessage, Customer
from server.db import db
from sqlalchemy import func

@whatsapp_bp.route('/contacts', methods=['GET'])
def api_wa_contacts():
    business_id = request.args.get("business_id", type=int)
    if not business_id:
        return jsonify({"error":"missing business_id"}), 400
    
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
def api_wa_messages():
    contact_id = request.args.get("contact_id")  # This is the phone number
    if not contact_id:
        return jsonify({"error":"missing contact_id"}), 400
    
    # Get business_id from session or assume business_1 for now
    business_id = 1  # TODO: Get from session/auth context
    
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
@csrf.exempt  # GET requests don't need CSRF
def get_conversation(phone_number):
    """
    Get WhatsApp conversation for a specific phone number
    Returns messages in format expected by WhatsAppChat component
    """
    try:
        # Get business_id from request or default to 1
        business_id = request.args.get('business_id', 1, type=int)
        
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
def api_wa_stats():
    business_id = request.args.get("business_id", type=int)
    if not business_id:
        return jsonify({"error":"missing business_id"}), 400
    
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
        tenant_id = data.get('tenantId', 'business_1')
        payload = data.get('payload', {})
        messages = payload.get('messages', [])
        
        log.info(f"📨 Baileys webhook: {len(messages)} message(s) from tenant {tenant_id}")
        
        if not messages:
            return jsonify({"ok": True, "processed": 0}), 200
        
        # Process each incoming message
        from server.services.customer_intelligence import CustomerIntelligence
        from server.whatsapp_provider import get_whatsapp_service
        
        wa_service = get_whatsapp_service()
        business_id = 1  # Default to business_1
        processed = 0
        
        for msg in messages:
            try:
                # Extract message details
                from_number = msg.get('key', {}).get('remoteJid', '').replace('@s.whatsapp.net', '')
                message_text = msg.get('message', {}).get('conversation', '') or \
                              msg.get('message', {}).get('extendedTextMessage', {}).get('text', '')
                
                if not from_number or not message_text:
                    continue
                
                log.info(f"📱 Processing message from {from_number}: {message_text[:50]}...")
                
                # ✅ FIX: Use correct CustomerIntelligence class
                ci_service = CustomerIntelligence(business_id=business_id)
                customer, lead, was_created = ci_service.find_or_create_customer_from_whatsapp(
                    phone_number=from_number,
                    message_text=message_text
                )
                
                action = "created" if was_created else "updated"
                log.info(f"✅ {action} customer/lead for {from_number}")
                
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
                
                # Generate AI response (simple for now - can be enhanced)
                response_text = f"שלום! קיבלתי את ההודעה שלך. נציג יחזור אליך בהקדם."
                
                # Send response via Baileys
                send_result = wa_service.send_message(
                    to=f"{from_number}@s.whatsapp.net",
                    message=response_text
                )
                
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
                
                processed += 1
                
            except Exception as e:
                log.error(f"❌ Error processing message: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return jsonify({"ok": True, "processed": processed}), 200
        
    except Exception as e:
        log.error(f"❌ Baileys webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@whatsapp_bp.route('/send', methods=['POST'])
@api_handler
def send_manual_message():
    """שליחת הודעה ידנית מנציג - Agent Takeover"""
    data = request.get_json(force=True)
    
    to_number = data.get('to')
    message = data.get('message')
    business_id = data.get('business_id', 1)
    
    if not to_number or not message:
        return {"ok": False, "error": "missing_required_fields"}, 400
    
    try:
        # שליחת הודעה דרך WhatsApp provider
        from server.whatsapp_provider import get_whatsapp_service
        
        wa_service = get_whatsapp_service()
        
        # התאמת פורמט המספר (אם נדרש)
        formatted_number = to_number
        if '@' not in formatted_number:
            formatted_number = f"{to_number}@s.whatsapp.net"
        
        send_result = wa_service.send_message(formatted_number, message)
        
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