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
        # TODO: במציאות נקרא מהדאטבייס
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # יצירת PDF בזיכרון
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הוספת פונט עברי (אם קיים)
        try:
            # ניסיון לטעון פונט עברי
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
        p.drawString(100, height - 100, f"Invoice #{invoice_id}")
        
        # פרטי החשבונית
        p.setFont(font_name, 12)
        y_position = height - 150
        
        invoice_details = [
            "Company: שי דירות ומשרדים בע״מ",
            f"Invoice ID: {invoice_id}",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            "Amount: ₪25,000",
            "Description: עמלת תיווך נדל״ן",
            "Status: Generated"
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
                'Content-Disposition': f'inline; filename=invoice-{invoice_id}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/invoice/<invoice_id>/download', methods=['GET'])
@require_api_auth()
def download_invoice(invoice_id):
    """הורדת חשבונית בפורמט PDF"""
    try:
        # בדיוק אותו קוד כמו view אבל עם attachment
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
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
        p.drawString(100, height - 100, f"Invoice #{invoice_id}")
        
        p.setFont(font_name, 12)
        y_position = height - 150
        
        invoice_details = [
            "Company: שי דירות ומשרדים בע״מ",
            f"Invoice ID: {invoice_id}",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            "Amount: ₪25,000",
            "Description: עמלת תיווך נדל״ן",
            "Status: Generated"
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
                'Content-Disposition': f'attachment; filename=invoice-{invoice_id}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/contract/<contract_id>/view', methods=['GET'])
@require_api_auth()
def view_contract(contract_id):
    """הצגת חוזה בפורמט PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
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
        p.drawString(100, height - 100, f"Contract #{contract_id}")
        
        # פרטי החוזה
        p.setFont(font_name, 12)
        y_position = height - 150
        
        contract_details = [
            "שי דירות ומשרדים בע״מ",
            f"Contract ID: {contract_id}",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            "Contract Type: Real Estate Agreement",
            "Property: דירת 4 חדרים",
            "Commission: 2.5%",
            "Status: Active"
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
                'Content-Disposition': f'inline; filename=contract-{contract_id}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/billing/contract/<contract_id>/download', methods=['GET'])
@require_api_auth()
def download_contract(contract_id):
    """הורדת חוזה בפורמט PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
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
        p.drawString(100, height - 100, f"Contract #{contract_id}")
        
        p.setFont(font_name, 12)
        y_position = height - 150
        
        contract_details = [
            "שי דירות ומשרדים בע״מ",
            f"Contract ID: {contract_id}",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            "Contract Type: Real Estate Agreement",
            "Property: דירת 4 חדרים",
            "Commission: 2.5%",
            "Status: Active"
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
                'Content-Disposition': f'attachment; filename=contract-{contract_id}.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת PDF: {str(e)}'}), 500