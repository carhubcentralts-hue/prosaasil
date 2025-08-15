# server/api_whatsapp_improved.py
from flask import Blueprint, request, jsonify
from server.authz import auth_required
import logging, uuid, datetime, os, json

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/api/whatsapp")
log = logging.getLogger(__name__)

def check_baileys_status():
    """Check actual Baileys connection status"""
    try:
        auth_folder = "./baileys_auth_info"
        status_file = os.path.join(auth_folder, "status.json")
        qr_file = os.path.join(auth_folder, "qr_code.txt")
        
        # Check if connected
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status = json.load(f)
                return {
                    "connected": status.get("connected", False),
                    "last_connected": status.get("timestamp"),
                    "qr_available": False
                }
        
        # Check if QR available
        if os.path.exists(qr_file):
            with open(qr_file, 'r') as f:
                qr_data = f.read().strip()
                return {
                    "connected": False,
                    "qr_available": True,
                    "qr_code": qr_data
                }
        
        return {"connected": False, "qr_available": False}
    except Exception as e:
        log.error(f"Error checking Baileys status: {e}")
        return {"connected": False, "qr_available": False}

@whatsapp_bp.get("/status")
def get_status():
    """Get WhatsApp connection status - NO AUTH REQUIRED FOR STATUS"""
    status = check_baileys_status()
    return jsonify({
        "ok": True,
        "connected": status.get("connected", False),
        "status": "connected" if status.get("connected") else "disconnected",
        "qr_available": status.get("qr_available", False),
        "last_connected": status.get("last_connected")
    }), 200

@whatsapp_bp.get("/qr")
def get_qr():
    """Get QR code for WhatsApp connection - NO AUTH REQUIRED"""
    status = check_baileys_status()
    
    if status.get("connected"):
        return jsonify({
            "ok": True,
            "connected": True,
            "message": "WhatsApp already connected"
        }), 200
    
    if status.get("qr_available") and status.get("qr_code"):
        return jsonify({
            "ok": True,
            "qr_code": status["qr_code"],
            "expires_in": 45,
            "instructions": "Scan this QR code with WhatsApp on your phone"
        }), 200
    
    return jsonify({
        "ok": False,
        "error": "QR code not available. Please wait for WhatsApp service to generate new QR.",
        "retry_in": 5
    }), 503

@whatsapp_bp.post("/send")
@auth_required
def send_message():
    """Send WhatsApp message via Baileys"""
    data = request.get_json()
    if not data or not data.get("to") or not data.get("text"):
        return jsonify({"error": "to and text required"}), 400
    
    to_number = data["to"]
    message_text = data["text"]
    customer_id = data.get("customer_id")
    
    # Import the real WhatsApp client
    from server.whatsapp_baileys_api import whatsapp_client
    
    # Send via Baileys
    result = whatsapp_client.send_message(to_number, message_text, customer_id)
    
    if result.get("success"):
        log.info("WhatsApp message sent via Baileys: %s to %s", result["message_id"], to_number)
        return jsonify({
            "ok": True, 
            "message_id": result["message_id"],
            "via": "baileys"
        }), 200
    else:
        log.error("Failed to send WhatsApp message: %s", result.get("error"))
        return jsonify({
            "error": result.get("error", "Failed to send message"),
            "ok": False
        }), 503

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