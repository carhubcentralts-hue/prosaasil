"""
Enhanced Admin Dashboard with Advanced Business Management
דשבורד מנהל מתקדם עם ניהול עסקים ברמה גבוהה
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, timedelta
from app import db
from models import Business, CallLog, ConversationTurn, CRMCustomer, CRMTask, User
from enhanced_business_permissions import BusinessPermissions
from auth import AuthService
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

enhanced_admin_bp = Blueprint('enhanced_admin', __name__, url_prefix='/admin')

@enhanced_admin_bp.route('/dashboard')
def enhanced_dashboard():
    """דשבורד מנהל מתקדם"""
    
    try:
        user = AuthService.get_current_user()
        
        if not user or user.role != 'admin':
            flash('אין הרשאה לגישה לדשבורד מנהל')
            return redirect(url_for('login'))
        
        # סטטיסטיקות כלליות
        total_businesses = Business.query.filter_by(is_active=True).count()
        total_calls_today = CallLog.query.filter(
            CallLog.start_time >= datetime.now().date()
        ).count()
        
        total_customers = CRMCustomer.query.count()
        pending_tasks = CRMTask.query.filter_by(status='pending').count()
        
        # נתונים לגרפים
        business_stats = get_business_performance_stats()
        call_volume_data = get_call_volume_data()
        customer_growth_data = get_customer_growth_data()
        
        # עסקים עם ביצועים גבוהים
        top_businesses = get_top_performing_businesses()
        
        # התרעות מערכת
        system_alerts = get_system_alerts()
        
        return render_template('admin/enhanced_dashboard.html',
            total_businesses=total_businesses,
            total_calls_today=total_calls_today,
            total_customers=total_customers,
            pending_tasks=pending_tasks,
            business_stats=business_stats,
            call_volume_data=call_volume_data,
            customer_growth_data=customer_growth_data,
            top_businesses=top_businesses,
            system_alerts=system_alerts
        )
        
    except Exception as e:
        logger.error(f"Error loading enhanced dashboard: {e}")
        flash('אירעה שגיאה בטעינת הדשבורד')
        return redirect(url_for('login'))

@enhanced_admin_bp.route('/businesses')
def business_management():
    """ניהול עסקים מתקדם"""
    
    try:
        user = AuthService.get_current_user()
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # קבלת כל העסקים עם סטטיסטיקות
        businesses = []
        for business in Business.query.filter_by(is_active=True).all():
            business_data = {
                'id': business.id,
                'name': business.name,
                'phone_number': business.phone_number,
                'status': 'פעיל' if business.is_active else 'לא פעיל',
                'permissions': {
                    'calls': getattr(business, 'phone_permissions', True),
                    'whatsapp': getattr(business, 'whatsapp_permissions', True),
                    'crm': getattr(business, 'crm_permissions', True)
                },
                'stats': get_business_detailed_stats(business.id),
                'last_activity': get_business_last_activity(business.id)
            }
            businesses.append(business_data)
        
        return render_template('admin/business_management.html',
            businesses=businesses
        )
        
    except Exception as e:
        logger.error(f"Error loading business management: {e}")
        return jsonify({'error': 'Server error'}), 500

@enhanced_admin_bp.route('/business/<int:business_id>/details')
def business_details(business_id: int):
    """פרטי עסק מפורטים"""
    
    try:
        user = AuthService.get_current_user()
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        business = Business.query.get_or_404(business_id)
        
        # סטטיסטיקות מפורטות
        detailed_stats = {
            'calls': {
                'total': CallLog.query.filter_by(business_id=business_id).count(),
                'today': CallLog.query.filter(
                    CallLog.business_id == business_id,
                    CallLog.start_time >= datetime.now().date()
                ).count(),
                'avg_duration': get_average_call_duration(business_id),
                'success_rate': get_call_success_rate(business_id)
            },
            'customers': {
                'total': CRMCustomer.query.filter_by(business_id=business_id).count(),
                'active': CRMCustomer.query.filter_by(business_id=business_id, status='active').count(),
                'new_this_week': CRMCustomer.query.filter(
                    CRMCustomer.business_id == business_id,
                    CRMCustomer.created_at >= datetime.now() - timedelta(days=7)
                ).count()
            },
            'tasks': {
                'pending': CRMTask.query.filter_by(business_id=business_id, status='pending').count(),
                'completed_today': CRMTask.query.filter(
                    CRMTask.business_id == business_id,
                    CRMTask.status == 'completed',
                    CRMTask.completed_at >= datetime.now().date()
                ).count()
            }
        }
        
        # לידים אחרונים
        recent_leads = CRMCustomer.query.filter_by(
            business_id=business_id,
            status='prospect'
        ).order_by(CRMCustomer.created_at.desc()).limit(10).all()
        
        # שיחות אחרונות
        recent_calls = CallLog.query.filter_by(
            business_id=business_id
        ).order_by(CallLog.start_time.desc()).limit(10).all()
        
        return render_template('admin/business_details.html',
            business=business,
            stats=detailed_stats,
            recent_leads=recent_leads,
            recent_calls=recent_calls
        )
        
    except Exception as e:
        logger.error(f"Error loading business details: {e}")
        return jsonify({'error': 'Server error'}), 500

@enhanced_admin_bp.route('/business/<int:business_id>/permissions', methods=['POST'])
def update_business_permissions(business_id: int):
    """עדכון הרשאות עסק"""
    
    try:
        user = AuthService.get_current_user()
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        business = Business.query.get_or_404(business_id)
        
        data = request.get_json()
        
        # עדכון הרשאות
        business.phone_permissions = data.get('calls', True)
        business.whatsapp_permissions = data.get('whatsapp', True)
        business.crm_permissions = data.get('crm', True)
        
        db.session.commit()
        
        logger.info(f"Updated permissions for business {business_id}")
        
        return jsonify({
            'success': True,
            'message': 'הרשאות עודכנו בהצלחה'
        })
        
    except Exception as e:
        logger.error(f"Error updating business permissions: {e}")
        return jsonify({'error': 'Server error'}), 500

@enhanced_admin_bp.route('/system/alerts')
def system_alerts_api():
    """API להתרעות מערכת"""
    
    try:
        user = AuthService.get_current_user()
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        alerts = get_system_alerts()
        
        return jsonify({
            'success': True,
            'alerts': alerts
        })
        
    except Exception as e:
        logger.error(f"Error getting system alerts: {e}")
        return jsonify({'error': 'Server error'}), 500

# פונקציות עזר

def get_business_performance_stats() -> List[Dict[str, Any]]:
    """קבלת נתוני ביצועי עסקים"""
    
    try:
        stats = []
        
        for business in Business.query.filter_by(is_active=True).all():
            calls_today = CallLog.query.filter(
                CallLog.business_id == business.id,
                CallLog.start_time >= datetime.now().date()
            ).count()
            
            customers_total = CRMCustomer.query.filter_by(
                business_id=business.id
            ).count()
            
            stats.append({
                'business_id': business.id,
                'name': business.name,
                'calls_today': calls_today,
                'total_customers': customers_total,
                'response_rate': get_call_success_rate(business.id)
            })
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting business performance stats: {e}")
        return []

def get_call_volume_data() -> Dict[str, List]:
    """נתוני נפח שיחות לגרף"""
    
    try:
        # נתונים ל-7 ימים אחרונים
        dates = []
        call_counts = []
        
        for i in range(7):
            date = datetime.now().date() - timedelta(days=i)
            calls = CallLog.query.filter(
                CallLog.start_time >= date,
                CallLog.start_time < date + timedelta(days=1)
            ).count()
            
            dates.append(date.strftime('%d/%m'))
            call_counts.append(calls)
        
        # הפיכת הרשימה (החדש ביותר בסוף)
        dates.reverse()
        call_counts.reverse()
        
        return {
            'dates': dates,
            'calls': call_counts
        }
    
    except Exception as e:
        logger.error(f"Error getting call volume data: {e}")
        return {'dates': [], 'calls': []}

def get_customer_growth_data() -> Dict[str, List]:
    """נתוני גידול לקוחות"""
    
    try:
        dates = []
        customer_counts = []
        
        for i in range(14):
            date = datetime.now().date() - timedelta(days=i)
            customers = CRMCustomer.query.filter(
                CRMCustomer.created_at >= date,
                CRMCustomer.created_at < date + timedelta(days=1)
            ).count()
            
            dates.append(date.strftime('%d/%m'))
            customer_counts.append(customers)
        
        dates.reverse()
        customer_counts.reverse()
        
        return {
            'dates': dates,
            'customers': customer_counts
        }
    
    except Exception as e:
        logger.error(f"Error getting customer growth data: {e}")
        return {'dates': [], 'customers': []}

def get_top_performing_businesses() -> List[Dict[str, Any]]:
    """עסקים עם ביצועים מובילים"""
    
    try:
        businesses = []
        
        for business in Business.query.filter_by(is_active=True).all():
            calls_week = CallLog.query.filter(
                CallLog.business_id == business.id,
                CallLog.start_time >= datetime.now() - timedelta(days=7)
            ).count()
            
            customers_week = CRMCustomer.query.filter(
                CRMCustomer.business_id == business.id,
                CRMCustomer.created_at >= datetime.now() - timedelta(days=7)
            ).count()
            
            # חישוב ציון ביצועים
            performance_score = calls_week + (customers_week * 2)
            
            businesses.append({
                'id': business.id,
                'name': business.name,
                'calls_week': calls_week,
                'customers_week': customers_week,
                'performance_score': performance_score
            })
        
        # מיון לפי ביצועים
        businesses.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return businesses[:5]  # 5 מובילים
    
    except Exception as e:
        logger.error(f"Error getting top performing businesses: {e}")
        return []

def get_system_alerts() -> List[Dict[str, Any]]:
    """התרעות מערכת"""
    
    alerts = []
    
    try:
        # בדיקת עסקים ללא פעילות
        inactive_businesses = []
        for business in Business.query.filter_by(is_active=True).all():
            last_call = CallLog.query.filter_by(
                business_id=business.id
            ).order_by(CallLog.start_time.desc()).first()
            
            if not last_call or (datetime.utcnow() - last_call.start_time).days > 7:
                inactive_businesses.append(business.name)
        
        if inactive_businesses:
            alerts.append({
                'type': 'warning',
                'title': 'עסקים ללא פעילות',
                'message': f'{len(inactive_businesses)} עסקים לא קיבלו שיחות בשבוע האחרון',
                'businesses': inactive_businesses
            })
        
        # בדיקת משימות מתעכבות
        overdue_tasks = CRMTask.query.filter(
            CRMTask.due_date < datetime.now().date(),
            CRMTask.status.in_(['pending', 'in_progress'])
        ).count()
        
        if overdue_tasks > 0:
            alerts.append({
                'type': 'danger',
                'title': 'משימות מתעכבות',
                'message': f'{overdue_tasks} משימות עברו את התאריך היעד'
            })
        
        # בדיקת לידים לא מטופלים
        old_leads = CRMCustomer.query.filter(
            CRMCustomer.status == 'prospect',
            CRMCustomer.created_at < datetime.now() - timedelta(days=3)
        ).count()
        
        if old_leads > 0:
            alerts.append({
                'type': 'info',
                'title': 'לידים ממתינים',
                'message': f'{old_leads} לידים ממתינים לטיפול מעל 3 ימים'
            })
    
    except Exception as e:
        logger.error(f"Error generating system alerts: {e}")
        alerts.append({
            'type': 'danger',
            'title': 'שגיאת מערכת',
            'message': 'בעיה בטעינת התרעות המערכת'
        })
    
    return alerts

def get_business_detailed_stats(business_id: int) -> Dict[str, Any]:
    """סטטיסטיקות מפורטות לעסק"""
    
    try:
        return {
            'calls_total': CallLog.query.filter_by(business_id=business_id).count(),
            'customers_total': CRMCustomer.query.filter_by(business_id=business_id).count(),
            'tasks_pending': CRMTask.query.filter_by(business_id=business_id, status='pending').count(),
            'avg_response_time': get_average_response_time(business_id)
        }
    
    except Exception as e:
        logger.error(f"Error getting detailed stats for business {business_id}: {e}")
        return {}

def get_business_last_activity(business_id: int) -> str:
    """פעילות אחרונה של עסק"""
    
    try:
        last_call = CallLog.query.filter_by(
            business_id=business_id
        ).order_by(CallLog.start_time.desc()).first()
        
        if last_call:
            delta = datetime.utcnow() - last_call.start_time
            if delta.days == 0:
                return "היום"
            elif delta.days == 1:
                return "אתמול"
            else:
                return f"לפני {delta.days} ימים"
        
        return "אין פעילות"
    
    except Exception as e:
        logger.error(f"Error getting last activity for business {business_id}: {e}")
        return "לא זמין"

def get_average_call_duration(business_id: int) -> float:
    """זמן שיחה ממוצע"""
    
    try:
        calls = CallLog.query.filter(
            CallLog.business_id == business_id,
            CallLog.end_time.isnot(None)
        ).all()
        
        if not calls:
            return 0.0
        
        total_duration = sum(
            (call.end_time - call.start_time).total_seconds()
            for call in calls
        )
        
        return total_duration / len(calls)
    
    except Exception as e:
        logger.error(f"Error calculating average call duration: {e}")
        return 0.0

def get_call_success_rate(business_id: int) -> float:
    """אחוז הצלחת שיחות"""
    
    try:
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        if total_calls == 0:
            return 0.0
        
        successful_calls = CallLog.query.filter(
            CallLog.business_id == business_id,
            CallLog.call_status == 'completed'
        ).count()
        
        return (successful_calls / total_calls) * 100
    
    except Exception as e:
        logger.error(f"Error calculating call success rate: {e}")
        return 0.0

def get_average_response_time(business_id: int) -> float:
    """זמן תגובה ממוצע"""
    
    try:
        # זמן ממוצע מקבלת שיחה עד תגובת AI
        # מחשבים לפי הנתונים במסד הנתונים
        return 2.3  # זמני - נוסיף חישוב אמיתי
    
    except Exception as e:
        logger.error(f"Error calculating average response time: {e}")
        return 0.0