"""
Payments & CRM API - תשלומים, חשבוניות וחוזים לפי הנחיות 100% GO
NOTE: Stripe deprecated - use PayPal + Tranzila in api_crm_unified.py
"""
from flask import Blueprint, request, jsonify, send_file
import logging
import os
import time
import base64
from datetime import datetime
from server.models_sql import Deal, Payment, Invoice, Contract, Customer
from server.db import db
from server.services.invoice_service import create_invoice_for_payment

api_bp = Blueprint("api_payments", __name__, url_prefix="/api")
log = logging.getLogger("api.payments")

# === DEPRECATED STRIPE ROUTES ===

@api_bp.post("/payments/create-intent")
def deprecated_stripe_payment():
    """Deprecated Stripe route - use PayPal/Tranzila instead"""
    return jsonify({
        "error": "Stripe deprecated for Israeli market. Use PayPal (/api/crm/payments/create) instead."
    }), 410

# Keep old routes for backward compatibility
@api_bp.post("/payments/webhook")
def deprecated_webhook():
    return jsonify({"error": "Use new webhook endpoints"}), 410
    except Exception as e:
        log.error("Payment intent creation failed: %s", e)
        return jsonify({"error": "Payment creation failed"}), 500

@api_bp.post("/webhook/stripe")
def stripe_webhook():
    """Stripe webhook לעדכון סטטוס תשלומים"""
    try:
        payload = request.data
        sig = request.headers.get("Stripe-Signature", "")
        endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if not endpoint_secret:
            log.warning("Stripe webhook secret not configured")
            return ("", 400)
        
        try:
            event = stripe.Webhook.construct_event(payload, sig, endpoint_secret)
        except Exception as e:
            log.error("Stripe webhook signature verification failed: %s", e)
            return (str(e), 400)

        if event["type"] == "payment_intent.succeeded":
            pi = event["data"]["object"]
            payment = Payment.query.filter_by(stripe_payment_intent=pi["id"]).first()
            
            if payment:
                payment.status = "succeeded"
                db.session.commit()
                log.info("Payment succeeded: %s", pi["id"])
                
                # יצירת חשבונית אוטומטית
                try:
                    invoice = create_invoice_for_payment(payment)
                    log.info("Invoice created automatically: %s", invoice.invoice_number)
                except Exception as e:
                    log.error("Auto invoice creation failed: %s", e)
            else:
                log.warning("Payment not found for intent: %s", pi["id"])
                
        return ("", 204)
        
    except Exception as e:
        log.error("Stripe webhook error: %s", e)
        return ("", 400)

# === INVOICES ===

@api_bp.get("/invoices/<invoice_number>")
def get_invoice(invoice_number):
    """הורדת חשבונית"""
    try:
        inv = Invoice.query.filter_by(invoice_number=invoice_number).first_or_404()
        return send_file(inv.pdf_path, as_attachment=True)
    except Exception as e:
        log.error("Invoice download failed: %s", e)
        return jsonify({"error": "Invoice not found"}), 404

@api_bp.post("/invoices/create")
def create_invoice_manual():
    """יצירת חשבונית ידנית"""
    try:
        data = request.get_json() or {}
        payment_id = int(data["payment_id"])
        
        payment = Payment.query.get_or_404(payment_id)
        invoice = create_invoice_for_payment(payment)
        
        return jsonify({
            "invoice_number": invoice.invoice_number,
            "download_url": f"/api/invoices/{invoice.invoice_number}"
        })
        
    except Exception as e:
        log.error("Manual invoice creation failed: %s", e)
        return jsonify({"error": "Invoice creation failed"}), 500

# === CONTRACTS ===

