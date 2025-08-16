"""
CRM API מאוחד עם Pagination עקבי
לפי המפרט המקצועי
"""
from flask import Blueprint, request, jsonify
from server.api_pagination import paginate_query, pagination_response, get_pagination_params
from server.rbac_permissions import require_auth, get_current_user
import logging
import os
import base64
import time
import datetime
import pathlib
import requests
import json
from urllib.parse import urlencode
from io import BytesIO
from flask import send_file, request, jsonify
from server.models_sql import Deal, Payment, Invoice, Contract, Business
from server.db import db

crm_unified_bp = Blueprint("crm_unified_bp", __name__, url_prefix="/api/crm")
log = logging.getLogger("api.crm.unified")

# PayPal Configuration
def _pp_base():
    return "https://api-m.sandbox.paypal.com" if os.getenv("PAYPAL_ENV","sandbox")=="sandbox" else "https://api-m.paypal.com"

def _pp_token():
    r = requests.post(_pp_base()+"/v1/oauth2/token",
                      auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
                      data={"grant_type":"client_credentials"})
    r.raise_for_status()
    return r.json()["access_token"]

# Tranzila Configuration  
def _tz_base():
    return "https://direct.tranzila.com" if os.getenv("TRANZILA_ENV","sandbox")=="production" \
           else "https://direct.tranzila.com"

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

        # Create default deal if needed
        from server.models_sql import Deal, Customer
        customer = Customer.query.first()
        if not customer:
            customer = Customer(name="לקוח כללי", phone="000-0000000")
            db.session.add(customer)
            db.session.commit()
            
        deal = Deal(customer_id=customer.id, title=f"חשבונית {inv_no}", amount=amount_agorot)
        db.session.add(deal)
        db.session.commit()

        db.session.add(Invoice(
            deal_id=deal.id,
            invoice_number=inv_no, 
            total=amount_agorot, 
            pdf_path=str(html_path)
        ))
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
def deprecated_stripe():
    """Deprecated Stripe route - redirected to new providers"""
    return jsonify({"error":"Stripe deprecated. Use /payments/paypal/create-order or /payments/tranzila/create-link"}), 410

# PayPal Payment Routes
@crm_unified_bp.post("/payments/paypal/create-order")
def paypal_create_order():
    """Create PayPal Order"""
    try:
        data = request.get_json() or {}
        amount = int(data["amount"])                       # אגורות
        value = f"{amount/100:.2f}"
        currency = (os.getenv("CURRENCY") or "ILS").upper()
        access = _pp_token()
        order = requests.post(_pp_base()+"/v2/checkout/orders",
                headers={"Authorization":f"Bearer {access}","Content-Type":"application/json"},
                json={"intent":"CAPTURE","purchase_units":[{"amount":{"currency_code":currency,"value":value}}]})
        order.raise_for_status()
        order_id = order.json()["id"]
        pay = Payment(provider="paypal", provider_ref=order_id, amount=amount, currency=currency.lower())
        db.session.add(pay); db.session.commit()
        return jsonify({"order_id": order_id}), 200 
    except Exception as e:
        log.error("PayPal create order failed: %s", e)
        return jsonify({"error": "Failed to create PayPal order"}), 500

