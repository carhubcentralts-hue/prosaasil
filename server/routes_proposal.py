"""
AgentLocator v42 - Proposal & Quote Generation Routes
מערכת יצירת הצעות מחיר והצעות עסקיות
"""

from flask import Blueprint, jsonify, request, send_file
import logging
from datetime import datetime, timedelta
from utils import get_db_connection
import json
from io import BytesIO
import uuid

logger = logging.getLogger(__name__)
proposal_bp = Blueprint('proposal', __name__)

@proposal_bp.route('/customers/<int:customer_id>/proposals', methods=['POST'])
def create_proposal(customer_id):
    """יצירת הצעת מחיר חדשה ללקוח"""
    try:
        data = request.get_json()
        
        # ולידציה
        required_fields = ['title', 'items', 'valid_until']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'נדרשים כל השדות הבסיסיים'}), 400
        
        items = data['items']
        if not items or not isinstance(items, list):
            return jsonify({'error': 'נדרשים פריטים בהצעה'}), 400
        
        # חישוב סכומים
        total_amount = 0
        for item in items:
            if 'quantity' in item and 'price' in item:
                total_amount += float(item['quantity']) * float(item['price'])
        
        # הוספת מעמ אם נדרש
        vat_rate = data.get('vat_rate', 17)  # 17% מעמ כברירת מחדל
        vat_amount = total_amount * (vat_rate / 100) if data.get('include_vat', True) else 0
        final_amount = total_amount + vat_amount
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # יצירת הצעה
        proposal_number = generate_proposal_number()
        
        cur.execute("""
            INSERT INTO proposals (
                customer_id, business_id, proposal_number, title, 
                description, items_json, subtotal, vat_amount, 
                total_amount, valid_until, status, created_at
            ) VALUES (
                %s, 
                (SELECT business_id FROM customers WHERE id = %s),
                %s, %s, %s, %s, %s, %s, %s, %s, 'draft', NOW()
            ) RETURNING id
        """, (customer_id, customer_id, proposal_number, data['title'],
              data.get('description', ''), json.dumps(items),
              total_amount, vat_amount, final_amount, data['valid_until']))
        
        proposal_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'id': proposal_id,
            'proposal_number': proposal_number,
            'total_amount': final_amount,
            'message': 'הצעת המחיר נוצרה בהצלחה'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        return jsonify({'error': 'שגיאה ביצירת הצעת המחיר'}), 500

@proposal_bp.route('/proposals/<int:proposal_id>', methods=['GET'])
def get_proposal(proposal_id):
    """קבלת פרטי הצעת מחיר"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT p.*, c.name as customer_name, c.email, c.phone,
                   b.name as business_name
            FROM proposals p
            JOIN customers c ON p.customer_id = c.id
            JOIN business b ON p.business_id = b.id
            WHERE p.id = %s
        """, (proposal_id,))
        
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'הצעה לא נמצאה'}), 404
        
        proposal = {
            'id': result[0],
            'customer_id': result[1],
            'business_id': result[2],
            'proposal_number': result[3],
            'title': result[4],
            'description': result[5],
            'items': json.loads(result[6]) if result[6] else [],
            'subtotal': float(result[7]) if result[7] else 0,
            'vat_amount': float(result[8]) if result[8] else 0,
            'total_amount': float(result[9]) if result[9] else 0,
            'valid_until': result[10].isoformat() if result[10] else None,
            'status': result[11],
            'created_at': result[12].isoformat() if result[12] else None,
            'customer': {
                'name': result[13],
                'email': result[14],
                'phone': result[15]
            },
            'business_name': result[16]
        }
        
        cur.close()
        conn.close()
        
        return jsonify(proposal), 200
        
    except Exception as e:
        logger.error(f"Error fetching proposal: {e}")
        return jsonify({'error': 'שגיאה בטעינת הצעת המחיר'}), 500

