"""
Invoice Blueprint - מודול חשבוניות כ-Blueprint נפרד
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from app import db
from models import CRMCustomer, Business
from auth import login_required
from invoice_generator import InvoiceGenerator
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Create Invoice Blueprint
invoice_bp = Blueprint('invoices', __name__, url_prefix='/invoices')

@invoice_bp.route('/')
@login_required
def invoice_dashboard():
    """דשבורד חשבוניות"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # קבלת לקוחות לרשימה הנפתחת
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        # Mock invoices data - יש להחליף במודל אמיתי
        invoices = []
        
        # סטטיסטיקות
        total_invoices = len(invoices)
        paid_invoices = len([i for i in invoices if i.get('status') == 'paid'])
        pending_invoices = len([i for i in invoices if i.get('status') == 'pending'])
        total_amount = sum([i.get('amount', 0) for i in invoices])
        
        return render_template('invoices.html',
                             customers=customers,
                             invoices=invoices,
                             total_invoices=total_invoices,
                             paid_invoices=paid_invoices,
                             pending_invoices=pending_invoices,
                             total_amount=total_amount)
                             
    except Exception as e:
        logger.error(f"Error in invoice dashboard: {e}")
        flash('שגיאה בטעינת דשבורד חשבוניות', 'error')
        return redirect(url_for('index'))

