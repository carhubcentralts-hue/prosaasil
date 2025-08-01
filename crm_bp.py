"""
CRM Blueprint - מודול CRM כ-Blueprint נפרד
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app import db
from models import CRMCustomer, CRMTask, Business
from auth import login_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create CRM Blueprint
crm_bp = Blueprint('crm', __name__, url_prefix='/crm')

@crm_bp.route('/')
@login_required
def crm_dashboard():
    """דשבורד CRM ראשי"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות CRM
        if not current_user.has_crm_access():
            flash('אין לך הרשאה לגשת למערכת CRM', 'error')
            return redirect(url_for('index'))
        
        # קבלת לקוחות לפי העסק
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        # סטטיסטיקות
        today = datetime.utcnow().date()
        today_contacts = len([c for c in customers if c.created_at.date() == today]) if customers else 0
        
        return render_template('crm.html', 
                             customers=customers,
                             today_contacts=today_contacts)
    except Exception as e:
        logger.error(f"Error in CRM dashboard: {e}")
        flash('שגיאה בטעינת דשבורד CRM', 'error')
        return redirect(url_for('index'))

@crm_bp.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    """הוספת לקוח חדש"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_crm_access():
            flash('אין לך הרשאה להוסיף לקוחות', 'error')
            return redirect(url_for('crm.crm_dashboard'))
        
        # קבלת נתונים מהטופס
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email', '')
        status = request.form.get('status', 'prospect')
        source = request.form.get('source', 'manual')
        notes = request.form.get('notes', '')
        
        if not name or not phone:
            flash('שם ומספר טלפון הם שדות חובה', 'error')
            return redirect(url_for('crm.crm_dashboard'))
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else request.form.get('business_id')
        
        # יצירת לקוח חדש
        customer = CRMCustomer(
            name=name,
            phone=phone,
            email=email if email else None,
            business_id=business_id,
            status=status,
            source=source,
            notes=notes
        )
        
        db.session.add(customer)
        db.session.commit()
        
        logger.info(f"✅ New customer added: {name} - {phone}")
        flash(f'לקוח {name} נוסף בהצלחה', 'success')
        
    except Exception as e:
        logger.error(f"❌ Error adding customer: {e}")
        db.session.rollback()
        flash('שגיאה בהוספת הלקוח', 'error')
    
    return redirect(url_for('crm.crm_dashboard'))

@crm_bp.route('/customer/<int:customer_id>')
@login_required
def view_customer(customer_id):
    """צפייה בפרטי לקוח"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        customer = CRMCustomer.query.get_or_404(customer_id)
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and customer.business_id != current_user.business_id:
            flash('אין לך הרשאה לצפות בלקוח זה', 'error')
            return redirect(url_for('crm.crm_dashboard'))
        
        # קבלת משימות הלקוח
        tasks = CRMTask.query.filter_by(customer_id=customer_id).all()
        
        return render_template('customer_details.html', 
                             customer=customer, 
                             tasks=tasks)
        
    except Exception as e:
        logger.error(f"Error viewing customer {customer_id}: {e}")
        flash('שגיאה בטעינת פרטי הלקוח', 'error')
        return redirect(url_for('crm.crm_dashboard'))

@crm_bp.route('/tasks')
@login_required
def tasks():
    """דף משימות CRM"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_crm_access():
            flash('אין לך הרשאה לגשת למשימות', 'error')
            return redirect(url_for('index'))
        
        # קבלת משימות לפי העסק
        if current_user.role == 'admin':
            tasks = CRMTask.query.all()
        else:
            tasks = CRMTask.query.filter_by(business_id=current_user.business_id).all()
        
        return render_template('crm_tasks.html', tasks=tasks)
        
    except Exception as e:
        logger.error(f"Error in CRM tasks: {e}")
        flash('שגיאה בטעינת המשימות', 'error')
        return redirect(url_for('crm.crm_dashboard'))

@crm_bp.route('/add_task', methods=['POST'])
@login_required
def add_task():
    """הוספת משימה חדשה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_crm_access():
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        title = request.form.get('title')
        description = request.form.get('description', '')
        customer_id = request.form.get('customer_id')
        priority = request.form.get('priority', 'medium')
        due_date = request.form.get('due_date')
        
        if not title:
            return jsonify({'success': False, 'message': 'כותרת המשימה חובה'})
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else request.form.get('business_id')
        
        # יצירת משימה חדשה
        task = CRMTask(
            title=title,
            description=description,
            business_id=business_id,
            customer_id=customer_id if customer_id else None,
            priority=priority,
            assigned_to=current_user.username,
            due_date=datetime.strptime(due_date, '%Y-%m-%d') if due_date else None
        )
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"✅ New task added: {title}")
        return jsonify({'success': True, 'message': 'המשימה נוספה בהצלחה'})
        
    except Exception as e:
        logger.error(f"❌ Error adding task: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'שגיאה בהוספת המשימה'})

@crm_bp.route('/update_task/<int:task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    """עדכון סטטוס משימה"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        task = CRMTask.query.get_or_404(task_id)
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and task.business_id != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        status = request.json.get('status')
        if status in ['pending', 'in_progress', 'completed', 'cancelled']:
            task.status = status
            if status == 'completed':
                task.completed_at = datetime.utcnow()
            
            db.session.commit()
            logger.info(f"✅ Task {task_id} updated to {status}")
            return jsonify({'success': True, 'message': 'המשימה עודכנה בהצלחה'})
        else:
            return jsonify({'success': False, 'message': 'סטטוס לא תקין'})
            
    except Exception as e:
        logger.error(f"❌ Error updating task {task_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'שגיאה בעדכון המשימה'})

@crm_bp.route('/api/customers')
@login_required
def api_customers():
    """API לקבלת רשימת לקוחות"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_crm_access():
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # קבלת לקוחות לפי העסק
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'email': c.email,
            'status': c.status,
            'source': c.source,
            'created_at': c.created_at.isoformat() if c.created_at else None
        } for c in customers])
        
    except Exception as e:
        logger.error(f"Error in API customers: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני לקוחות'}), 500

@crm_bp.route('/api/stats')
@login_required
def api_stats():
    """API לסטטיסטיקות CRM"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_crm_access():
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # קבלת נתונים לפי העסק
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
            tasks = CRMTask.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
            tasks = CRMTask.query.filter_by(business_id=current_user.business_id).all()
        
        today = datetime.utcnow().date()
        
        stats = {
            'total_customers': len(customers),
            'active_customers': len([c for c in customers if c.status == 'active']),
            'prospects': len([c for c in customers if c.status == 'prospect']),
            'today_contacts': len([c for c in customers if c.created_at.date() == today]),
            'total_tasks': len(tasks),
            'pending_tasks': len([t for t in tasks if t.status == 'pending']),
            'completed_tasks': len([t for t in tasks if t.status == 'completed'])
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error in API stats: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500