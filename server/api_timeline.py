from flask import Blueprint, jsonify
from server.authz import auth_required
try:
    from server.models import db, CallLog, Customer
    # Try to import other models if they exist
    try:
        from server.models import WhatsAppMsg, Task, Invoice, Contract
    except ImportError:
        WhatsAppMsg = Task = Invoice = Contract = None
except ImportError:
    # Fallback if models not available
    db = CallLog = Customer = WhatsAppMsg = Task = Invoice = Contract = None

timeline_bp = Blueprint("timeline", __name__, url_prefix="/api/customers")

@timeline_bp.get("/<int:cid>/timeline")
@auth_required
def customer_timeline(cid):
    if not Customer:
        return jsonify([]), 200
        
    items = []
    
    # Add call logs
    if CallLog:
        items += [ {"type":"call", "at":c.created_at, "data":c.to_dict()} 
                  for c in CallLog.query.filter_by(customer_id=cid).all() ]
    
    # Add WhatsApp messages if available
    if WhatsAppMsg:
        items += [ {"type":"whatsapp", "at":w.created_at, "data":w.to_dict()} 
                  for w in WhatsAppMsg.query.filter_by(customer_id=cid).all() ]
    
    # Add tasks if available
    if Task:
        items += [ {"type":"task", "at":t.due_at, "data":t.to_dict()} 
                  for t in Task.query.filter_by(customer_id=cid).all() ]
    
    # Add invoices if available
    if Invoice:
        items += [ {"type":"invoice", "at":i.issued_at, "data":i.to_dict()} 
                  for i in Invoice.query.filter_by(customer_id=cid).all() ]
    
    # Add contracts if available
    if Contract:
        items += [ {"type":"contract", "at":k.signed_at, "data":k.to_dict()} 
                  for k in Contract.query.filter_by(customer_id=cid).all() ]
    
    # Sort by date, newest first
    items.sort(key=lambda x: x["at"] if x["at"] else "", reverse=True)
    return jsonify(items), 200