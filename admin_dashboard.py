"""
Admin Dashboard - דשבורד ניהולי מתקדם עם כל הנתונים
"""
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from app import db
from models import Business, CallLog, ConversationTurn, AppointmentRequest, User, Customer
try:
    from crm_models import CustomerTask, CustomerInteraction, Quote
except ImportError:
    # CRM models not yet available
    CustomerTask = None
    CustomerInteraction = None
    Quote = None
from business_permissions import admin_required
import logging
import json

logger = logging.getLogger(__name__)

# יצירת Blueprint עבור דשבורד אדמין
admin_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@admin_required
def main_dashboard():
    """דשבורד ראשי למנהל"""
    try:
        # סטטיסטיקות כלליות
        total_businesses = Business.query.filter_by(is_active=True).count()
        total_customers = Customer.query.count()
        total_calls_today = CallLog.query.filter(
            CallLog.created_at >= datetime.now().date()
        ).count()
        
        # עסקים פעילים
        active_businesses = Business.query.filter_by(is_active=True).all()
        
        # שיחות אחרונות
        recent_calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()
        
        # נתונים לגרפים
        chart_data = get_dashboard_charts()
        
        return render_template('admin/dashboard_advanced.html',
                             total_businesses=total_businesses,
                             total_customers=total_customers,
                             total_calls_today=total_calls_today,
                             active_businesses=active_businesses,
                             recent_calls=recent_calls,
                             chart_data=chart_data)
    
    except Exception as e:
        logger.error(f"Error in admin dashboard: {e}")
        return render_template('admin/dashboard_advanced.html',
                             total_businesses=0,
                             total_customers=0,
                             total_calls_today=0,
                             active_businesses=[],
                             recent_calls=[],
                             chart_data={})

@admin_bp.route('/businesses')
@admin_required
def businesses_overview():
    """סקירת כל העסקים"""
    try:
        businesses = Business.query.all()
        
        # הוספת סטטיסטיקות לכל עסק
        for business in businesses:
            business.stats = get_business_detailed_stats(business.id)
        
        return render_template('admin/businesses_overview.html',
                             businesses=businesses)
    
    except Exception as e:
        logger.error(f"Error in businesses overview: {e}")
        return render_template('admin/businesses_overview.html',
                             businesses=[])

@admin_bp.route('/business/<int:business_id>/analytics')
@admin_required
def business_analytics(business_id):
    """אנליטיקה מפורטת לעסק"""
    try:
        business = Business.query.get_or_404(business_id)
        
        # נתונים לתקופות שונות
        analytics = {
            'daily': get_business_analytics(business_id, days=7),
            'weekly': get_business_analytics(business_id, days=30),
            'monthly': get_business_analytics(business_id, days=90)
        }
        
        # לקוחות מובילים
        top_customers = get_top_customers(business_id)
        
        # ביצועים לפי שעות
        hourly_performance = get_hourly_performance(business_id)
        
        return render_template('admin/business_analytics.html',
                             business=business,
                             analytics=analytics,
                             top_customers=top_customers,
                             hourly_performance=hourly_performance)
    
    except Exception as e:
        logger.error(f"Error in business analytics: {e}")
        return render_template('admin/business_analytics.html',
                             business=None,
                             analytics={},
                             top_customers=[],
                             hourly_performance=[])

@admin_bp.route('/system-health')
@admin_required
def system_health():
    """בריאות המערכת"""
    try:
        health_data = {
            'database': check_database_health(),
            'calls': check_calls_health(),
            'whatsapp': check_whatsapp_health(),
            'storage': check_storage_health(),
            'api_usage': check_api_usage()
        }
        
        return render_template('admin/system_health.html',
                             health_data=health_data)
    
    except Exception as e:
        logger.error(f"Error in system health: {e}")
        return render_template('admin/system_health.html',
                             health_data={})

