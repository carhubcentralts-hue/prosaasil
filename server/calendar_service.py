"""
Calendar Service - שירות לוח שנה ופגישות
ניהול תורים, פגישות, והתראות מתקדם
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, time
from app import db
from models import CRMCustomer, Business, CRMTask

logger = logging.getLogger(__name__)

# מודל פגישה (להוסיף למסד הנתונים)
class Appointment(db.Model):
    """מודל פגישות"""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('crm_customer.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    note = db.Column(db.Text)
    status = db.Column(db.String(50), default='scheduled')  # scheduled, confirmed, completed, cancelled
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # יחסים
    customer = db.relationship('CRMCustomer', backref='appointments')
    business = db.relationship('Business', backref='appointments')

class CalendarService:
    """שירות לוח שנה מתקדם"""
    
    @staticmethod
    def schedule_appointment(customer_id: int, business_id: int, 
                           appointment_date: datetime, duration: int = 60,
                           note: str = '') -> Dict[str, Any]:
        """קביעת פגישה חדשה"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            business = Business.query.get(business_id)
            
            if not customer or not business:
                return {'success': False, 'error': 'לקוח או עסק לא נמצאו'}
            
            # בדיקת עסק תואם
            if customer.business_id != business_id:
                return {'success': False, 'error': 'לקוח לא שייך לעסק זה'}
            
            # בדיקת זמן פנוי
            conflict_check = CalendarService._check_time_conflict(
                business_id, appointment_date, duration
            )
            
            if not conflict_check['available']:
                return {
                    'success': False, 
                    'error': f'הזמן לא פנוי. פגישה קיימת: {conflict_check["conflict_time"]}'
                }
            
            # יצירת פגישה
            appointment = Appointment(
                customer_id=customer_id,
                business_id=business_id,
                appointment_date=appointment_date,
                duration_minutes=duration,
                note=note,
                status='scheduled'
            )
            
            db.session.add(appointment)
            
            # יצירת משימת תזכורת
            reminder_task = CRMTask(
                business_id=business_id,
                customer_id=customer_id,
                title=f"פגישה עם {customer.name}",
                description=f"פגישה מתוכננת ב-{appointment_date.strftime('%d/%m/%Y %H:%M')}. {note}",
                priority='high',
                status='pending',
                due_date=appointment_date.date(),
                created_at=datetime.utcnow()
            )
            
            db.session.add(reminder_task)
            db.session.commit()
            
            logger.info(f"Scheduled appointment for customer {customer_id} on {appointment_date}")
            
            return {
                'success': True,
                'appointment_id': appointment.id,
                'message': f'פגישה נקבעה ל-{appointment_date.strftime("%d/%m/%Y בשעה %H:%M")}',
                'customer_name': customer.name,
                'appointment_date': appointment_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scheduling appointment: {e}")
            db.session.rollback()
            return {'success': False, 'error': 'שגיאה בקביעת הפגישה'}
    
    @staticmethod
    def _check_time_conflict(business_id: int, appointment_date: datetime, 
                           duration: int) -> Dict[str, Any]:
        """בדיקת התנגשות זמנים"""
        
        try:
            start_time = appointment_date
            end_time = start_time + timedelta(minutes=duration)
            
            # חיפוש פגישות חופפות
            conflicts = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.status.in_(['scheduled', 'confirmed']),
                Appointment.appointment_date < end_time,
                db.func.datetime(
                    Appointment.appointment_date, 
                    f'+{Appointment.duration_minutes} minutes'
                ) > start_time
            ).all()
            
            if conflicts:
                conflict = conflicts[0]
                conflict_time = conflict.appointment_date.strftime('%d/%m/%Y %H:%M')
                return {
                    'available': False,
                    'conflict_time': conflict_time,
                    'conflict_customer': conflict.customer.name if conflict.customer else 'לא ידוע'
                }
            
            return {'available': True}
            
        except Exception as e:
            logger.error(f"Error checking time conflict: {e}")
            return {'available': False, 'error': 'שגיאה בבדיקת זמנים'}
    
    @staticmethod
    def get_business_calendar(business_id: int, start_date: datetime, 
                            end_date: datetime) -> List[Dict[str, Any]]:
        """קבלת לוח שנה לעסק"""
        
        try:
            appointments = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.appointment_date >= start_date,
                Appointment.appointment_date <= end_date
            ).order_by(Appointment.appointment_date.asc()).all()
            
            calendar_events = []
            
            for appointment in appointments:
                event = {
                    'id': appointment.id,
                    'title': f'{appointment.customer.name}' if appointment.customer else 'לקוח לא ידוע',
                    'start': appointment.appointment_date.isoformat(),
                    'end': (appointment.appointment_date + timedelta(
                        minutes=appointment.duration_minutes
                    )).isoformat(),
                    'description': appointment.note or '',
                    'status': appointment.status,
                    'customer_phone': appointment.customer.phone if appointment.customer else '',
                    'backgroundColor': CalendarService._get_status_color(appointment.status)
                }
                
                calendar_events.append(event)
            
            return calendar_events
            
        except Exception as e:
            logger.error(f"Error getting business calendar: {e}")
            return []
    
    @staticmethod
    def _get_status_color(status: str) -> str:
        """צבע לפי סטטוס פגישה"""
        
        colors = {
            'scheduled': '#007bff',  # כחול
            'confirmed': '#28a745',  # ירוק
            'completed': '#6c757d',  # אפור
            'cancelled': '#dc3545'   # אדום
        }
        
        return colors.get(status, '#007bff')
    
    @staticmethod
    def update_appointment_status(appointment_id: int, new_status: str, 
                                business_id: int) -> Dict[str, Any]:
        """עדכון סטטוס פגישה"""
        
        try:
            appointment = Appointment.query.get(appointment_id)
            
            if not appointment or appointment.business_id != business_id:
                return {'success': False, 'error': 'פגישה לא נמצאה או אין הרשאה'}
            
            valid_statuses = ['scheduled', 'confirmed', 'completed', 'cancelled']
            if new_status not in valid_statuses:
                return {'success': False, 'error': 'סטטוס לא תקין'}
            
            old_status = appointment.status
            appointment.status = new_status
            appointment.updated_at = datetime.utcnow()
            
            # אם הפגישה הושלמה, נוסיף הערה ללקוח
            if new_status == 'completed':
                customer = appointment.customer
                if customer:
                    completion_note = f"\n[פגישה הושלמה] {appointment.appointment_date.strftime('%d/%m/%Y %H:%M')} - {appointment.note or 'ללא הערות'}"
                    customer.notes = (customer.notes or "") + completion_note
                    customer.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"Updated appointment {appointment_id} status: {old_status} -> {new_status}")
            
            return {
                'success': True,
                'message': f'סטטוס הפגישה עודכן ל-{new_status}',
                'appointment_id': appointment_id,
                'new_status': new_status
            }
            
        except Exception as e:
            logger.error(f"Error updating appointment status: {e}")
            db.session.rollback()
            return {'success': False, 'error': 'שגיאה בעדכון הפגישה'}
    
    @staticmethod
    def get_upcoming_appointments(business_id: int, hours_ahead: int = 2) -> List[Dict[str, Any]]:
        """פגישות מתקרבות לשליחת התראות"""
        
        try:
            now = datetime.utcnow()
            upcoming_time = now + timedelta(hours=hours_ahead)
            
            appointments = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.status.in_(['scheduled', 'confirmed']),
                Appointment.appointment_date > now,
                Appointment.appointment_date <= upcoming_time,
                Appointment.reminder_sent == False
            ).all()
            
            upcoming_list = []
            
            for appointment in appointments:
                time_until = appointment.appointment_date - now
                minutes_until = int(time_until.total_seconds() / 60)
                
                upcoming_list.append({
                    'appointment_id': appointment.id,
                    'customer_name': appointment.customer.name if appointment.customer else 'לא ידוע',
                    'customer_phone': appointment.customer.phone if appointment.customer else '',
                    'appointment_date': appointment.appointment_date.isoformat(),
                    'minutes_until': minutes_until,
                    'note': appointment.note or ''
                })
            
            return upcoming_list
            
        except Exception as e:
            logger.error(f"Error getting upcoming appointments: {e}")
            return []
    
    @staticmethod
    def mark_reminder_sent(appointment_id: int) -> bool:
        """סימון שהתראה נשלחה"""
        
        try:
            appointment = Appointment.query.get(appointment_id)
            if appointment:
                appointment.reminder_sent = True
                db.session.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error marking reminder sent: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_calendar_statistics(business_id: int) -> Dict[str, Any]:
        """סטטיסטיקות לוח שנה"""
        
        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            week_start = today_start - timedelta(days=today_start.weekday())
            week_end = week_start + timedelta(days=7)
            
            # פגישות היום
            today_appointments = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.appointment_date >= today_start,
                Appointment.appointment_date < today_end
            ).count()
            
            # פגישות השבוע
            week_appointments = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.appointment_date >= week_start,
                Appointment.appointment_date < week_end
            ).count()
            
            # פגישות שהושלמו השבוע
            completed_this_week = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.status == 'completed',
                Appointment.appointment_date >= week_start,
                Appointment.appointment_date < week_end
            ).count()
            
            # פגישות שבוטלו השבוע
            cancelled_this_week = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.status == 'cancelled',
                Appointment.appointment_date >= week_start,
                Appointment.appointment_date < week_end
            ).count()
            
            # שיעור השלמה
            completion_rate = 0
            if week_appointments > 0:
                completion_rate = round((completed_this_week / week_appointments) * 100, 1)
            
            return {
                'today_appointments': today_appointments,
                'week_appointments': week_appointments,
                'completed_this_week': completed_this_week,
                'cancelled_this_week': cancelled_this_week,
                'completion_rate': completion_rate,
                'business_id': business_id
            }
            
        except Exception as e:
            logger.error(f"Error getting calendar statistics: {e}")
            return {
                'today_appointments': 0,
                'week_appointments': 0,
                'completed_this_week': 0,
                'cancelled_this_week': 0,
                'completion_rate': 0
            }
    
    @staticmethod
    def suggest_available_times(business_id: int, preferred_date: datetime, 
                              duration: int = 60) -> List[str]:
        """הצעת זמנים פנויים"""
        
        try:
            # שעות עבודה (9:00-17:00)
            work_start = time(9, 0)
            work_end = time(17, 0)
            
            suggested_times = []
            current_time = preferred_date.replace(
                hour=work_start.hour, 
                minute=work_start.minute, 
                second=0, 
                microsecond=0
            )
            
            end_of_day = preferred_date.replace(
                hour=work_end.hour, 
                minute=work_end.minute, 
                second=0, 
                microsecond=0
            )
            
            # בדיקת כל חצי שעה
            while current_time + timedelta(minutes=duration) <= end_of_day:
                conflict_check = CalendarService._check_time_conflict(
                    business_id, current_time, duration
                )
                
                if conflict_check['available']:
                    suggested_times.append(current_time.strftime('%H:%M'))
                
                current_time += timedelta(minutes=30)
                
                # מקסימום 10 הצעות
                if len(suggested_times) >= 10:
                    break
            
            return suggested_times
            
        except Exception as e:
            logger.error(f"Error suggesting available times: {e}")
            return []

# יצירת instance גלובלי
calendar_service = CalendarService()