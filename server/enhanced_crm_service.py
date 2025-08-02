"""
Enhanced CRM Service with Advanced Customer Management
שירות CRM מתקדם עם ניהול לקוחות ברמה מקצועית
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app import db
from models import Business, CRMCustomer, CRMTask

logger = logging.getLogger(__name__)

class EnhancedCRMService:
    """שירות CRM מתקדם עם פונקציונליות מלאה"""
    
    @staticmethod
    def create_customer_from_interaction(business_id: int, phone_number: str, 
                                       source: str, interaction_data: Dict) -> Optional[CRMCustomer]:
        """יצירת לקוח חדש מאינטראקציה (שיחה או WhatsApp)"""
        
        try:
            # בדיקת לקוח קיים
            existing_customer = CRMCustomer.query.filter_by(
                business_id=business_id,
                phone=phone_number
            ).first()
            
            if existing_customer:
                # עדכון לקוח קיים
                existing_customer.last_interaction = datetime.utcnow()
                existing_customer.source = source  # עדכון מקור אחרון
                db.session.commit()
                return existing_customer
            
            # יצירת לקוח חדש - Agent task #3 with proper source recording
            customer_name = interaction_data.get('extracted_name', f"לקוח {phone_number[-4:]}")
            
            new_customer = CRMCustomer(
                business_id=business_id,
                name=customer_name,
                phone=phone_number,
                source=source,  # Ensure source is recorded as "call" or "whatsapp"
                status='active',  # Start as active customer  
                notes=f"נוצר אוטומטית מ-{source} ב-{datetime.now().strftime('%d/%m/%Y %H:%M')}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(new_customer)
            db.session.commit()
            
            logger.info(f"Created new customer from {source}: {customer_name}")
            
            # יצירת משימת מעקב אוטומטית
            EnhancedCRMService.create_follow_up_task(
                business_id=business_id,
                customer_id=new_customer.id,
                source=source
            )
            
            return new_customer
            
        except Exception as e:
            logger.error(f"Error creating customer from interaction: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def create_follow_up_task(business_id: int, customer_id: int, 
                            source: str, priority: str = 'medium') -> Optional[CRMTask]:
        """יצירת משימת מעקב אוטומטית"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return None
            
            task_title = f"מעקב אחר לקוח חדש - {customer.name}"
            task_description = f"לקוח יצר קשר דרך {source}. יש לערוך מעקב תוך 24 שעות."
            
            follow_up_task = CRMTask(
                business_id=business_id,
                customer_id=customer_id,
                title=task_title,
                description=task_description,
                priority=priority,
                status='pending',
                due_date=datetime.now() + timedelta(hours=24),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(follow_up_task)
            db.session.commit()
            
            logger.info(f"Created follow-up task for customer {customer_id}")
            return follow_up_task
            
        except Exception as e:
            logger.error(f"Error creating follow-up task: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def update_customer_from_conversation(customer_id: int, 
                                        conversation_data: Dict) -> bool:
        """עדכון לקוח מתוך נתוני שיחה"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return False
            
            # עדכון מידע מהשיחה
            intent = conversation_data.get('intent', '')
            ai_response = conversation_data.get('ai_response', '')
            
            # עדכון סטטוס לקוח לפי intent
            if intent == 'appointment_request':
                customer.status = 'active'  # לקוח שמבקש תור הופך לפעיל
                
                # יצירת משימת קבלת תור
                appointment_task = CRMTask(
                    business_id=customer.business_id,
                    customer_id=customer.id,
                    title=f"קביעת תור ללקוח {customer.name}",
                    description=f"הלקוח ביקש לקבוע תור. פרטי השיחה: {ai_response[:200]}...",
                    priority='high',
                    status='pending',
                    due_date=datetime.now() + timedelta(hours=4),
                    created_at=datetime.utcnow()
                )
                db.session.add(appointment_task)
                
            elif intent == 'complaint':
                customer.status = 'active'
                # יצירת משימת טיפול בתלונה
                complaint_task = CRMTask(
                    business_id=customer.business_id,
                    customer_id=customer.id,
                    title=f"טיפול בתלונה - {customer.name}",
                    description=f"הלקוח הביע תלונה. דרוש טיפול דחוף. פרטים: {ai_response[:200]}...",
                    priority='urgent',
                    status='pending',
                    due_date=datetime.now() + timedelta(hours=2),
                    created_at=datetime.utcnow()
                )
                db.session.add(complaint_task)
            
            # עדכון זמן אינטראקציה אחרון
# Update interaction time if field exists
            customer.updated_at = datetime.utcnow()
            
            # הוספת הערה לשיחה - Agent task #3 use valid JSON not plain text
            current_notes = customer.notes or ""
            
            import json
            interaction_log = {
                "timestamp": datetime.now().isoformat(),
                "type": "conversation",
                "source": conversation_data.get('source', 'unknown'),
                "intent": intent,
                "ai_response_summary": ai_response[:150],
                "channel": conversation_data.get('channel', 'phone')
            }
            
            conversation_note = f"\n[INTERACTION] {json.dumps(interaction_log, ensure_ascii=False)}"
            customer.notes = current_notes + conversation_note
            
            db.session.commit()
            
            logger.info(f"Updated customer {customer_id} from conversation")
            return True
            
        except Exception as e:
            logger.error(f"Error updating customer from conversation: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def tag_customer(customer_id: int, tags: List[str]) -> bool:
        """תיוג לקוח"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return False
            
            # שמירת תגיות בהערות (או שדה נפרד אם נוסיף)
            current_notes = customer.notes or ""
            tags_string = ", ".join(tags)
            tag_note = f"\n[תגיות] {tags_string}"
            
            customer.notes = current_notes + tag_note
            customer.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"Tagged customer {customer_id} with: {tags_string}")
            return True
            
        except Exception as e:
            logger.error(f"Error tagging customer: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_customers_with_filters(business_id: int, date_from: str = None, 
                                 phone_filter: str = None, source_filter: str = None) -> List[CRMCustomer]:
        """חיפוש לקוחות עם פילטרים - Agent task #3"""
        
        try:
            query = CRMCustomer.query.filter_by(business_id=business_id)
            
            # פילטר תאריך
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, '%Y-%m-%d')
                    query = query.filter(CRMCustomer.created_at >= from_date)
                except ValueError:
                    logger.warning(f"Invalid date format: {date_from}")
            
            # פילטר טלפון
            if phone_filter:
                query = query.filter(CRMCustomer.phone.contains(phone_filter))
            
            # פילטר מקור
            if source_filter and source_filter != 'all':
                query = query.filter(CRMCustomer.source == source_filter)
            
            customers = query.order_by(CRMCustomer.created_at.desc()).all()
            
            logger.info(f"Found {len(customers)} customers with filters")
            return customers
            
        except Exception as e:
            logger.error(f"Error filtering customers: {e}")
            return []
    
    @staticmethod 
    def update_customer_status(customer_id: int, new_status: str) -> bool:
        """עדכון סטטוס לקוח - Agent task #3 support active/inactive/blocked"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return False
            
            valid_statuses = ['active', 'inactive', 'blocked', 'prospect', 'lead']
            if new_status not in valid_statuses:
                logger.error(f"Invalid status: {new_status}")
                return False
            
            old_status = customer.status
            customer.status = new_status
            customer.updated_at = datetime.utcnow()
            
            # Add status change log
            status_change = {
                "timestamp": datetime.now().isoformat(),
                "type": "status_change",
                "old_status": old_status,
                "new_status": new_status
            }
            
            import json
            status_note = f"\n[STATUS_CHANGE] {json.dumps(status_change, ensure_ascii=False)}"
            customer.notes = (customer.notes or "") + status_note
            
            db.session.commit()
            
            logger.info(f"Updated customer {customer_id} status: {old_status} -> {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating customer status: {e}")  
            db.session.rollback()
            return False
    
    @staticmethod
    def get_customer_analytics(business_id: int, days: int = 30) -> Dict[str, Any]:
        """אנליטיקת לקוחות מתקדמת"""
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # סטטיסטיקות בסיסיות
            total_customers = CRMCustomer.query.filter_by(business_id=business_id).count()
            
            new_customers = CRMCustomer.query.filter(
                CRMCustomer.business_id == business_id,
                CRMCustomer.created_at >= cutoff_date
            ).count()
            
            active_customers = CRMCustomer.query.filter_by(
                business_id=business_id,
                status='active'
            ).count()
            
            prospects = CRMCustomer.query.filter_by(
                business_id=business_id,
                status='prospect'
            ).count()
            
            # התפלגות לפי מקור
            source_distribution = {}
            sources = db.session.query(CRMCustomer.source).filter_by(
                business_id=business_id
            ).distinct().all()
            
            for source_tuple in sources:
                source = source_tuple[0] or 'unknown'
                count = CRMCustomer.query.filter_by(
                    business_id=business_id,
                    source=source
                ).count()
                source_distribution[source] = count
            
            # משימות פתוחות
            open_tasks = CRMTask.query.filter(
                CRMTask.business_id == business_id,
                CRMTask.status.in_(['pending', 'in_progress'])
            ).count()
            
            # אנליטיקה מתקדמת
            return {
                'total_customers': total_customers,
                'new_customers': new_customers,
                'active_customers': active_customers,
                'prospects': prospects,
                'source_distribution': source_distribution,
                'open_tasks': open_tasks,
                'period_days': days,
                'conversion_rate': round((active_customers / max(total_customers, 1)) * 100, 1) if total_customers > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting customer analytics: {e}")
            return {
                'total_customers': 0,
                'new_customers': 0,
                'active_customers': 0,
                'prospects': 0,
                'source_distribution': {},
                'open_tasks': 0,
                'period_days': days,
                'conversion_rate': 0
            }


# יצירת instance גלובלי - Agent task #3 ready for use
enhanced_crm_service = EnhancedCRMService()
            ).distinct().all()
            
            for source in sources:
                if source[0]:
                    count = CRMCustomer.query.filter_by(
                        business_id=business_id,
                        source=source[0]
                    ).count()
                    source_distribution[source[0]] = count
            
            # לקוחות פעילים לפי יום
            daily_activity = {}
            for i in range(7):
                date = datetime.now().date() - timedelta(days=i)
                activity_count = CRMCustomer.query.filter(
                    CRMCustomer.business_id == business_id,
                    CRMCustomer.last_interaction >= date,
                    CRMCustomer.last_interaction < date + timedelta(days=1)
                ).count()
                
                daily_activity[date.strftime('%d/%m')] = activity_count
            
            # לקוחות שלא התפעלו זמן רב
            inactive_customers = CRMCustomer.query.filter(
                CRMCustomer.business_id == business_id,
                or_(
                    # last_interaction check if field exists
                    CRMCustomer.updated_at < datetime.now() - timedelta(days=30)
                )
            ).count()
            
            return {
                'total_customers': total_customers,
                'new_customers': new_customers,
                'active_customers': active_customers,
                'prospects': prospects,
                'inactive_customers': inactive_customers,
                'conversion_rate': (active_customers / total_customers * 100) if total_customers > 0 else 0,
                'source_distribution': source_distribution,
                'daily_activity': daily_activity,
                'growth_rate': (new_customers / (total_customers or 1)) * 100
            }
            
        except Exception as e:
            logger.error(f"Error getting customer analytics: {e}")
            return {}
    
    @staticmethod
    def get_customer_lifecycle(customer_id: int) -> List[Dict[str, Any]]:
        """מחזור חיי לקוח מפורט"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return []
            
            lifecycle = []
            
            # יצירת לקוח
            lifecycle.append({
                'date': customer.created_at,
                'event': 'יצירת לקוח',
                'details': f"נוצר דרך {customer.source}",
                'type': 'creation'
            })
            
            # משימות קשורות
            tasks = CRMTask.query.filter_by(customer_id=customer_id).order_by(
                CRMTask.created_at.asc()
            ).all()
            
            for task in tasks:
                lifecycle.append({
                    'date': task.created_at,
                    'event': 'משימה נוצרה',
                    'details': task.title,
                    'type': 'task_created',
                    'priority': task.priority
                })
                
                if task.completed_at:
                    lifecycle.append({
                        'date': task.completed_at,
                        'event': 'משימה הושלמה',
                        'details': task.title,
                        'type': 'task_completed'
                    })
            
            # אינטראקציה אחרונה
            if customer.last_interaction:
                lifecycle.append({
                    'date': customer.last_interaction,
                    'event': 'אינטראקציה אחרונה',
                    'details': 'פעילות אחרונה של הלקוח',
                    'type': 'interaction'
                })
            
            # מיון לפי תאריך
            lifecycle.sort(key=lambda x: x['date'])
            
            return lifecycle
            
        except Exception as e:
            logger.error(f"Error getting customer lifecycle: {e}")
            return []
    
    @staticmethod
    def get_hot_leads(business_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """קבלת לידים חמים (מתעניינים אחרונים)"""
        
        try:
            # לקוחות שיצרו קשר ב-48 שעות האחרונות
            hot_leads = CRMCustomer.query.filter(
                CRMCustomer.business_id == business_id,
                CRMCustomer.status == 'prospect',
                CRMCustomer.updated_at >= datetime.now() - timedelta(hours=48)
            ).order_by(CRMCustomer.updated_at.desc()).limit(limit).all()
            
            leads_data = []
            for lead in hot_leads:
                # חיפוש משימות פתוחות
                open_tasks = CRMTask.query.filter_by(
                    customer_id=lead.id,
                    status='pending'
                ).count()
                
                # חישוב זמן מאז אינטראקציה אחרונה
                time_since_contact = datetime.now() - (lead.updated_at or lead.created_at)
                hours_since = int(time_since_contact.total_seconds() / 3600)
                
                leads_data.append({
                    'id': lead.id,
                    'name': lead.name,
                    'phone': lead.phone,
                    'source': lead.source,
                    'hours_since_contact': hours_since,
                    'open_tasks': open_tasks,
                    'urgency_score': max(0, 48 - hours_since) + (open_tasks * 10)
                })
            
            # מיון לפי ציון דחיפות
            leads_data.sort(key=lambda x: x['urgency_score'], reverse=True)
            
            return leads_data
            
        except Exception as e:
            logger.error(f"Error getting hot leads: {e}")
            return []
    
    @staticmethod
    def mark_customer(customer_id: int, marked: bool = True) -> bool:
        """סימון לקוח חשוב"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return False
            
            # שמירת הסימון בהערות
            current_notes = customer.notes or ""
            
            if marked:
                if "[מסומן]" not in current_notes:
                    customer.notes = f"[מסומן] {current_notes}"
            else:
                customer.notes = current_notes.replace("[מסומן]", "").strip()
            
            customer.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Customer {customer_id} marked: {marked}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking customer: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def export_customers_data(business_id: int, format: str = 'csv') -> Optional[str]:
        """ייצוא נתוני לקוחות"""
        
        try:
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            
            if format == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # כותרות
                writer.writerow([
                    'שם', 'טלפון', 'אימייל', 'סטטוס', 'מקור', 
                    'תאריך יצירה', 'אינטראקציה אחרונה', 'הערות'
                ])
                
                # נתונים
                for customer in customers:
                    writer.writerow([
                        customer.name,
                        customer.phone,
                        customer.email or '',
                        customer.status,
                        customer.source,
                        customer.created_at.strftime('%d/%m/%Y') if customer.created_at else '',
                        customer.last_interaction.strftime('%d/%m/%Y') if customer.last_interaction else '',
                        customer.notes or ''
                    ])
                
                return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting customers data: {e}")
            return None

# יצירת instance גלובלי
enhanced_crm_service = EnhancedCRMService()