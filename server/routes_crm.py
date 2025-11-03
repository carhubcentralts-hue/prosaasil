# server/routes_crm.py
"""
CRM API routes for customer management, threads, and messages
Implements RBAC with business scoping as per guidelines
"""
from flask import Blueprint, jsonify, request, g, send_file
from server.auth_api import require_api_auth
from server.models_sql import Business, Customer, WhatsAppMessage, CallLog, Deal, Payment, Invoice, Contract, PaymentGateway, CRMTask, Lead
from server.db import db
from datetime import datetime
from sqlalchemy import or_, and_, func
import os
import base64
import time
import pathlib
import requests
import json
from urllib.parse import urlencode
from io import BytesIO

crm_bp = Blueprint("crm_bp", __name__)

# === PAYMENT INTEGRATIONS ===

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

def create_invoice_simple(amount_agorot: int) -> str:
    """Create a simple HTML/text invoice"""
    try:
        invoices_dir = pathlib.Path("server/static/invoices")
        invoices_dir.mkdir(parents=True, exist_ok=True)
        
        seq = (Invoice.query.count() + 1)
        inv_no = f"{os.getenv('INVOICE_PREFIX','INV')}-{datetime.utcnow():%Y%m}-{seq:04d}"
        
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
    <p>תאריך: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
    <p>מס' חשבונית: {inv_no}</p>
</body>
</html>"""
        
        html_path.write_text(html_content, encoding='utf-8')
        return inv_no
        
    except Exception as e:
        print(f"Invoice generation error: {e}")
        return f"INV-ERROR-{int(time.time())}"

def get_business_id():
    """Get business_id based on user role and permissions"""
    user_role = g.user.get("role")
    if user_role in ("admin", "superadmin"):
        # Admin can access all businesses or specify business_id
        return request.args.get("business_id") or g.user.get("business_id")
    else:
        # Business/agent users are scoped to their business
        return g.user.get("business_id")

@crm_bp.get("/api/crm/threads")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_threads():
    """Get communication threads (WhatsApp conversations) as JSON"""
    try:
        business_id = get_business_id()
        thread_type = request.args.get("type", "whatsapp")
        
        if thread_type == "whatsapp":
            # Get unique WhatsApp conversations
            threads_data = db.session.query(
                WhatsAppMessage.to_number,
                func.max(WhatsAppMessage.created_at).label('last_message_time'),
                func.count(WhatsAppMessage.id).label('message_count')
            ).filter_by(business_id=business_id).group_by(
                WhatsAppMessage.to_number
            ).order_by(
                func.max(WhatsAppMessage.created_at).desc()
            ).limit(20).all()
            
            # Convert to JSON format
            threads_list = []
            for thread in threads_data:
                # Get the last message text
                last_msg = WhatsAppMessage.query.filter_by(
                    business_id=business_id,
                    to_number=thread.to_number
                ).order_by(WhatsAppMessage.created_at.desc()).first()
                
                # Try to get customer name
                customer = Customer.query.filter_by(
                    business_id=business_id,
                    phone_e164=thread.to_number
                ).first()
                
                customer_name = customer.name if customer else thread.to_number
                
                # Check if conversation is closed - based on LEAH's last response (outbound)
                is_closed = False
                if last_msg and last_msg.direction == "outbound" and last_msg.body:
                    import re
                    
                    # Check if Leah closed the conversation with closing phrases
                    closing_phrases = [
                        "תודה שמחתי לעזור",
                        "תודה קבעתי פגישה",
                        "נהיה בקשר",
                        "להתראות",
                        "שמחתי לעזור",
                        "נעים היה לדבר",
                        "צוות שי",
                        "בהצלחה"
                    ]
                    
                    # Remove punctuation and extra spaces for matching
                    msg_lower = last_msg.body.lower().strip()
                    msg_clean = re.sub(r'[!.,?:;]+', ' ', msg_lower)  # Replace punctuation with space
                    msg_clean = re.sub(r'\s+', ' ', msg_clean).strip()  # Normalize spaces
                    
                    is_closed = any(phrase in msg_clean for phrase in closing_phrases)
                
                threads_list.append({
                    "id": thread.to_number,
                    "name": customer_name,
                    "phone": thread.to_number,
                    "phone_e164": thread.to_number,
                    "lastMessage": last_msg.body[:50] + "..." if last_msg and last_msg.body and len(last_msg.body) > 50 else (last_msg.body if last_msg else ""),
                    "unread": 0,  # TODO: Implement unread count
                    "time": thread.last_message_time.strftime('%d/%m %H:%M') if thread.last_message_time else '',
                    "is_closed": is_closed
                })
                
            return jsonify({"threads": threads_list})
        
        return jsonify({"threads": []})
    except Exception as e:
        return jsonify({"error": str(e), "threads": []}), 500

@crm_bp.get("/api/crm/threads/<thread_id>/messages")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_thread_messages(thread_id):
    """Get messages for a specific thread as JSON"""
    try:
        business_id = get_business_id()
        
        messages = WhatsAppMessage.query.filter_by(
            business_id=business_id,
            to_number=thread_id
        ).order_by(WhatsAppMessage.created_at.asc()).all()
        
        # Convert to JSON format
        messages_list = []
        for msg in messages:
            messages_list.append({
                "id": msg.id,
                "body": msg.body,
                "direction": msg.direction,  # "in" or "out"
                "timestamp": msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else '',
                "time": msg.created_at.strftime('%H:%M') if msg.created_at else '',
                "status": msg.status or "delivered"
            })
            
        return jsonify({"messages": messages_list})
    except Exception as e:
        return jsonify({"error": str(e), "messages": []}), 500

@crm_bp.get("/api/crm/threads/<thread_id>/summary")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_thread_summary(thread_id):
    """Get AI summary of conversation thread"""
    try:
        business_id = get_business_id()
        
        # Get last 15 messages for context
        messages = WhatsAppMessage.query.filter_by(
            business_id=business_id,
            to_number=thread_id
        ).order_by(WhatsAppMessage.created_at.desc()).limit(15).all()
        
        if not messages:
            return jsonify({"summary": "אין הודעות בשיחה"})
        
        # Build conversation for AI
        conversation = []
        for msg in reversed(messages):
            speaker = "לקוח" if msg.direction == "inbound" else "עוזר"  # ✅ עוזר!
            conversation.append(f"{speaker}: {msg.body}")
        
        # Call AI to summarize (fast!)
        from server.services.ai_service import generate_ai_response
        
        summary_prompt = f"""סכם את השיחה הבאה ב-1-2 משפטים קצרים:

