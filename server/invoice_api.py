"""
Invoice API endpoints for React frontend
API נקודות עבור מערכת חשבוניות עם React
"""
from flask import Blueprint, request, jsonify
from app import db
from models import Invoice, Business
from auth import login_required, AuthService, check_business_access
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Invoice API Blueprint
invoice_api_bp = Blueprint('invoice_api', __name__, url_prefix='/api/invoice')

def check_business_permission(business, feature):
    """בדיקת הרשאות עסק לתכונה ספציפית"""
    if not getattr(business, feature, False):
        return False
    return True

@invoice_api_bp.route('/invoices', methods=['GET'])
@login_required
def get_invoices():
    """קבלת רשימת חשבוניות עבור React"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה לגשת למערכת חשבוניות'}), 403
        
        # קבלת חשבוניות לפי העסק
        if current_user.role == 'admin':
            invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
        else:
            if not current_user.business_id:
                return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
                
            # בדיקת הרשאות עסק
            business = Business.query.get(current_user.business_id)
            if not business or not check_business_permission(business, 'invoice_enabled'):
                return jsonify({'error': 'העסק לא מורשה לשימוש בחשבוניות'}), 403
            
            invoices = Invoice.query.filter_by(
                business_id=current_user.business_id
            ).order_by(Invoice.created_at.desc()).all()
        
        # המרת חשבוניות לפורמט JSON
        invoices_data = []
        for invoice in invoices:
            invoices_data.append({
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer_name,
                'customer_email': invoice.customer_email,
                'amount': float(invoice.amount) if invoice.amount else 0,
                'status': invoice.status,
                'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
                'description': invoice.description
            })
        
        # סטטיסטיקות
        total_invoices = len(invoices)
        paid_count = len([i for i in invoices if i.status == 'paid'])
        pending_count = len([i for i in invoices if i.status == 'pending'])
        overdue_count = len([i for i in invoices if i.status == 'overdue'])
        total_amount = sum([float(i.amount) for i in invoices if i.amount])
        paid_amount = sum([float(i.amount) for i in invoices if i.amount and i.status == 'paid'])
        
        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'stats': {
                'total_invoices': total_invoices,
                'paid': paid_count,
                'pending': pending_count,
                'overdue': overdue_count,
                'total_amount': total_amount,
                'paid_amount': paid_amount,
                'outstanding_amount': total_amount - paid_amount
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting invoices: {e}")
        return jsonify({'error': 'שגיאה בטעינת חשבוניות'}), 500

@invoice_api_bp.route('/invoices', methods=['POST'])
@login_required
def create_invoice():
    """יצירת חשבונית חדשה"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה ליצור חשבוניות'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
        
        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        amount = data.get('amount')
        description = data.get('description', '')
        invoice_date_str = data.get('invoice_date')
        due_date_str = data.get('due_date')
        
        if not all([customer_name, amount]):
            return jsonify({'error': 'שם לקוח וסכום הם שדות חובה'}), 400
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return jsonify({'error': 'סכום לא תקין'}), 400
        
        # המרת תאריכים
        invoice_date = datetime.utcnow()
        if invoice_date_str:
            try:
                invoice_date = datetime.fromisoformat(invoice_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'תאריך חשבונית לא תקין'}), 400
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'תאריך פירעון לא תקין'}), 400
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else data.get('business_id')
        
        if business_id:
            # בדיקת הרשאות עסק
            business = Business.query.get(business_id)
            if not business or not check_business_permission(business, 'invoice_enabled'):
                return jsonify({'error': 'העסק לא מורשה לשימוש בחשבוניות'}), 403
        
        # יצירת מספר חשבונית אוטומטי
        import uuid
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # יצירת חשבונית חדשה
        invoice = Invoice(
            invoice_number=invoice_number,
            customer_name=customer_name,
            customer_email=customer_email,
            amount=amount,
            description=description,
            business_id=business_id,
            status='pending',
            invoice_date=invoice_date,
            due_date=due_date
        )
        
        db.session.add(invoice)
        db.session.commit()
        
        logger.info(f"New invoice created: {invoice_number} for {customer_name} by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'חשבונית נוצרה בהצלחה עבור {customer_name}',
            'invoice': {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer_name,
                'amount': float(invoice.amount),
                'status': invoice.status,
                'created_at': invoice.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה ביצירת חשבונית'}), 500

@invoice_api_bp.route('/invoices/<int:invoice_id>/pay', methods=['POST'])
@login_required
def mark_invoice_paid(invoice_id):
    """סימון חשבונית כשולמה"""
    try:
        current_user = AuthService.get_current_user()
        
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # בדיקת הרשאות
        if (current_user and current_user.role != 'admin' and 
            current_user.business_id and invoice.business_id != current_user.business_id):
            return jsonify({'error': 'אין הרשאה לעדכן חשבונית זו'}), 403
        
        # עדכון סטטוס לשולם
        invoice.status = 'paid'
        invoice.paid_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Invoice marked as paid: {invoice.invoice_number} by {current_user.username if current_user else 'unknown'}")
        
        return jsonify({
            'success': True,
            'message': 'החשבונית סומנה כשולמה',
            'invoice': {
                'id': invoice.id,
                'status': invoice.status,
                'paid_at': invoice.paid_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error marking invoice as paid: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בעדכון חשבונית'}), 500