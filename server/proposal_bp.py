"""
Proposal Blueprint - מודול הצעות מחיר כ-Blueprint נפרד
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from app import db
from models import CRMCustomer, Business
from auth import login_required
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Create Proposal Blueprint
proposal_bp = Blueprint('proposals', __name__, url_prefix='/proposals')

@proposal_bp.route('/')
@login_required
def proposal_dashboard():
    """דשבורד הצעות מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # קבלת לקוחות לרשימה הנפתחת
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        # Mock proposals data - יש להחליף במודל אמיתי
        proposals = []
        
        # סטטיסטיקות
        total_proposals = len(proposals)
        accepted_proposals = len([p for p in proposals if p.get('status') == 'accepted'])
        pending_proposals = len([p for p in proposals if p.get('status') == 'pending'])
        total_value = sum([p.get('total_amount', 0) for p in proposals])
        today = datetime.utcnow().date()
        
        return render_template('proposal.html',
                             customers=customers,
                             proposals=proposals,
                             total_proposals=total_proposals,
                             accepted_proposals=accepted_proposals,
                             pending_proposals=pending_proposals,
                             total_value=total_value,
                             today=today)
                             
    except Exception as e:
        logger.error(f"Error in proposal dashboard: {e}")
        flash('שגיאה בטעינת דשבורד הצעות מחיר', 'error')
        return redirect(url_for('index'))