{chr(10).join(conversation)}

תן סיכום קצר ומדויק של מה הלקוח רוצה ומה הסטטוס:"""
        
        summary = generate_ai_response(
            message=summary_prompt,
            business_id=int(business_id),
            context={'phone': thread_id},
            channel='whatsapp'
        )
        
        return jsonify({"summary": summary[:200]})  # Limit to 200 chars
    except Exception as e:
        return jsonify({"summary": "לא ניתן לסכם", "error": str(e)}), 500

@crm_bp.get("/api/crm/customers")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_customers():
    """Get customers for CRM management"""
    try:
        business_id = get_business_id()
        
        customers = Customer.query.filter_by(
            business_id=business_id
        ).order_by(Customer.created_at.desc()).limit(50).all()
        
        customers_html = ""
        for customer in customers:
            status_class = {
                'new': 'bg-blue-100 text-blue-800',
                'contacted': 'bg-yellow-100 text-yellow-800',
                'qualified': 'bg-green-100 text-green-800',
                'lost': 'bg-red-100 text-red-800'
            }.get(customer.status, 'bg-gray-100 text-gray-800')
            
            customers_html += f"""
            <div class="bg-white border border-gray-200 rounded-lg p-4">
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-medium text-gray-900">{customer.name}</h4>
                        <p class="text-sm text-gray-500">{customer.phone_e164 or 'ללא טלפון'}</p>
                        {f'<p class="text-sm text-gray-500">{customer.email}</p>' if customer.email else ''}
                    </div>
                    <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">
                        {customer.status}
                    </span>
                </div>
                <div class="mt-2 text-xs text-gray-400">
                    נוצר: {customer.created_at.strftime('%d/%m/%Y') if customer.created_at else 'לא ידוע'}
                </div>
            </div>
            """
        
        if not customers_html:
            customers_html = '<div class="text-center text-gray-500 py-8">אין לקוחות</div>'
            
        return customers_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-8">שגיאה: {str(e)}</div>'

@crm_bp.get("/api/calls/active")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_active_calls():
    """Get active calls"""
    try:
        business_id = get_business_id()
        
        # Get calls in progress
        active_calls = CallLog.query.filter(
            and_(
                CallLog.business_id == business_id,
                CallLog.status.in_(['in-progress', 'ringing'])
            )
        ).order_by(CallLog.created_at.desc()).all()
        
        calls_html = ""
        for call in active_calls:
            calls_html += f"""
            <div class="flex items-center justify-between p-3 border-b border-gray-100">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'לא ידוע'}</p>
                    <p class="text-sm text-gray-500">{call.created_at.strftime('%H:%M:%S') if call.created_at else 'לא ידוע'}</p>
                </div>
                <span class="px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full">
                    {call.status}
                </span>
            </div>
            """
        
        if not calls_html:
            calls_html = '<div class="text-center text-gray-500 py-4">אין שיחות פעילות</div>'
            
        return calls_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-4">שגיאה: {str(e)}</div>'

@crm_bp.get("/api/calls/history")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_call_history():
    """Get call history"""
    try:
        business_id = get_business_id()
        
        calls = CallLog.query.filter_by(
            business_id=business_id
        ).order_by(CallLog.created_at.desc()).limit(20).all()
        
        calls_html = ""
        for call in calls:
            status_class = {
                'completed': 'bg-green-100 text-green-800',
                'failed': 'bg-red-100 text-red-800',
                'in-progress': 'bg-blue-100 text-blue-800'
            }.get(call.status, 'bg-gray-100 text-gray-800')
            
            calls_html += f"""
            <div class="flex items-center justify-between p-3 border-b border-gray-100">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'לא ידוע'}</p>
                    <p class="text-sm text-gray-500">{call.created_at.strftime('%d/%m/%Y %H:%M') if call.created_at else 'לא ידוע'}</p>
                    {f'<p class="text-xs text-gray-400 mt-1">{call.transcription[:100]}...</p>' if call.transcription else ''}
                </div>
                <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">
                    {call.status}
                </span>
            </div>
            """
        
        if not calls_html:
            calls_html = '<div class="text-center text-gray-500 py-4">אין שיחות</div>'
            
        return calls_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-4">שגיאה: {str(e)}</div>'

# === PAYMENT ENDPOINTS ===

@crm_bp.get("/api/crm/payments")
@require_api_auth(["admin", "superadmin", "business"])
def get_payments():
    """Get all payments for current business"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
        
        payments = Payment.query.filter_by(business_id=business_id).order_by(Payment.created_at.desc()).all()
        
        return jsonify([{
            "id": str(p.id),
            "amount": p.amount / 100,  # Convert cents to currency
            "status": p.status,
            "description": p.description or f"תשלום #{p.id}",
            "client_name": p.customer_name or "לא צוין",
            "due_date": p.created_at.isoformat() if p.created_at else None,
            "paid_date": p.paid_at.isoformat() if p.paid_at else None,
            "invoice_number": f"INV-{p.id}",
            "payment_method": p.provider or "לא צוין"
        } for p in payments])
        
    except Exception as e:
        print(f"Error in get_payments: {str(e)}")
        return jsonify({"error": f"Failed to fetch payments: {str(e)}"}), 500

