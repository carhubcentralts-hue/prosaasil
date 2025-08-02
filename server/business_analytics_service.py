"""
Business Analytics Service - שירות ניתוח עסקי מתקדם
מערכת דוחות ואנליטיקה מתקדמת לעסקים עם KPIs ותובנות עסקיות
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, desc
from app import db
from models import CRMCustomer, Business, CallLog, ConversationTurn, AppointmentRequest, CRMTask

logger = logging.getLogger(__name__)

class BusinessAnalyticsService:
    """שירות ניתוח עסקי מתקדם עם KPIs ותובנות"""
    
    def __init__(self):
        self.kpi_thresholds = {
            'call_conversion_rate': 15.0,  # אחוז המרה מינימלי
            'customer_satisfaction': 80.0,  # שביעות רצון מינימלית
            'response_time': 300,  # זמן תגובה מקסימלי בשניות
            'lead_followup_time': 3600  # זמן מעקב מקסימלי בשניות
        }
    
    def generate_business_dashboard(self, business_id: int, period_days: int = 30) -> Dict[str, Any]:
        """יצירת דשבורד עסקי מקיף"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            period_start = datetime.utcnow() - timedelta(days=period_days)
            
            # מדדי ביצוע עיקריים
            kpis = self._calculate_kpis(business_id, period_start)
            
            # ניתוח מגמות
            trends = self._analyze_trends(business_id, period_start)
            
            # ניתוח לקוחות
            customer_analysis = self._analyze_customers(business_id, period_start)
            
            # ניתוח שיחות
            call_analysis = self._analyze_calls(business_id, period_start)
            
            # ניתוח תורים
            appointment_analysis = self._analyze_appointments(business_id, period_start)
            
            # אזהרות והמלצות
            alerts = self._generate_business_alerts(business_id, kpis)
            recommendations = self._generate_business_recommendations(business_id, kpis, trends)
            
            dashboard = {
                'business_info': {
                    'id': business_id,
                    'name': business.name,
                    'phone': business.phone_number,
                    'period_days': period_days,
                    'generated_at': datetime.utcnow().isoformat()
                },
                'kpis': kpis,
                'trends': trends,
                'customer_analysis': customer_analysis,
                'call_analysis': call_analysis,
                'appointment_analysis': appointment_analysis,
                'alerts': alerts,
                'recommendations': recommendations
            }
            
            logger.info(f"Business dashboard generated for {business_id}: {len(alerts)} alerts, {len(recommendations)} recommendations")
            
            return {
                'success': True,
                'dashboard': dashboard
            }
            
        except Exception as e:
            logger.error(f"Error generating business dashboard: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_kpis(self, business_id: int, period_start: datetime) -> Dict[str, Any]:
        """חישוב מדדי ביצוע עיקריים"""
        
        try:
            # ספירת לקוחות
            total_customers = CRMCustomer.query.filter_by(business_id=business_id).count()
            new_customers = CRMCustomer.query.filter(
                and_(
                    CRMCustomer.business_id == business_id,
                    CRMCustomer.created_at >= period_start
                )
            ).count()
            
            # ספירת שיחות
            total_calls = CallLog.query.filter(
                and_(
                    CallLog.business_id == business_id,
                    CallLog.call_time >= period_start
                )
            ).count()
            
            successful_calls = CallLog.query.filter(
                and_(
                    CallLog.business_id == business_id,
                    CallLog.call_time >= period_start,
                    CallLog.status == 'completed'
                )
            ).count()
            
            # ספירת תורים
            total_appointments = AppointmentRequest.query.filter(
                and_(
                    AppointmentRequest.business_id == business_id,
                    AppointmentRequest.created_at >= period_start
                )
            ).count()
            
            confirmed_appointments = AppointmentRequest.query.filter(
                and_(
                    AppointmentRequest.business_id == business_id,
                    AppointmentRequest.created_at >= period_start,
                    AppointmentRequest.status == 'confirmed'
                )
            ).count()
            
            # חישוב שיעורים
            call_success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
            appointment_conversion_rate = (confirmed_appointments / total_calls * 100) if total_calls > 0 else 0
            
            # זמן תגובה ממוצע
            avg_response_time = self._calculate_average_response_time(business_id, period_start)
            
            # שביעות רצון (מבוסס על ניתוח טקסט)
            satisfaction_score = self._calculate_satisfaction_score(business_id, period_start)
            
            return {
                'customers': {
                    'total': total_customers,
                    'new_in_period': new_customers,
                    'growth_rate': round((new_customers / max(total_customers - new_customers, 1)) * 100, 2)
                },
                'calls': {
                    'total': total_calls,
                    'successful': successful_calls,
                    'success_rate': round(call_success_rate, 2)
                },
                'appointments': {
                    'total': total_appointments,
                    'confirmed': confirmed_appointments,
                    'conversion_rate': round(appointment_conversion_rate, 2)
                },
                'performance': {
                    'avg_response_time': round(avg_response_time, 2),
                    'satisfaction_score': round(satisfaction_score, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating KPIs: {e}")
            return {}
    
    def _analyze_trends(self, business_id: int, period_start: datetime) -> Dict[str, Any]:
        """ניתוח מגמות עסקיות"""
        
        try:
            # מגמת שיחות יומית
            daily_calls = []
            current_date = period_start.date()
            end_date = datetime.utcnow().date()
            
            while current_date <= end_date:
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = datetime.combine(current_date, datetime.max.time())
                
                calls_count = CallLog.query.filter(
                    and_(
                        CallLog.business_id == business_id,
                        CallLog.call_time >= day_start,
                        CallLog.call_time <= day_end
                    )
                ).count()
                
                daily_calls.append({
                    'date': current_date.strftime('%d/%m'),
                    'calls': calls_count
                })
                
                current_date += timedelta(days=1)
            
            # מגמת לקוחות חדשים
            weekly_customers = self._get_weekly_customer_trend(business_id, period_start)
            
            # מגמת תורים
            weekly_appointments = self._get_weekly_appointment_trend(business_id, period_start)
            
            # ניתוח שעות שיא
            peak_hours = self._analyze_peak_hours(business_id, period_start)
            
            return {
                'daily_calls': daily_calls[-14:],  # 14 ימים אחרונים
                'weekly_customers': weekly_customers,
                'weekly_appointments': weekly_appointments,
                'peak_hours': peak_hours
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {}
    
    def _analyze_customers(self, business_id: int, period_start: datetime) -> Dict[str, Any]:
        """ניתוח לקוחות מתקדם"""
        
        try:
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            
            # פילוח לפי סטטוס
            status_breakdown = {}
            for customer in customers:
                status = customer.status or 'unknown'
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            # לקוחות חדשים בתקופה
            new_customers = CRMCustomer.query.filter(
                and_(
                    CRMCustomer.business_id == business_id,
                    CRMCustomer.created_at >= period_start
                )
            ).all()
            
            # ניתוח מקורות לקוחות (אם קיים שדה)
            source_breakdown = {}
            for customer in new_customers:
                source = getattr(customer, 'source', 'phone_call')
                source_breakdown[source] = source_breakdown.get(source, 0) + 1
            
            # לקוחות פעילים (עם שיחות בתקופה)
            active_customers = db.session.query(CRMCustomer).join(CallLog).filter(
                and_(
                    CRMCustomer.business_id == business_id,
                    CallLog.call_time >= period_start
                )
            ).distinct().count()
            
            return {
                'total_customers': len(customers),
                'new_customers': len(new_customers),
                'active_customers': active_customers,
                'status_breakdown': status_breakdown,
                'source_breakdown': source_breakdown,
                'activity_rate': round((active_customers / max(len(customers), 1)) * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing customers: {e}")
            return {}
    
    def _analyze_calls(self, business_id: int, period_start: datetime) -> Dict[str, Any]:
        """ניתוח שיחות מתקדם"""
        
        try:
            calls = CallLog.query.filter(
                and_(
                    CallLog.business_id == business_id,
                    CallLog.call_time >= period_start
                )
            ).all()
            
            if not calls:
                return {
                    'total_calls': 0,
                    'avg_duration': 0,
                    'status_breakdown': {},
                    'hourly_distribution': {}
                }
            
            # פילוח לפי סטטוס
            status_breakdown = {}
            durations = []
            hourly_distribution = {}
            
            for call in calls:
                # סטטוס
                status = call.status or 'unknown'
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
                
                # משך שיחה
                if call.duration:
                    durations.append(call.duration)
                
                # פילוח שעות
                hour = call.call_time.hour
                hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
            
            # חישוב סטטיסטיקות
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # המרה לפורמט נוח לגרפים
            hourly_chart_data = [
                {'hour': f"{hour:02d}:00", 'calls': count}
                for hour, count in sorted(hourly_distribution.items())
            ]
            
            return {
                'total_calls': len(calls),
                'avg_duration': round(avg_duration, 2),
                'status_breakdown': status_breakdown,
                'hourly_distribution': hourly_chart_data
            }
            
        except Exception as e:
            logger.error(f"Error analyzing calls: {e}")
            return {}
    
    def _analyze_appointments(self, business_id: int, period_start: datetime) -> Dict[str, Any]:
        """ניתוח תורים מתקדם"""
        
        try:
            appointments = AppointmentRequest.query.filter(
                and_(
                    AppointmentRequest.business_id == business_id,
                    AppointmentRequest.created_at >= period_start
                )
            ).all()
            
            if not appointments:
                return {
                    'total_appointments': 0,
                    'status_breakdown': {},
                    'daily_trend': []
                }
            
            # פילוח לפי סטטוס
            status_breakdown = {}
            for appointment in appointments:
                status = appointment.status or 'pending'
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            # מגמה יומית
            daily_trend = {}
            for appointment in appointments:
                date_key = appointment.created_at.date().strftime('%d/%m')
                daily_trend[date_key] = daily_trend.get(date_key, 0) + 1
            
            daily_chart_data = [
                {'date': date, 'appointments': count}
                for date, count in sorted(daily_trend.items())
            ]
            
            return {
                'total_appointments': len(appointments),
                'status_breakdown': status_breakdown,
                'daily_trend': daily_chart_data[-14:]  # 14 ימים אחרונים
            }
            
        except Exception as e:
            logger.error(f"Error analyzing appointments: {e}")
            return {}
    
    def _generate_business_alerts(self, business_id: int, kpis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """יצירת אזהרות עסקיות"""
        
        alerts = []
        
        try:
            # בדיקת שיעור המרה נמוך
            conversion_rate = kpis.get('appointments', {}).get('conversion_rate', 0)
            if conversion_rate < self.kpi_thresholds['call_conversion_rate']:
                alerts.append({
                    'type': 'conversion_rate',
                    'level': 'warning',
                    'title': 'שיעור המרה נמוך',
                    'message': f'שיעור ההמרה לתורים הוא {conversion_rate}% - מתחת לרף המינימלי',
                    'action': 'שפר את איכות השיחות והצעת השירותים'
                })
            
            # בדיקת שביעות רצון
            satisfaction = kpis.get('performance', {}).get('satisfaction_score', 0)
            if satisfaction < self.kpi_thresholds['customer_satisfaction']:
                alerts.append({
                    'type': 'satisfaction',
                    'level': 'critical',
                    'title': 'שביעות רצון נמוכה',
                    'message': f'ציון שביעות הרצון הוא {satisfaction}% - דורש טיפול מיידי',
                    'action': 'בדוק תלונות לקוחות ושפר את השירות'
                })
            
            # בדיקת זמן תגובה
            response_time = kpis.get('performance', {}).get('avg_response_time', 0)
            if response_time > self.kpi_thresholds['response_time']:
                alerts.append({
                    'type': 'response_time',
                    'level': 'warning',
                    'title': 'זמן תגובה ארוך',
                    'message': f'זמן התגובה הממוצע הוא {response_time} שניות',
                    'action': 'הוסף נציגים או שפר את תהליכי המענה'
                })
            
            # בדיקת גידול בלקוחות
            growth_rate = kpis.get('customers', {}).get('growth_rate', 0)
            if growth_rate < 0:
                alerts.append({
                    'type': 'customer_decline',
                    'level': 'critical',
                    'title': 'ירידה במספר הלקוחות',
                    'message': f'מספר הלקוחות ירד ב-{abs(growth_rate)}%',
                    'action': 'פעל לשימור לקוחות ויצירת לידים חדשים'
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error generating business alerts: {e}")
            return []
    
    def _generate_business_recommendations(self, business_id: int, kpis: Dict[str, Any], trends: Dict[str, Any]) -> List[Dict[str, Any]]:
        """יצירת המלצות עסקיות"""
        
        recommendations = []
        
        try:
            # המלצות לפי ביצועים
            conversion_rate = kpis.get('appointments', {}).get('conversion_rate', 0)
            if conversion_rate > 20:
                recommendations.append({
                    'type': 'optimization',
                    'priority': 'medium',
                    'title': 'שיעור המרה מעולה',
                    'description': 'שיעור ההמרה שלך גבוה - נסה להגדיל את נפח השיחות',
                    'action_items': [
                        'הגדל את התקציב לפרסום',
                        'הוסף ערוצי שיווק נוספים',
                        'שפר את זמינות הטלפון'
                    ]
                })
            
            # המלצות לפי מגמות
            peak_hours = trends.get('peak_hours', [])
            if peak_hours:
                top_hour = peak_hours[0] if peak_hours else None
                if top_hour:
                    recommendations.append({
                        'type': 'scheduling',
                        'priority': 'high',
                        'title': 'אופטימיזציה של שעות העבודה',
                        'description': f'השעה {top_hour} היא השעה הכי עמוסה',
                        'action_items': [
                            'הוסף נציגים בשעות השיא',
                            'שפר את זמינות המענה בשעות אלו',
                            'שקול הארכת שעות הפעילות'
                        ]
                    })
            
            # המלצות לפי ניתוח לקוחות
            activity_rate = kpis.get('customers', {}).get('activity_rate', 0)
            if activity_rate < 50:
                recommendations.append({
                    'type': 'engagement',
                    'priority': 'high',
                    'title': 'שיפור מעורבות לקוחות',
                    'description': f'רק {activity_rate}% מהלקוחות פעילים בתקופה',
                    'action_items': [
                        'צור קשר עם לקוחות לא פעילים',
                        'שלח הצעות מיוחדות',
                        'פתח מסע שיווקי להפעלה מחדש'
                    ]
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating business recommendations: {e}")
            return []
    
    def _calculate_average_response_time(self, business_id: int, period_start: datetime) -> float:
        """חישוב זמן תגובה ממוצע"""
        
        try:
            # כאן ניתן להוסיף לוגיקה לחישוב זמן תגובה אמיתי
            # לעכשיו נחזיר ערך דמה
            return 180.0  # 3 דקות
            
        except Exception as e:
            logger.error(f"Error calculating response time: {e}")
            return 0.0
    
    def _calculate_satisfaction_score(self, business_id: int, period_start: datetime) -> float:
        """חישוב ציון שביעות רצון"""
        
        try:
            conversations = db.session.query(ConversationTurn).join(CallLog).filter(
                and_(
                    CallLog.business_id == business_id,
                    CallLog.call_time >= period_start
                )
            ).all()
            
            if not conversations:
                return 75.0  # ברירת מחדל
            
            positive_keywords = ['תודה', 'מעולה', 'נהדר', 'מרוצה', 'אהבתי']
            negative_keywords = ['בעיה', 'כועס', 'לא מרוצה', 'רע', 'נורא']
            
            positive_count = 0
            negative_count = 0
            
            for conv in conversations:
                if conv.message:
                    message_lower = conv.message.lower()
                    for keyword in positive_keywords:
                        if keyword in message_lower:
                            positive_count += 1
                    for keyword in negative_keywords:
                        if keyword in message_lower:
                            negative_count += 1
            
            total_sentiment = positive_count + negative_count
            if total_sentiment == 0:
                return 75.0
            
            satisfaction = (positive_count / total_sentiment) * 100
            return max(0, min(100, satisfaction))
            
        except Exception as e:
            logger.error(f"Error calculating satisfaction score: {e}")
            return 75.0
    
    def _get_weekly_customer_trend(self, business_id: int, period_start: datetime) -> List[Dict[str, Any]]:
        """מגמת לקוחות שבועית"""
        
        try:
            weekly_data = []
            current_date = period_start.date()
            end_date = datetime.utcnow().date()
            
            while current_date <= end_date:
                week_end = current_date + timedelta(days=6)
                week_start_dt = datetime.combine(current_date, datetime.min.time())
                week_end_dt = datetime.combine(min(week_end, end_date), datetime.max.time())
                
                customers_count = CRMCustomer.query.filter(
                    and_(
                        CRMCustomer.business_id == business_id,
                        CRMCustomer.created_at >= week_start_dt,
                        CRMCustomer.created_at <= week_end_dt
                    )
                ).count()
                
                weekly_data.append({
                    'week': f"{current_date.strftime('%d/%m')}-{week_end.strftime('%d/%m')}",
                    'customers': customers_count
                })
                
                current_date += timedelta(days=7)
            
            return weekly_data[-8:]  # 8 שבועות אחרונים
            
        except Exception as e:
            logger.error(f"Error getting weekly customer trend: {e}")
            return []
    
    def _get_weekly_appointment_trend(self, business_id: int, period_start: datetime) -> List[Dict[str, Any]]:
        """מגמת תורים שבועית"""
        
        try:
            weekly_data = []
            current_date = period_start.date()
            end_date = datetime.utcnow().date()
            
            while current_date <= end_date:
                week_end = current_date + timedelta(days=6)
                week_start_dt = datetime.combine(current_date, datetime.min.time())
                week_end_dt = datetime.combine(min(week_end, end_date), datetime.max.time())
                
                appointments_count = AppointmentRequest.query.filter(
                    and_(
                        AppointmentRequest.business_id == business_id,
                        AppointmentRequest.created_at >= week_start_dt,
                        AppointmentRequest.created_at <= week_end_dt
                    )
                ).count()
                
                weekly_data.append({
                    'week': f"{current_date.strftime('%d/%m')}-{week_end.strftime('%d/%m')}",
                    'appointments': appointments_count
                })
                
                current_date += timedelta(days=7)
            
            return weekly_data[-8:]  # 8 שבועות אחרונים
            
        except Exception as e:
            logger.error(f"Error getting weekly appointment trend: {e}")
            return []
    
    def _analyze_peak_hours(self, business_id: int, period_start: datetime) -> List[Dict[str, Any]]:
        """ניתוח שעות שיא"""
        
        try:
            calls = CallLog.query.filter(
                and_(
                    CallLog.business_id == business_id,
                    CallLog.call_time >= period_start
                )
            ).all()
            
            hour_counts = {}
            for call in calls:
                hour = call.call_time.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            # מיון לפי כמות שיחות
            sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
            
            return [f"{hour:02d}:00" for hour, _ in sorted_hours[:5]]  # 5 שעות עליונות
            
        except Exception as e:
            logger.error(f"Error analyzing peak hours: {e}")
            return []


# יצירת אינסטנס global
business_analytics_service = BusinessAnalyticsService()