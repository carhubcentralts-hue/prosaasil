"""
CRM Routes - Advanced Hebrew CRM System  
מסלולי CRM מתקדמים למערכת עברית
All-in-One CRM: Customers, Contracts, Invoices, Tasks, Calendar
"""

from flask import request, jsonify, render_template, redirect, url_for, flash
from app import app, db
from models import Business, CRMCustomer, CRMTask, Customer, CallLog, WhatsAppMessage, WhatsAppConversation
from datetime import datetime, timedelta
import logging
from werkzeug.utils import secure_filename
import os

logger = logging.getLogger(__name__)

@app.route("/crm")
def crm_dashboard():
    """
    דשבורד CRM עם טבלת לקוחות וסינון
    """
    try:
        # For demo, use first business - in production, get from session
        business = Business.query.filter_by(crm_enabled=True).first()
        if not business:
            flash("אין עסק מוגדר עם CRM מופעל", "error")
            return redirect("/")
            
        # Get customers with pagination
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filters
        search = request.args.get('search', '')
        status_filter = request.args.get('status', '')
        source_filter = request.args.get('source', '')
        
        # Build query
        query = CRMCustomer.query.filter_by(business_id=business.id)
        
        if search:
            query = query.filter(
                db.or_(
                    CRMCustomer.name.contains(search),
                    CRMCustomer.phone.contains(search),
                    CRMCustomer.email.contains(search)
                )
            )
            
        if status_filter:
            query = query.filter_by(status=status_filter)
            
        if source_filter:
            query = query.filter_by(source=source_filter)
            
        customers = query.order_by(CRMCustomer.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Statistics
        total_customers = CRMCustomer.query.filter_by(business_id=business.id).count()
        active_customers = CRMCustomer.query.filter_by(business_id=business.id, status='active').count()
        new_this_month = CRMCustomer.query.filter_by(business_id=business.id).filter(
            CRMCustomer.created_at >= datetime.utcnow().replace(day=1)
        ).count()
        
        # Recent tasks
        recent_tasks = CRMTask.query.filter_by(business_id=business.id).order_by(CRMTask.created_at.desc()).limit(5).all()
        
        stats = {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'new_this_month': new_this_month,
            'completion_rate': 85  # Mock for now
        }
        
        return render_template('crm.html',
                             customers=customers,
                             stats=stats,
                             recent_tasks=recent_tasks,
                             business=business,
                             search=search,
                             status_filter=status_filter,
                             source_filter=source_filter)
                             
    except Exception as e:
        logger.error(f"Error loading CRM dashboard: {str(e)}")
        flash("שגיאה בטעינת דשבורד CRM", "error")
        return redirect("/")

@app.route("/crm/customer/<int:customer_id>")
def crm_customer_detail(customer_id):
    """
    דף לקוח מפורט עם כל הפעילות:
    - שיחות מוקלטות
    - הודעות WhatsApp  
    - חוזים וחשבוניות
    - משימות
    """
    try:
        customer = CRMCustomer.query.get_or_404(customer_id)
        
        # Verify business access
        business = Business.query.get(customer.business_id)
        if not business or not business.crm_enabled:
            flash("אין גישה ללקוח זה", "error")
            return redirect("/crm")
            
        # Get all customer activity
        
        # 1. Call logs
        call_logs = CallLog.query.filter_by(
            business_id=business.id,
            from_number=customer.phone
        ).order_by(CallLog.created_at.desc()).all()
        
        # 2. WhatsApp conversations
        whatsapp_conversations = WhatsAppConversation.query.filter_by(
            business_id=business.id,
            customer_phone=customer.phone
        ).all()
        
        # Get WhatsApp messages
        whatsapp_messages = []
        for conv in whatsapp_conversations:
            messages = WhatsAppMessage.query.filter_by(conversation_id=conv.id).order_by(WhatsAppMessage.timestamp.desc()).limit(10).all()
            whatsapp_messages.extend(messages)
            
        # 3. Tasks related to customer
        tasks = CRMTask.query.filter_by(
            business_id=business.id,
            customer_id=customer.id
        ).order_by(CRMTask.due_date.asc()).all()
        
        # 4. Customer timeline (combined activity)
        timeline = []
        
        # Add calls to timeline
        for call in call_logs:
            timeline.append({
                'type': 'call',
                'date': call.created_at,
                'title': f"שיחה - {call.call_duration or 0} שניות",
                'description': call.conversation_summary or "שיחה ללא תיעוד",
                'icon': 'phone',
                'data': call
            })
            
        # Add WhatsApp messages to timeline
        for msg in whatsapp_messages[:10]:  # Last 10 messages
            timeline.append({
                'type': 'whatsapp',
                'date': msg.timestamp,
                'title': f"WhatsApp - {msg.direction}",
                'description': msg.message_text[:100] + "..." if len(msg.message_text) > 100 else msg.message_text,
                'icon': 'message-circle',
                'data': msg
            })
            
        # Add tasks to timeline
        for task in tasks:
            timeline.append({
                'type': 'task',
                'date': task.created_at,
                'title': f"משימה - {task.priority}",
                'description': task.description,
                'icon': 'check-square',
                'data': task
            })
            
        # Sort timeline by date
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        # Customer stats
        customer_stats = {
            'total_calls': len(call_logs),
            'total_messages': len(whatsapp_messages),
            'total_tasks': len(tasks),
            'completion_rate': len([t for t in tasks if t.status == 'completed']) / len(tasks) * 100 if tasks else 0,
            'last_contact': max([call.created_at for call in call_logs] + [msg.timestamp for msg in whatsapp_messages]) if call_logs or whatsapp_messages else None
        }
        
        return render_template('crm_customer.html',
                             customer=customer,
                             business=business,
                             timeline=timeline[:20],  # Last 20 activities
                             stats=customer_stats,
                             call_logs=call_logs,
                             whatsapp_messages=whatsapp_messages[:5],
                             tasks=tasks)
                             
    except Exception as e:
        logger.error(f"Error loading customer detail: {str(e)}")
        flash("שגיאה בטעינת פרטי לקוח", "error")
        return redirect("/crm")

@app.route("/crm/customer/<int:customer_id>/add_task", methods=["POST"])
def add_customer_task(customer_id):
    """הוספת משימה ללקוח"""
    try:
        customer = CRMCustomer.query.get_or_404(customer_id)
        
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        due_date_str = data.get('due_date')
        
        if not title:
            return jsonify({'error': 'כותרת המשימה נדרשת'}), 400
            
        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'תאריך לא תקין'}), 400
                
        # Create task
        task = CRMTask(
            business_id=customer.business_id,
            customer_id=customer.id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            status='pending',
            assigned_to='מערכת'  # In production, use current user
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'המשימה נוספה בהצלחה',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Error adding customer task: {str(e)}")
        return jsonify({'error': 'שגיאה בהוספת המשימה'}), 500

@app.route("/crm/customer/<int:customer_id>/send_message", methods=["POST"])
def send_customer_message(customer_id):
    """שליחת הודעה ללקוח ישירות מה-CRM"""
    try:
        customer = CRMCustomer.query.get_or_404(customer_id)
        
        data = request.get_json()
        message = data.get('message')
        message_type = data.get('type', 'whatsapp')  # whatsapp, sms
        
        if not message:
            return jsonify({'error': 'תוכן ההודעה נדרש'}), 400
            
        if message_type == 'whatsapp':
            # Send via WhatsApp (use existing WhatsApp service)
            # This would integrate with routes_whatsapp.py
            from routes_whatsapp import send_twilio_whatsapp_message
            
            message_id = send_twilio_whatsapp_message(customer.phone, message)
            
            if message_id:
                # Log the message in conversation
                conversation = WhatsAppConversation.query.filter_by(
                    business_id=customer.business_id,
                    customer_phone=customer.phone
                ).first()
                
                if not conversation:
                    conversation = WhatsAppConversation(
                        business_id=customer.business_id,
                        customer_phone=customer.phone,
                        customer_name=customer.name,
                        platform='crm'
                    )
                    db.session.add(conversation)
                    db.session.flush()
                    
                # Save outgoing message
                whatsapp_message = WhatsAppMessage(
                    conversation_id=conversation.id,
                    business_id=customer.business_id,
                    sender_phone=Business.query.get(customer.business_id).whatsapp_number,
                    message_text=message,
                    message_type='text',
                    direction='outgoing',
                    platform='crm',
                    external_id=message_id
                )
                db.session.add(whatsapp_message)
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'הודעה נשלחה בהצלחה',
                    'platform': 'whatsapp'
                })
            else:
                return jsonify({'error': 'שגיאה בשליחת ההודעה'}), 500
                
        elif message_type == 'sms':
            # Send via SMS (use Twilio SMS)
            from twilio_service import TwilioService
            
            twilio = TwilioService()
            message_sid = twilio.send_sms(customer.phone, message)
            
            return jsonify({
                'status': 'success',
                'message': 'SMS נשלח בהצלחה',
                'platform': 'sms',
                'message_id': message_sid
            })
            
        else:
            return jsonify({'error': 'סוג הודעה לא נתמך'}), 400
            
    except Exception as e:
        logger.error(f"Error sending customer message: {str(e)}")
        return jsonify({'error': 'שגיאה בשליחת ההודעה'}), 500