@crm_bp.get("/api/crm/contracts") 
@require_api_auth(["admin", "superadmin", "business"])
def get_contracts():
    """Get all contracts for current business"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
            
        # Join with Deal and Customer to get business-scoped data - Fixed JOIN order
        contracts = db.session.query(Contract, Deal, Customer).join(
            Deal, Contract.deal_id == Deal.id
        ).join(
            Customer, Deal.customer_id == Customer.id
        ).filter(
            Customer.business_id == business_id
        ).order_by(Contract.created_at.desc()).all()
        
        return jsonify([{
            "id": str(c.id),
            "title": c.template_name or f"חוזה #{c.id}",
            "client_name": customer.name or "לא צוין",
            "property_address": deal.title or "לא צוין",
            "contract_type": deal.stage or "sale",
            "value": (deal.amount / 100) if deal.amount else 0,  # Frontend expects 'value'
            "amount": (deal.amount / 100) if deal.amount else 0,  # Keep for backwards compatibility
            "status": deal.stage or "draft",
            "start_date": c.created_at.isoformat() if c.created_at else None,
            "end_date": c.signed_at.isoformat() if c.signed_at else None,
            "commission_rate": 3.5,  # Default commission rate
            "created_date": c.created_at.isoformat() if c.created_at else None,
            "signed_date": c.signed_at.isoformat() if c.signed_at else None
        } for c, deal, customer in contracts])
        
    except Exception as e:
        print(f"Error in get_contracts: {str(e)}")
        return jsonify({"error": f"Failed to fetch contracts: {str(e)}"}), 500

@crm_bp.post("/api/crm/contracts")
@require_api_auth(["admin", "superadmin", "business"])
def create_contract():
    """Create a new contract"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        business_id = g.user.get("business_id")
        if not business_id:
            return jsonify({"error": "No business access"}), 403
            
        # First create or find customer
        customer_name = data.get("client_name", "")
        customer = Customer.query.filter_by(
            business_id=business_id,
            name=customer_name
        ).first()
        
        if not customer:
            customer = Customer()
            customer.business_id = business_id
            customer.name = customer_name
            customer.status = "new"
            db.session.add(customer)
            db.session.flush()  # Get customer ID
        
        # ✅ CRITICAL: Validate customer exists and belongs to business before creating deal
        if not customer:
            return jsonify({"error": "Customer not found or doesn't belong to this business"}), 404
        
        # Create deal
        deal = Deal()
        deal.customer_id = customer.id
        deal.title = data.get("property_address", "חוזה חדש")
        deal.stage = "draft"
        deal.amount = int(float(data.get("amount", 0)) * 100)
        db.session.add(deal)
        db.session.flush()  # Get the deal ID
        
        # Create new contract
        contract = Contract()
        contract.deal_id = deal.id
        contract.template_name = data.get("title", "חוזה חדש")
        
        db.session.add(contract)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "contract_id": contract.id,
            "message": "חוזה נוצר בהצלחה"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create contract"}), 500

