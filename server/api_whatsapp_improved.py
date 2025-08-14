# server/api_whatsapp_improved.py
from flask import Blueprint, request, jsonify
from server.authz import auth_required
import logging, uuid, datetime

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/api/whatsapp")
log = logging.getLogger(__name__)

@whatsapp_bp.get("/status")
@auth_required
def get_status():
    """Get WhatsApp connection status"""
    # Mock status - replace with actual Baileys/Twilio integration
    return jsonify({
        "ok": True,
        "connected": False,
        "status": "disconnected",
        "qr_available": True,
        "last_connected": None
    }), 200

@whatsapp_bp.get("/qr")
@auth_required  
def get_qr():
    """Get QR code for WhatsApp connection"""
    # Mock QR - replace with actual Baileys QR generation
    return jsonify({
        "ok": True,
        "qr_code": "mock_qr_data_here",
        "expires_in": 45  # seconds
    }), 200

@whatsapp_bp.post("/send")
@auth_required
def send_message():
    """Send WhatsApp message"""
    data = request.get_json()
    if not data or not data.get("to") or not data.get("text"):
        return jsonify({"error": "to and text required"}), 400
    
    to_number = data["to"]
    message_text = data["text"]
    
    # Mock message sending
    message_id = str(uuid.uuid4())
    
    # Store in mock database
    mock_message = {
        "id": message_id,
        "to": to_number,
        "text": message_text,
        "direction": "outbound",
        "status": "sent",
        "sent_at": datetime.datetime.now().isoformat(),
        "customer_id": data.get("customer_id")  # Link to customer if provided
    }
    
    log.info("WhatsApp message sent: %s to %s", message_id, to_number)
    return jsonify({"ok": True, "message_id": message_id}), 200

@whatsapp_bp.post("/webhook")
def webhook():
    """Handle incoming WhatsApp messages (from Twilio or Meta)"""
    data = request.get_json() or request.form
    
    # Log all incoming webhooks
    log.info("WhatsApp webhook received: %s", data)
    
    # Extract message data (format depends on provider)
    from_number = data.get("From") or data.get("from")
    message_body = data.get("Body") or data.get("text")
    
    if from_number and message_body:
        # Mock message processing
        mock_incoming = {
            "id": str(uuid.uuid4()),
            "from": from_number,
            "text": message_body,
            "direction": "inbound", 
            "status": "received",
            "received_at": datetime.datetime.now().isoformat()
        }
        
        log.info("Processed incoming WhatsApp: %s", mock_incoming["id"])
        
        # Here you would:
        # 1. Link to customer by phone number
        # 2. Generate AI response if needed
        # 3. Store in database
    
    # Always return 200 to acknowledge webhook
    return jsonify({"ok": True}), 200

@whatsapp_bp.get("/messages")
@auth_required
def list_messages():
    """List WhatsApp messages with pagination"""
    try:
        page = max(int(request.args.get("page", 1)), 1)
        limit = min(max(int(request.args.get("limit", 50)), 1), 100)
    except ValueError:
        return jsonify({"error": "invalid paging"}), 400
    
    customer_id = request.args.get("customer_id")
    
    # Mock message history
    mock_messages = [
        {
            "id": "msg-001",
            "from": "+972501234567",
            "to": "business_number",
            "text": "שלום, אני מעוניין בדירה",
            "direction": "inbound",
            "status": "received",
            "timestamp": "2024-01-16T10:30:00Z",
            "customer_id": 1
        },
        {
            "id": "msg-002", 
            "from": "business_number",
            "to": "+972501234567",
            "text": "שלום! אשמח לעזור לך. איזה סוג דירה אתה מחפש?",
            "direction": "outbound",
            "status": "delivered",
            "timestamp": "2024-01-16T10:32:00Z",
            "customer_id": 1
        }
    ]
    
    # Filter by customer if requested
    if customer_id:
        filtered = [m for m in mock_messages if str(m.get("customer_id")) == customer_id]
    else:
        filtered = mock_messages
    
    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    items = filtered[start:end]
    
    return jsonify({
        "page": page,
        "limit": limit,
        "total": total,
        "items": items
    }), 200

@whatsapp_bp.post("/connect")
@auth_required
def connect():
    """Start WhatsApp connection process"""
    # Mock connection start
    log.info("Starting WhatsApp connection")
    return jsonify({
        "ok": True,
        "status": "connecting",
        "qr_available": True
    }), 200

@whatsapp_bp.post("/disconnect")  
@auth_required
def disconnect():
    """Disconnect WhatsApp"""
    # Mock disconnection
    log.info("Disconnecting WhatsApp")
    return jsonify({
        "ok": True,
        "status": "disconnected"
    }), 200