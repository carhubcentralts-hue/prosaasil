"""
Receipts & Contracts API
⚠️ BUILD 154: All payment/contract features are DISABLED by default.
Set ENABLE_PAYMENTS=true and ENABLE_CONTRACTS=true in .env to enable.
"""
from flask import Blueprint, request, jsonify
from server.auth_api import require_api_auth
import uuid
import os
from datetime import datetime
import base64

# Blueprint for receipts and contracts
receipts_contracts_bp = Blueprint('receipts_contracts', __name__)

# ============================================
# ⚠️ BUILD 154: Feature Flag Guards
# ============================================
def _payments_disabled():
    """Check if payments feature is disabled"""
    return os.getenv("ENABLE_PAYMENTS", "false").lower() != "true"

def _contracts_disabled():
    """Check if contracts feature is disabled"""
    return os.getenv("ENABLE_CONTRACTS", "false").lower() != "true"

def _feature_disabled_response(feature_name):
    """Standard response for disabled features"""
    return jsonify({
        "success": False,
        "error": f"{feature_name} feature is currently disabled in this environment.",
        "detail": f"Set ENABLE_{feature_name.upper()}=true in environment to enable.",
        "status": "feature_disabled"
    }), 410

@receipts_contracts_bp.route('/api/receipts', methods=['GET'])
@require_api_auth()
def list_receipts():
    """רשימת כל החשבוניות"""
    if _payments_disabled():
        return _feature_disabled_response("payments")
    try:
        from server.models_sql import Invoice, Deal, Payment, db, Lead
        from server.routes_crm import get_business_id
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        # Get all invoices for this business (AgentKit invoices may not have payment/deal)
        invoices_raw = Invoice.query.filter_by(business_id=business_id).order_by(Invoice.issued_at.desc()).all()
        
        invoices_list = []
        for invoice in invoices_raw:
            # AgentKit invoices: use fields directly from invoice
            # Legacy invoices: try to load from related payment/deal
            invoices_list.append({
                'id': invoice.id,
                'payment_id': invoice.payment_id,
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number or f"INV-{invoice.id}",
                'amount': float(invoice.subtotal) if invoice.subtotal else 0,
                'tax': float(invoice.vat_amount) if invoice.vat_amount else 0,
                'total': float(invoice.total) if invoice.total else 0,
                'description': f"{invoice.customer_name} - חשבונית",
                'customer_name': invoice.customer_name,
                'status': invoice.status or 'final',
                'lead_id': invoice.customer_id,
                'created_at': invoice.issued_at.isoformat() if invoice.issued_at else None,
                'paid_at': None  # TODO: Track payment date
            })
        
        return jsonify({
            'success': True,
            'invoices': invoices_list,
            'total': len(invoices_list)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה בשליפת חשבוניות: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/receipts', methods=['POST'])
@require_api_auth()
def create_receipt():
    """יצירת חשבונית אמיתית ושמירה ב-DB"""
    if _payments_disabled():
        return _feature_disabled_response("payments")
    try:
        from server.models_sql import Invoice, Deal, Payment, db, Lead
        from server.routes_crm import get_business_id
        
        data = request.get_json()
        lead_id = data.get('lead_id')
        amount = data.get('amount', 0)
        description = data.get('description', 'שירותי תיווך')
        customer_name = data.get('customer_name', '')
        
        if not lead_id:
            return jsonify({'success': False, 'message': 'Lead ID נדרש'}), 400
            
        if not isinstance(amount, (int, float)) or amount <= 0:
            return jsonify({'success': False, 'message': 'סכום חייב להיות מספר חיובי'}), 400
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        # Get lead details
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'success': False, 'message': 'ליד לא נמצא'}), 404
        
        if not customer_name:
            customer_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "לקוח"
        
        # 🔥 FIX: Create or find Customer (not use lead_id directly!)
        from server.models_sql import Customer
        customer = None
        if lead.phone_e164:
            customer = Customer.query.filter_by(
                business_id=business_id,
                phone_e164=lead.phone_e164
            ).first()
        
        if not customer:
            # Create new customer from lead
            customer = Customer()
            customer.business_id = business_id
            customer.name = customer_name
            customer.phone_e164 = lead.phone_e164
            customer.status = "new"
            db.session.add(customer)
            db.session.flush()  # Get customer ID
        
        # Create deal if doesn't exist (use real customer_id!)
        deal = Deal.query.filter_by(customer_id=customer.id).first()
        if not deal:
            deal = Deal()
            deal.customer_id = customer.id  # ✅ Now uses real Customer ID!
            deal.title = f"עסקה - {customer_name}"
            deal.stage = "new"
            deal.amount = int(amount)
            deal.created_at = datetime.utcnow()
            db.session.add(deal)
            db.session.flush()
        
        # Convert amount to agorot (cents)
        amount_agorot = int(float(amount) * 100)
        
        # Create payment record
        payment = Payment()
        payment.business_id = business_id
        payment.deal_id = deal.id
        payment.provider = 'manual'  # Manual invoice
        payment.provider_ref = f'INV-{datetime.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
        payment.amount = amount_agorot
        payment.currency = 'ils'
        payment.status = 'created'
        payment.customer_name = customer_name
        # payment.description = description  # ❌ Column doesn't exist in DB
        payment.created_at = datetime.utcnow()
        
        db.session.add(payment)
        db.session.flush()
        
        # Create invoice record
        invoice = Invoice()
        invoice.deal_id = deal.id
        invoice.payment_id = payment.id  # Link directly to payment
        invoice.invoice_number = f'INV-{datetime.now().year}-{payment.id:05d}'
        invoice.subtotal = amount_agorot
        invoice.tax = int(amount_agorot * 0.18)  # 18% VAT (Israel)
        invoice.total = amount_agorot + invoice.tax
        invoice.issued_at = datetime.utcnow()
        
        db.session.add(invoice)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'חשבונית {invoice.invoice_number} נוצרה בסכום {amount:,.2f} ₪',
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'payment_id': payment.id,
            'amount': amount,
            'total_with_tax': invoice.total / 100
        })
        
    except Exception as e:
        try:
            from server.models_sql import db
            db.session.rollback()
        except:
            pass  # DB might not be imported if error happened early
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה ביצירת חשבונית: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/contracts', methods=['GET'])
@require_api_auth()
def list_contracts():
    """רשימת כל החוזים"""
    if _contracts_disabled():
        return _feature_disabled_response("contracts")
    try:
        from server.models_sql import Contract, Deal, Lead, db
        from server.routes_crm import get_business_id
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        # Get all contracts with lead info
        contracts = db.session.query(Contract, Deal, Lead).join(
            Deal, Contract.deal_id == Deal.id
        ).join(
            Lead, Deal.customer_id == Lead.id
        ).filter(
            Lead.tenant_id == business_id
        ).order_by(Contract.created_at.desc()).all()
        
        contracts_list = []
        for contract, deal, lead in contracts:
            contracts_list.append({
                'id': contract.id,
                'deal_id': deal.id,
                'lead_id': lead.id,  # Add lead_id for filtering in frontend
                'title': contract.template_name or f'חוזה #{contract.id}',
                'description': contract.template_name,
                'customer_name': lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "לקוח",
                'type': deal.stage or 'mediation',
                'status': 'signed' if contract.signed_at else 'draft',
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'signed_at': contract.signed_at.isoformat() if contract.signed_at else None,
                'signed_name': contract.signed_name
            })
        
        return jsonify({
            'success': True,
            'contracts': contracts_list,
            'total': len(contracts_list)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה בשליפת חוזים: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/contracts', methods=['POST'])
@require_api_auth()
def create_contract():
    """יצירת חוזה אמיתי ושמירה ב-DB"""
    if _contracts_disabled():
        return _feature_disabled_response("contracts")
    try:
        from server.models_sql import Contract, Deal, db, Lead
        from server.routes_crm import get_business_id
        
        data = request.get_json()
        lead_id = data.get('lead_id')
        contract_type = data.get('type', 'mediation')  # sale, rent, mediation, custom
        custom_title = data.get('title', '')
        
        if not lead_id:
            return jsonify({'success': False, 'message': 'Lead ID נדרש'}), 400
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        # Get lead details
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'success': False, 'message': 'ליד לא נמצא'}), 404
        
        customer_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "לקוח"
        
        # 🔥 FIX: Create or find Customer (not use lead_id directly!)
        from server.models_sql import Customer
        customer = None
        if lead.phone_e164:
            customer = Customer.query.filter_by(
                business_id=business_id,
                phone_e164=lead.phone_e164
            ).first()
        
        if not customer:
            # Create new customer from lead
            customer = Customer()
            customer.business_id = business_id
            customer.name = customer_name
            customer.phone_e164 = lead.phone_e164
            customer.status = "new"
            db.session.add(customer)
            db.session.flush()  # Get customer ID
        
        # Create deal if doesn't exist (use real customer_id!)
        deal = Deal.query.filter_by(customer_id=customer.id).first()
        if not deal:
            deal = Deal()
            deal.customer_id = customer.id  # ✅ Now uses real Customer ID!
            deal.title = f"עסקה - {customer_name}"
            deal.stage = "new"
            deal.created_at = datetime.utcnow()
            db.session.add(deal)
            db.session.flush()
        
        # סוגי חוזים
        contract_types = {
            'sale': 'חוזה מכירה',
            'rent': 'חוזה שכירות', 
            'mediation': 'חוזה תיווך',
            'custom': custom_title or 'חוזה מותאם אישית'
        }
        
        contract_name = contract_types.get(contract_type, custom_title or 'חוזה כללי')
        
        # Create contract record
        contract = Contract()
        contract.deal_id = deal.id
        contract.template_name = contract_name
        contract.version = 'v1'
        contract.created_at = datetime.utcnow()
        
        db.session.add(contract)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{contract_name} נוצר בהצלחה',
            'contract_id': contract.id,
            'type': contract_type,
            'deal_id': deal.id
        })
        
    except Exception as e:
        try:
            from server.models_sql import db
            db.session.rollback()
        except:
            pass  # DB might not be imported if error happened early
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה ביצירת חוזה: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/contracts/<int:contract_id>', methods=['GET'])
@require_api_auth()
def get_contract(contract_id):
    """שליפת פרטי חוזה"""
    if _contracts_disabled():
        return _feature_disabled_response("contracts")
    try:
        from server.models_sql import Contract, Deal, Lead, db
        from server.routes_crm import get_business_id
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'success': False, 'message': 'חוזה לא נמצא'}), 404
        
        # Get deal and lead info
        deal = Deal.query.get(contract.deal_id) if contract.deal_id else None
        lead = Lead.query.get(deal.customer_id) if deal and deal.customer_id else None
        
        return jsonify({
            'success': True,
            'contract': {
                'id': contract.id,
                'template_name': contract.template_name,
                'version': contract.version,
                'signed_name': contract.signed_name,
                'signed_at': contract.signed_at.isoformat() if contract.signed_at else None,
                'signature_data': contract.signature_data,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'customer_name': lead.full_name if lead else None,
                'deal_title': deal.title if deal else None
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה בשליפת חוזה: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/contracts/<int:contract_id>/sign', methods=['POST'])
@require_api_auth()
def sign_contract(contract_id):
    """חתימה דיגיטלית על חוזה"""
    if _contracts_disabled():
        return _feature_disabled_response("contracts")
    try:
        from server.models_sql import Contract, db
        from server.routes_crm import get_business_id
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        data = request.get_json()
        signature_data = data.get('signature_data')  # Base64 image
        signed_name = data.get('signed_name', '')
        
        if not signature_data:
            return jsonify({'success': False, 'message': 'חתימה נדרשת'}), 400
        
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'success': False, 'message': 'חוזה לא נמצא'}), 404
        
        # Validate base64
        if not signature_data.startswith('data:image/'):
            return jsonify({'success': False, 'message': 'פורמט חתימה לא תקין'}), 400
        
        # Save signature
        contract.signature_data = signature_data
        contract.signed_name = signed_name
        contract.signed_at = datetime.utcnow()
        contract.signed_ip = request.remote_addr
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'חוזה נחתם בהצלחה על ידי {signed_name}',
            'contract_id': contract.id,
            'signed_at': contract.signed_at.isoformat()
        })
        
    except Exception as e:
        try:
            from server.models_sql import db
            db.session.rollback()
        except:
            pass  # DB might not be imported if error happened early
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה בחתימת חוזה: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/invoice/<invoice_id>/view', methods=['GET'])
@require_api_auth()
def view_invoice(invoice_id):
    """הצגת חשבונית בפורמט PDF"""
    if _payments_disabled():
        return _feature_disabled_response("payments")
    try:
        from server.models_sql import Invoice, Payment, Business, Deal, db
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # שליפת החשבונית מהדאטבייס
        invoice = Invoice.query.get(int(invoice_id))
        if not invoice:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'}), 404
        
        # שליפת התשלום המקושר (prefer payment_id, fallback to deal_id)
        if invoice.payment_id:
            payment = Payment.query.get(invoice.payment_id)
        elif invoice.deal_id:
            payment = Payment.query.filter_by(deal_id=invoice.deal_id).first()
        else:
            payment = None
        
        if not payment:
            return jsonify({'success': False, 'message': 'תשלום לא נמצא'}), 404
        
        # שליפת פרטי העסק
        business = Business.query.get(payment.business_id) if payment.business_id else None
        business_name = business.name if business else "העסק"
        
        # יצירת PDF בזיכרון
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הוספת פונט עברי (נדרש לתמיכה בעברית)
        from reportlab.pdfbase.pdfmetrics import stringWidth
        font_name = 'Helvetica'  # Default font
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                # Fallback - try other common Hebrew font paths
                alt_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansBold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        pdfmetrics.registerFont(TTFont('Hebrew', alt_path))
                        font_name = 'Hebrew'
                        break
        except Exception as e:
            print(f"Font loading error: {e}")
            font_name = 'Helvetica'
        
        # Function to draw RTL text (for Hebrew)
        def draw_rtl_text(canvas_obj, x, y, text, font, size):
            canvas_obj.setFont(font, size)
            # For RTL, draw from right edge
            text_width = stringWidth(text, font, size)
            canvas_obj.drawString(width - x - text_width, y, text)
        
        # כותרת החשבונית בעברית
        p.setFont(font_name, 26)
        title = f"חשבונית #{invoice.invoice_number}"
        draw_rtl_text(p, 50, height - 80, title, font_name, 26)
        
        # קו הפרדה
        p.setStrokeColorRGB(0.8, 0.8, 0.8)
        p.setLineWidth(1)
        p.line(50, height - 100, width - 50, height - 100)
        
        # פרטי החשבונית - נתונים אמיתיים מה-DB בעברית
        p.setFont(font_name, 12)
        y_position = height - 130
        
        invoice_details = [
            f"חברה: {business_name}",
            f"מספר חשבונית: {invoice.invoice_number}",
            f"תאריך: {invoice.issued_at.strftime('%d/%m/%Y %H:%M') if invoice.issued_at else 'לא צוין'}",
            "",
            f"סכום ביניים: ₪{invoice.subtotal / 100:,.2f}",
            f"מע\"מ (18%): ₪{invoice.tax / 100:,.2f}",
            f"סכום כולל: ₪{invoice.total / 100:,.2f}",
            "",
            f"תיאור: {payment.description or 'עמלת תיווך נדל״ן'}",
            f"לקוח: {payment.customer_name or 'לא צוין'}",
            f"סטטוס: {payment.status or 'created'}",
            f"אמצעי תשלום: {payment.provider or 'ידני'}"
        ]
        
        for detail in invoice_details:
            if detail:  # Skip empty lines
                draw_rtl_text(p, 50, y_position, detail, font_name, 12)
            y_position -= 25
        
        # שמירת ה-PDF
        p.save()
        buffer.seek(0)
        
        # החזרת הקובץ
        from flask import Response
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename=invoice-{invoice.invoice_number}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"Error generating invoice PDF: {e}")
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/invoice/<invoice_id>/download', methods=['GET'])
@require_api_auth()
def download_invoice(invoice_id):
    """הורדת חשבונית בפורמט PDF"""
    if _payments_disabled():
        return _feature_disabled_response("payments")
    try:
        from server.models_sql import Invoice, Payment, Business, Deal, db
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # שליפת החשבונית מהדאטבייס
        invoice = Invoice.query.get(int(invoice_id))
        if not invoice:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'}), 404
        
        # שליפת התשלום המקושר (prefer payment_id, fallback to deal_id)
        if invoice.payment_id:
            payment = Payment.query.get(invoice.payment_id)
        elif invoice.deal_id:
            payment = Payment.query.filter_by(deal_id=invoice.deal_id).first()
        else:
            payment = None
        
        if not payment:
            return jsonify({'success': False, 'message': 'תשלום לא נמצא'}), 404
        
        # שליפת פרטי העסק
        business = Business.query.get(payment.business_id) if payment.business_id else None
        business_name = business.name if business else "העסק"
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הוספת פונט עברי (נדרש לתמיכה בעברית)
        from reportlab.pdfbase.pdfmetrics import stringWidth
        font_name = 'Helvetica'  # Default font
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                # Fallback - try other common Hebrew font paths
                alt_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansBold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        pdfmetrics.registerFont(TTFont('Hebrew', alt_path))
                        font_name = 'Hebrew'
                        break
        except Exception as e:
            print(f"Font loading error: {e}")
            font_name = 'Helvetica'
        
        # Function to draw RTL text (for Hebrew)
        def draw_rtl_text(canvas_obj, x, y, text, font, size):
            canvas_obj.setFont(font, size)
            # For RTL, draw from right edge
            text_width = stringWidth(text, font, size)
            canvas_obj.drawString(width - x - text_width, y, text)
        
        # כותרת החשבונית בעברית
        p.setFont(font_name, 26)
        title = f"חשבונית #{invoice.invoice_number}"
        draw_rtl_text(p, 50, height - 80, title, font_name, 26)
        
        # קו הפרדה
        p.setStrokeColorRGB(0.8, 0.8, 0.8)
        p.setLineWidth(1)
        p.line(50, height - 100, width - 50, height - 100)
        
        # פרטי החשבונית - נתונים אמיתיים מה-DB בעברית
        p.setFont(font_name, 12)
        y_position = height - 130
        
        invoice_details = [
            f"חברה: {business_name}",
            f"מספר חשבונית: {invoice.invoice_number}",
            f"תאריך: {invoice.issued_at.strftime('%d/%m/%Y %H:%M') if invoice.issued_at else 'לא צוין'}",
            "",
            f"סכום ביניים: ₪{invoice.subtotal / 100:,.2f}",
            f"מע\"מ (18%): ₪{invoice.tax / 100:,.2f}",
            f"סכום כולל: ₪{invoice.total / 100:,.2f}",
            "",
            f"תיאור: {payment.description or 'עמלת תיווך נדל״ן'}",
            f"לקוח: {payment.customer_name or 'לא צוין'}",
            f"סטטוס: {payment.status or 'created'}",
            f"אמצעי תשלום: {payment.provider or 'ידני'}"
        ]
        
        for detail in invoice_details:
            if detail:  # Skip empty lines
                draw_rtl_text(p, 50, y_position, detail, font_name, 12)
            y_position -= 25
        
        p.save()
        buffer.seek(0)
        
        from flask import Response
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=invoice-{invoice.invoice_number}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"Error downloading invoice PDF: {e}")
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/contract/<contract_id>/view', methods=['GET'])
@require_api_auth()
def view_contract(contract_id):
    """הצגת חוזה בפורמט PDF"""
    if _contracts_disabled():
        return _feature_disabled_response("contracts")
    try:
        from server.models_sql import Contract, Deal, Customer, Business, db
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # שליפת נתוני החוזה מהדאטבייס
        contract = Contract.query.get(int(contract_id))
        if not contract:
            return jsonify({'success': False, 'message': 'חוזה לא נמצא'}), 404
        
        # שליפת Deal וCustomer
        deal = Deal.query.get(contract.deal_id) if contract.deal_id else None
        customer = Customer.query.get(deal.customer_id) if deal and deal.customer_id else None
        business = Business.query.get(customer.business_id) if customer and customer.business_id else None
        
        business_name = business.name if business else "העסק"
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הוספת פונט עברי (נדרש לתמיכה בעברית)
        from reportlab.pdfbase.pdfmetrics import stringWidth
        font_name = 'Helvetica'  # Default font
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                # Fallback - try other common Hebrew font paths
                alt_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansBold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        pdfmetrics.registerFont(TTFont('Hebrew', alt_path))
                        font_name = 'Hebrew'
                        break
        except Exception as e:
            print(f"Font loading error: {e}")
            font_name = 'Helvetica'
        
        # Function to draw RTL text (for Hebrew)
        def draw_rtl_text(canvas_obj, x, y, text, font, size):
            canvas_obj.setFont(font, size)
            # For RTL, draw from right edge
            text_width = stringWidth(text, font, size)
            canvas_obj.drawString(width - x - text_width, y, text)
        
        # כותרת החוזה בעברית
        p.setFont(font_name, 26)
        title = f"חוזה #{contract.id}"
        draw_rtl_text(p, 50, height - 80, title, font_name, 26)
        
        # קו הפרדה
        p.setStrokeColorRGB(0.8, 0.8, 0.8)
        p.setLineWidth(1)
        p.line(50, height - 100, width - 50, height - 100)
        
        # פרטי החוזה - נתונים אמיתיים מה-DB בעברית
        p.setFont(font_name, 12)
        y_position = height - 130
        
        contract_details = [
            f"חברה: {business_name}",
            f"מספר חוזה: {contract.id}",
            f"תבנית: {contract.template_name or 'חוזה רגיל'}",
            f"תאריך יצירה: {contract.created_at.strftime('%d/%m/%Y %H:%M') if contract.created_at else 'לא צוין'}",
            "",
            f"לקוח: {customer.name if customer else 'לא צוין'}",
            f"עסקה: {deal.title if deal else 'לא צוין'}",  # 🔥 BUILD 200: Generic term
            f"סכום: ₪{deal.amount / 100:,.2f}" if deal and deal.amount else "סכום: לא צוין",
            "",
            f"נחתם על ידי: {contract.signed_name if contract.signed_name else 'טרם נחתם'}",
            f"תאריך חתימה: {contract.signed_at.strftime('%d/%m/%Y %H:%M') if contract.signed_at else 'לא צוין'}"
        ]
        
        for detail in contract_details:
            if detail:  # Skip empty lines
                draw_rtl_text(p, 50, y_position, detail, font_name, 12)
            y_position -= 25
        
        # הוספת חתימה אם קיימת
        if contract.signature_data:
            try:
                from reportlab.lib.utils import ImageReader
                import io
                
                # המרת base64 לתמונה
                signature_b64 = contract.signature_data.split(',')[1] if ',' in contract.signature_data else contract.signature_data
                signature_bytes = base64.b64decode(signature_b64)
                signature_img = ImageReader(io.BytesIO(signature_bytes))
                
                # ציור החתימה ב-PDF
                y_position -= 40
                draw_rtl_text(p, 50, y_position, "חתימה דיגיטלית:", font_name, 12)
                y_position -= 10
                # Draw signature image aligned to right
                p.drawImage(signature_img, width - 200, y_position - 60, width=150, height=50, preserveAspectRatio=True)
                y_position -= 70
                if contract.signed_name:
                    draw_rtl_text(p, 50, y_position, f"נחתם על ידי: {contract.signed_name}", font_name, 12)
            except Exception as sig_error:
                print(f"Error adding signature to PDF: {sig_error}")
                # Continue without signature if there's an error
        
        p.save()
        buffer.seek(0)
        
        from flask import Response
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename=contract-{contract.id}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"Error generating contract PDF: {e}")
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/contract/<contract_id>/download', methods=['GET'])
@require_api_auth()
def download_contract(contract_id):
    """הורדת חוזה בפורמט PDF"""
    if _contracts_disabled():
        return _feature_disabled_response("contracts")
    try:
        from server.models_sql import Contract, Deal, Customer, Business, db
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # שליפת נתוני החוזה מהדאטבייס
        contract = Contract.query.get(int(contract_id))
        if not contract:
            return jsonify({'success': False, 'message': 'חוזה לא נמצא'}), 404
        
        # שליפת Deal וCustomer
        deal = Deal.query.get(contract.deal_id) if contract.deal_id else None
        customer = Customer.query.get(deal.customer_id) if deal and deal.customer_id else None
        business = Business.query.get(customer.business_id) if customer and customer.business_id else None
        
        business_name = business.name if business else "העסק"
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הוספת פונט עברי (נדרש לתמיכה בעברית)
        from reportlab.pdfbase.pdfmetrics import stringWidth
        font_name = 'Helvetica'  # Default font
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                # Fallback - try other common Hebrew font paths
                alt_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansBold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        pdfmetrics.registerFont(TTFont('Hebrew', alt_path))
                        font_name = 'Hebrew'
                        break
        except Exception as e:
            print(f"Font loading error: {e}")
            font_name = 'Helvetica'
        
        # Function to draw RTL text (for Hebrew)
        def draw_rtl_text(canvas_obj, x, y, text, font, size):
            canvas_obj.setFont(font, size)
            # For RTL, draw from right edge
            text_width = stringWidth(text, font, size)
            canvas_obj.drawString(width - x - text_width, y, text)
        
        # כותרת החוזה בעברית
        p.setFont(font_name, 26)
        title = f"חוזה #{contract.id}"
        draw_rtl_text(p, 50, height - 80, title, font_name, 26)
        
        # קו הפרדה
        p.setStrokeColorRGB(0.8, 0.8, 0.8)
        p.setLineWidth(1)
        p.line(50, height - 100, width - 50, height - 100)
        
        # פרטי החוזה - נתונים אמיתיים מה-DB בעברית
        p.setFont(font_name, 12)
        y_position = height - 130
        
        contract_details = [
            f"חברה: {business_name}",
            f"מספר חוזה: {contract.id}",
            f"תבנית: {contract.template_name or 'חוזה רגיל'}",
            f"תאריך יצירה: {contract.created_at.strftime('%d/%m/%Y %H:%M') if contract.created_at else 'לא צוין'}",
            "",
            f"לקוח: {customer.name if customer else 'לא צוין'}",
            f"עסקה: {deal.title if deal else 'לא צוין'}",  # 🔥 BUILD 200: Generic term
            f"סכום: ₪{deal.amount / 100:,.2f}" if deal and deal.amount else "סכום: לא צוין",
            "",
            f"נחתם על ידי: {contract.signed_name if contract.signed_name else 'טרם נחתם'}",
            f"תאריך חתימה: {contract.signed_at.strftime('%d/%m/%Y %H:%M') if contract.signed_at else 'לא צוין'}"
        ]
        
        for detail in contract_details:
            if detail:  # Skip empty lines
                draw_rtl_text(p, 50, y_position, detail, font_name, 12)
            y_position -= 25
        
        # הוספת חתימה אם קיימת
        if contract.signature_data:
            try:
                from reportlab.lib.utils import ImageReader
                import io
                
                # המרת base64 לתמונה
                signature_b64 = contract.signature_data.split(',')[1] if ',' in contract.signature_data else contract.signature_data
                signature_bytes = base64.b64decode(signature_b64)
                signature_img = ImageReader(io.BytesIO(signature_bytes))
                
                # ציור החתימה ב-PDF
                y_position -= 40
                draw_rtl_text(p, 50, y_position, "חתימה דיגיטלית:", font_name, 12)
                y_position -= 10
                # Draw signature image aligned to right
                p.drawImage(signature_img, width - 200, y_position - 60, width=150, height=50, preserveAspectRatio=True)
                y_position -= 70
                if contract.signed_name:
                    draw_rtl_text(p, 50, y_position, f"נחתם על ידי: {contract.signed_name}", font_name, 12)
            except Exception as sig_error:
                print(f"Error adding signature to PDF: {sig_error}")
                # Continue without signature if there's an error
        
        p.save()
        buffer.seek(0)
        
        from flask import Response
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=contract-{contract.id}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"Error downloading contract PDF: {e}")
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500