from flask import Blueprint, request, jsonify
from server.auth_api import require_api_auth
import uuid
from datetime import datetime

# Blueprint for receipts and contracts
receipts_contracts_bp = Blueprint('receipts_contracts', __name__)

@receipts_contracts_bp.route('/api/receipts', methods=['GET'])
@require_api_auth()
def list_receipts():
    """רשימת כל החשבוניות"""
    try:
        from server.models_sql import Invoice, Deal, Payment, db, Lead
        from server.routes_crm import get_business_id
        
        business_id = get_business_id()
        if not business_id:
            return jsonify({'success': False, 'message': 'Business ID נדרש'}), 400
        
        # Get all invoices (prefer payment_id, fallback to deal_id for legacy)
        from sqlalchemy import or_
        invoices = db.session.query(Invoice, Payment).join(
            Payment,
            or_(
                Invoice.payment_id == Payment.id,
                (Invoice.payment_id.is_(None) & (Invoice.deal_id == Payment.deal_id))
            )
        ).filter(
            Payment.business_id == business_id
        ).order_by(Invoice.issued_at.desc()).all()
        
        invoices_list = []
        for invoice, payment in invoices:
            invoices_list.append({
                'id': invoice.id,  # Always use invoice ID for PDF endpoints
                'payment_id': payment.id,
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'amount': invoice.subtotal / 100,
                'tax': invoice.tax / 100,
                'total': invoice.total / 100,
                'description': payment.description,
                'customer_name': payment.customer_name,
                'status': payment.status,
                'created_at': invoice.issued_at.isoformat() if invoice.issued_at else None,
                'paid_at': payment.paid_at.isoformat() if payment.paid_at else None
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
        
        # Create deal if doesn't exist
        deal = Deal.query.filter_by(customer_id=lead_id).first()
        if not deal:
            deal = Deal()
            deal.customer_id = lead_id
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
        payment.description = description
        payment.created_at = datetime.utcnow()
        
        db.session.add(payment)
        db.session.flush()
        
        # Create invoice record
        invoice = Invoice()
        invoice.deal_id = deal.id
        invoice.payment_id = payment.id  # Link directly to payment
        invoice.invoice_number = f'INV-{datetime.now().year}-{payment.id:05d}'
        invoice.subtotal = amount_agorot
        invoice.tax = int(amount_agorot * 0.17)  # 17% VAT
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
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'שגיאה ביצירת חשבונית: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/contracts', methods=['POST'])
@require_api_auth()
def create_contract():
    """יצירת חוזה ללקוח"""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        contract_type = data.get('type', 'sale')  # sale, rent, mediation, custom
        custom_title = data.get('title', '')
        
        if not lead_id:
            return jsonify({'success': False, 'message': 'Lead ID נדרש'}), 400
            
        # סוגי חוזים
        contract_types = {
            'sale': 'חוזה מכירה',
            'rent': 'חוזה שכירות', 
            'mediation': 'חוזה תיווך',
            'custom': custom_title or 'חוזה מותאם אישית'
        }
        
        contract_name = contract_types.get(contract_type, custom_title or 'חוזה כללי')
        contract_id = str(uuid.uuid4())
        
        contract_data = {
            'id': contract_id,
            'lead_id': lead_id,
            'type': contract_type,
            'name': contract_name,
            'created_at': datetime.now().isoformat(),
            'status': 'draft'
        }
        
        # TODO: שמירה בדאטבייס כשנוסיף טבלת חוזים
        
        return jsonify({
            'success': True,
            'message': f'{contract_name} נוצר בהצלחה',
            'contract_id': contract_id,
            'type': contract_type
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת חוזה: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/invoice/<invoice_id>/view', methods=['GET'])
@require_api_auth()
def view_invoice(invoice_id):
    """הצגת חשבונית בפורמט PDF"""
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
        business_name = business.name if business else "שי דירות ומשרדים בע״מ"
        
        # יצירת PDF בזיכרון
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הוספת פונט עברי (אם קיים)
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                font_name = 'Helvetica'
        except:
            font_name = 'Helvetica'
        
        # כותרת החשבונית
        p.setFont(font_name, 24)
        p.drawString(100, height - 100, f"Invoice #{invoice.invoice_number}")
        
        # פרטי החשבונית - נתונים אמיתיים מה-DB
        p.setFont(font_name, 12)
        y_position = height - 150
        
        invoice_details = [
            f"Company: {business_name}",
            f"Invoice Number: {invoice.invoice_number}",
            f"Date: {invoice.issued_at.strftime('%Y-%m-%d %H:%M') if invoice.issued_at else 'N/A'}",
            f"Subtotal: ₪{invoice.subtotal / 100:,.2f}",
            f"Tax (17%): ₪{invoice.tax / 100:,.2f}",
            f"Total: ₪{invoice.total / 100:,.2f}",
            f"Description: {payment.description or 'עמלת תיווך נדל״ן'}",
            f"Customer: {payment.customer_name or 'לא צוין'}",
            f"Status: {payment.status or 'created'}",
            f"Payment Method: {payment.provider or 'manual'}"
        ]
        
        for detail in invoice_details:
            p.drawString(100, y_position, detail)
            y_position -= 20
        
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
        business_name = business.name if business else "שי דירות ומשרדים בע״מ"
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                font_name = 'Helvetica'
        except:
            font_name = 'Helvetica'
        
        p.setFont(font_name, 24)
        p.drawString(100, height - 100, f"Invoice #{invoice.invoice_number}")
        
        p.setFont(font_name, 12)
        y_position = height - 150
        
        invoice_details = [
            f"Company: {business_name}",
            f"Invoice Number: {invoice.invoice_number}",
            f"Date: {invoice.issued_at.strftime('%Y-%m-%d %H:%M') if invoice.issued_at else 'N/A'}",
            f"Subtotal: ₪{invoice.subtotal / 100:,.2f}",
            f"Tax (17%): ₪{invoice.tax / 100:,.2f}",
            f"Total: ₪{invoice.total / 100:,.2f}",
            f"Description: {payment.description or 'עמלת תיווך נדל״ן'}",
            f"Customer: {payment.customer_name or 'לא צוין'}",
            f"Status: {payment.status or 'created'}",
            f"Payment Method: {payment.provider or 'manual'}"
        ]
        
        for detail in invoice_details:
            p.drawString(100, y_position, detail)
            y_position -= 20
        
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
        
        business_name = business.name if business else "שי דירות ומשרדים בע״מ"
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                font_name = 'Helvetica'
        except:
            font_name = 'Helvetica'
        
        # כותרת החוזה
        p.setFont(font_name, 24)
        p.drawString(100, height - 100, f"Contract #{contract.id}")
        
        # פרטי החוזה - נתונים אמיתיים מה-DB
        p.setFont(font_name, 12)
        y_position = height - 150
        
        contract_details = [
            f"Company: {business_name}",
            f"Contract ID: {contract.id}",
            f"Template: {contract.template_name or 'Standard Agreement'}",
            f"Created: {contract.created_at.strftime('%Y-%m-%d %H:%M') if contract.created_at else 'N/A'}",
            f"Customer: {customer.name if customer else 'לא צוין'}",
            f"Property: {deal.title if deal else 'לא צוין'}",
            f"Amount: ₪{deal.amount / 100:,.2f}" if deal and deal.amount else "Amount: N/A",
            f"Signed By: {contract.signed_name if contract.signed_name else 'Not Signed'}",
            f"Signed At: {contract.signed_at.strftime('%Y-%m-%d %H:%M') if contract.signed_at else 'N/A'}"
        ]
        
        for detail in contract_details:
            p.drawString(100, y_position, detail)
            y_position -= 20
        
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
        
        business_name = business.name if business else "שי דירות ומשרדים בע״מ"
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        try:
            hebrew_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(hebrew_font_path):
                pdfmetrics.registerFont(TTFont('Hebrew', hebrew_font_path))
                font_name = 'Hebrew'
            else:
                font_name = 'Helvetica'
        except:
            font_name = 'Helvetica'
        
        p.setFont(font_name, 24)
        p.drawString(100, height - 100, f"Contract #{contract.id}")
        
        p.setFont(font_name, 12)
        y_position = height - 150
        
        contract_details = [
            f"Company: {business_name}",
            f"Contract ID: {contract.id}",
            f"Template: {contract.template_name or 'Standard Agreement'}",
            f"Created: {contract.created_at.strftime('%Y-%m-%d %H:%M') if contract.created_at else 'N/A'}",
            f"Customer: {customer.name if customer else 'לא צוין'}",
            f"Property: {deal.title if deal else 'לא צוין'}",
            f"Amount: ₪{deal.amount / 100:,.2f}" if deal and deal.amount else "Amount: N/A",
            f"Signed By: {contract.signed_name if contract.signed_name else 'Not Signed'}",
            f"Signed At: {contract.signed_at.strftime('%Y-%m-%d %H:%M') if contract.signed_at else 'N/A'}"
        ]
        
        for detail in contract_details:
            p.drawString(100, y_position, detail)
            y_position -= 20
        
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