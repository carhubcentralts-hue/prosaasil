"""
Daily Reports Service - שירות דוחות יומיים מתקדם
מערכת יצירת דוחות אוטומטיים עם ניתוח נתונים ושליחה למנהלים
"""

import logging
import json
from typing import Dict, List, Any
from datetime import datetime, timedelta
import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO
from app import db
from models import Business, CallLog, ConversationTurn, AppointmentRequest, CRMCustomer
from twilio_service import send_sms
from notification_service import send_email

logger = logging.getLogger(__name__)

class DailyReportsService:
    """שירות דוחות יומיים אוטומטיים"""
    
    def __init__(self):
        self.report_types = {
            'daily_summary': 'סיכום יומי',
            'weekly_overview': 'סקירה שבועית', 
            'monthly_insights': 'תובנות חודשיות',
            'business_performance': 'ביצועים עסקיים',
            'customer_analysis': 'ניתוח לקוחות'
        }
        
        # הגדרת פונט עברי
        try:
            pdfmetrics.registerFont(TTFont('Hebrew', 'static/fonts/NotoSansHebrew-Regular.ttf'))
        except:
            logger.warning("Hebrew font not found, using default")
    
    def generate_daily_report(self, business_id: int, report_date: datetime = None) -> Dict[str, Any]:
        """יצירת דוח יומי מפורט"""
        
        if not report_date:
            report_date = datetime.now()
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # נתוני היום
            start_date = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            # שיחות היום
            daily_calls = CallLog.query.filter(
                CallLog.business_id == business_id,
                CallLog.call_time >= start_date,
                CallLog.call_time < end_date
            ).all()
            
            # תורים שנקבעו היום
            appointments = AppointmentRequest.query.filter(
                AppointmentRequest.business_id == business_id,
                AppointmentRequest.created_at >= start_date,
                AppointmentRequest.created_at < end_date
            ).all()
            
            # לקוחות חדשים היום
            new_customers = CRMCustomer.query.filter(
                CRMCustomer.business_id == business_id,
                CRMCustomer.created_at >= start_date,
                CRMCustomer.created_at < end_date
            ).all()
            
            # חישוב מטריקות
            total_calls = len(daily_calls)
            successful_calls = len([c for c in daily_calls if c.duration and c.duration > 30])
            call_success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
            
            total_appointments = len(appointments)
            confirmed_appointments = len([a for a in appointments if a.status == 'confirmed'])
            
            avg_call_duration = sum(c.duration or 0 for c in daily_calls) / total_calls if total_calls > 0 else 0
            
            # בניית הדוח
            report_data = {
                'business_name': business.name,
                'report_date': report_date.strftime('%d/%m/%Y'),
                'report_type': 'daily_summary',
                'metrics': {
                    'calls': {
                        'total': total_calls,
                        'successful': successful_calls,
                        'success_rate': round(call_success_rate, 1),
                        'avg_duration': round(avg_call_duration, 1)
                    },
                    'appointments': {
                        'total': total_appointments,
                        'confirmed': confirmed_appointments,
                        'confirmation_rate': round((confirmed_appointments / total_appointments * 100) if total_appointments > 0 else 0, 1)
                    },
                    'customers': {
                        'new_today': len(new_customers),
                        'active_today': len(set(c.from_number for c in daily_calls))
                    }
                },
                'details': {
                    'top_call_hours': self._analyze_call_hours(daily_calls),
                    'conversation_insights': self._analyze_conversations(daily_calls),
                    'appointment_analysis': self._analyze_appointments(appointments)
                },
                'trends': self._calculate_trends(business_id, report_date),
                'recommendations': self._generate_recommendations(business_id, report_data)
            }
            
            # יצירת PDF
            pdf_buffer = self._create_pdf_report(report_data)
            pdf_filename = f"daily_report_{business.name}_{report_date.strftime('%Y%m%d')}.pdf"
            
            # שמירת הקובץ
            reports_dir = 'static/reports'
            os.makedirs(reports_dir, exist_ok=True)
            pdf_path = os.path.join(reports_dir, pdf_filename)
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            
            logger.info(f"Daily report generated for business {business_id}: {pdf_filename}")
            
            return {
                'success': True,
                'report_data': report_data,
                'pdf_filename': pdf_filename,
                'pdf_path': pdf_path
            }
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_report_to_managers(self, business_id: int, report_result: Dict[str, Any]) -> Dict[str, Any]:
        """שליחת דוח למנהלי העסק"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            if not report_result.get('success'):
                return {'success': False, 'error': 'דוח לא זמין'}
            
            report_data = report_result['report_data']
            pdf_path = report_result['pdf_path']
            
            # הודעת סיכום
            summary_text = f"""
