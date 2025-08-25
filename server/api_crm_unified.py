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

# Create unified API blueprint for new endpoints
api_bp = Blueprint("api", __name__, url_prefix="/api")

# PayPal Configuration
def _pp_base():
    return "https://api-m.sandbox.paypal.com" if os.getenv("PAYPAL_ENV","sandbox")=="sandbox" else "https://api-m.paypal.com"

def _pp_token():
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    client_secret = os.getenv("PAYPAL_SECRET")
    if not client_id or not client_secret:
        raise ValueError("PayPal credentials not configured")
    r = requests.post(_pp_base()+"/v1/oauth2/token",
                      auth=(client_id, client_secret),
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

# === MULTI-TENANT PAYMENTS API ===

import os
from server.providers.payments import create_payment_link, sys_enabled
from server.models_sql import PaymentGateway

@crm_unified_bp.post("/payments/create-intent")
def deprecated_stripe():
    """Deprecated Stripe route - redirected to new providers"""
    return jsonify({"error":"Stripe deprecated. Use /api/crm/payments/create"}), 410

@crm_unified_bp.post("/payments/create")
def payments_create():
    """Multi-tenant payment creation with simulation support"""
    try:
        data = request.get_json() or {}
        business_id = int(data["business_id"])       # Required to know which business
        amount = int(data["amount"])                 # אגורות
        currency = (data.get("currency") or "ILS").upper()
        provider = (data.get("provider") or "").lower()

        biz = Business.query.get(business_id)
        if not biz:
            return jsonify({"error": "Business not found"}), 404
        gw = PaymentGateway.query.filter_by(business_id=biz.id, provider=(provider or biz.default_provider)).first()

        # Create payment record even in simulation
        pay = Payment(
            business_id=biz.id, 
            provider=(provider or biz.default_provider or "paypal"),
            amount=amount, 
            currency=currency.lower(),
            status=("created" if sys_enabled() and biz.payments_enabled else "simulated")
        )
        db.session.add(pay)
        db.session.commit()

        res = create_payment_link(biz, gw, provider, amount, currency, pay.id)
        
        # Save provider_ref if received (PayPal order_id)
        if res.data.get("order_id"): 
            pay.provider_ref = res.data["order_id"]
            db.session.commit()

        return jsonify({
            "ok": res.ok, 
            "payment_id": pay.id, 
            "note": res.error,
            **res.data
        }), (200 if res.ok else 202)
    except Exception as e:
        log.error("Payment creation failed: %s", e)
        return jsonify({"error": "Payment creation failed"}), 500

# ---- Simulation Screen (when payments disabled) ----
@crm_unified_bp.get("/__payments/mock")
def payments_mock():
    """Internal payment simulation screen"""
    pid = request.args.get("payment_id")
    amount = request.args.get("amount", "0")
    currency = request.args.get("currency", "ILS")
    
    return f"""<html dir="rtl" lang="he">
<head><meta charset="UTF-8"><title>סימולציית תשלום</title></head>
<body style="font-family: Arial; padding: 20px;">
    <h3>סימולציית תשלום</h3>
    <p>סכום: {int(amount)/100:.2f} {currency}</p>
    <p>מזהה תשלום: {pid}</p>
    <form method="post" action="/api/crm/payments/simulate-capture">
      <input type="hidden" name="payment_id" value="{pid or ''}" />
      <button type="submit" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 5px;">
        ✅ סמן כהושלם (captured)
      </button>
    </form>
    <br>
    <form method="post" action="/api/crm/payments/simulate-capture">
      <input type="hidden" name="payment_id" value="{pid or ''}" />
      <input type="hidden" name="status" value="failed" />
      <button type="submit" style="padding: 10px 20px; background: #dc3545; color: white; border: none; border-radius: 5px;">
        ❌ סמן כנכשל (failed)
      </button>
    </form>
</body></html>""", 200, {'Content-Type': 'text/html; charset=utf-8'}

@crm_unified_bp.post("/payments/simulate-capture")
def payments_simulate_capture():
    """Simulate payment capture/failure"""
    try:
        pid = request.form.get("payment_id") or (request.get_json() or {}).get("payment_id")
        status = request.form.get("status", "captured")
        
        pay = Payment.query.get_or_404(int(pid))
        pay.status = status
        db.session.commit()
        
        # Auto-create invoice if captured
        if status == "captured":
            try:
                invoice_no = create_invoice_simple(pay.amount)
                log.info("Auto-created invoice %s for simulated payment %s", invoice_no, pay.id)
            except Exception as e:
                log.error("Failed to create invoice: %s", e)
        
        return jsonify({"ok": True, "payment_id": pay.id, "status": pay.status})
    except Exception as e:
        log.error("Payment simulation failed: %s", e)
        return jsonify({"error": "Simulation failed"}), 500 
    except Exception as e:
        log.error("PayPal create order failed: %s", e)
        return jsonify({"error": "Failed to create PayPal order"}), 500

@crm_unified_bp.post("/webhook/paypal")
def paypal_webhook():
    """PayPal webhook with business context recovery"""
    try:
        if not sys_enabled(): 
            return ("", 204)
            
        evt = request.get_json() or {}
        et = evt.get("event_type", "")
        res = evt.get("resource", {}) or {}
        
        # Get custom_id from purchase units (contains "biz_id:payment_id")
        custom_id = ""
        if "purchase_units" in res and res["purchase_units"]:
            custom_id = (res["purchase_units"][0].get("custom_id") or "")
        
        # Parse "biz:pay" format
        try:
            biz_id, pid = [int(x) for x in (custom_id.split(":") if custom_id else [])]
        except Exception:
            return ("", 204)
            
        pay = Payment.query.get(pid)
        if not pay or pay.business_id != biz_id: 
            return ("", 204)
            
        if et in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED"):
            pay.status = "captured" if et == "PAYMENT.CAPTURE.COMPLETED" else "approved"
            if not pay.provider_ref: 
                pay.provider_ref = res.get("id")
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
        return ("", 204)

# Legacy routes cleanup - all payment creation now goes through /payments/create

@crm_unified_bp.get("/payments/tranzila/return/success")
def tranzila_return_success():
    """Tranzila success return handler with business context recovery"""
    try:
        if not sys_enabled(): 
            return ("", 204)
            
        args = request.args
        pid = args.get("ordernum")  # Our payment ID
        biz_id = args.get("udf")    # Business ID from udf parameter
        resp = args.get("Response") or args.get("result")
        tranid = args.get("tranid") or args.get("tempref")
        
        if not (pid and pid.isdigit() and biz_id and biz_id.isdigit()):
            return ("", 204)
            
        pay = Payment.query.get(int(pid))
        if not pay or pay.business_id != int(biz_id): 
            return ("", 204)
            
        if resp in ("000", "0", "approved", "success"):
            pay.status = "captured"
            pay.provider_ref = tranid or pay.provider_ref
            db.session.commit()
            
            # Auto-create invoice
            try:
                invoice_no = create_invoice_simple(pay.amount)
                log.info("Auto-created invoice %s for Tranzila payment %s", invoice_no, pay.id)
            except Exception as e:
                log.error("Failed to create invoice: %s", e)
                
            return "תשלום הושלם בהצלחה", 200
        
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
        pid = request.args.get("ordernum")
        if pid and pid.isdigit():
            pay = Payment.query.get(int(pid))
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

# === UNIFIED API ENDPOINTS ===

@api_bp.route("/threads", methods=["GET"])
def list_threads():
    """Get threads with optional filtering"""
    try:
        from server.dao_crm import get_threads
        business_id = request.args.get('business_id', 1, type=int)
        type_ = request.args.get('type') or None  # whatsapp or call
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        threads = get_threads(business_id=business_id, type_=type_, limit=limit, offset=offset)
        return jsonify({"threads": threads, "count": len(threads)}), 200
        
    except Exception as e:
        log.error(f"Error listing threads: {e}")
        return jsonify({"error": "Failed to list threads"}), 500

@api_bp.route("/threads/<int:thread_id>/messages", methods=["GET"])
def get_thread_messages(thread_id: int):
    """Get messages for a specific thread"""
    try:
        from server.dao_crm import get_thread_messages
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        messages = get_thread_messages(thread_id=thread_id, limit=limit, offset=offset)
        return jsonify({"messages": messages, "count": len(messages)}), 200
        
    except Exception as e:
        log.error(f"Error getting thread messages: {e}")
        return jsonify({"error": "Failed to get messages"}), 500

@api_bp.route("/whatsapp/send", methods=["POST"])
def whatsapp_send():
    """Send WhatsApp message through unified provider system"""
    try:
        data = request.get_json(force=True)
        to = data.get("to")
        text = data.get("text")
        media_url = data.get("media_url")
        provider = data.get("provider", "auto").lower()
        business_id = data.get("business_id", 1)
        
        if not to:
            return jsonify({"error": "'to' field is required"}), 400
        
        from server.whatsapp_outbound import send_and_record
        result = send_and_record(
            to=to, 
            text=text, 
            media_url=media_url, 
            provider=provider, 
            business_id=business_id
        )
        
        if result["ok"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        log.error(f"WhatsApp send error: {e}")
        return jsonify({"error": "Failed to send message"}), 500