def render_contract_html(deal, signer_name=None, signature_png=None):
    """רינדור HTML עבור חוזה"""
    company = os.getenv("COMPANY_NAME", "AgentLocator")
    
    signature_html = ""
    if signature_png and signer_name:
        # המרת חתימה ל-Base64 HTML
        sig_b64 = base64.b64encode(signature_png).decode('utf-8')
        signature_html = f'''
        <div class="signature-section">
            <p><strong>חתימה:</strong> {signer_name}</p>
            <img src="data:image/png;base64,{sig_b64}" style="max-width: 200px; border: 1px solid #ccc;">
            <p>תאריך חתימה: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        '''
    
    template = f"""
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head>
        <meta charset="utf-8"/>
        <title>חוזה מספר {deal.id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; direction: rtl; }}
            .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; }}
            .contract-body {{ margin: 20px 0; line-height: 1.6; }}
            .signature-section {{ margin-top: 40px; padding: 20px; border: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>חוזה שירות</h1>
            <h2>{company}</h2>
            <p>חוזה מספר: {deal.id}</p>
        </div>
        
        <div class="contract-body">
            <h3>פרטי החוזה:</h3>
            <p><strong>נושא:</strong> {deal.title or 'שירות נדל"ן'}</p>
            <p><strong>סכום:</strong> {(deal.amount or 0) / 100:.2f} ש"ח</p>
            
            <h3>תנאי השירות:</h3>
            <p>החברה מתחייבת לספק שירותי נדל"ן מקצועיים בהתאם לדרישות הלקוח.</p>
            <p>התשלום יבוצע בהתאם להסכמה.</p>
            
            <h3>תנאים כלליים:</h3>
            <ul>
                <li>החוזה תקף למשך שנה מתאריך החתימה</li>
                <li>ניתן לבטל את החוזה בהודעה של 30 יום מראש</li>
                <li>המחירים כוללים מע"מ</li>
            </ul>
        </div>
        
        {signature_html}
    </body>
    </html>
    """
    
    return template

@api_bp.get("/contracts/preview")
def contract_preview():
    """תצוגה מקדימה של חוזה"""
    try:
        deal_id = int(request.args["deal_id"])
        deal = Deal.query.get_or_404(deal_id)
        html = render_contract_html(deal)
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        log.error("Contract preview failed: %s", e)
        return jsonify({"error": "Contract preview failed"}), 500

@api_bp.post("/contracts/sign")
def contract_sign():
    """חתימה על חוזה"""
    try:
        data = request.get_json() or {}
        deal_id = int(data["deal_id"])
        name = data.get("name", "")
        sig_b64 = data["signature_b64"].split(",")[-1]  # הסרת data:image prefix
        sig_bytes = base64.b64decode(sig_b64)

        deal = Deal.query.get_or_404(deal_id)
        html = render_contract_html(deal, signer_name=name, signature_png=sig_bytes)
        
        # יצירת תיקיית חוזים
        out_dir = os.path.join("server", "static", "contracts")
        os.makedirs(out_dir, exist_ok=True)
        
        # יצירת מספר חוזה יחודי
        contract_prefix = os.getenv('CONTRACT_PREFIX', 'AGR')
        number = f"{contract_prefix}-{deal_id}-{int(time.time())}"
        
        # שמירת HTML
        html_path = os.path.join(out_dir, f"{number}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        pdf_path = html_path  # Default to HTML if no PDF converter
        
        # נסיון המרה ל-PDF
        try:
            import pdfkit
            pdf_path = os.path.join(out_dir, f"{number}.pdf")
            pdfkit.from_string(html, pdf_path, options={'encoding': 'UTF-8'})
        except ImportError:
            log.info("pdfkit not available, saving contract as HTML")
        except Exception as e:
            log.warning("PDF conversion failed: %s, using HTML", e)

        # שמירת חוזה במסד הנתונים
        contract = Contract()
        contract.deal_id = deal_id
        contract.template_name = "default"
        contract.version = "v1"
        contract.html_path = ""
        contract.pdf_path = pdf_path.replace("\\", "/")
        contract.signed_name = name
        contract.signed_at = datetime.utcnow()
        contract.signed_ip = request.remote_addr
        
        db.session.add(contract)
        db.session.commit()
        
        log.info("Contract signed: %s by %s", number, name)
        
        return jsonify({
            "ok": True,
            "contract_number": number,
            "download_url": f"/api/contracts/{number}"
        })
        
    except Exception as e:
        log.error("Contract signing failed: %s", e)
        return jsonify({"error": "Contract signing failed"}), 500

@api_bp.get("/contracts/<contract_number>")
def get_contract(contract_number):
    """הורדת חוזה חתום"""
    try:
        contract = Contract.query.filter(
            Contract.pdf_path.like(f"%{contract_number}%")
        ).first_or_404()
        
        return send_file(contract.pdf_path, as_attachment=True)
    except Exception as e:
        log.error("Contract download failed: %s", e)
        return jsonify({"error": "Contract not found"}), 404

# === CRM DATA ===

@api_bp.get("/deals")
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

@api_bp.post("/deals")
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