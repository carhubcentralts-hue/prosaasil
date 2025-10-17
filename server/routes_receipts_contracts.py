from flask import Blueprint, request, jsonify
from server.auth_api import require_api_auth
import uuid
from datetime import datetime

# Blueprint for receipts and contracts
receipts_contracts_bp = Blueprint('receipts_contracts', __name__)

@receipts_contracts_bp.route('/api/receipts', methods=['POST'])
@require_api_auth()
def create_receipt():
    """יצירת חשבונית ללקוח"""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        amount = data.get('amount', 0)
        description = data.get('description', 'שירותי תיווך')
        
        if not lead_id:
            return jsonify({'success': False, 'message': 'Lead ID נדרש'}), 400
            
        if not isinstance(amount, (int, float)) or amount <= 0:
            return jsonify({'success': False, 'message': 'סכום חייב להיות מספר חיובי'}), 400
            
        # יצירת חשבונית פשוטה
        receipt_id = str(uuid.uuid4())
        receipt_data = {
            'id': receipt_id,
            'lead_id': lead_id,
            'amount': amount,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'status': 'created'
        }
        
        # TODO: שמירה בדאטבייס כשנוסיף טבלת חשבוניות
        
        return jsonify({
            'success': True, 
            'message': f'חשבונית נוצרה בסכום {amount:,} ₪',
            'receipt_id': receipt_id,
            'amount': amount
        })
        
    except Exception as e:
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
        from server.models_sql import Payment, Business, db
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # שליפת נתוני התשלום מהדאטבייס
        payment = Payment.query.get(int(invoice_id))
        if not payment:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'}), 404
        
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
        p.drawString(100, height - 100, f"Invoice #{payment.id}")
        
        # פרטי החשבונית - נתונים אמיתיים מה-DB
        p.setFont(font_name, 12)
        y_position = height - 150
        
        invoice_details = [
            f"Company: {business_name}",
            f"Invoice ID: {payment.id}",
            f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else 'N/A'}",
            f"Amount: ₪{payment.amount / 100:,.2f}",
            f"Description: {payment.description or 'עמלת תיווך נדל״ן'}",
            f"Customer: {payment.customer_name or 'לא צוין'}",
            f"Status: {payment.status or 'created'}",
            f"Payment Method: {payment.provider or 'N/A'}"
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
                'Content-Disposition': f'inline; filename=invoice-{payment.id}.pdf',
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
        from server.models_sql import Payment, Business, db
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # שליפת נתוני התשלום מהדאטבייס
        payment = Payment.query.get(int(invoice_id))
        if not payment:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'}), 404
        
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
        p.drawString(100, height - 100, f"Invoice #{payment.id}")
        
        p.setFont(font_name, 12)
        y_position = height - 150
        
        invoice_details = [
            f"Company: {business_name}",
            f"Invoice ID: {payment.id}",
            f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else 'N/A'}",
            f"Amount: ₪{payment.amount / 100:,.2f}",
            f"Description: {payment.description or 'עמלת תיווך נדל״ן'}",
            f"Customer: {payment.customer_name or 'לא צוין'}",
            f"Status: {payment.status or 'created'}",
            f"Payment Method: {payment.provider or 'N/A'}"
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
                'Content-Disposition': f'attachment; filename=invoice-{payment.id}.pdf',
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