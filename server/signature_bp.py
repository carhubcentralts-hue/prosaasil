"""
Digital Signature Blueprint - מודול חתימות דיגיטליות כ-Blueprint נפרד
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from app import db
from models import CRMCustomer, Business
from auth import login_required
from digital_signature_service import DigitalSignatureService
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Create Signature Blueprint
signature_bp = Blueprint('signatures', __name__, url_prefix='/signatures')

@signature_bp.route('/')
@login_required
def signature_dashboard():
    """דשבורד חתימות דיגיטליות"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # קבלת לקוחות לרשימה הנפתחת
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        # Mock signatures data - יש להחליף במודל אמיתי
        signatures = []
        
        # סטטיסטיקות
        total_signatures = len(signatures)
        signed_count = len([s for s in signatures if s.get('status') == 'signed'])
        pending_count = len([s for s in signatures if s.get('status') == 'pending'])
        today_signatures = len([s for s in signatures if s.get('created_at') and s['created_at'].date() == datetime.utcnow().date()])
        
        return render_template('signature.html',
                             customers=customers,
                             signatures=signatures,
                             total_signatures=total_signatures,
                             signed_count=signed_count,
                             pending_count=pending_count,
                             today_signatures=today_signatures)
                             
    except Exception as e:
        logger.error(f"Error in signature dashboard: {e}")
        flash('שגיאה בטעינת דשבורד חתימות', 'error')
        return redirect(url_for('index'))

