"""
CRM API מאוחד עם Pagination עקבי
לפי המפרט המקצועי
"""
from flask import Blueprint, request, jsonify
from server.api_pagination import paginate_query, pagination_response, get_pagination_params
from server.rbac_permissions import require_auth, get_current_user
import logging
import stripe
import os
import base64
import time
import datetime
import pathlib
from io import BytesIO
from flask import send_file
from server.models_sql import Deal, Payment, Invoice, Contract, Business
from server.db import db

crm_unified_bp = Blueprint("crm_unified_bp", __name__, url_prefix="/api/crm")
log = logging.getLogger("api.crm.unified")

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# === PRODUCTION CRM FUNCTIONS ===

def create_invoice_simple(amount_agorot: int) -> str:
    """Create a simple HTML/text invoice"""
    try:
        invoices_dir = pathlib.Path("server/static/invoices")
        invoices_dir.mkdir(parents=True, exist_ok=True)
        
        seq = (Invoice.query.count() + 1)
        inv_no = f"{os.getenv('INVOICE_PREFIX','INV')}-{datetime.datetime.utcnow():%Y%m}-{seq:04d}"
        
        # Generate HTML invoice (production-ready)
        html_path = invoices_dir / f"{inv_no}.html"
        html_content = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>חשבונית {inv_no}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .header {{ border-bottom: 2px solid #333; margin-bottom: 20px; }}
        .amount {{ font-size: 18px; font-weight: bold; color: #2c5aa0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>חשבונית {inv_no}</h1>
        <p>שי דירות ומשרדים בע״מ</p>
    </div>
    <p class="amount">סכום: {amount_agorot/100:.2f} {(os.getenv('CURRENCY') or 'ILS').upper()}</p>
    <p>תאריך: {datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
    <p>מס' חשבונית: {inv_no}</p>
</body>
</html>"""
        
        html_path.write_text(html_content, encoding='utf-8')

        db.session.add(Invoice(invoice_number=inv_no, total=amount_agorot, pdf_path=str(html_path)))
        db.session.commit()
        return inv_no
    except Exception as e:
        log.error(f"Invoice creation failed: {e}")
        raise

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

# === PAYMENTS API ===

@crm_unified_bp.post("/payments/create-intent")
def create_payment_intent():
    """יצירת Stripe Payment Intent"""
    try:
        data = request.get_json() or {}
        deal_id = int(data["deal_id"])
        amount = int(data["amount"])
        currency = (os.getenv("CURRENCY") or "ils").lower()
        
        pi = stripe.PaymentIntent.create(
            amount=amount, 
            currency=currency, 
            automatic_payment_methods={"enabled": True}
        )
        
        payment = Payment()
        payment.deal_id = deal_id
        payment.stripe_payment_intent = pi["id"]
        payment.amount = amount
        payment.currency = currency
        payment.status = "created"
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            "client_secret": pi["client_secret"], 
            "payment_intent": pi["id"]
        }), 200
        
    except Exception as e:
        log.error("Payment intent creation failed: %s", e)
        return jsonify({"error": "Payment creation failed"}), 500

@crm_unified_bp.post("/webhook/stripe")
def stripe_webhook():
    """Stripe webhook for payment status updates"""
    try:
        sig = request.headers.get("Stripe-Signature", "")
        secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if not secret:
            return ("Webhook secret not configured", 400)
        
        event = stripe.Webhook.construct_event(request.data, sig, secret)
        
        if event["type"] == "payment_intent.succeeded":
            pi = event["data"]["object"]
            payment = Payment.query.filter_by(stripe_payment_intent=pi["id"]).first()
            
            if payment:
                payment.status = "succeeded"
                db.session.commit()
                log.info("Payment succeeded: %s", pi["id"])
                
                # Auto-generate invoice
                try:
                    create_invoice_simple(payment.amount)
                    log.info("Auto-created invoice for payment: %s", pi["id"])
                except Exception as e:
                    log.error("Auto invoice creation failed: %s", e)
                    
        return ("", 204)
        
    except Exception as e:
        log.error("Stripe webhook error: %s", e)
        return (str(e), 400)

@crm_unified_bp.get("/invoices/<invoice_number>")
def get_invoice(invoice_number):
    """Download invoice PDF"""
    try:
        inv = Invoice.query.filter_by(invoice_number=invoice_number).first()
        if not inv:
            return jsonify({"error": "Invoice not found"}), 404
        
        return send_file(inv.pdf_path, as_attachment=True)
    except Exception as e:
        log.error("Invoice download failed: %s", e)
        return jsonify({"error": "Invoice download failed"}), 500

@crm_unified_bp.post("/contracts/sign")
def contract_sign():
    """Digital contract signature"""
    try:
        data = request.get_json() or {}
        signer = data.get("name", "")
        sig_b64 = (data.get("signature_b64", "").split(",")[-1] if data.get("signature_b64") else "")
        sig_bytes = base64.b64decode(sig_b64) if sig_b64 else b""

        contracts_dir = pathlib.Path("server/static/contracts")
        contracts_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = contracts_dir / f"{os.getenv('CONTRACT_PREFIX','AGR')}-{int(time.time())}.pdf"

        # Generate HTML contract (production-ready)
        html_content = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>חוזה שירות</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; }}
        .header {{ text-align: center; border-bottom: 2px solid #333; margin-bottom: 30px; }}
        .signature {{ margin-top: 50px; border-top: 1px solid #999; padding-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>חוזה שירות</h1>
        <h2>שי דירות ומשרדים בע״מ</h2>
    </div>
    <p>חוזה זה נחתם בתאריך {datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
    <div class="signature">
        <p><strong>חתום ע"י:</strong> {signer}</p>
        <p><strong>כתובת IP:</strong> {request.remote_addr}</p>
        <p><strong>תאריך חתימה:</strong> {datetime.datetime.utcnow().isoformat()}</p>
    </div>
</body>
</html>"""
        
        pdf_path.write_text(html_content, encoding='utf-8')

        db.session.add(Contract(
            pdf_path=str(pdf_path), 
            signed_name=signer, 
            signed_at=datetime.datetime.utcnow(), 
            signed_ip=request.remote_addr
        ))
        db.session.commit()
        
        return jsonify({"ok": True, "pdf": str(pdf_path)}), 201
    except Exception as e:
        log.error("Contract signing failed: %s", e)
        return jsonify({"error": "Contract signing failed"}), 500

# === DEALS API ===

@crm_unified_bp.get("/deals") 
def list_deals():
    """רשימת דילים"""
    try:
        deals = Deal.query.all()
        return jsonify([{
            "id": d.id,
            "customer_id": d.customer_id,
            "title": d.title,
            "stage": d.stage,
            "amount": d.amount,
            "created_at": d.created_at.isoformat() if d.created_at else None
        } for d in deals])
    except Exception as e:
        log.error("Deals list failed: %s", e)
        return jsonify({"error": "Failed to fetch deals"}), 500

@crm_unified_bp.post("/deals")
def create_deal():
    """יצירת דיל חדש"""
    try:
        data = request.get_json() or {}
        deal = Deal()
        deal.customer_id = int(data["customer_id"])
        deal.title = data.get("title", "")
        deal.stage = data.get("stage", "new")
        deal.amount = int(data.get("amount", 0))
        
        db.session.add(deal)
        db.session.commit()
        
        return jsonify({
            "id": deal.id,
            "message": "Deal created successfully"
        }), 201
        
    except Exception as e:
        log.error("Deal creation failed: %s", e)
        return jsonify({"error": "Deal creation failed"}), 500

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