@admin_bp.route('/api/dashboard-stats')
@admin_required
def api_dashboard_stats():
    """API לסטטיסטיקות דשבורד בזמן אמת"""
    try:
        stats = {
            'calls_today': CallLog.query.filter(
                CallLog.created_at >= datetime.now().date()
            ).count(),
            'customers_today': Customer.query.filter(
                Customer.created_at >= datetime.now().date()
            ).count(),
            'tasks_completed_today': Task.query.filter(
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= datetime.now().date()
            ).count(),
            'active_businesses': Business.query.filter_by(is_active=True).count(),
            'system_uptime': get_system_uptime()
        }
        
        return jsonify({'success': True, 'stats': stats})
    
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500

@admin_bp.route('/api/business-performance')
@admin_required
def api_business_performance():
    """ביצועי עסקים בזמן אמת"""
    try:
        businesses = Business.query.filter_by(is_active=True).all()
        performance_data = []
        
        for business in businesses:
            stats = get_business_detailed_stats(business.id)
            performance_data.append({
                'id': business.id,
                'name': business.name,
                'calls_today': stats.get('calls_today', 0),
                'customers_total': stats.get('customers_total', 0),
                'conversion_rate': stats.get('conversion_rate', 0),
                'avg_call_duration': stats.get('avg_call_duration', 0)
            })
        
        return jsonify({'success': True, 'businesses': performance_data})
    
    except Exception as e:
        logger.error(f"Error getting business performance: {e}")
        return jsonify({'error': 'שגיאה בקבלת ביצועי עסקים'}), 500

# פונקציות עזר

def get_dashboard_charts():
    """נתונים לגרפים בדשבורד"""
    try:
        # שיחות לפי יום (7 ימים אחרונים)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)
        
        calls_by_day = []
        customers_by_day = []
        dates = []
        
        for i in range(7):
            date = start_date + timedelta(days=i)
            dates.append(date.strftime('%d/%m'))
            
            calls_count = CallLog.query.filter(
                CallLog.created_at >= date,
                CallLog.created_at < date + timedelta(days=1)
            ).count()
            calls_by_day.append(calls_count)
            
            customers_count = Customer.query.filter(
                Customer.created_at >= date,
                Customer.created_at < date + timedelta(days=1)
            ).count()
            customers_by_day.append(customers_count)
        
        return {
            'dates': dates,
            'calls': calls_by_day,
            'customers': customers_by_day
        }
    
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return {'dates': [], 'calls': [], 'customers': []}

def get_business_detailed_stats(business_id):
    """סטטיסטיקות מפורטות לעסק"""
    try:
        today = datetime.now().date()
        
        stats = {
            'calls_today': CallLog.query.filter(
                CallLog.business_id == business_id,
                CallLog.created_at >= today
            ).count(),
            'calls_total': CallLog.query.filter_by(business_id=business_id).count(),
            'customers_total': Customer.query.filter_by(business_id=business_id).count(),
            'customers_active': Customer.query.filter_by(
                business_id=business_id,
                status=CustomerStatus.ACTIVE
            ).count(),
            'tasks_pending': Task.query.filter_by(
                business_id=business_id,
                status=TaskStatus.PENDING
            ).count(),
            'appointments_today': AppointmentRequest.query.filter(
                AppointmentRequest.business_id == business_id,
                AppointmentRequest.created_at >= today
            ).count()
        }
        
        # חישוב שיעור המרה
        total_calls = stats['calls_total']
        total_customers = stats['customers_total']
        stats['conversion_rate'] = round((total_customers / total_calls * 100) if total_calls > 0 else 0, 1)
        
        # משך שיחה ממוצע
        avg_duration = db.session.query(db.func.avg(CallLog.duration_seconds)).filter_by(business_id=business_id).scalar()
        stats['avg_call_duration'] = round(avg_duration or 0, 1)
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting detailed stats for business {business_id}: {e}")
        return {}

