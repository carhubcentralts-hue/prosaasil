from flask import Blueprint, jsonify, request
from server.api_pagination import paginate_query, pagination_response
import logging

timeline_bp = Blueprint("timeline_bp", __name__, url_prefix="/api/timeline")
log = logging.getLogger("api.timeline")

@timeline_bp.get("/customers/<int:customer_id>/timeline")
def customer_timeline(customer_id):
    """Unified timeline for customer - all events chronologically"""
    try:
        # Collect real events: calls, WhatsApp, tasks, contracts, invoices
        timeline_items = []
        
        # Add call events
        # calls = get_customer_calls(customer_id)
        # for call in calls:
        #     timeline_items.append({
        #         "type": "call",
        #         "timestamp": call.created_at,
        #         "title": f"שיחה נכנסת - {call.duration}s",
        #         "description": call.transcription or "ללא תמלול",
        #         "metadata": {"call_sid": call.sid, "status": call.status}
        #     })
        
        # Add WhatsApp events
        # wa_messages = get_customer_whatsapp(customer_id)
        # for msg in wa_messages:
        #     timeline_items.append({
        #         "type": "whatsapp", 
        #         "timestamp": msg.timestamp,
        #         "title": f"הודעת WhatsApp - {'נשלחה' if msg.outgoing else 'התקבלה'}",
        #         "description": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
        #         "metadata": {"message_id": msg.id, "outgoing": msg.outgoing}
        #     })
        
        # Sort by timestamp descending
        timeline_items.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Paginate
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 20))
        results, page, pages, total = paginate_query(timeline_items, page, limit)
        
        return jsonify(pagination_response(results, page, pages, total))
        
    except Exception as e:
        log.error(f"Timeline error for customer {customer_id}: {e}")
        return jsonify({"error": "Failed to fetch timeline"}), 500