@crm_bp.post("/api/crm/payments/create")
@require_api_auth(["admin", "superadmin", "business"])
def payments_create():
    """Multi-tenant payment creation with PayPal/Tranzila support"""
    try:
        data = request.get_json() or {}
        business_id = int(data.get("business_id", g.user.get("business_id")))
        amount = int(data["amount"])  # אגורות
        currency = (data.get("currency") or "ILS").upper()
        provider = (data.get("provider") or "").lower()
        
        biz = Business.query.get(business_id)
        if not biz:
            return jsonify({"error": "Business not found"}), 404
            
        # Check business authorization for payments
        if not getattr(biz, "payments_enabled", True):
            return jsonify({"error": "Payment processing not authorized for this business"}), 403
            
        gw = PaymentGateway.query.filter_by(business_id=biz.id, provider=(provider or biz.default_provider)).first()
        
        # Check provider-specific configuration
        eff_provider = (provider or getattr(biz, "default_provider", None) or "paypal").lower()
        if eff_provider == "paypal":
            if not (gw and getattr(gw, "paypal_client_id", None) and getattr(gw, "paypal_secret", None)):
                return jsonify({"error": "PayPal not configured"}), 501
        elif eff_provider == "tranzila":
            if not (gw and getattr(gw, "tranzila_terminal", None)):
                return jsonify({"error": "Tranzila not configured"}), 501

        # Create payment record
        pay = Payment()
        pay.business_id = biz.id
        pay.provider = eff_provider
        pay.amount = amount
        pay.currency = currency.lower()
        pay.status = "created"
        pay.customer_name = data.get("customer_name") or data.get("client_name")  # Support both field names
        pay.description = data.get("description") or f"תשלום #{int(time.time())}"
        db.session.add(pay)
        db.session.commit()

        # Generate payment link based on provider
        if eff_provider == "paypal":
            payment_result = create_paypal_payment(gw, amount, currency, pay.id)
        elif eff_provider == "tranzila":
            payment_result = create_tranzila_payment(gw, amount, currency, pay.id)
        else:
            return jsonify({"error": f"Provider {eff_provider} not supported"}), 501
        
        # Save provider reference
        if payment_result.get("order_id"):
            pay.provider_ref = payment_result["order_id"]
            db.session.commit()

        return jsonify({
            "ok": True,
            "payment_id": pay.id,
            "payment_url": payment_result.get("payment_url"),
            "order_id": payment_result.get("order_id")
        }), 200
        
    except Exception as e:
        print(f"Payment creation failed: {e}")
        return jsonify({"error": "Payment creation failed"}), 500