@signature_bp.route('/create', methods=['POST'])
@login_required
def create_signature():
    """יצירת חתימה דיגיטלית חדשה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        customer_id = request.form.get('customer_id')
        document_type = request.form.get('document_type')
        notes = request.form.get('notes', '')
        
        if not customer_id or not document_type:
            flash('לקוח וסוג מסמך הם שדות חובה', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # בדיקת העלאת קובץ
        if 'document' not in request.files:
            flash('נדרש להעלות קובץ מסמך', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        file = request.files['document']
        if file.filename == '':
            flash('לא נבחר קובץ', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            flash('לקוח לא נמצא', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and customer.business_id != current_user.business_id:
            flash('אין לך הרשאה ליצור חתימה עבור לקוח זה', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # יצירת חתימה דיגיטלית
        signature_service = DigitalSignatureService()
        result = signature_service.create_signature_document(
            customer_id=customer_id,
            document_type=document_type,
            document_file=file,
            notes=notes,
            business_id=customer.business_id
        )
        
        if result.get('success'):
            logger.info(f"✅ Digital signature created for customer {customer_id}")
            flash('חתימה דיגיטלית נוצרה בהצלחה', 'success')
            
            # שליחה אוטומטית אם נבחר
            if request.form.get('send_immediately'):
                send_result = signature_service.send_signature_request(
                    signature_id=result['signature_id'],
                    customer=customer
                )
                if send_result.get('success'):
                    flash('החתימה נשלחה ללקוח בהצלחה', 'success')
                else:
                    flash('החתימה נוצרה אך לא ניתן היה לשלוח ללקוח', 'warning')
        else:
            logger.error(f"❌ Failed to create signature for customer {customer_id}")
            flash('שגיאה ביצירת החתימה הדיגיטלית', 'error')
            
    except Exception as e:
        logger.error(f"❌ Error creating signature: {e}")
        flash('שגיאה ביצירת החתימה', 'error')
    
    return redirect(url_for('signatures.signature_dashboard'))

@signature_bp.route('/create_advanced', methods=['POST'])
@login_required
def create_advanced_signature():
    """יצירת חתימה דיגיטלית מתקדמת"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        customer_id = request.form.get('customer_id')
        document_type = request.form.get('document_type')
        title = request.form.get('title', '')
        notes = request.form.get('notes', '')
        expiry_date = request.form.get('expiry_date')
        send_method = request.form.get('send_method', 'whatsapp')
        send_immediately = request.form.get('send_immediately') == 'on'
        
        if not customer_id or not document_type:
            flash('לקוח וסוג מסמך הם שדות חובה', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # בדיקת העלאת קובץ
        if 'document' not in request.files:
            flash('נדרש להעלות קובץ מסמך', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        file = request.files['document']
        if file.filename == '':
            flash('לא נבחר קובץ', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            flash('לקוח לא נמצא', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and customer.business_id != current_user.business_id:
            flash('אין לך הרשאה ליצור חתימה עבור לקוח זה', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # יצירת חתימה דיגיטלית מתקדמת
        signature_service = DigitalSignatureService()
        result = signature_service.create_advanced_signature(
            customer_id=customer_id,
            document_type=document_type,
            document_file=file,
            title=title,
            notes=notes,
            expiry_date=datetime.strptime(expiry_date, '%Y-%m-%d') if expiry_date else None,
            send_method=send_method,
            business_id=customer.business_id
        )
        
        if result.get('success'):
            logger.info(f"✅ Advanced digital signature created for customer {customer_id}")
            flash('חתימה דיגיטלית מתקדמת נוצרה בהצלחה', 'success')
            
            # שליחה אוטומטית אם נבחר
            if send_immediately:
                send_result = signature_service.send_signature_request(
                    signature_id=result['signature_id'],
                    customer=customer,
                    send_method=send_method
                )
                if send_result.get('success'):
                    flash('החתימה נשלחה ללקוח בהצלחה', 'success')
                else:
                    flash('החתימה נוצרה אך לא ניתן היה לשלוח ללקוח', 'warning')
        else:
            logger.error(f"❌ Failed to create advanced signature for customer {customer_id}")
            flash('שגיאה ביצירת החתימה הדיגיטלית', 'error')
            
    except Exception as e:
        logger.error(f"❌ Error creating advanced signature: {e}")
        flash('שגיאה ביצירת החתימה', 'error')
    
    return redirect(url_for('signatures.signature_dashboard'))

@signature_bp.route('/view/<int:signature_id>')
@login_required
def view_signature(signature_id):
    """צפייה בחתימה דיגיטלית"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # Mock signature data - יש להחליף במודל אמיתי
        signature_service = DigitalSignatureService()
        signature = signature_service.get_signature_by_id(signature_id)
        
        if not signature:
            flash('חתימה דיגיטלית לא נמצאה', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and signature.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה לצפות בחתימה זו', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        return render_template('signature_view.html', signature=signature)
        
    except Exception as e:
        logger.error(f"Error viewing signature {signature_id}: {e}")
        flash('שגיאה בטעינת החתימה', 'error')
        return redirect(url_for('signatures.signature_dashboard'))

@signature_bp.route('/download/<int:signature_id>')
@login_required
def download_signature(signature_id):
    """הורדת מסמך החתימה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        signature_service = DigitalSignatureService()
        signature = signature_service.get_signature_by_id(signature_id)
        
        if not signature:
            flash('חתימה דיגיטלית לא נמצאה', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and signature.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה להוריד חתימה זו', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
        
        # הורדת הקובץ
        file_path = signature.get('file_path')
        if file_path and os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('קובץ החתימה לא נמצא', 'error')
            return redirect(url_for('signatures.signature_dashboard'))
            
    except Exception as e:
        logger.error(f"Error downloading signature {signature_id}: {e}")
        flash('שגיאה בהורדת החתימה', 'error')
        return redirect(url_for('signatures.signature_dashboard'))

@signature_bp.route('/send/<int:signature_id>', methods=['POST'])
@login_required
def send_signature(signature_id):
    """שליחת חתימה ללקוח"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        signature_service = DigitalSignatureService()
        signature = signature_service.get_signature_by_id(signature_id)
        
        if not signature:
            return jsonify({'success': False, 'message': 'חתימה לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and signature.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(signature.get('customer_id'))
        if not customer:
            return jsonify({'success': False, 'message': 'לקוח לא נמצא'})
        
        # שליחת החתימה
        result = signature_service.send_signature_request(
            signature_id=signature_id,
            customer=customer
        )
        
        if result.get('success'):
            logger.info(f"✅ Signature {signature_id} sent to customer")
            return jsonify({'success': True, 'message': 'החתימה נשלחה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בשליחת החתימה'})
            
    except Exception as e:
        logger.error(f"❌ Error sending signature {signature_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשליחת החתימה'})

@signature_bp.route('/remind/<int:signature_id>', methods=['POST'])
@login_required
def remind_signature(signature_id):
    """שליחת תזכורת לחתימה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        signature_service = DigitalSignatureService()
        signature = signature_service.get_signature_by_id(signature_id)
        
        if not signature:
            return jsonify({'success': False, 'message': 'חתימה לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and signature.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(signature.get('customer_id'))
        if not customer:
            return jsonify({'success': False, 'message': 'לקוח לא נמצא'})
        
        # שליחת תזכורת
        result = signature_service.send_signature_reminder(
            signature_id=signature_id,
            customer=customer
        )
        
        if result.get('success'):
            logger.info(f"✅ Signature reminder {signature_id} sent to customer")
            return jsonify({'success': True, 'message': 'תזכורת נשלחה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בשליחת התזכורת'})
            
    except Exception as e:
        logger.error(f"❌ Error sending signature reminder {signature_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשליחת התזכורת'})

@signature_bp.route('/api/signatures')
@login_required
def api_signatures():
    """API לקבלת רשימת חתימות"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        signature_service = DigitalSignatureService()
        
        # קבלת חתימות לפי העסק
        if current_user.role == 'admin':
            signatures = signature_service.get_all_signatures()
        else:
            signatures = signature_service.get_signatures_by_business(current_user.business_id)
        
        return jsonify(signatures)
        
    except Exception as e:
        logger.error(f"Error in API signatures: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני חתימות'}), 500

@signature_bp.route('/public/sign/<signature_token>')
def public_sign(signature_token):
    """עמוד חתימה ציבורי ללקוח"""
    try:
        signature_service = DigitalSignatureService()
        signature = signature_service.get_signature_by_token(signature_token)
        
        if not signature:
            return render_template('error_404.html'), 404
        
        # בדיקת תוקף
        if signature.get('expired'):
            return render_template('signature_expired.html'), 410
        
        return render_template('public_signature.html', 
                             signature=signature,
                             token=signature_token)
        
    except Exception as e:
        logger.error(f"Error in public signature page: {e}")
        return render_template('error_500.html'), 500

@signature_bp.route('/public/submit/<signature_token>', methods=['POST'])
def submit_signature(signature_token):
    """קבלת חתימה מהלקוח"""
    try:
        signature_service = DigitalSignatureService()
        signature_data = request.json.get('signature')
        customer_details = request.json.get('customer_details')
        
        if not signature_data:
            return jsonify({'success': False, 'message': 'חתימה נדרשת'})
        
        result = signature_service.process_signature(
            token=signature_token,
            signature_data=signature_data,
            customer_details=customer_details
        )
        
        if result.get('success'):
            logger.info(f"✅ Signature received for token {signature_token}")
            return jsonify({'success': True, 'message': 'החתימה התקבלה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בעיבוד החתימה'})
            
    except Exception as e:
        logger.error(f"❌ Error processing signature: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בעיבוד החתימה'})