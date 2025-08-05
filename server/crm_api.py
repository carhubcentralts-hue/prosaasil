"""
CRM API endpoints for React frontend  
API נקודות עבור מערכת CRM עם React
"""
from flask import Blueprint, request, jsonify
from app import db
from models import CRMCustomer, CRMTask, Business
from auth import login_required, AuthService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create CRM API Blueprint
crm_api_bp = Blueprint('crm_api', __name__, url_prefix='/api/crm')

@crm_api_bp.route('/customers', methods=['GET'])
@login_required
def get_customers():
    """קבלת רשימת לקוחות עבור React"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user or not current_user.has_crm_access():
            return jsonify({'error': 'אין הרשאה לגשת למערכת CRM'}), 403
        
        # קבלת לקוחות לפי העסק
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(business_id=current_user.business_id).all()
        
        # סטטיסטיקות
        today = datetime.utcnow().date()
        today_contacts = len([c for c in customers if c.created_at.date() == today]) if customers else 0
        active_customers = len([c for c in customers if c.status == 'active']) if customers else 0
        
        # המרת לקוחות לפורמט JSON
        customers_data = []
        for customer in customers:
            customers_data.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'status': customer.status,
                'source': customer.source,
                'notes': customer.notes,
                'created_at': customer.created_at.isoformat() if customer.created_at else None,
                'updated_at': customer.updated_at.isoformat() if customer.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'customers': customers_data,
            'stats': {
                'total_customers': len(customers),
                'active_customers': active_customers,
                'today_contacts': today_contacts
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting CRM customers: {e}")
        return jsonify({'error': 'שגיאה בטעינת לקוחות'}), 500

@crm_api_bp.route('/customers', methods=['POST'])
@login_required
def add_customer():
    """הוספת לקוח חדש"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user or not current_user.has_crm_access():
            return jsonify({'error': 'אין הרשאה להוסיף לקוחות'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
        
        name = data.get('name')
        phone = data.get('phone')
        email = data.get('email', '')
        status = data.get('status', 'prospect')
        source = data.get('source', 'manual')
        notes = data.get('notes', '')
        
        if not name or not phone:
            return jsonify({'error': 'שם ומספר טלפון הם שדות חובה'}), 400
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else data.get('business_id')
        
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
        
        logger.info(f"New customer added: {name} ({phone}) by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'לקוח {name} נוסף בהצלחה',
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'status': customer.status,
                'source': customer.source,
                'notes': customer.notes,
                'created_at': customer.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding customer: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בהוספת לקוח'}), 500

@crm_api_bp.route('/tasks', methods=['GET'])
@login_required
def get_tasks():
    """קבלת רשימת משימות"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user or not current_user.has_crm_access():
            return jsonify({'error': 'אין הרשאה לגשת למשימות'}), 403
        
        # קבלת משימות לפי העסק
        if current_user.role == 'admin':
            tasks = CRMTask.query.order_by(CRMTask.created_at.desc()).all()
        else:
            tasks = CRMTask.query.filter_by(business_id=current_user.business_id).order_by(CRMTask.created_at.desc()).all()
        
        # המרת משימות לפורמט JSON
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'assigned_to': task.assigned_to,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            })
        
        return jsonify({
            'success': True,
            'tasks': tasks_data
        })
        
    except Exception as e:
        logger.error(f"Error getting CRM tasks: {e}")
        return jsonify({'error': 'שגיאה בטעינת משימות'}), 500

@crm_api_bp.route('/tasks', methods=['POST'])
@login_required
def add_task():
    """הוספת משימה חדשה"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user or not current_user.has_crm_access():
            return jsonify({'error': 'אין הרשאה להוסיף משימות'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
        
        title = data.get('title')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        due_date_str = data.get('due_date')
        
        if not title:
            return jsonify({'error': 'כותרת המשימה נדרשת'}), 400
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'תאריך יעד לא תקין'}), 400
        
        # יצירת משימה חדשה
        task = CRMTask(
            title=title,
            description=description,
            priority=priority,
            business_id=current_user.business_id if current_user.role != 'admin' else data.get('business_id'),
            assigned_to=current_user.username,
            due_date=due_date
        )
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"New task added: {title} by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'משימה "{title}" נוספה בהצלחה',
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'created_at': task.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בהוספת משימה'}), 500