@app.route("/crm/customers/add", methods=["POST"])
def add_customer():
    """הוספת לקוח חדש"""
    try:
        data = request.get_json()
        
        name = data.get('name')
        phone = data.get('phone')
        email = data.get('email', '')
        business_id = data.get('business_id')
        notes = data.get('notes', '')
        
        if not all([name, phone, business_id]):
            return jsonify({'error': 'שם וטלפון נדרשים'}), 400
            
        # Verify business has CRM enabled
        business = Business.query.get(business_id)
        if not business or not business.crm_enabled:
            return jsonify({'error': 'עסק לא מורשה ל-CRM'}), 403
            
        # Check if customer already exists
        existing_customer = CRMCustomer.query.filter_by(
            business_id=business_id,
            phone=phone
        ).first()
        
        if existing_customer:
            return jsonify({'error': 'לקוח עם מספר טלפון זה כבר קיים'}), 400
            
        # Create customer
        customer = CRMCustomer(
            name=name,
            phone=phone,
            email=email,
            business_id=business_id,
            notes=notes,
            status='active',
            source='manual'
        )
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'לקוח נוסף בהצלחה',
            'customer_id': customer.id
        })
        
    except Exception as e:
        logger.error(f"Error adding customer: {str(e)}")
        return jsonify({'error': 'שגיאה בהוספת הלקוח'}), 500