📊 דוח יומי - {business.name}
תאריך: {report_data['report_date']}

📞 שיחות:
• סה"כ: {report_data['metrics']['calls']['total']}
• מוצלחות: {report_data['metrics']['calls']['successful']} ({report_data['metrics']['calls']['success_rate']}%)
• משך ממוצע: {report_data['metrics']['calls']['avg_duration']} שניות

📅 תורים:
• נקבעו היום: {report_data['metrics']['appointments']['total']}
• אושרו: {report_data['metrics']['appointments']['confirmed']} ({report_data['metrics']['appointments']['confirmation_rate']}%)

👥 לקוחות:
• חדשים היום: {report_data['metrics']['customers']['new_today']}
• פעילים היום: {report_data['metrics']['customers']['active_today']}

📈 המלצות:
{chr(10).join(f"• {rec}" for rec in report_data['recommendations'][:3])}
            """
            
            # שליחה בדוא"ל (אם יש כתובת מנהל)
            manager_email = business.manager_email if hasattr(business, 'manager_email') else None
            if manager_email:
                email_result = send_email(
                    to_email=manager_email,
                    subject=f"דוח יומי - {business.name}",
                    body=summary_text,
                    attachment_path=pdf_path
                )
                
                if not email_result.get('success'):
                    logger.warning(f"Failed to send email report to {manager_email}")
            
            # שליחה ב-SMS (אם יש מספר מנהל)
            manager_phone = business.manager_phone if hasattr(business, 'manager_phone') else None
            if manager_phone:
                # גרסה מקוצרת ל-SMS
                sms_text = f"""
