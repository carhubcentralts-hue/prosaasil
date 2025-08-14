# server/whatsapp_api.py
from flask import Blueprint, request, jsonify
from server.authz import auth_required
from server.logging_setup import _mask_phone
import json, logging

whatsapp_api_bp = Blueprint("whatsapp_api", __name__, url_prefix="/api/whatsapp")
log = logging.getLogger("whatsapp")

@whatsapp_api_bp.route("/status", methods=["GET"])
@auth_required
def whatsapp_status():
    """Get WhatsApp connection status"""
    try:
        # In a real implementation, check actual connection status
        return jsonify({
            "success": True,
            "connected": False,
            "status": "disconnected",
            "qr_code": None,
            "message": "WhatsApp client ready for connection"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@whatsapp_api_bp.route("/send", methods=["POST"])
@auth_required
def send_message():
    """Send WhatsApp message"""
    try:
        data = request.get_json()
        phone = data.get("phone")
        message = data.get("message")
        
        if not phone or not message:
            return jsonify({
                "success": False,
                "error": "Phone and message required"
            }), 400
        
        masked_phone = _mask_phone(phone)
        log.info("Send WA: to=%s len=%d", masked_phone, len(message))
            
        # In a real implementation, send via WhatsApp client
        return jsonify({
            "success": True,
            "message_id": "fake_msg_id",
            "status": "queued"
        }), 200
        
    except Exception as e:
        log.error("WA send failed: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@whatsapp_api_bp.route("/connect", methods=["POST"])
@auth_required
def connect_whatsapp():
    """Initialize WhatsApp connection"""
    try:
        # In a real implementation, start WhatsApp client
        return jsonify({
            "success": True,
            "qr_code": "data:image/png;base64,fake_qr_code",
            "message": "Scan QR code to connect"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500