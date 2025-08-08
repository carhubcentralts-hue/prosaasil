"""
AgentLocator v39 - Customer Timeline API
API מאוחד לקבלת ציר זמן מלא של כל אירועי הלקוח
"""

from flask import Blueprint, request, jsonify
from .models import db, CallLog, Customer, Task
from sqlalchemy import desc, text
from datetime import datetime
import logging

timeline_bp = Blueprint("timeline_bp", __name__, url_prefix="/api")

logger = logging.getLogger(__name__)

@timeline_bp.get("/customers/<int:customer_id>/timeline")
def customer_timeline(customer_id):
    """
    מחזיר ציר זמן מאוחד של כל אירועי הלקוח
    Returns unified timeline of all customer events
    """
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
        items = []
        
        # Verify customer exists
        customer = Customer.query.get_or_404(customer_id)
        logger.info(f"Fetching timeline for customer {customer_id}: {customer.name}")
        
        # Fetch call logs
        try:
            calls = CallLog.query.filter_by(customer_id=customer_id)\
                          .order_by(desc(CallLog.created_at))\
                          .limit(limit)
            
            for call in calls:
                items.append({
                    "id": f"call_{call.id}",
                    "kind": "call",
                    "timestamp": call.created_at.isoformat() if call.created_at else None,
                    "reference": call.call_sid or str(call.id),
                    "title": "שיחה נכנסת" if call.direction == "incoming" else "שיחה יוצאת", 
                    "metadata": {
                        "duration": call.duration,
                        "status": call.call_status,
                        "direction": call.direction,
                        "from_phone": call.from_phone,
                        "to_phone": call.to_phone,
                        "transcription": call.transcription[:100] + "..." if call.transcription and len(call.transcription) > 100 else call.transcription,
                        "summary": call.summary
                    },
                    "actions": [
                        {"type": "view", "label": "צפה בשיחה", "url": f"/calls/{call.id}"}
                    ]
                })
            
            logger.info(f"Found {len([i for i in items if i['kind'] == 'call'])} call records")
            
        except Exception as e:
            logger.warning(f"Could not fetch call logs: {e}")
        
        # Fetch WhatsApp messages
        try:
            # Check if WhatsAppMessage model exists
            from .models import WhatsAppMessage
            
            messages = WhatsAppMessage.query.filter_by(customer_id=customer_id)\
                                      .order_by(desc(WhatsAppMessage.created_at))\
                                      .limit(limit)
            
            for msg in messages:
                items.append({
                    "id": f"whatsapp_{msg.id}",
                    "kind": "whatsapp", 
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                    "reference": str(msg.id),
                    "title": "הודעת WhatsApp נכנסת" if msg.direction == "inbound" else "הודעת WhatsApp יוצאת",
                    "metadata": {
                        "direction": msg.direction,
                        "status": msg.status,
                        "message_body": msg.body[:100] + "..." if msg.body and len(msg.body) > 100 else msg.body,
                        "message_type": getattr(msg, 'message_type', 'text')
                    },
                    "actions": [
                        {"type": "reply", "label": "השב", "url": f"/whatsapp/conversation/{customer_id}"}
                    ]
                })
                
            logger.info(f"Found {len([i for i in items if i['kind'] == 'whatsapp'])} WhatsApp messages")
            
        except ImportError:
            logger.info("WhatsAppMessage model not available")
        except Exception as e:
            logger.warning(f"Could not fetch WhatsApp messages: {e}")
        
        # Fetch tasks
        try:
            tasks = Task.query.filter_by(customer_id=customer_id)\
                         .order_by(desc(Task.created_at))\
                         .limit(limit)
            
            for task in tasks:
                status_hebrew = {
                    'open': 'פתוחה',
                    'in_progress': 'בביצוע', 
                    'completed': 'הושלמה',
                    'cancelled': 'בוטלה',
                    'overdue': 'באיחור'
                }.get(task.status, task.status)
                
                items.append({
                    "id": f"task_{task.id}",
                    "kind": "task",
                    "timestamp": task.created_at.isoformat() if task.created_at else None,
                    "reference": str(task.id),
                    "title": f"משימה: {task.title}",
                    "metadata": {
                        "status": task.status,
                        "status_hebrew": status_hebrew,
                        "priority": task.priority,
                        "due_at": task.due_at.isoformat() if task.due_at else None,
                        "channel": task.channel,
                        "notes": task.notes[:100] + "..." if task.notes and len(task.notes) > 100 else task.notes,
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None
                    },
                    "actions": [
                        {"type": "edit", "label": "ערוך משימה", "url": f"/tasks/{task.id}/edit"}
                    ]
                })
                
            logger.info(f"Found {len([i for i in items if i['kind'] == 'task'])} tasks")
            
        except ImportError:
            logger.info("Task model not available")  
        except Exception as e:
            logger.warning(f"Could not fetch tasks: {e}")
            
        # Fetch contracts
        try:
            from .models import Contract
            
            contracts = Contract.query.filter_by(customer_id=customer_id)\
                               .order_by(desc(Contract.created_at))\
                               .limit(limit)
            
            for contract in contracts:
                status_hebrew = {
                    'draft': 'טיוטה',
                    'sent': 'נשלח',
                    'viewed': 'נצפה',
                    'signed': 'נחתם',
                    'completed': 'הושלם',
                    'cancelled': 'בוטל'
                }.get(contract.status, contract.status)
                
                items.append({
                    "id": f"contract_{contract.id}",
                    "kind": "contract",
                    "timestamp": contract.created_at.isoformat() if contract.created_at else None,
                    "reference": str(contract.id),
                    "title": f"חוזה: {contract.title or 'ללא כותרת'}",
                    "metadata": {
                        "status": contract.status,
                        "status_hebrew": status_hebrew,
                        "signed_at": contract.signed_at.isoformat() if hasattr(contract, 'signed_at') and contract.signed_at else None
                    },
                    "actions": [
                        {"type": "view", "label": "צפה בחוזה", "url": f"/contracts/{contract.id}"}
                    ]
                })
                
            logger.info(f"Found {len([i for i in items if i['kind'] == 'contract'])} contracts")
            
        except ImportError:
            logger.info("Contract model not available")
        except Exception as e:
            logger.warning(f"Could not fetch contracts: {e}")
        
        # Fetch invoices
        try:
            from .models import Invoice
            
            invoices = Invoice.query.filter_by(customer_id=customer_id)\
                             .order_by(desc(Invoice.created_at))\
                             .limit(limit)
            
            for invoice in invoices:
                status_hebrew = {
                    'draft': 'טיוטה',
                    'sent': 'נשלח',
                    'paid': 'שולם',
                    'overdue': 'באיחור',
                    'cancelled': 'בוטל'
                }.get(invoice.status, invoice.status)
                
                items.append({
                    "id": f"invoice_{invoice.id}",
                    "kind": "invoice", 
                    "timestamp": invoice.created_at.isoformat() if invoice.created_at else None,
                    "reference": str(invoice.id),
                    "title": f"חשבונית #{invoice.invoice_number or invoice.id}",
                    "metadata": {
                        "status": invoice.status,
                        "status_hebrew": status_hebrew,
                        "amount": float(invoice.amount) if invoice.amount else 0,
                        "due_date": invoice.due_date.isoformat() if hasattr(invoice, 'due_date') and invoice.due_date else None,
                        "paid_at": invoice.paid_at.isoformat() if hasattr(invoice, 'paid_at') and invoice.paid_at else None
                    },
                    "actions": [
                        {"type": "view", "label": "צפה בחשבונית", "url": f"/invoices/{invoice.id}"}
                    ]
                })
                
            logger.info(f"Found {len([i for i in items if i['kind'] == 'invoice'])} invoices")
            
        except ImportError:
            logger.info("Invoice model not available")
        except Exception as e:
            logger.warning(f"Could not fetch invoices: {e}")
        
        # Sort all items by timestamp (newest first)
        items = sorted(
            items, 
            key=lambda x: datetime.fromisoformat(x["timestamp"].replace('Z', '+00:00')) if x.get("timestamp") else datetime.min,
            reverse=True
        )[:limit]
        
        # Add summary statistics
        summary = {
            "total_items": len(items),
            "calls": len([i for i in items if i["kind"] == "call"]),
            "whatsapp": len([i for i in items if i["kind"] == "whatsapp"]),
            "tasks": len([i for i in items if i["kind"] == "task"]),
            "contracts": len([i for i in items if i["kind"] == "contract"]),
            "invoices": len([i for i in items if i["kind"] == "invoice"]),
            "date_range": {
                "earliest": items[-1]["timestamp"] if items else None,
                "latest": items[0]["timestamp"] if items else None
            }
        }
        
        logger.info(f"Timeline generated for customer {customer_id}: {summary['total_items']} items")
        
        return jsonify({
            "success": True,
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone
            },
            "summary": summary,
            "items": items
        })
        
    except Exception as e:
        logger.error(f"Failed to generate timeline for customer {customer_id}: {e}")
        return jsonify({
            "success": False,
            "error": "timeline_error",
            "message": f"שגיאה ביצירת ציר הזמן: {str(e)}"
        }), 500