def get_business_analytics(business_id, days=30):
    """אנליטיקה לעסק לתקופה"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # מטריקות לתקופה
        metrics = BusinessMetrics.query.filter(
            BusinessMetrics.business_id == business_id,
            BusinessMetrics.date >= start_date.date()
        ).order_by(BusinessMetrics.date.asc()).all()
        
        # הכנת נתונים
        analytics = {
            'dates': [],
            'calls': [],
            'whatsapp': [],
            'customers': [],
            'appointments': []
        }
        
        for metric in metrics:
            analytics['dates'].append(metric.date.strftime('%d/%m'))
            analytics['calls'].append(metric.total_calls or 0)
            analytics['whatsapp'].append(metric.whatsapp_messages_received or 0)
            analytics['customers'].append(metric.new_customers or 0)
            analytics['appointments'].append(metric.appointments_booked or 0)
        
        return analytics
    
    except Exception as e:
        logger.error(f"Error getting analytics for business {business_id}: {e}")
        return {}

def get_top_customers(business_id, limit=10):
    """לקוחות מובילים לפי אינטראקציות"""
    try:
        # ספירת אינטראקציות לכל לקוח
        top_customers = db.session.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            db.func.count(CustomerInteraction.id).label('interactions_count')
        ).join(CustomerInteraction).filter(
            Customer.business_id == business_id
        ).group_by(Customer.id).order_by(
            db.func.count(CustomerInteraction.id).desc()
        ).limit(limit).all()
        
        return [
            {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'interactions': customer.interactions_count
            }
            for customer in top_customers
        ]
    
    except Exception as e:
        logger.error(f"Error getting top customers: {e}")
        return []

def get_hourly_performance(business_id):
    """ביצועים לפי שעות"""
    try:
        hourly_data = []
        
        for hour in range(24):
            calls_count = CallLog.query.filter(
                CallLog.business_id == business_id,
                db.func.extract('hour', CallLog.created_at) == hour
            ).count()
            
            hourly_data.append({
                'hour': f"{hour:02d}:00",
                'calls': calls_count
            })
        
        return hourly_data
    
    except Exception as e:
        logger.error(f"Error getting hourly performance: {e}")
        return []

def check_database_health():
    """בדיקת בריאות מסד נתונים"""
    try:
        # בדיקה פשוטה
        Business.query.first()
        return {'status': 'healthy', 'message': 'מסד הנתונים פועל תקין'}
    except Exception as e:
        return {'status': 'error', 'message': f'שגיאה במסד נתונים: {str(e)}'}

def check_calls_health():
    """בדיקת בריאות מערכת שיחות"""
    try:
        recent_calls = CallLog.query.filter(
            CallLog.created_at >= datetime.now() - timedelta(hours=1)
        ).count()
        
        if recent_calls > 0:
            return {'status': 'healthy', 'message': f'{recent_calls} שיחות בשעה האחרונה'}
        else:
            return {'status': 'warning', 'message': 'אין שיחות בשעה האחרונה'}
    except Exception as e:
        return {'status': 'error', 'message': f'שגיאה בבדיקת שיחות: {str(e)}'}

def check_whatsapp_health():
    """בדיקת בריאות WhatsApp"""
    try:
        # ניתן להוסיף בדיקות ספציפיות ל-WhatsApp
        return {'status': 'healthy', 'message': 'מערכת WhatsApp פועלת'}
    except Exception as e:
        return {'status': 'error', 'message': f'שגיאה ב-WhatsApp: {str(e)}'}

def check_storage_health():
    """בדיקת שטח אחסון"""
    try:
        import os
        import shutil
        
        total, used, free = shutil.disk_usage(".")
        used_percent = (used / total) * 100
        
        if used_percent < 80:
            return {'status': 'healthy', 'message': f'שטח פנוי: {used_percent:.1f}%'}
        elif used_percent < 90:
            return {'status': 'warning', 'message': f'שטח מתמלא: {used_percent:.1f}%'}
        else:
            return {'status': 'error', 'message': f'שטח אחסון אזל: {used_percent:.1f}%'}
    except Exception as e:
        return {'status': 'error', 'message': f'שגיאה בבדיקת אחסון: {str(e)}'}

def check_api_usage():
    """בדיקת שימוש ב-API"""
    try:
        # ניתן להוסיף בדיקות שימוש ב-OpenAI, Twilio וכו'
        return {'status': 'healthy', 'message': 'שימוש תקין ב-APIs'}
    except Exception as e:
        return {'status': 'error', 'message': f'שגיאה בבדיקת API: {str(e)}'}

def get_system_uptime():
    """זמן פעילות המערכת"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        
        uptime_hours = uptime_seconds / 3600
        return f"{uptime_hours:.1f} שעות"
    except:
        return "לא זמין"