דוח יומי {business.name} - {report_data['report_date']}
📞 {report_data['metrics']['calls']['total']} שיחות ({report_data['metrics']['calls']['success_rate']}% הצלחה)
📅 {report_data['metrics']['appointments']['total']} תורים
👥 {report_data['metrics']['customers']['new_today']} לקוחות חדשים
                """
                
                sms_result = send_sms(manager_phone, sms_text.strip())
                
                if not sms_result.get('success'):
                    logger.warning(f"Failed to send SMS report to {manager_phone}")
            
            logger.info(f"Report sent to managers for business {business_id}")
            
            return {
                'success': True,
                'message': 'דוח נשלח בהצלחה למנהלים',
                'email_sent': manager_email is not None,
                'sms_sent': manager_phone is not None
            }
            
        except Exception as e:
            logger.error(f"Error sending report to managers: {e}")
            return {'success': False, 'error': str(e)}
    
    def schedule_automated_reports(self, business_id: int, schedule_config: Dict[str, Any]) -> Dict[str, Any]:
        """תזמון דוחות אוטומטיים"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # שמירת הגדרות תזמון (בדוגמה - בשדה system_prompt)
            schedule_settings = {
                'daily_reports': schedule_config.get('daily', False),
                'weekly_reports': schedule_config.get('weekly', False),
                'monthly_reports': schedule_config.get('monthly', False),
                'send_time': schedule_config.get('send_time', '08:00'),
                'recipients': schedule_config.get('recipients', []),
                'report_types': schedule_config.get('report_types', ['daily_summary'])
            }
            
            # שמירה במערכת (בייצור יהיה טבלה נפרדת)
            current_prompt = business.system_prompt or ""
            schedule_note = f"\n[REPORT_SCHEDULE] {json.dumps(schedule_settings)} - {datetime.now().strftime('%d/%m/%Y')}"
            business.system_prompt = current_prompt + schedule_note
            
            db.session.commit()
            
            logger.info(f"Automated reports scheduled for business {business_id}")
            
            return {
                'success': True,
                'message': 'דוחות אוטומטיים הוגדרו בהצלחה',
                'schedule_settings': schedule_settings
            }
            
        except Exception as e:
            logger.error(f"Error scheduling automated reports: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_report_history(self, business_id: int, days_back: int = 30) -> Dict[str, Any]:
        """קבלת היסטוריית דוחות"""
        
        try:
            reports_dir = 'static/reports'
            if not os.path.exists(reports_dir):
                return {
                    'success': True,
                    'reports': [],
                    'message': 'אין דוחות קיימים'
                }
            
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # חיפוש קבצי דוחות
            report_files = []
            for filename in os.listdir(reports_dir):
                if filename.startswith(f'daily_report_{business.name}_'):
                    file_path = os.path.join(reports_dir, filename)
                    file_stat = os.stat(file_path)
                    file_date = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    if (datetime.now() - file_date).days <= days_back:
                        report_files.append({
                            'filename': filename,
                            'file_path': file_path,
                            'created_date': file_date.strftime('%d/%m/%Y %H:%M'),
                            'file_size': f"{file_stat.st_size // 1024} KB",
                            'download_url': f'/static/reports/{filename}'
                        })
            
            # מיון לפי תאריך
            report_files.sort(key=lambda x: x['created_date'], reverse=True)
            
            return {
                'success': True,
                'reports': report_files,
                'total_reports': len(report_files)
            }
            
        except Exception as e:
            logger.error(f"Error getting report history: {e}")
            return {'success': False, 'error': str(e)}
    
    def _analyze_call_hours(self, calls: List[CallLog]) -> Dict[str, int]:
        """ניתוח שעות השיחות הפופולריות"""
        
        hour_counts = {}
        for call in calls:
            if call.call_time:
                hour = call.call_time.hour
                hour_counts[f"{hour:02d}:00"] = hour_counts.get(f"{hour:02d}:00", 0) + 1
        
        # החזרת 3 השעות הפופולריות ביותר
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_hours[:3])
    
    def _analyze_conversations(self, calls: List[CallLog]) -> Dict[str, Any]:
        """ניתוח תוכן השיחות"""
        
        total_conversations = 0
        appointment_requests = 0
        info_requests = 0
        
        for call in calls:
            conversations = ConversationTurn.query.filter_by(call_log_id=call.id).all()
            total_conversations += len(conversations)
            
            # ניתוח פשוט של תוכן השיחות
            for conv in conversations:
                if conv.transcript:
                    text = conv.transcript.lower()
                    if any(word in text for word in ['תור', 'זמן', 'לקבוע', 'פגישה']):
                        appointment_requests += 1
                    elif any(word in text for word in ['מידע', 'שעות', 'מיקום', 'מחיר']):
                        info_requests += 1
        
        return {
            'total_messages': total_conversations,
            'appointment_requests': appointment_requests,
            'info_requests': info_requests,
            'engagement_score': round((total_conversations / len(calls)) if calls else 0, 1)
        }
    
    def _analyze_appointments(self, appointments: List[AppointmentRequest]) -> Dict[str, Any]:
        """ניתוח תורים שנקבעו"""
        
        if not appointments:
            return {'message': 'לא נקבעו תורים היום'}
        
        # ניתוח לפי סטטוס
        status_counts = {}
        for appointment in appointments:
            status = appointment.status or 'pending'
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # ניתוח לפי שעות מועדפות
        preferred_hours = {}
        for appointment in appointments:
            if appointment.requested_time:
                hour = appointment.requested_time.split(':')[0] if ':' in appointment.requested_time else '00'
                preferred_hours[f"{hour}:00"] = preferred_hours.get(f"{hour}:00", 0) + 1
        
        return {
            'status_breakdown': status_counts,
            'preferred_hours': preferred_hours,
            'conversion_rate': round((len(appointments) / max(1, len(appointments))) * 100, 1)
        }
    
    def _calculate_trends(self, business_id: int, current_date: datetime) -> Dict[str, Any]:
        """חישוב מגמות לעומת תקופות קודמות"""
        
        try:
            # השוואה לשבוע קודם
            week_ago = current_date - timedelta(days=7)
            week_start = week_ago.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=1)
            
            last_week_calls = CallLog.query.filter(
                CallLog.business_id == business_id,
                CallLog.call_time >= week_start,
                CallLog.call_time < week_end
            ).count()
            
            current_calls = CallLog.query.filter(
                CallLog.business_id == business_id,
                CallLog.call_time >= current_date.replace(hour=0, minute=0, second=0, microsecond=0),
                CallLog.call_time < current_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            ).count()
            
            calls_trend = ((current_calls - last_week_calls) / max(1, last_week_calls)) * 100
            
            return {
                'calls_vs_last_week': {
                    'current': current_calls,
                    'previous': last_week_calls,
                    'change_percent': round(calls_trend, 1),
                    'trend': 'עלייה' if calls_trend > 0 else 'ירידה' if calls_trend < 0 else 'יציב'
                }
            }
            
        except Exception as e:
            logger.warning(f"Error calculating trends: {e}")
            return {'message': 'לא ניתן לחשב מגמות'}
    
    def _generate_recommendations(self, business_id: int, report_data: Dict[str, Any]) -> List[str]:
        """יצירת המלצות על בסיס הנתונים"""
        
        recommendations = []
        metrics = report_data['metrics']
        
        # המלצות על בסיס שיחות
        if metrics['calls']['success_rate'] < 70:
            recommendations.append('שיעור הצלחת השיחות נמוך - שקול שיפור סקריפט השיחה או זמן המענה')
        
        if metrics['calls']['avg_duration'] < 60:
            recommendations.append('משך השיחות קצר - יכול להצביע על חוסר עניין או בעיות טכניות')
        
        # המלצות על בסיס תורים
        if metrics['appointments']['total'] == 0:
            recommendations.append('לא נקבעו תורים היום - שקול שיפור הצעת השירותים או תמריצים')
        elif metrics['appointments']['confirmation_rate'] < 80:
            recommendations.append('שיעור אישור התורים נמוך - שקול הוספת תזכורות אוטומטיות')
        
        # המלצות על בסיס לקוחות חדשים
        if metrics['customers']['new_today'] == 0:
            recommendations.append('לא נוספו לקוחות חדשים - שקול קמפיין שיווקי או שיפור חוויית הלקוח')
        
        # המלצות כלליות
        if metrics['calls']['total'] > 20:
            recommendations.append('יום עמוס בשיחות - וודא שיש מספיק זמינות לטיפול איכותי')
        
        return recommendations[:5]  # החזרת עד 5 המלצות
    
    def _create_pdf_report(self, report_data: Dict[str, Any]) -> BytesIO:
        """יצירת דוח PDF מעוצב"""
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # כותרת
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, height - 50, f"Daily Report - {report_data['business_name']}")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 75, f"Date: {report_data['report_date']}")
        
        y_position = height - 120
        
        # מטריקות עיקריות
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "Key Metrics")
        y_position -= 30
        
        c.setFont("Helvetica", 10)
        metrics = report_data['metrics']
        
        # שיחות
        c.drawString(70, y_position, f"Calls: {metrics['calls']['total']} total, {metrics['calls']['successful']} successful ({metrics['calls']['success_rate']}%)")
        y_position -= 20
        
        # תורים
        c.drawString(70, y_position, f"Appointments: {metrics['appointments']['total']} booked, {metrics['appointments']['confirmed']} confirmed")
        y_position -= 20
        
        # לקוחות
        c.drawString(70, y_position, f"Customers: {metrics['customers']['new_today']} new, {metrics['customers']['active_today']} active")
        y_position -= 40
        
        # המלצות
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "Recommendations")
        y_position -= 25
        
        c.setFont("Helvetica", 10)
        for i, recommendation in enumerate(report_data['recommendations'][:5], 1):
            c.drawString(70, y_position, f"{i}. {recommendation}")
            y_position -= 20
        
        c.save()
        buffer.seek(0)
        return buffer


# יצירת אינסטנס global
daily_reports_service = DailyReportsService()