"""
Tasks API - Task Management System
API משימות - מערכת ניהול משימות
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
import logging
from models import db, Task, Customer, User, Notification
from feature_flags import require_feature
from sqlalchemy import func, or_, and_
import pytz

logger = logging.getLogger(__name__)

# Create Tasks API Blueprint
tasks_api_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')

@tasks_api_bp.route('', methods=['POST'])
@require_feature('crm')
def create_task():
    """Create a new task"""
    try:
        data = request.get_json()
        business = g.business
        
        # Validate required fields
        required_fields = ['customer_id', 'title', 'channel', 'due_at']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': 'missing_field',
                    'message': f'שדה חובה חסר: {field}',
                    'field': field
                }), 400
        
        # Validate customer exists and belongs to business
        customer = Customer.query.filter_by(
            id=data['customer_id'], 
            business_id=business.id
        ).first()
        
        if not customer:
            return jsonify({
                'error': 'customer_not_found',
                'message': 'לקוח לא נמצא'
            }), 404
        
        # Parse due date
        try:
            due_at = datetime.fromisoformat(data['due_at'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({
                'error': 'invalid_date',
                'message': 'פורמט תאריך לא תקין'
            }), 400
        
        # Create task
        task = Task(
            business_id=business.id,
            customer_id=data['customer_id'],
            title=data['title'],
            notes=data.get('notes', ''),
            channel=data['channel'],
            due_at=due_at,
            assignee_user_id=data.get('assignee_user_id'),
            priority=data.get('priority', 'medium'),
            status='open'
        )
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"Task created: {task.id} for customer {customer.name}")
        
        # Return task with customer info
        return jsonify({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'notes': task.notes,
                'channel': task.channel,
                'due_at': task.due_at.isoformat(),
                'priority': task.priority,
                'status': task.status,
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'phone': customer.phone
                },
                'assignee_id': task.assignee_user_id,
                'created_at': task.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating task: {e}")
        return jsonify({
            'error': 'creation_failed',
            'message': 'שגיאה ביצירת משימה'
        }), 500

@tasks_api_bp.route('', methods=['GET'])
@require_feature('crm')
def get_tasks():
    """Get tasks with filtering and pagination"""
    try:
        business = g.business
        
        # Query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        range_filter = request.args.get('range', 'all')  # today, week, month, overdue, all
        status = request.args.get('status')
        assignee_id = request.args.get('assignee_id', type=int)
        customer_id = request.args.get('customer_id', type=int)
        channel = request.args.get('channel')
        priority = request.args.get('priority')
        
        # Build query
        query = Task.query.filter_by(business_id=business.id)
        
        # Apply filters
        if status:
            query = query.filter(Task.status == status)
        
        if assignee_id:
            query = query.filter(Task.assignee_user_id == assignee_id)
            
        if customer_id:
            query = query.filter(Task.customer_id == customer_id)
            
        if channel:
            query = query.filter(Task.channel == channel)
            
        if priority:
            query = query.filter(Task.priority == priority)
        
        # Date range filtering
        now = datetime.utcnow()
        if range_filter == 'today':
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            query = query.filter(Task.due_at.between(today_start, today_end))
        elif range_filter == 'week':
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
            query = query.filter(Task.due_at.between(week_start, week_end))
        elif range_filter == 'overdue':
            query = query.filter(
                and_(Task.due_at < now, Task.status.in_(['open', 'in_progress']))
            )
        
        # Paginate
        tasks_paginated = query.order_by(Task.due_at.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format tasks with related data
        tasks_data = []
        for task in tasks_paginated.items:
            customer = Customer.query.get(task.customer_id)
            assignee = User.query.get(task.assignee_user_id) if task.assignee_user_id else None
            
            task_data = {
                'id': task.id,
                'title': task.title,
                'notes': task.notes,
                'channel': task.channel,
                'due_at': task.due_at.isoformat(),
                'priority': task.priority,
                'status': task.status,
                'is_overdue': task.due_at < now and task.status in ['open', 'in_progress'],
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'phone': customer.phone
                } if customer else None,
                'assignee': {
                    'id': assignee.id,
                    'name': assignee.username
                } if assignee else None,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat() if hasattr(task, 'updated_at') else None
            }
            tasks_data.append(task_data)
        
        return jsonify({
            'success': True,
            'tasks': tasks_data,
            'pagination': {
                'page': tasks_paginated.page,
                'per_page': tasks_paginated.per_page,
                'total': tasks_paginated.total,
                'pages': tasks_paginated.pages,
                'has_next': tasks_paginated.has_next,
                'has_prev': tasks_paginated.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return jsonify({
            'error': 'fetch_failed',
            'message': 'שגיאה בטעינת משימות'
        }), 500

@tasks_api_bp.route('/<int:task_id>', methods=['PATCH'])
@require_feature('crm')
def update_task(task_id):
    """Update task status, snooze, or other fields"""
    try:
        business = g.business
        data = request.get_json()
        
        # Find task
        task = Task.query.filter_by(id=task_id, business_id=business.id).first()
        if not task:
            return jsonify({
                'error': 'task_not_found',
                'message': 'משימה לא נמצאה'
            }), 404
        
        # Update allowed fields
        allowed_updates = ['status', 'snooze_until', 'title', 'notes', 'priority', 'assignee_user_id']
        updated_fields = []
        
        for field in allowed_updates:
            if field in data:
                if field == 'snooze_until' and data[field]:
                    try:
                        snooze_time = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                        setattr(task, field, snooze_time)
                        updated_fields.append(field)
                    except ValueError:
                        return jsonify({
                            'error': 'invalid_snooze_date',
                            'message': 'פורמט תאריך נדנוד לא תקין'
                        }), 400
                else:
                    setattr(task, field, data[field])
                    updated_fields.append(field)
        
        # Set completion time if task is completed
        if data.get('status') == 'completed' and not hasattr(task, 'completed_at'):
            task.completed_at = datetime.utcnow()
            updated_fields.append('completed_at')
        
        db.session.commit()
        
        logger.info(f"Task {task_id} updated: {updated_fields}")
        
        return jsonify({
            'success': True,
            'message': 'משימה עודכנה בהצלחה',
            'updated_fields': updated_fields
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating task {task_id}: {e}")
        return jsonify({
            'error': 'update_failed',
            'message': 'שגיאה בעדכון משימה'
        }), 500

@tasks_api_bp.route('/summary', methods=['GET'])
@require_feature('crm')  
def get_task_summary():
    """Get task summary statistics"""
    try:
        business = g.business
        now = datetime.utcnow()
        
        # Count tasks by status
        total_tasks = Task.query.filter_by(business_id=business.id).count()
        open_tasks = Task.query.filter_by(business_id=business.id, status='open').count()
        in_progress_tasks = Task.query.filter_by(business_id=business.id, status='in_progress').count()
        completed_tasks = Task.query.filter_by(business_id=business.id, status='completed').count()
        
        # Overdue tasks
        overdue_tasks = Task.query.filter(
            Task.business_id == business.id,
            Task.due_at < now,
            Task.status.in_(['open', 'in_progress'])
        ).count()
        
        # Today's tasks
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_tasks = Task.query.filter(
            Task.business_id == business.id,
            Task.due_at.between(today_start, today_end),
            Task.status.in_(['open', 'in_progress'])
        ).count()
        
        # This week's tasks
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        week_tasks = Task.query.filter(
            Task.business_id == business.id,
            Task.due_at.between(week_start, week_end),
            Task.status.in_(['open', 'in_progress'])
        ).count()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_tasks': total_tasks,
                'open_tasks': open_tasks,
                'in_progress_tasks': in_progress_tasks,
                'completed_tasks': completed_tasks,
                'overdue_tasks': overdue_tasks,
                'today_tasks': today_tasks,
                'week_tasks': week_tasks
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching task summary: {e}")
        return jsonify({
            'error': 'summary_failed',
            'message': 'שגיאה בטעינת סיכום משימות'
        }), 500