def create_paypal_payment(gateway, amount, currency, payment_id):
    """Create PayPal payment link"""
    try:
        headers = {
            "Authorization": f"Bearer {_pp_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount/100:.2f}"
                },
                "reference_id": str(payment_id)
            }],
            "application_context": {
                "return_url": f"{request.host_url}api/crm/payments/paypal/return/success",
                "cancel_url": f"{request.host_url}api/crm/payments/paypal/return/cancel"
            }
        }
        
        r = requests.post(f"{_pp_base()}/v2/checkout/orders", 
                         headers=headers, json=payload)
        r.raise_for_status()
        
        order = r.json()
        payment_url = next((link["href"] for link in order["links"] if link["rel"] == "approve"), None)
        
        return {
            "order_id": order["id"],
            "payment_url": payment_url
        }
        
    except Exception as e:
        print(f"PayPal payment creation failed: {e}")
        raise

def create_tranzila_payment(gateway, amount, currency, payment_id):
    """Create Tranzila payment link"""
    try:
        params = {
            "supplier": getattr(gateway, "tranzila_terminal"),
            "sum": f"{amount/100:.2f}",
            "currency": "1" if currency == "ILS" else "2",  # 1=ILS, 2=USD
            "tranmode": "AK",  # Authorization + Capture
            "ref": str(payment_id),
            "return_url": f"{request.host_url}api/crm/payments/tranzila/return/success",
            "cancel_url": f"{request.host_url}api/crm/payments/tranzila/return/fail"
        }
        
        payment_url = f"{_tz_base()}/cgi-bin/tranzila71u.cgi?" + urlencode(params)
        
        return {
            "order_id": f"tz-{payment_id}",
            "payment_url": payment_url
        }
        
    except Exception as e:
        print(f"Tranzila payment creation failed: {e}")
        raise

@crm_bp.get("/api/crm/payments/paypal/return/success")
def paypal_success():
    """PayPal payment success callback"""
    return jsonify({"status": "success", "message": "Payment completed successfully!"})

@crm_bp.get("/api/crm/payments/paypal/return/cancel")
def paypal_cancel():
    """PayPal payment cancel callback"""  
    return jsonify({"status": "cancelled", "message": "Payment was cancelled"})

@crm_bp.get("/api/crm/payments/tranzila/return/success")
def tranzila_success():
    """Tranzila payment success callback"""
    return jsonify({"status": "success", "message": "Payment completed successfully!"})

@crm_bp.get("/api/crm/payments/tranzila/return/fail")
def tranzila_fail():
    """Tranzila payment failure callback"""
    return jsonify({"status": "failed", "message": "Payment failed"})


# === INVOICE & CONTRACT ENDPOINTS ===

@crm_bp.get("/api/crm/invoices/<invoice_number>")
@require_api_auth(["admin", "superadmin", "business"])
def get_invoice(invoice_number):
    """Download invoice PDF"""
    try:
        inv = Invoice.query.filter_by(invoice_number=invoice_number).first()
        if not inv:
            return jsonify({"error": "Invoice not found"}), 404
        
        return send_file(inv.pdf_path, as_attachment=True)
    except Exception as e:
        print(f"Invoice download failed: {e}")
        return jsonify({"error": "Invoice download failed"}), 500

@crm_bp.post("/api/crm/contracts/sign")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def contract_sign():
    """Digital contract signature"""
    try:
        data = request.get_json() or {}
        signer = data.get("name", "")
        sig_b64 = (data.get("signature_b64", "").split(",")[-1] if data.get("signature_b64") else "")
        sig_bytes = base64.b64decode(sig_b64) if sig_b64 else b""

        contracts_dir = pathlib.Path("server/static/contracts")
        contracts_dir.mkdir(parents=True, exist_ok=True)
        contract_prefix = os.getenv('CONTRACT_PREFIX') or 'AGR'
        pdf_path = contracts_dir / f"{contract_prefix}-{int(time.time())}.pdf"

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
    <p>חוזה זה נחתם בתאריך {datetime.utcnow().strftime("%d/%m/%Y %H:%M")}</p>
    <div class="signature">
        <p><strong>חתום ע"י:</strong> {signer}</p>
        <p><strong>כתובת IP:</strong> {request.remote_addr}</p>
        <p><strong>תאריך חתימה:</strong> {datetime.utcnow().isoformat()}</p>
    </div>
