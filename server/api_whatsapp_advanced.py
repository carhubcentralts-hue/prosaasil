"""
Advanced WhatsApp API Routes for React Frontend
Enhanced WhatsApp management with Baileys and Twilio support
"""

from flask import request, jsonify
from app import app, db
from models import Business, WhatsAppConversation, WhatsAppMessage, CRMCustomer
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
import logging

logger = logging.getLogger(__name__)

@app.route("/api/whatsapp/conversations", methods=["GET"])
def api_get_whatsapp_conversations():
    """
    Get WhatsApp conversations with filtering
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
            
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filters
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        
        # Build query
        query = WhatsAppConversation.query.filter_by(business_id=business_id)
        
        # Search by phone number or customer name
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    WhatsAppConversation.customer_phone.ilike(search_term),
                    WhatsAppConversation.customer_name.ilike(search_term)
                )
            )
            
        # Status filter
        if status_filter:
            query = query.filter(WhatsAppConversation.status == status_filter)
        
        # Execute query with pagination
        conversations_paginated = query.order_by(WhatsAppConversation.last_message_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Convert to dict with additional data
        conversations_data = []
        for conv in conversations_paginated.items:
            # Get last message
            last_message = WhatsAppMessage.query.filter_by(
                conversation_id=conv.id
            ).order_by(WhatsAppMessage.timestamp.desc()).first()
            
            # Count unread messages
            unread_count = WhatsAppMessage.query.filter_by(
                conversation_id=conv.id,
                direction='inbound',
                is_read=False
            ).count()
            
            conversation_dict = {
                'id': conv.id,
                'phone_number': conv.customer_phone,
                'customer_name': conv.customer_name,
                'status': conv.status,
                'status_hebrew': get_whatsapp_status_hebrew(conv.status),
                'last_message': last_message.message_text[:50] + "..." if last_message and len(last_message.message_text) > 50 else (last_message.message_text if last_message else ""),
                'last_message_at': conv.last_message_at.isoformat() if conv.last_message_at else None,
                'updated_at': conv.updated_at.isoformat() if conv.updated_at else None,
                'unread_count': unread_count,
                'created_at': conv.created_at.isoformat() if conv.created_at else None
            }
            conversations_data.append(conversation_dict)
        
        response = {
            'conversations': conversations_data,
            'pagination': {
                'page': conversations_paginated.page,
                'per_page': conversations_paginated.per_page,
                'total': conversations_paginated.total,
                'pages': conversations_paginated.pages,
                'has_next': conversations_paginated.has_next,
                'has_prev': conversations_paginated.has_prev
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp conversations: {e}")
        return jsonify({"error": "Failed to get conversations"}), 500

@app.route("/api/whatsapp/messages", methods=["GET"])
def api_get_whatsapp_messages():
    """
    Get messages for a specific conversation
    """
    try:
        conversation_id = request.args.get('conversation_id', type=int)
        if not conversation_id:
            return jsonify({"error": "Missing conversation_id"}), 400
        
        # Get messages
        messages = WhatsAppMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(WhatsAppMessage.timestamp.asc()).all()
        
        # Convert to dict
        messages_data = []
        for msg in messages:
            message_dict = {
                'id': msg.id,
                'content': msg.message_text,
                'direction': msg.direction,
                'created_at': msg.timestamp.isoformat() if msg.timestamp else None,
                'is_read': msg.is_read,
                'message_type': msg.message_type or 'text',
                'media_url': msg.media_url
            }
            messages_data.append(message_dict)
        
        # Mark messages as read
        WhatsAppMessage.query.filter_by(
            conversation_id=conversation_id,
            direction='inbound'
        ).update({'is_read': True})
        db.session.commit()
        
        return jsonify({'messages': messages_data})
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp messages: {e}")
        return jsonify({"error": "Failed to get messages"}), 500

@app.route("/api/whatsapp/send", methods=["POST"])
def api_send_whatsapp_message():
    """
    Send WhatsApp message via Twilio or Baileys
    """
    try:
        data = request.get_json()
        business_id = data.get('business_id')
        conversation_id = data.get('conversation_id')
        message = data.get('message', '').strip()
        service_type = data.get('service_type', 'twilio')
        
        if not all([business_id, conversation_id, message]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get conversation
        conversation = WhatsAppConversation.query.get(conversation_id)
        if not conversation or conversation.business_id != business_id:
            return jsonify({"error": "Conversation not found"}), 404
        
        # Send message based on service type
        success = False
        
        if service_type == 'twilio':
            # Use Twilio WhatsApp API
            from twilio_service import send_whatsapp_message
            success = send_whatsapp_message(
                to_number=conversation.customer_phone,
                message=message,
                business_id=business_id
            )
        elif service_type == 'baileys':
            # Use Baileys WhatsApp Web
            from baileys_integration import send_message
            success = send_message(
                phone_number=conversation.customer_phone,
                message=message,
                business_id=business_id
            )
        
        if success:
            # Save message to database
            new_message = WhatsAppMessage(
                conversation_id=conversation_id,
                direction='outbound',
                message_text=message,
                timestamp=datetime.utcnow(),
                is_read=True,
                message_type='text'
            )
            db.session.add(new_message)
            
            # Update conversation
            conversation.last_message_at = datetime.utcnow()
            conversation.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Message sent successfully'})
        else:
            return jsonify({'error': 'Failed to send message'}), 500
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return jsonify({"error": "Failed to send message"}), 500

@app.route("/api/whatsapp/stats", methods=["GET"])
def api_get_whatsapp_stats():
    """
    Get WhatsApp statistics dashboard
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
        
        # Current date calculations
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        
        # Basic counts
        total_conversations = WhatsAppConversation.query.filter_by(business_id=business_id).count()
        
        today_messages = WhatsAppMessage.query.join(WhatsAppConversation).filter(
            WhatsAppConversation.business_id == business_id,
            func.date(WhatsAppMessage.timestamp) == today
        ).count()
        
        # Pending conversations (unread messages)
        pending_conversations = db.session.query(WhatsAppConversation.id).join(WhatsAppMessage).filter(
            WhatsAppConversation.business_id == business_id,
            WhatsAppMessage.direction == 'inbound',
            WhatsAppMessage.is_read == False
        ).distinct().count()
        
        # Average response time calculation (mock for now - would need more complex logic)
        avg_response_time = 15  # minutes
        
        # Additional stats
        active_conversations = WhatsAppConversation.query.filter_by(
            business_id=business_id,
            status='active'
        ).count()
        
        stats = {
            'total_conversations': total_conversations,
            'today_messages': today_messages,
            'pending_conversations': pending_conversations,
            'avg_response_time': avg_response_time,
            'active_conversations': active_conversations,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp stats: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

@app.route("/api/whatsapp/status", methods=["GET"])
def api_get_whatsapp_status():
    """
    Get WhatsApp service connection status
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
        
        # Check business WhatsApp settings
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        # Default to Twilio if WhatsApp is enabled
        status = 'connected' if business.whatsapp_enabled else 'disconnected'
        service_type = 'twilio'  # Default to Twilio
        
        # TODO: Check Baileys connection status from a status file or service
        # For now, assume Twilio is the primary service
        
        response = {
            'status': status,
            'service_type': service_type,
            'whatsapp_enabled': business.whatsapp_enabled,
            'phone_number': business.phone_whatsapp
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp status: {e}")
        return jsonify({"error": "Failed to get status"}), 500

@app.route("/api/whatsapp/baileys/connect", methods=["POST"])
def api_connect_baileys():
    """
    Connect to WhatsApp Web via Baileys
    """
    try:
        data = request.get_json()
        business_id = data.get('business_id')
        
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
        
        # Initialize Baileys connection
        from baileys_integration import initialize_baileys
        qr_code = initialize_baileys(business_id)
        
        if qr_code:
            return jsonify({
                'success': True,
                'qr_code': qr_code,
                'message': 'Scan QR code with WhatsApp'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Already connected or failed to generate QR'
            })
            
    except Exception as e:
        logger.error(f"Error connecting Baileys: {e}")
        return jsonify({"error": "Failed to connect"}), 500

# Helper functions
def get_whatsapp_status_hebrew(status):
    """Convert WhatsApp status to Hebrew"""
    status_map = {
        'active': 'פעיל',
        'pending': 'ממתין',
        'resolved': 'נפתר',
        'closed': 'סגור',
        'archived': 'בארכיון'
    }
    return status_map.get(status, status)

if __name__ == '__main__':
    print("✅ Advanced WhatsApp API routes loaded successfully")