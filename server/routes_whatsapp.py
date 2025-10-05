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
def qr():
    """B4) תמיד JSON - QR route לפי ההוראות"""
    # קריאה מקבצים (tenant אחיד business_1)
    if os.path.exists(QR_TXT):
        with open(QR_TXT, "r", encoding="utf-8") as f:
            qr_text = f.read().strip()
        return jsonify({"dataUrl": None, "qrText": qr_text}), 200
    
    # אם אין קבצים, ננסה את המערכת הנוכחית
    t = tenant_id_from_ctx()
    try:
        r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/qr", headers=_headers(), timeout=10)
        if r.status_code == 404:           # אין QR כרגע
            return jsonify({"dataUrl": None, "qrText": None}), 200  # תמיד JSON!
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"dataUrl": None, "qrText": None, "error": str(e)}), 200  # תמיד JSON!

@whatsapp_bp.route('/start', methods=['POST'])
def start():
    """B4) תמיד JSON ב-/api/whatsapp/start - לפי ההוראות"""
    return jsonify({'ok': True}), 200

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