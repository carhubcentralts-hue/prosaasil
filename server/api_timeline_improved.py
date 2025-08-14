# server/api_timeline_improved.py
from flask import Blueprint, jsonify
from server.authz import auth_required
import logging

timeline_bp = Blueprint("timeline", __name__, url_prefix="/api/customers")
log = logging.getLogger(__name__)

@timeline_bp.get("/<int:customer_id>/timeline")
@auth_required
def customer_timeline(customer_id):
    """Get unified timeline for a specific customer"""
    
    # Mock timeline data - replace with actual database queries
    timeline_items = []
    
    # Mock call logs
    if customer_id == 1:
        timeline_items.extend([
            {
                "type": "call",
                "at": "2024-01-16T09:15:00Z",
                "data": {
                    "id": "call-001",
                    "call_sid": "CA123456789",
                    "duration": 245,  # seconds
                    "direction": "inbound",
                    "from": "+972-50-123-4567",
                    "to": "+972-77-123-4567",
                    "status": "completed",
                    "transcription": "שלום, אני מחפש דירת 3 חדרים בתל אביב",
                    "ai_response": "שלום! אשמח לעזור לך למצוא דירה מתאימה. איזה תקציב יש לך?"
                }
            },
            {
                "type": "call", 
                "at": "2024-01-15T14:30:00Z",
                "data": {
                    "id": "call-002",
                    "call_sid": "CA987654321",
                    "duration": 180,
                    "direction": "inbound", 
                    "from": "+972-50-123-4567",
                    "to": "+972-77-123-4567",
                    "status": "completed",
                    "transcription": "התקשרתי אתמול, רציתי לשמוע עדכון",
                    "ai_response": "כמובן! יש לי מספר אפשרויות חדשות שעולות על קריטריונים שלך."
                }
            }
        ])
    
    # Mock WhatsApp messages
    if customer_id == 1:
        timeline_items.extend([
            {
                "type": "whatsapp",
                "at": "2024-01-16T11:45:00Z",
                "data": {
                    "id": "wa-001",
                    "from": "+972501234567",
                    "to": "business_number",
                    "text": "תוכל לשלוח לי תמונות של הדירה?",
                    "direction": "inbound",
                    "status": "received"
                }
            },
            {
                "type": "whatsapp",
                "at": "2024-01-16T11:47:00Z", 
                "data": {
                    "id": "wa-002",
                    "from": "business_number",
                    "to": "+972501234567", 
                    "text": "בטח! אני שולח כמה תמונות עכשיו.",
                    "direction": "outbound",
                    "status": "delivered"
                }
            }
        ])
    
    # Mock tasks
    if customer_id == 1:
        timeline_items.extend([
            {
                "type": "task",
                "at": "2024-01-17T10:00:00Z",  # Future - due date
                "data": {
                    "id": "task-001",
                    "title": "לחזור ללקוח עם מענה על שאלת המימון",
                    "description": "הלקוח שאל על אפשרויות מימון - צריך לברר ולחזור אליו",
                    "status": "pending",
                    "priority": "high",
                    "assigned_to": "שי",
                    "due_at": "2024-01-17T10:00:00Z"
                }
            }
        ])
    
    # Mock invoices  
    if customer_id == 1:
        timeline_items.extend([
            {
                "type": "invoice",
                "at": "2024-01-14T16:20:00Z",
                "data": {
                    "id": "inv-001", 
                    "amount": 15000.00,
                    "currency": "ILS",
                    "status": "paid",
                    "description": "דמי תיווך - דירת 3 חדרים ברמת גן",
                    "issued_at": "2024-01-14T16:20:00Z",
                    "paid_at": "2024-01-15T09:30:00Z"
                }
            }
        ])
    
    # Mock contracts
    if customer_id == 1:
        timeline_items.extend([
            {
                "type": "contract",
                "at": "2024-01-13T13:15:00Z",
                "data": {
                    "id": "contract-001",
                    "title": "הסכם תיווך - רמת גן רח׳ הרצל 15",
                    "type": "brokerage",
                    "status": "signed",
                    "signed_at": "2024-01-13T13:15:00Z",
                    "property_address": "רמת גן, רח׳ הרצל 15, קומה 3",
                    "commission": 12000.00,
                    "commission_rate": 2.0  # percent
                }
            }
        ])
    
    # Sort by timestamp (newest first)
    timeline_items.sort(key=lambda x: x["at"], reverse=True)
    
    log.info("Retrieved timeline for customer %d: %d items", customer_id, len(timeline_items))
    
    return jsonify(timeline_items), 200

@timeline_bp.get("/<int:customer_id>/summary")
@auth_required
def customer_summary(customer_id):
    """Get customer interaction summary statistics"""
    
    # Mock summary data
    if customer_id == 1:
        summary = {
            "customer_id": customer_id,
            "total_interactions": 8,
            "last_contact": "2024-01-16T11:47:00Z",
            "calls": {
                "total": 2,
                "total_duration": 425,  # seconds
                "avg_duration": 212.5,
                "last_call": "2024-01-16T09:15:00Z"
            },
            "whatsapp": {
                "total": 4,
                "last_message": "2024-01-16T11:47:00Z",
                "unread": 0
            },
            "tasks": {
                "total": 1,
                "pending": 1, 
                "completed": 0,
                "overdue": 0,
                "next_due": "2024-01-17T10:00:00Z"
            },
            "financial": {
                "total_invoiced": 15000.00,
                "total_paid": 15000.00,
                "outstanding": 0.00,
                "last_invoice": "2024-01-14T16:20:00Z"
            },
            "contracts": {
                "total": 1,
                "active": 1,
                "signed": 1,
                "last_signed": "2024-01-13T13:15:00Z"
            }
        }
    else:
        # Default for unknown customers
        summary = {
            "customer_id": customer_id,
            "total_interactions": 0,
            "last_contact": None,
            "calls": {"total": 0, "total_duration": 0, "avg_duration": 0, "last_call": None},
            "whatsapp": {"total": 0, "last_message": None, "unread": 0},
            "tasks": {"total": 0, "pending": 0, "completed": 0, "overdue": 0, "next_due": None},
            "financial": {"total_invoiced": 0, "total_paid": 0, "outstanding": 0, "last_invoice": None},
            "contracts": {"total": 0, "active": 0, "signed": 0, "last_signed": None}
        }
    
    log.info("Retrieved summary for customer %d", customer_id)
    return jsonify(summary), 200