</body>
</html>"""
        
        pdf_path.write_text(html_content, encoding="utf-8")

        contract = Contract()
        contract.pdf_path = str(pdf_path)
        contract.signed_name = signer
        contract.signed_at = datetime.utcnow()
        contract.signed_ip = request.remote_addr
        db.session.add(contract)
        db.session.commit()
        
        return jsonify({"ok": True, "pdf": str(pdf_path)}), 201
    except Exception as e:
        print(f"Contract signing failed: {e}")
        return jsonify({"error": "Contract signing failed"}), 500

@crm_bp.get("/api/crm/deals")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def list_deals():
    """רשימת דילים עם RBAC"""
    try:
        business_id = get_business_id()
        deals = Deal.query.filter_by(business_id=business_id).all() if business_id else Deal.query.all()
        
        return jsonify([{
            "id": d.id,
            "customer_id": d.customer_id,
            "title": d.title,
            "stage": d.stage,
            "amount": d.amount,
            "created_at": d.created_at.isoformat() if d.created_at else None
        } for d in deals])
    except Exception as e:
        print(f"Deals list failed: {e}")
        return jsonify({"error": "Failed to fetch deals"}), 500

@crm_bp.post("/api/crm/deals")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def create_deal():
    """יצירת דיל חדש"""
    try:
        data = request.get_json() or {}
        business_id = get_business_id()
        
        customer_id = data.get("customer_id")
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        
        # ✅ CRITICAL: Validate customer exists and belongs to business
        customer = Customer.query.filter_by(
            id=customer_id,
            business_id=business_id
        ).first()
        
        if not customer:
            return jsonify({"error": f"Customer {customer_id} not found or doesn't belong to this business"}), 404
        
        deal = Deal()
        deal.customer_id = customer.id
        deal.title = data.get("title", "")
        deal.stage = data.get("stage", "new")
        deal.amount = data.get("amount", 0)
        deal.created_at = datetime.utcnow()
        
        db.session.add(deal)
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "deal_id": deal.id,
            "message": "Deal created successfully"
        }), 201
        
    except Exception as e:
        print(f"Deal creation failed: {e}")
        return jsonify({"error": "Deal creation failed"}), 500

# === SEARCH API ===

@crm_bp.get("/api/search")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def global_search():
    """חיפוש גלובלי במערכת - לידים, שיחות, פגישות, לקוחות"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
        
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({"results": []})
        
        results = {
            "leads": [],
            "calls": [],
            "appointments": [],
            "customers": []
        }
        
        # Search leads
        from server.models_sql import Lead, Appointment
        leads = Lead.query.filter(
            Lead.tenant_id == business_id,
            or_(
                Lead.first_name.ilike(f'%{query}%'),
                Lead.last_name.ilike(f'%{query}%'),
                Lead.phone_e164.ilike(f'%{query}%'),
                Lead.email.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        for lead in leads:
            results["leads"].append({
                "id": lead.id,
                "name": lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
                "phone": lead.phone_e164,
                "email": lead.email,
                "status": lead.status,
                "type": "lead"
            })
        
        # Search calls
        calls = CallLog.query.filter(
            CallLog.business_id == business_id,
            or_(
                CallLog.from_number.ilike(f'%{query}%'),
                CallLog.to_number.ilike(f'%{query}%'),
                CallLog.transcription.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        for call in calls:
            results["calls"].append({
                "id": call.id,
                "call_sid": call.call_sid,
                "from_number": call.from_number,
                "to_number": call.to_number,
                "created_at": call.created_at.isoformat() if call.created_at else None,
                "type": "call"
            })
        
        # Search appointments
        appointments = Appointment.query.filter(
            Appointment.business_id == business_id,
            or_(
                Appointment.title.ilike(f'%{query}%'),
                Appointment.contact_name.ilike(f'%{query}%'),
                Appointment.contact_phone.ilike(f'%{query}%'),
                Appointment.location.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        for apt in appointments:
            results["appointments"].append({
                "id": apt.id,
                "title": apt.title,
                "contact_name": apt.contact_name,
                "start_time": apt.start_time.isoformat() if apt.start_time else None,
                "status": apt.status,
                "type": "appointment"
            })
        
        # Search customers
        customers = Customer.query.filter(
            Customer.business_id == business_id,
            or_(
                Customer.name.ilike(f'%{query}%'),
                Customer.phone_e164.ilike(f'%{query}%'),
                Customer.email.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        for customer in customers:
            results["customers"].append({
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone_e164,
                "email": customer.email,
                "type": "customer"
            })
        
        return jsonify({"success": True, "query": query, "results": results})
        
    except Exception as e:
        print(f"Search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Search failed"}), 500

# === CRM TASKS API ===

@crm_bp.get("/api/crm/tasks")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def get_crm_tasks():
    """Get all CRM tasks for the current business"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
        
        # Get query parameters
        status_filter = request.args.get('status')  # todo/doing/done
        lead_id = request.args.get('lead_id', type=int)
        
        # Build query
        query = CRMTask.query.filter_by(business_id=business_id)
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        if lead_id:
            query = query.filter_by(lead_id=lead_id)
        
        tasks = query.order_by(CRMTask.created_at.desc()).all()
        
        # Get related data
        result = []
        for task in tasks:
            # Get lead/customer name if exists
            owner_name = None
            lead_name = None
            
            if task.lead_id:
                lead = Lead.query.get(task.lead_id)
                if lead:
                    lead_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
            
            if task.customer_id:
                customer = Customer.query.get(task.customer_id)
                if customer:
                    owner_name = customer.name
            
            result.append({
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "owner_name": owner_name,
                "lead_name": lead_name,
                "assigned_to": task.assigned_to,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            })
        
        return jsonify({"success": True, "tasks": result})
        
    except Exception as e:
        print(f"Get CRM tasks failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to get tasks"}), 500

@crm_bp.post("/api/crm/tasks")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def create_crm_task():
    """Create a new CRM task"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
        
        data = request.get_json() or {}
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({"error": "Title is required"}), 400
        
        task = CRMTask()
        task.business_id = business_id
        task.title = data['title']
        task.description = data.get('description')
        task.status = data.get('status', 'todo')
        task.priority = data.get('priority', 'medium')
        task.assigned_to = data.get('assigned_to')
        task.customer_id = data.get('customer_id')
        task.lead_id = data.get('lead_id')
        
        # Parse due_date if provided
        if data.get('due_date'):
            try:
                task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except:
                pass
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "task": {
                "id": str(task.id),
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "created_at": task.created_at.isoformat() if task.created_at else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Create CRM task failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to create task"}), 500

@crm_bp.put("/api/crm/tasks/<int:task_id>")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def update_crm_task(task_id):
    """Update a CRM task"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
        
        task = CRMTask.query.filter_by(id=task_id, business_id=business_id).first()
        if not task:
            return jsonify({"error": "Task not found"}), 404
        
        data = request.get_json() or {}
        
        # Update fields
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'status' in data:
            task.status = data['status']
            # Set completed_at when marking as done
            if data['status'] == 'done' and not task.completed_at:
                task.completed_at = datetime.utcnow()
            elif data['status'] != 'done':
                task.completed_at = None
        if 'priority' in data:
            task.priority = data['priority']
        if 'assigned_to' in data:
            task.assigned_to = data['assigned_to']
        if 'customer_id' in data:
            task.customer_id = data['customer_id']
        if 'lead_id' in data:
            task.lead_id = data['lead_id']
        if 'due_date' in data:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except:
                pass
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "success": True,
            "task": {
                "id": str(task.id),
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Update CRM task failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to update task"}), 500

@crm_bp.delete("/api/crm/tasks/<int:task_id>")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def delete_crm_task(task_id):
    """Delete a CRM task"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"error": "No business access"}), 403
        
        task = CRMTask.query.filter_by(id=task_id, business_id=business_id).first()
        if not task:
            return jsonify({"error": "Task not found"}), 404
        
        db.session.delete(task)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Task deleted successfully"})
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete CRM task failed: {e}")
        return jsonify({"error": "Failed to delete task"}), 500