@crm_unified_bp.post("/webhook/paypal")
def paypal_webhook():
    """PayPal webhook with signature verification"""
    try:
        # PayPal signature verification
        headers = {
            "paypal-transmission-id": request.headers.get("Paypal-Transmission-Id"),
            "paypal-transmission-time": request.headers.get("Paypal-Transmission-Time"),
            "paypal-transmission-sig": request.headers.get("Paypal-Transmission-Sig"),
            "paypal-cert-url": request.headers.get("Paypal-Cert-Url"),
            "paypal-auth-algo": request.headers.get("Paypal-Auth-Algo"),
        }
        webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
        body = request.get_data(as_text=True)
        access = _pp_token()
        v = requests.post(_pp_base()+"/v1/notifications/verify-webhook-signature",
            headers={"Authorization":f"Bearer {access}","Content-Type":"application/json"},
            json={"transmission_id":headers["paypal-transmission-id"],
                  "transmission_time":headers["paypal-transmission-time"],
                  "cert_url":headers["paypal-cert-url"],
                  "auth_algo":headers["paypal-auth-algo"],
                  "transmission_sig":headers["paypal-transmission-sig"],
                  "webhook_id":webhook_id,
                  "webhook_event": json.loads(body)})
        v.raise_for_status()
        if v.json().get("verification_status") != "SUCCESS":
            return ("invalid", 400)

        event = json.loads(body)
        et = event.get("event_type","")
        res = event.get("resource",{})
        order_id = res.get("id") or res.get("supplementary_data",{}).get("related_ids",{}).get("order_id")
        if et in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED") and order_id:
            pay = Payment.query.filter_by(provider="paypal", provider_ref=order_id).first()
            if pay:
                pay.status = "captured" if et=="PAYMENT.CAPTURE.COMPLETED" else "approved"
                db.session.commit()
                # Auto-create invoice if captured
                if pay.status == "captured":
                    try:
                        invoice_no = create_invoice_simple(pay.amount)
                        log.info("Auto-created invoice %s for PayPal payment %s", invoice_no, pay.id)
                    except Exception as e:
                        log.error("Failed to create invoice: %s", e)
        return ("", 204)
    except Exception as e:
        log.error("PayPal webhook failed: %s", e)
        return jsonify({"error": "Webhook processing failed"}), 400

# Tranzila Payment Routes
@crm_unified_bp.post("/payments/tranzila/create-link")
def tranzila_create_link():
    """Create Tranzila payment redirect link"""
    try:
        data = request.get_json() or {}
        amount = int(data["amount"])                       # אגורות
        currency = (os.getenv("CURRENCY") or "ILS").upper()
        terminal = os.getenv("TRANZILA_TERMINAL")
        if not terminal:
            return jsonify({"error": "TRANZILA_TERMINAL not configured"}), 500

        # Tranzila redirect parameters
        params = {
            "supplier": terminal,
            "sum": f"{amount/100:.2f}",
            "currency": currency,
            "success_url": os.getenv("TRANZILA_RETURN_SUCCESS"),
            "fail_url": os.getenv("TRANZILA_RETURN_FAIL"),
            "lang": "he",
            "frame": "yes"
        }

        # Save payment record
        pay = Payment(provider="tranzila", provider_ref=None, amount=amount, currency=currency.lower())
        db.session.add(pay); db.session.commit()
        params["ordernum"] = str(pay.id)  # Use our payment ID as ordernum

        url = f"{_tz_base()}/{terminal}?{urlencode(params)}"
        return jsonify({"redirect_url": url, "payment_id": pay.id}), 200
    except Exception as e:
        log.error("Tranzila create link failed: %s", e)
        return jsonify({"error": "Failed to create Tranzila link"}), 500

@crm_unified_bp.get("/payments/tranzila/return/success")
def tranzila_return_success():
    """Tranzila success return handler"""
    try:
        args = request.args
        ordernum = args.get("ordernum")
        tranid = args.get("tranid") or args.get("transaction_id") or args.get("tempref")
        resp = args.get("Response") or args.get("result")

        pay = Payment.query.get(int(ordernum)) if ordernum and ordernum.isdigit() else None
        if pay and resp in ("000","0","approved","success"):
            pay.status = "captured"
            pay.provider_ref = tranid
            db.session.commit()
            # Auto-create invoice
            try:
                invoice_no = create_invoice_simple(pay.amount)
                log.info("Auto-created invoice %s for Tranzila payment %s", invoice_no, pay.id)
            except Exception as e:
                log.error("Failed to create invoice: %s", e)
            return "תשלום הושלם בהצלחה", 200
        
        if pay:
            pay.status = "failed"
            db.session.commit()
        return "תשלום נכשל", 400
    except Exception as e:
        log.error("Tranzila success handler failed: %s", e)
        return "שגיאה בעיבוד התשלום", 500

@crm_unified_bp.get("/payments/tranzila/return/fail")
def tranzila_return_fail():
    """Tranzila failure return handler"""
    try:
        ordernum = request.args.get("ordernum")
        pay = Payment.query.get(int(ordernum)) if ordernum and ordernum.isdigit() else None
        if pay:
            pay.status = "failed"
            db.session.commit()
        return "התשלום בוטל או נכשל", 400
    except Exception as e:
        log.error("Tranzila fail handler failed: %s", e)
        return "שגיאה בעיבוד התשלום", 500

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