@app.route("/crm/tasks")
def crm_tasks():
    """דף משימות CRM"""
    try:
        business = Business.query.filter_by(crm_enabled=True).first()
        if not business:
            flash("אין עסק מוגדר עם CRM מופעל", "error")
            return redirect("/")
            
        # Get tasks with filters
        status_filter = request.args.get('status', '')
        priority_filter = request.args.get('priority', '')
        assigned_filter = request.args.get('assigned', '')
        
        query = CRMTask.query.filter_by(business_id=business.id)
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        if priority_filter:
            query = query.filter_by(priority=priority_filter)
        if assigned_filter:
            query = query.filter_by(assigned_to=assigned_filter)
            
        tasks = query.order_by(CRMTask.due_date.asc()).all()
        
        # Group tasks by status
        tasks_by_status = {
            'pending': [t for t in tasks if t.status == 'pending'],
            'in_progress': [t for t in tasks if t.status == 'in_progress'],
            'completed': [t for t in tasks if t.status == 'completed']
        }
        
        # Task statistics
        task_stats = {
            'total': len(tasks),
            'pending': len(tasks_by_status['pending']),
            'in_progress': len(tasks_by_status['in_progress']),
            'completed': len(tasks_by_status['completed']),
            'overdue': len([t for t in tasks if t.due_date and t.due_date < datetime.utcnow() and t.status != 'completed'])
        }
        
        return render_template('crm_tasks.html',
                             tasks_by_status=tasks_by_status,
                             task_stats=task_stats,
                             business=business,
                             status_filter=status_filter,
                             priority_filter=priority_filter)
                             
    except Exception as e:
        logger.error(f"Error loading CRM tasks: {str(e)}")
        flash("שגיאה בטעינת משימות", "error")
        return redirect("/crm")

