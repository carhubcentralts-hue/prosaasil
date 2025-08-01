"""
CRM Service - שירותי CRM מתקדמים
שירותים מרכזיים לניהול לקוחות, אינטראקציות ומעקב
"""

from app import db
from crm_models import Customer, CustomerInteraction, Task, BusinessSettings, CRMAnalytics
from models import Business, CallLog, ConversationTurn, WhatsAppMessage
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_
import logging
import json

logger = logging.getLogger(__name__)

class CRMService:
    """שירות CRM מרכזי"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    # === ניהול לקוחות ===
    
    def get_or_create_customer(self, business_id, phone_number, **kwargs):
        """קבלת לקוח קיים או יצירת חדש"""
        try:
            # נסה למצוא לקוח קיים
            customer = Customer.query.filter_by(
                business_id=business_id,
                phone_number=phone_number
            ).first()
            
            if customer:
                # עדכן נתונים אם סופקו
                updated = False
                for key, value in kwargs.items():
                    if hasattr(customer, key) and value:
                        setattr(customer, key, value)
                        updated = True
                
                if updated:
                    customer.updated_at = datetime.utcnow()
                    db.session.commit()
                
                self.logger.info(f"✅ Found existing customer {customer.id} for {phone_number}")
                return customer
            
            # צור לקוח חדש
            customer_data = {
                'business_id': business_id,
                'phone_number': phone_number,
                'source': kwargs.get('source', 'unknown'),
                'status': 'lead',
                **kwargs
            }
            
            customer = Customer(**customer_data)
            db.session.add(customer)
            db.session.commit()
            
            self.logger.info(f"✅ Created new customer {customer.id} for {phone_number}")
            return customer
            
        except Exception as e:
            self.logger.error(f"❌ Error managing customer {phone_number}: {e}")
            db.session.rollback()
            return None
    
    def update_customer(self, customer_id, updates):
        """עדכון פרטי לקוח"""
        try:
            customer = Customer.query.get(customer_id)
            if not customer:
                return False
            
            for key, value in updates.items():
                if hasattr(customer, key):
                    setattr(customer, key, value)
            
            customer.updated_at = datetime.utcnow()
            db.session.commit()
            
            self.logger.info(f"✅ Updated customer {customer_id}: {list(updates.keys())}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error updating customer {customer_id}: {e}")
            db.session.rollback()
            return False
    
    def get_customer_stats(self, business_id, customer_id):
        """סטטיסטיקות לקוח"""
        try:
            customer = Customer.query.filter_by(
                id=customer_id, 
                business_id=business_id
            ).first()
            
            if not customer:
                return None
            
            # סטטיסטיקות אינטראקציות
            interactions = CustomerInteraction.query.filter_by(customer_id=customer_id)
            total_interactions = interactions.count()
            
            calls_count = interactions.filter_by(interaction_type='call').count()
            whatsapp_count = interactions.filter_by(interaction_type='whatsapp').count()
            
            # אינטראקציה אחרונה
            last_interaction = interactions.order_by(desc(CustomerInteraction.interaction_date)).first()
            
            # משימות פעילות
            active_tasks = Task.query.filter_by(
                customer_id=customer_id,
                status='pending'
            ).count()
            
            return {
                'customer': customer,
                'total_interactions': total_interactions,
                'calls_count': calls_count,
                'whatsapp_count': whatsapp_count,
                'last_interaction_date': last_interaction.interaction_date if last_interaction else None,
                'active_tasks': active_tasks,
                'days_since_last_contact': (datetime.utcnow() - last_interaction.interaction_date).days if last_interaction else 0
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting customer stats {customer_id}: {e}")
            return None
    
    # === ניהול אינטראקציות ===
    
    def log_interaction(self, customer_id, business_id, interaction_type, **kwargs):
        """רישום אינטראקציה חדשה"""
        try:
            interaction = CustomerInteraction(
                customer_id=customer_id,
                business_id=business_id,
                interaction_type=interaction_type,
                **kwargs
            )
            
            db.session.add(interaction)
            
            # עדכן זמן אינטראקציה אחרונה של הלקוח
            customer = Customer.query.get(customer_id)
            if customer:
                customer.last_contact_at = datetime.utcnow()
                customer.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            self.logger.info(f"✅ Logged {interaction_type} interaction for customer {customer_id}")
            return interaction
            
        except Exception as e:
            self.logger.error(f"❌ Error logging interaction: {e}")
            db.session.rollback()
            return None
    
    def link_call_to_customer(self, call_sid, customer_id):
        """קישור שיחה קיימת ללקוח"""
        try:
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                return False
            
            # צור אינטראקציה מהשיחה
            conversation_turns = ConversationTurn.query.filter_by(call_sid=call_sid).all()
            content = "\n".join([f"{turn.speaker}: {turn.message}" for turn in conversation_turns])
            
            interaction = self.log_interaction(
                customer_id=customer_id,
                business_id=call_log.business_id,
                interaction_type='call',
                direction='inbound',
                content=content,
                call_sid=call_sid,
                duration=call_log.call_duration,
                status='completed',
                interaction_date=call_log.created_at
            )
            
            return interaction is not None
            
        except Exception as e:
            self.logger.error(f"❌ Error linking call {call_sid} to customer {customer_id}: {e}")
            return False
    
    def link_whatsapp_to_customer(self, message_sid, customer_id):
        """קישור הודעת WhatsApp ללקוח"""
        try:
            whatsapp_msg = WhatsAppMessage.query.filter_by(message_sid=message_sid).first()
            if not whatsapp_msg:
                return False
            
            interaction = self.log_interaction(
                customer_id=customer_id,
                business_id=whatsapp_msg.business_id,
                interaction_type='whatsapp',
                direction=whatsapp_msg.direction,
                content=whatsapp_msg.message_body,
                message_sid=message_sid,
                status='completed',
                interaction_date=whatsapp_msg.created_at
            )
            
            return interaction is not None
            
        except Exception as e:
            self.logger.error(f"❌ Error linking WhatsApp {message_sid} to customer {customer_id}: {e}")
            return False
    
    # === ניהול משימות ===
    
    def create_task(self, business_id, title, **kwargs):
        """יצירת משימה חדשה"""
        try:
            task = Task(
                business_id=business_id,
                title=title,
                **kwargs
            )
            
            db.session.add(task)
            db.session.commit()
            
            self.logger.info(f"✅ Created task: {title}")
            return task
            
        except Exception as e:
            self.logger.error(f"❌ Error creating task: {e}")
            db.session.rollback()
            return None
    
    def get_business_tasks(self, business_id, status=None, limit=50):
        """קבלת משימות עסק"""
        try:
            query = Task.query.filter_by(business_id=business_id)
            
            if status:
                query = query.filter_by(status=status)
            
            tasks = query.order_by(desc(Task.created_at)).limit(limit).all()
            return tasks
            
        except Exception as e:
            self.logger.error(f"❌ Error getting business tasks: {e}")
            return []
    
    def complete_task(self, task_id):
        """סיום משימה"""
        try:
            task = Task.query.get(task_id)
            if not task:
                return False
            
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
            self.logger.info(f"✅ Completed task {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error completing task {task_id}: {e}")
            db.session.rollback()
            return False
    
    # === אנליטיקה ודוחות ===
    
    def get_business_analytics(self, business_id, days=30):
        """אנליטיקה עסקית"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # לקוחות
            total_customers = Customer.query.filter_by(business_id=business_id).count()
            new_customers = Customer.query.filter(
                Customer.business_id == business_id,
                Customer.created_at >= start_date
            ).count()
            
            # אינטראקציות
            interactions = CustomerInteraction.query.filter(
                CustomerInteraction.business_id == business_id,
                CustomerInteraction.interaction_date >= start_date
            )
            
            total_interactions = interactions.count()
            calls_count = interactions.filter_by(interaction_type='call').count()
            whatsapp_count = interactions.filter_by(interaction_type='whatsapp').count()
            
            # משימות
            total_tasks = Task.query.filter_by(business_id=business_id).count()
            pending_tasks = Task.query.filter_by(
                business_id=business_id,
                status='pending'
            ).count()
            
            completed_tasks = Task.query.filter(
                Task.business_id == business_id,
                Task.status == 'completed',
                Task.completed_at >= start_date
            ).count()
            
            # חישוב שעת תגובה ממוצעת
            avg_response_time = self._calculate_avg_response_time(business_id, start_date)
            
            return {
                'period_days': days,
                'total_customers': total_customers,
                'new_customers': new_customers,
                'total_interactions': total_interactions,
                'calls_count': calls_count,
                'whatsapp_count': whatsapp_count,
                'total_tasks': total_tasks,
                'pending_tasks': pending_tasks,
                'completed_tasks': completed_tasks,
                'avg_response_time_minutes': avg_response_time,
                'conversion_rate': (new_customers / max(total_interactions, 1)) * 100 if total_interactions > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting analytics for business {business_id}: {e}")
            return {}
    
    def _calculate_avg_response_time(self, business_id, start_date):
        """חישוב זמן תגובה ממוצע"""
        try:
            # קבל אינטראקציות נכנסות וחזרות
            inbound_interactions = CustomerInteraction.query.filter(
                CustomerInteraction.business_id == business_id,
                CustomerInteraction.direction == 'inbound',
                CustomerInteraction.interaction_date >= start_date
            ).all()
            
            response_times = []
            
            for interaction in inbound_interactions:
                # חפש תגובה בעוד 10 דקות
                response_window = interaction.interaction_date + timedelta(minutes=10)
                
                response = CustomerInteraction.query.filter(
                    CustomerInteraction.customer_id == interaction.customer_id,
                    CustomerInteraction.direction == 'outbound',
                    CustomerInteraction.interaction_date > interaction.interaction_date,
                    CustomerInteraction.interaction_date <= response_window
                ).first()
                
                if response:
                    response_time = (response.interaction_date - interaction.interaction_date).total_seconds() / 60
                    response_times.append(response_time)
            
            return sum(response_times) / len(response_times) if response_times else 0
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating response time: {e}")
            return 0
    
    def generate_daily_analytics(self, business_id, date=None):
        """יצירת אנליטיקה יומית"""
        try:
            if not date:
                date = datetime.utcnow().date()
            
            # בדיקה אם כבר קיים
            existing = CRMAnalytics.query.filter_by(
                business_id=business_id,
                date=date
            ).first()
            
            if existing:
                return existing
            
            # חישוב מדדים יומיים
            start_datetime = datetime.combine(date, datetime.min.time())
            end_datetime = start_datetime + timedelta(days=1)
            
            analytics = CRMAnalytics(
                business_id=business_id,
                date=start_datetime,
                total_customers=Customer.query.filter_by(business_id=business_id).count(),
                new_customers=Customer.query.filter(
                    Customer.business_id == business_id,
                    Customer.created_at >= start_datetime,
                    Customer.created_at < end_datetime
                ).count(),
                total_interactions=CustomerInteraction.query.filter(
                    CustomerInteraction.business_id == business_id,
                    CustomerInteraction.interaction_date >= start_datetime,
                    CustomerInteraction.interaction_date < end_datetime
                ).count(),
                tasks_created=Task.query.filter(
                    Task.business_id == business_id,
                    Task.created_at >= start_datetime,
                    Task.created_at < end_datetime
                ).count(),
                tasks_completed=Task.query.filter(
                    Task.business_id == business_id,
                    Task.completed_at >= start_datetime,
                    Task.completed_at < end_datetime
                ).count()
            )
            
            db.session.add(analytics)
            db.session.commit()
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"❌ Error generating daily analytics: {e}")
            db.session.rollback()
            return None
    
    # === חיפוש ומיון ===
    
    def search_customers(self, business_id, query, limit=20):
        """חיפוש לקוחות"""
        try:
            customers = Customer.query.filter(
                Customer.business_id == business_id,
                db.or_(
                    Customer.full_name.ilike(f'%{query}%'),
                    Customer.first_name.ilike(f'%{query}%'),
                    Customer.last_name.ilike(f'%{query}%'),
                    Customer.phone_number.ilike(f'%{query}%'),
                    Customer.email.ilike(f'%{query}%')
                )
            ).limit(limit).all()
            
            return customers
            
        except Exception as e:
            self.logger.error(f"❌ Error searching customers: {e}")
            return []
    
    def get_customer_timeline(self, customer_id, limit=50):
        """ציר זמן של לקוח"""
        try:
            interactions = CustomerInteraction.query.filter_by(
                customer_id=customer_id
            ).order_by(desc(CustomerInteraction.interaction_date)).limit(limit).all()
            
            tasks = Task.query.filter_by(
                customer_id=customer_id
            ).order_by(desc(Task.created_at)).limit(10).all()
            
            # מיזוג וסידור לפי זמן
            timeline = []
            
            for interaction in interactions:
                timeline.append({
                    'type': 'interaction',
                    'date': interaction.interaction_date,
                    'data': interaction
                })
            
            for task in tasks:
                timeline.append({
                    'type': 'task',
                    'date': task.created_at,
                    'data': task
                })
            
            timeline.sort(key=lambda x: x['date'], reverse=True)
            return timeline[:limit]
            
        except Exception as e:
            self.logger.error(f"❌ Error getting customer timeline: {e}")
            return []
    
    # === ייצוא נתונים ===
    
    def export_customers_csv(self, business_id):
        """ייצוא לקוחות לCSV"""
        try:
            import csv
            import io
            
            customers = Customer.query.filter_by(business_id=business_id).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # כותרות
            writer.writerow(['ID', 'שם מלא', 'טלפון', 'WhatsApp', 'אימייל', 'סטטוס', 'מקור', 'תאריך יצירה'])
            
            # נתונים
            for customer in customers:
                writer.writerow([
                    customer.id,
                    customer.display_name,
                    customer.phone_number,
                    customer.whatsapp_number or '',
                    customer.email or '',
                    customer.status,
                    customer.source or '',
                    customer.created_at.strftime('%Y-%m-%d %H:%M')
                ])
            
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(f"❌ Error exporting customers CSV: {e}")
            return None

# === פונקציות עזר גלובליות ===

def record_interaction(customer_id, interaction_type, direction='inbound', content='', ai_response='', call_sid=None, **kwargs):
    """רישום אינטראקציה עם לקוח ב-CRM - פונקציה גלובלית להשימוש מmodules אחרים"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            logger.error(f"❌ Customer {customer_id} not found")
            return None
            
        interaction = CustomerInteraction(
            customer_id=customer_id,
            business_id=customer.business_id,
            interaction_type=interaction_type,
            direction=direction,
            content=content,
            ai_response=ai_response,
            call_sid=call_sid,
            interaction_date=datetime.utcnow(),
            status='completed',
            metadata=json.dumps(kwargs) if kwargs else None
        )
        
        db.session.add(interaction)
        db.session.commit()
        
        logger.info(f"✅ Recorded {interaction_type} interaction for customer {customer_id}")
        return interaction
        
    except Exception as e:
        logger.error(f"❌ Failed to record interaction: {e}")
        db.session.rollback()
        return None