@timeline_bp.get("/customers/<int:customer_id>/timeline/summary")
def customer_timeline_summary(customer_id):
    """
    מחזיר סיכום מהיר של פעילות הלקוח
    Returns quick summary of customer activity
    """
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Count different types of activities
        summary = {
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone
            },
            "activity_counts": {
                "total_calls": 0,
                "total_whatsapp": 0,
                "total_tasks": 0,
                "open_tasks": 0,
                "total_contracts": 0,
                "total_invoices": 0,
                "unpaid_invoices": 0
            },
            "recent_activity": None
        }
        
        # Count calls
        try:
            summary["activity_counts"]["total_calls"] = CallLog.query.filter_by(customer_id=customer_id).count()
        except Exception:
            pass
            
        # Count WhatsApp messages
        try:
            from .models import WhatsAppMessage
            summary["activity_counts"]["total_whatsapp"] = WhatsAppMessage.query.filter_by(customer_id=customer_id).count()
        except Exception:
            pass
            
        # Count tasks
        try:
            summary["activity_counts"]["total_tasks"] = Task.query.filter_by(customer_id=customer_id).count()
            summary["activity_counts"]["open_tasks"] = Task.query.filter_by(customer_id=customer_id, status='open').count()
        except Exception:
            pass
            
        # Count contracts
        try:
            from .models import Contract
            summary["activity_counts"]["total_contracts"] = Contract.query.filter_by(customer_id=customer_id).count()
        except Exception:
            pass
            
        # Count invoices
        try:
            from .models import Invoice
            summary["activity_counts"]["total_invoices"] = Invoice.query.filter_by(customer_id=customer_id).count()
            summary["activity_counts"]["unpaid_invoices"] = Invoice.query.filter(
                Invoice.customer_id == customer_id,
                Invoice.status.in_(['sent', 'overdue'])
            ).count()
        except Exception:
            pass
        
        # Get most recent activity
        try:
            most_recent_call = CallLog.query.filter_by(customer_id=customer_id)\
                                      .order_by(desc(CallLog.created_at))\
                                      .first()
            if most_recent_call:
                summary["recent_activity"] = {
                    "type": "call",
                    "timestamp": most_recent_call.created_at.isoformat(),
                    "description": f"שיחה בת {most_recent_call.duration or 0} שניות"
                }
        except Exception:
            pass
            
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Failed to generate timeline summary for customer {customer_id}: {e}")
        return jsonify({
            "error": "summary_error", 
            "message": f"שגיאה ביצירת סיכום: {str(e)}"
        }), 500