@invoice_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    """יצירת חשבונית חדשה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if request.method == 'GET':
            # הצגת טופס יצירת חשבונית
            if current_user.role == 'admin':
                customers = CRMCustomer.query.all()
            else:
                customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
            
            return render_template('create_invoice.html', customers=customers)
        
        # עיבוד יצירת החשבונית
        customer_id = request.form.get('customer_id')
        invoice_date = request.form.get('invoice_date')
        due_date = request.form.get('due_date')
        description = request.form.get('description')
        
        # פריטי החשבונית
        item_names = request.form.getlist('item_name[]')
        item_quantities = request.form.getlist('item_quantity[]')
        item_prices = request.form.getlist('item_price[]')
        
        if not customer_id or not item_names:
            flash('לקוח ופריטים הם שדות חובה', 'error')
            return redirect(url_for('invoices.create_invoice'))
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            flash('לקוח לא נמצא', 'error')
            return redirect(url_for('invoices.create_invoice'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and customer.business_id != current_user.business_id:
            flash('אין לך הרשאה ליצור חשבונית עבור לקוח זה', 'error')
            return redirect(url_for('invoices.create_invoice'))
        
        # הכנת פריטי החשבונית
        items = []
        for i in range(len(item_names)):
            if item_names[i]:  # רק פריטים עם שם
                items.append({
                    'name': item_names[i],
                    'quantity': float(item_quantities[i]) if item_quantities[i] else 1,
                    'price': float(item_prices[i]) if item_prices[i] else 0
                })
        
        # יצירת החשבונית
        invoice_generator = InvoiceGenerator()
        result = invoice_generator.create_invoice(
            customer_id=customer_id,
            items=items,
            invoice_date=datetime.strptime(invoice_date, '%Y-%m-%d') if invoice_date else datetime.utcnow(),
            due_date=datetime.strptime(due_date, '%Y-%m-%d') if due_date else None,
            description=description,
            business_id=customer.business_id
        )
        
        if result.get('success'):
            logger.info(f"✅ Invoice created for customer {customer_id}")
            flash('חשבונית נוצרה בהצלחה', 'success')
            
            # שליחה אוטומטית אם נבחר
            if request.form.get('send_immediately'):
                send_result = invoice_generator.send_invoice(
                    invoice_id=result['invoice_id'],
                    customer=customer
                )
                if send_result.get('success'):
                    flash('החשבונית נשלחה ללקוח בהצלחה', 'success')
                else:
                    flash('החשבונית נוצרה אך לא ניתן היה לשלוח ללקוח', 'warning')
            
            return redirect(url_for('invoices.invoice_dashboard'))
        else:
            logger.error(f"❌ Failed to create invoice for customer {customer_id}")
            flash('שגיאה ביצירת החשבונית', 'error')
            return redirect(url_for('invoices.create_invoice'))
            
    except Exception as e:
        logger.error(f"❌ Error creating invoice: {e}")
        flash('שגיאה ביצירת החשבונית', 'error')
        return redirect(url_for('invoices.create_invoice'))

@invoice_bp.route('/view/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    """צפייה בחשבונית"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        invoice = invoice_generator.get_invoice_by_id(invoice_id)
        
        if not invoice:
            flash('חשבונית לא נמצאה', 'error')
            return redirect(url_for('invoices.invoice_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and invoice.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה לצפות בחשבונית זו', 'error')
            return redirect(url_for('invoices.invoice_dashboard'))
        
        return render_template('invoice_view.html', invoice=invoice)
        
    except Exception as e:
        logger.error(f"Error viewing invoice {invoice_id}: {e}")
        flash('שגיאה בטעינת החשבונית', 'error')
        return redirect(url_for('invoices.invoice_dashboard'))

@invoice_bp.route('/download/<int:invoice_id>')
@login_required
def download_invoice(invoice_id):
    """הורדת PDF חשבונית"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        invoice = invoice_generator.get_invoice_by_id(invoice_id)
        
        if not invoice:
            flash('חשבונית לא נמצאה', 'error')
            return redirect(url_for('invoices.invoice_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and invoice.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה להוריד חשבונית זו', 'error')
            return redirect(url_for('invoices.invoice_dashboard'))
        
        # יצירת PDF והורדה
        pdf_path = invoice_generator.generate_invoice_pdf(invoice_id)
        if pdf_path and os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True, 
                           download_name=f'invoice_{invoice_id}.pdf')
        else:
            flash('שגיאה ביצירת PDF החשבונית', 'error')
            return redirect(url_for('invoices.invoice_dashboard'))
            
    except Exception as e:
        logger.error(f"Error downloading invoice {invoice_id}: {e}")
        flash('שגיאה בהורדת החשבונית', 'error')
        return redirect(url_for('invoices.invoice_dashboard'))

@invoice_bp.route('/send/<int:invoice_id>', methods=['POST'])
@login_required
def send_invoice(invoice_id):
    """שליחת חשבונית ללקוח"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        invoice = invoice_generator.get_invoice_by_id(invoice_id)
        
        if not invoice:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and invoice.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(invoice.get('customer_id'))
        if not customer:
            return jsonify({'success': False, 'message': 'לקוח לא נמצא'})
        
        # שליחת החשבונית
        result = invoice_generator.send_invoice(
            invoice_id=invoice_id,
            customer=customer
        )
        
        if result.get('success'):
            logger.info(f"✅ Invoice {invoice_id} sent to customer")
            return jsonify({'success': True, 'message': 'החשבונית נשלחה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בשליחת החשבונית'})
            
    except Exception as e:
        logger.error(f"❌ Error sending invoice {invoice_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשליחת החשבונית'})

@invoice_bp.route('/remind/<int:invoice_id>', methods=['POST'])
@login_required
def remind_invoice(invoice_id):
    """שליחת תזכורת תשלום"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        invoice = invoice_generator.get_invoice_by_id(invoice_id)
        
        if not invoice:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and invoice.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(invoice.get('customer_id'))
        if not customer:
            return jsonify({'success': False, 'message': 'לקוח לא נמצא'})
        
        # שליחת תזכורת
        result = invoice_generator.send_payment_reminder(
            invoice_id=invoice_id,
            customer=customer
        )
        
        if result.get('success'):
            logger.info(f"✅ Payment reminder {invoice_id} sent to customer")
            return jsonify({'success': True, 'message': 'תזכורת נשלחה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בשליחת התזכורת'})
            
    except Exception as e:
        logger.error(f"❌ Error sending payment reminder {invoice_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשליחת התזכורת'})

@invoice_bp.route('/mark_paid/<int:invoice_id>', methods=['POST'])
@login_required
def mark_paid(invoice_id):
    """סימון חשבונית כשולמה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        invoice = invoice_generator.get_invoice_by_id(invoice_id)
        
        if not invoice:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and invoice.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        payment_method = request.json.get('payment_method', 'manual')
        payment_date = request.json.get('payment_date')
        notes = request.json.get('notes', '')
        
        # סימון החשבונית כשולמה
        result = invoice_generator.mark_invoice_paid(
            invoice_id=invoice_id,
            payment_method=payment_method,
            payment_date=datetime.strptime(payment_date, '%Y-%m-%d') if payment_date else datetime.utcnow(),
            notes=notes
        )
        
        if result.get('success'):
            logger.info(f"✅ Invoice {invoice_id} marked as paid")
            return jsonify({'success': True, 'message': 'החשבונית סומנה כשולמה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בסימון החשבונית'})
            
    except Exception as e:
        logger.error(f"❌ Error marking invoice {invoice_id} as paid: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בסימון החשבונית'})

@invoice_bp.route('/api/invoices')
@login_required
def api_invoices():
    """API לקבלת רשימת חשבוניות"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        
        # קבלת חשבוניות לפי העסק
        if current_user.role == 'admin':
            invoices = invoice_generator.get_all_invoices()
        else:
            invoices = invoice_generator.get_invoices_by_business(current_user.business_id)
        
        return jsonify(invoices)
        
    except Exception as e:
        logger.error(f"Error in API invoices: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני חשבוניות'}), 500

@invoice_bp.route('/api/stats')
@login_required
def api_stats():
    """API לסטטיסטיקות חשבוניות"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        
        # קבלת נתונים לפי העסק
        if current_user.role == 'admin':
            stats = invoice_generator.get_global_stats()
        else:
            stats = invoice_generator.get_business_stats(current_user.business_id)
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error in API stats: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500

@invoice_bp.route('/payment_link/<int:invoice_id>')
@login_required
def generate_payment_link(invoice_id):
    """יצירת קישור תשלום"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        invoice_generator = InvoiceGenerator()
        invoice = invoice_generator.get_invoice_by_id(invoice_id)
        
        if not invoice:
            return jsonify({'success': False, 'message': 'חשבונית לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and invoice.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # יצירת קישור תשלום
        result = invoice_generator.generate_payment_link(invoice_id)
        
        if result.get('success'):
            logger.info(f"✅ Payment link generated for invoice {invoice_id}")
            return jsonify({
                'success': True, 
                'payment_link': result['payment_link'],
                'message': 'קישור תשלום נוצר בהצלחה'
            })
        else:
            return jsonify({'success': False, 'message': 'שגיאה ביצירת קישור התשלום'})
            
    except Exception as e:
        logger.error(f"❌ Error generating payment link for invoice {invoice_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה ביצירת קישור התשלום'})