@proposal_bp.route('/proposals/<int:proposal_id>/send', methods=['POST'])
def send_proposal(proposal_id):
    """שליחת הצעת מחיר ללקוח"""
    try:
        data = request.get_json()
        send_method = data.get('method', 'email')  # email/whatsapp/sms
        custom_message = data.get('message', '')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # עדכון סטטוס לנשלח
        cur.execute("""
            UPDATE proposals 
            SET status = 'sent', sent_at = NOW()
            WHERE id = %s
            RETURNING customer_id, proposal_number, title
        """, (proposal_id,))
        
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'הצעה לא נמצאה'}), 404
        
        conn.commit()
        
        # קבלת פרטי הלקוח לשליחה
        cur.execute("""
            SELECT name, email, phone FROM customers 
            WHERE id = %s
        """, (result[0],))
        
        customer = cur.fetchone()
        cur.close()
        conn.close()
        
        # שליחת ההצעה
        if send_method == 'email' and customer[1]:
            send_proposal_by_email(proposal_id, customer[1], custom_message)
        elif send_method == 'whatsapp' and customer[2]:
            send_proposal_by_whatsapp(proposal_id, customer[2], custom_message)
        elif send_method == 'sms' and customer[2]:
            send_proposal_by_sms(proposal_id, customer[2], custom_message)
        else:
            return jsonify({'error': 'שיטת שליחה לא זמינה או חסרים פרטי יצירת קשר'}), 400
        
        return jsonify({
            'message': f'הצעת המחיר נשלחה ללקוח ב{send_method}',
            'proposal_number': result[1]
        }), 200
        
    except Exception as e:
        logger.error(f"Error sending proposal: {e}")
        return jsonify({'error': 'שגיאה בשליחת הצעת המחיר'}), 500

@proposal_bp.route('/proposals/<int:proposal_id>/accept', methods=['POST'])
def accept_proposal(proposal_id):
    """אישור הצעת מחיר על ידי הלקוח"""
    try:
        data = request.get_json()
        customer_signature = data.get('signature', '')
        customer_comments = data.get('comments', '')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE proposals 
            SET status = 'accepted',
                accepted_at = NOW(),
                customer_signature = %s,
                customer_comments = %s
            WHERE id = %s AND status = 'sent'
            RETURNING proposal_number, total_amount, customer_id
        """, (customer_signature, customer_comments, proposal_id))
        
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'הצעה לא נמצאה או לא ניתנת לאישור'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        # יצירת חוזה אוטומטית מהצעה מאושרת
        try:
            contract_id = create_contract_from_proposal(proposal_id)
            logger.info(f"Contract {contract_id} created from proposal {proposal_id}")
        except Exception as e:
            logger.warning(f"Failed to create contract from proposal: {e}")
        
        return jsonify({
            'message': 'הצעת המחיר אושרה בהצלחה',
            'proposal_number': result[0],
            'amount': float(result[1])
        }), 200
        
    except Exception as e:
        logger.error(f"Error accepting proposal: {e}")
        return jsonify({'error': 'שגיאה באישור הצעת המחיר'}), 500

@proposal_bp.route('/proposals/<int:proposal_id>/pdf', methods=['GET'])
def generate_proposal_pdf(proposal_id):
    """יצירת PDF של הצעת המחיר"""
    try:
        # כאן תבוא הלוגיקה ליצירת PDF בעברית
        # עם הפרטים המלאים של ההצעה
        
        # לעת עתה - החזרת placeholder
        pdf_content = generate_pdf_content(proposal_id)
        
        return send_file(
            BytesIO(pdf_content),
            as_attachment=True,
            download_name=f'proposal_{proposal_id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'error': 'שגיאה ביצירת PDF'}), 500

def generate_proposal_number():
    """יצירת מספר הצעה ייחודי"""
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_id = str(uuid.uuid4())[:8]
    return f"PROP-{timestamp}-{unique_id.upper()}"

def send_proposal_by_email(proposal_id, email, message):
    """שליחת הצעה במייל"""
    logger.info(f"Sending proposal {proposal_id} to {email}")
    # כאן תבוא האינטגרציה עם שירות המייל
    pass

def send_proposal_by_whatsapp(proposal_id, phone, message):
    """שליחת הצעה ב-WhatsApp"""
    logger.info(f"Sending proposal {proposal_id} to WhatsApp {phone}")
    # כאן תבוא האינטגרציה עם WhatsApp API
    pass

def send_proposal_by_sms(proposal_id, phone, message):
    """שליחת הצעה ב-SMS"""
    logger.info(f"Sending proposal {proposal_id} to SMS {phone}")
    # כאן תבוא האינטגרציה עם Twilio SMS
    pass

def create_contract_from_proposal(proposal_id):
    """יצירת חוזה מהצעת מחיר מאושרת"""
    # פלייסהולדר ליצירת חוזה
    logger.info(f"Creating contract from proposal {proposal_id}")
    return f"CONTRACT-{proposal_id}"

def generate_pdf_content(proposal_id):
    """יצירת תוכן PDF"""
    # פלייסהולדר ליצירת PDF
    return b"PDF Content Placeholder"