@app.route("/crm/reports")
def crm_reports():
    """דוחות וסטטיסטיקות CRM"""
    try:
        business = Business.query.filter_by(crm_enabled=True).first()
        if not business:
            flash("אין עסק מוגדר עם CRM מופעל", "error")
            return redirect("/")
            
        # Date range for reports
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)  # Last 30 days
        
        # Customer statistics
        total_customers = CRMCustomer.query.filter_by(business_id=business.id).count()
        new_customers_month = CRMCustomer.query.filter_by(business_id=business.id).filter(
            CRMCustomer.created_at >= start_date
        ).count()
        
        # Call statistics
        total_calls = CallLog.query.filter_by(business_id=business.id).count()
        calls_month = CallLog.query.filter_by(business_id=business.id).filter(
            CallLog.created_at >= start_date
        ).count()
        
        # WhatsApp statistics
        total_whatsapp = WhatsAppMessage.query.filter_by(business_id=business.id).count()
        whatsapp_month = WhatsAppMessage.query.filter_by(business_id=business.id).filter(
            WhatsAppMessage.timestamp >= start_date
        ).count()
        
        # Task statistics
        total_tasks = CRMTask.query.filter_by(business_id=business.id).count()
        completed_tasks = CRMTask.query.filter_by(business_id=business.id, status='completed').count()
        
        reports_data = {
            'customers': {
                'total': total_customers,
                'new_month': new_customers_month,
                'growth_rate': (new_customers_month / total_customers * 100) if total_customers > 0 else 0
            },
            'calls': {
                'total': total_calls,
                'month': calls_month,
                'avg_per_day': calls_month / 30 if calls_month > 0 else 0
            },
            'whatsapp': {
                'total': total_whatsapp,
                'month': whatsapp_month,
                'avg_per_day': whatsapp_month / 30 if whatsapp_month > 0 else 0
            },
            'tasks': {
                'total': total_tasks,
                'completed': completed_tasks,
                'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
        }
        
        return render_template('crm_reports.html',
                             reports=reports_data,
                             business=business,
                             date_range={'start': start_date, 'end': end_date})
                             
    except Exception as e:
        logger.error(f"Error generating CRM reports: {str(e)}")
        flash("שגיאה בהפקת דוחות", "error")
        return redirect("/crm")

# API endpoints for AJAX requests
@app.route("/api/crm/customer/<int:customer_id>/status", methods=["PUT"])
def update_customer_status(customer_id):
    """עדכון סטטוס לקוח"""
    try:
        customer = CRMCustomer.query.get_or_404(customer_id)
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['active', 'inactive', 'prospect']:
            return jsonify({'error': 'סטטוס לא תקין'}), 400
            
        customer.status = new_status
        customer.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'סטטוס עודכן בהצלחה'})
        
    except Exception as e:
        logger.error(f"Error updating customer status: {str(e)}")
        return jsonify({'error': 'שגיאה בעדכון הסטטוס'}), 500

@app.route("/api/crm/task/<int:task_id>/status", methods=["PUT"])
def update_task_status(task_id):
    """עדכון סטטוס משימה"""
    try:
        task = CRMTask.query.get_or_404(task_id)
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['pending', 'in_progress', 'completed']:
            return jsonify({'error': 'סטטוס לא תקין'}), 400
            
        task.status = new_status
        task.updated_at = datetime.utcnow()
        
        if new_status == 'completed':
            task.completed_at = datetime.utcnow()
            
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'סטטוס המשימה עודכן בהצלחה'})
        
    except Exception as e:
        logger.error(f"Error updating task status: {str(e)}")
        return jsonify({'error': 'שגיאה בעדכון סטטוס המשימה'}), 500