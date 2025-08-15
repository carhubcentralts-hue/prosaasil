"""
CRM API מאוחד עם Pagination עקבי
לפי המפרט המקצועי
"""
from flask import Blueprint, request, jsonify
from server.api_pagination import paginate_query, pagination_response, get_pagination_params
from server.rbac_permissions import require_auth, get_current_user
import logging

crm_unified_bp = Blueprint("crm_unified_bp", __name__, url_prefix="/api/crm")
log = logging.getLogger("api.crm.unified")

# Mock data for demonstration - יוחלף בDB אמיתי
MOCK_CUSTOMERS = [
    {"id": 1, "name": "משה כהן", "phone": "+972501234567", "email": "moshe@example.com", "status": "פעיל", "business_id": 1},
    {"id": 2, "name": "שרה לוי", "phone": "+972502345678", "email": "sara@example.com", "status": "פעיל", "business_id": 1},
    {"id": 3, "name": "דוד רוזן", "phone": "+972503456789", "email": "david@example.com", "status": "לא פעיל", "business_id": 1},
    {"id": 4, "name": "רחל אברהם", "phone": "+972504567890", "email": "rachel@example.com", "status": "פעיל", "business_id": 2},
    {"id": 5, "name": "יוסף מרכוס", "phone": "+972505678901", "email": "yosef@example.com", "status": "פעיל", "business_id": 1},
]

MOCK_CALLS = [
    {"id": 1, "customer_id": 1, "call_sid": "CA123", "from_number": "+972501234567", "duration": 45, "status": "completed", "transcription": "שלום, אני מעוניין בדירה במרכז תל אביב"},
    {"id": 2, "customer_id": 2, "call_sid": "CA124", "from_number": "+972502345678", "duration": 32, "status": "completed", "transcription": "האם יש לכם משרדים להשכרה באזור?"},
    {"id": 3, "customer_id": 1, "call_sid": "CA125", "from_number": "+972501234567", "duration": 67, "status": "completed", "transcription": "רציתי לדעת על המחירים של הדירות החדשות"},
]

MOCK_WA_MESSAGES = [
    {"id": 1, "customer_id": 1, "direction": "in", "body": "שלום, אני מחפש דירה", "ts": "2024-08-15T10:30:00"},
    {"id": 2, "customer_id": 1, "direction": "out", "body": "שלום! אשמח לעזור לך למצוא דירה מתאימה", "ts": "2024-08-15T10:31:00"},
    {"id": 3, "customer_id": 2, "direction": "in", "body": "יש לכם משרדים קטנים?", "ts": "2024-08-15T11:00:00"},
]

@crm_unified_bp.get("/customers") 
@require_auth()
def customers_list():
    """רשימת לקוחות עם חיפוש ופאג'ינציה"""
    try:
        page, limit = get_pagination_params(request)
        search_q = request.args.get('q', '')
        
        # סינון לפי חיפוש
        customers = MOCK_CUSTOMERS
        if search_q:
            customers = [c for c in customers if search_q.lower() in c["name"].lower() or search_q in c["phone"]]
        
        results, page, pages, total = paginate_query(customers, page, limit)
        
        return jsonify(pagination_response(results, page, pages, total))
        
    except Exception as e:
        log.error("Error fetching customers: %s", e)
        return jsonify({"error": "Failed to fetch customers"}), 500

@crm_unified_bp.get("/customers/<int:customer_id>/timeline")
@require_auth()
def customer_timeline(customer_id):
    """Timeline מאוחד ללקוח - calls, WhatsApp, חשבוניות, וכו'"""
    try:
        page, limit = get_pagination_params(request)
        
        # אחד אירועים מכל המקורות
        timeline_items = []
        
        # הוסף שיחות
        for call in MOCK_CALLS:
            if call["customer_id"] == customer_id:
                timeline_items.append({
                    "type": "call",
                    "title": f"שיחה ({call['duration']} שניות)",
                    "ts": "2024-08-15T10:00:00",  # היה צריך להיות מהDB
                    "ref_id": call["id"],
                    "details": {
                        "call_sid": call["call_sid"],
                        "transcription": call["transcription"],
                        "status": call["status"]
                    }
                })
        
        # הוסף הודעות WhatsApp
        for msg in MOCK_WA_MESSAGES:
            if msg["customer_id"] == customer_id:
                timeline_items.append({
                    "type": "whatsapp",
                    "title": f"WhatsApp {'נכנס' if msg['direction'] == 'in' else 'יוצא'}",
                    "ts": msg["ts"],
                    "ref_id": msg["id"],
                    "details": {
                        "body": msg["body"],
                        "direction": msg["direction"]
                    }
                })
        
        # מיין לפי זמן (הכי חדש קודם)
        timeline_items.sort(key=lambda x: x["ts"], reverse=True)
        
        # Direct pagination for timeline to avoid count() issues
        total = len(timeline_items)
        pages = (total + limit - 1) // limit
        start = (page - 1) * limit
        end = start + limit
        results = timeline_items[start:end]
        
        return jsonify({
            "customer_id": customer_id,
            "timeline": pagination_response(results, page, pages, total)
        })
        
    except Exception as e:
        log.error("Error fetching customer timeline: %s", e)
        return jsonify({"error": "Failed to fetch timeline"}), 500

@crm_unified_bp.get("/calls")
@require_auth()
def calls_list():
    """רשימת שיחות עם סינון לפי לקוח"""
    try:
        page, limit = get_pagination_params(request)
        customer_id = request.args.get("customer_id", type=int)
        
        calls = MOCK_CALLS.copy()  # Make a copy to avoid modifying original
        if customer_id:
            calls = [c for c in calls if c["customer_id"] == customer_id]
        
        # Direct pagination for list to avoid count() issues
        total = len(calls)
        pages = (total + limit - 1) // limit  # Ceiling division
        start = (page - 1) * limit
        end = start + limit
        results = calls[start:end]
        
        return jsonify(pagination_response(results, page, pages, total))
        
    except Exception as e:
        log.error("Error fetching calls: %s", e)
        return jsonify({"error": "Failed to fetch calls"}), 500

@crm_unified_bp.get("/calls/<int:call_id>/transcript")
@require_auth()
def call_transcript(call_id):
    """תמלול שיחה ספציפית"""
    try:
        call = next((c for c in MOCK_CALLS if c["id"] == call_id), None)
        if not call:
            return jsonify({"error": "Call not found"}), 404
        
        return jsonify({
            "call_id": call_id,
            "call_sid": call["call_sid"],
            "transcription": call["transcription"],
            "duration": call["duration"]
        })
        
    except Exception as e:
        log.error("Error fetching transcript: %s", e)
        return jsonify({"error": "Failed to fetch transcript"}), 500

@crm_unified_bp.get("/wa/messages")
@require_auth()
def wa_messages_list():
    """הודעות WhatsApp לפי לקוח"""
    try:
        page, limit = get_pagination_params(request)
        customer_id = request.args.get("customer_id", type=int)
        
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        
        messages = [msg for msg in MOCK_WA_MESSAGES if msg["customer_id"] == customer_id]
        
        # Direct pagination for messages to avoid count() issues  
        total = len(messages)
        pages = (total + limit - 1) // limit
        start = (page - 1) * limit
        end = start + limit
        results = messages[start:end]
        
        return jsonify(pagination_response(results, page, pages, total))
        
    except Exception as e:
        log.error("Error fetching WhatsApp messages: %s", e)
        return jsonify({"error": "Failed to fetch messages"}), 500