@proposal_bp.route('/create', methods=['POST'])
@login_required
def create_proposal():
    """יצירת הצעת מחיר חדשה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        customer_id = request.form.get('customer_id')
        title = request.form.get('title')
        description = request.form.get('description', '')
        valid_until = request.form.get('valid_until')
        category = request.form.get('category', 'other')
        
        # פריטי ההצעה
        item_names = request.form.getlist('item_name[]')
        item_quantities = request.form.getlist('item_quantity[]')
        item_prices = request.form.getlist('item_price[]')
        total_amount = request.form.get('total_amount', 0)
        
        if not customer_id or not title or not item_names:
            flash('לקוח, כותרת ופריטים הם שדות חובה', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            flash('לקוח לא נמצא', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and customer.business_id != current_user.business_id:
            flash('אין לך הרשאה ליצור הצעת מחיר עבור לקוח זה', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # הכנת פריטי ההצעה
        items = []
        for i in range(len(item_names)):
            if item_names[i]:  # רק פריטים עם שם
                items.append({
                    'name': item_names[i],
                    'quantity': float(item_quantities[i]) if item_quantities[i] else 1,
                    'price': float(item_prices[i]) if item_prices[i] else 0
                })
        
        # יצירת הצעת המחיר (Mock - יש לממש במודל אמיתי)
        proposal_data = {
            'customer_id': customer_id,
            'customer_name': customer.name,
            'customer_phone': customer.phone,
            'title': title,
            'description': description,
            'category': category,
            'items': items,
            'total_amount': float(total_amount),
            'valid_until': datetime.strptime(valid_until, '%Y-%m-%d') if valid_until else None,
            'status': 'draft',
            'created_at': datetime.utcnow(),
            'business_id': customer.business_id
        }
        
        # כאן יש לשמור את ההצעה במסד הנתונים
        # proposal = Proposal(**proposal_data)
        # db.session.add(proposal)
        # db.session.commit()
        
        logger.info(f"✅ Proposal created for customer {customer_id}")
        flash('הצעת מחיר נוצרה בהצלחה', 'success')
        
        # שליחה אוטומטית אם נבחר
        if request.form.get('send_immediately'):
            # שליחת ההצעה ללקוח
            send_result = send_proposal_to_customer(proposal_data, customer)
            if send_result.get('success'):
                flash('הצעת המחיר נשלחה ללקוח בהצלחה', 'success')
            else:
                flash('הצעת המחיר נוצרה אך לא ניתן היה לשלוח ללקוח', 'warning')
            
    except Exception as e:
        logger.error(f"❌ Error creating proposal: {e}")
        flash('שגיאה ביצירת הצעת המחיר', 'error')
    
    return redirect(url_for('proposals.proposal_dashboard'))

@proposal_bp.route('/view/<int:proposal_id>')
@login_required
def view_proposal(proposal_id):
    """צפייה בהצעת מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # Mock proposal data - יש להחליף במודל אמיתי
        proposal = get_proposal_by_id(proposal_id)
        
        if not proposal:
            flash('הצעת מחיר לא נמצאה', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and proposal.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה לצפות בהצעת מחיר זו', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        return render_template('proposal_view.html', proposal=proposal)
        
    except Exception as e:
        logger.error(f"Error viewing proposal {proposal_id}: {e}")
        flash('שגיאה בטעינת הצעת המחיר', 'error')
        return redirect(url_for('proposals.proposal_dashboard'))

@proposal_bp.route('/edit/<int:proposal_id>')
@login_required
def edit_proposal(proposal_id):
    """עריכת הצעת מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # Mock proposal data - יש להחליף במודל אמיתי
        proposal = get_proposal_by_id(proposal_id)
        
        if not proposal:
            flash('הצעת מחיר לא נמצאה', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and proposal.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה לערוך הצעת מחיר זו', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # קבלת לקוחות לרשימה הנפתחת
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        return render_template('proposal_edit.html', proposal=proposal, customers=customers)
        
    except Exception as e:
        logger.error(f"Error editing proposal {proposal_id}: {e}")
        flash('שגיאה בטעינת עריכת הצעת המחיר', 'error')
        return redirect(url_for('proposals.proposal_dashboard'))

@proposal_bp.route('/download/<int:proposal_id>')
@login_required
def download_proposal(proposal_id):
    """הורדת PDF הצעת מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        proposal = get_proposal_by_id(proposal_id)
        
        if not proposal:
            flash('הצעת מחיר לא נמצאה', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and proposal.get('business_id') != current_user.business_id:
            flash('אין לך הרשאה להוריד הצעת מחיר זו', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
        
        # יצירת PDF והורדה
        pdf_path = generate_proposal_pdf(proposal_id)
        if pdf_path and os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True, 
                           download_name=f'proposal_{proposal_id}.pdf')
        else:
            flash('שגיאה ביצירת PDF הצעת המחיר', 'error')
            return redirect(url_for('proposals.proposal_dashboard'))
            
    except Exception as e:
        logger.error(f"Error downloading proposal {proposal_id}: {e}")
        flash('שגיאה בהורדת הצעת המחיר', 'error')
        return redirect(url_for('proposals.proposal_dashboard'))

@proposal_bp.route('/send/<int:proposal_id>', methods=['POST'])
@login_required
def send_proposal(proposal_id):
    """שליחת הצעת מחיר ללקוח"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        proposal = get_proposal_by_id(proposal_id)
        
        if not proposal:
            return jsonify({'success': False, 'message': 'הצעת מחיר לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and proposal.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # קבלת פרטי הלקוח
        customer = CRMCustomer.query.get(proposal.get('customer_id'))
        if not customer:
            return jsonify({'success': False, 'message': 'לקוח לא נמצא'})
        
        # שליחת הצעת המחיר
        result = send_proposal_to_customer(proposal, customer)
        
        if result.get('success'):
            # עדכון סטטוס ההצעה
            update_proposal_status(proposal_id, 'sent')
            logger.info(f"✅ Proposal {proposal_id} sent to customer")
            return jsonify({'success': True, 'message': 'הצעת המחיר נשלחה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בשליחת הצעת המחיר'})
            
    except Exception as e:
        logger.error(f"❌ Error sending proposal {proposal_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשליחת הצעת המחיר'})

@proposal_bp.route('/duplicate/<int:proposal_id>', methods=['POST'])
@login_required
def duplicate_proposal(proposal_id):
    """שכפול הצעת מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        proposal = get_proposal_by_id(proposal_id)
        
        if not proposal:
            return jsonify({'success': False, 'message': 'הצעת מחיר לא נמצאה'})
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and proposal.get('business_id') != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        # יצירת עותק של ההצעה
        new_proposal = proposal.copy()
        new_proposal.update({
            'id': None,  # יימוצא ID חדש
            'title': proposal['title'] + ' - עותק',
            'status': 'draft',
            'created_at': datetime.utcnow(),
            'sent_at': None
        })
        
        # שמירת ההצעה החדשה
        new_proposal_id = save_proposal(new_proposal)
        
        if new_proposal_id:
            logger.info(f"✅ Proposal {proposal_id} duplicated as {new_proposal_id}")
            return jsonify({'success': True, 'message': 'הצעת המחיר שוכפלה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'שגיאה בשכפול הצעת המחיר'})
            
    except Exception as e:
        logger.error(f"❌ Error duplicating proposal {proposal_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשכפול הצעת המחיר'})

@proposal_bp.route('/api/proposals')
@login_required
def api_proposals():
    """API לקבלת רשימת הצעות מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # קבלת הצעות מחיר לפי העסק
        if current_user.role == 'admin':
            proposals = get_all_proposals()
        else:
            proposals = get_proposals_by_business(current_user.business_id)
        
        return jsonify(proposals)
        
    except Exception as e:
        logger.error(f"Error in API proposals: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני הצעות מחיר'}), 500

@proposal_bp.route('/api/stats')
@login_required
def api_stats():
    """API לסטטיסטיקות הצעות מחיר"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # קבלת נתונים לפי העסק
        if current_user.role == 'admin':
            proposals = get_all_proposals()
        else:
            proposals = get_proposals_by_business(current_user.business_id)
        
        stats = {
            'total_proposals': len(proposals),
            'accepted_proposals': len([p for p in proposals if p.get('status') == 'accepted']),
            'pending_proposals': len([p for p in proposals if p.get('status') == 'pending']),
            'rejected_proposals': len([p for p in proposals if p.get('status') == 'rejected']),
            'total_value': sum([p.get('total_amount', 0) for p in proposals]),
            'accepted_value': sum([p.get('total_amount', 0) for p in proposals if p.get('status') == 'accepted']),
            'average_value': sum([p.get('total_amount', 0) for p in proposals]) / len(proposals) if proposals else 0
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error in API stats: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500

# Helper functions - יש לממש במודל אמיתי
def get_proposal_by_id(proposal_id):
    """קבלת הצעת מחיר לפי ID"""
    # Mock implementation
    return None

def get_all_proposals():
    """קבלת כל הצעות המחיר"""
    # Mock implementation
    return []

def get_proposals_by_business(business_id):
    """קבלת הצעות מחיר לפי עסק"""
    # Mock implementation
    return []

def send_proposal_to_customer(proposal, customer):
    """שליחת הצעת מחיר ללקוח"""
    try:
        # ניתן לשלוח דרך WhatsApp או אימייל
        from whatsapp_service import WhatsAppService
        
        whatsapp_service = WhatsAppService()
        message = f"""
שלום {customer.name},

אני שמח לשלוח לך הצעת מחיר עבור: {proposal.get('title')}

סכום ההצעה: {proposal.get('total_amount', 0):,.0f}₪

לצפייה והתקדמות בהצעה: [קישור להצעה]

תודה,
הצוות
        """
        
        result = whatsapp_service.send_whatsapp_message(
            to_number=customer.phone,
            message_text=message,
            business_id=customer.business_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error sending proposal to customer: {e}")
        return {'success': False, 'message': str(e)}

def update_proposal_status(proposal_id, status):
    """עדכון סטטוס הצעת מחיר"""
    # Mock implementation
    pass

def save_proposal(proposal_data):
    """שמירת הצעת מחיר"""
    # Mock implementation
    return 1

def generate_proposal_pdf(proposal_id):
    """יצירת PDF הצעת מחיר"""
    # Mock implementation
    return None