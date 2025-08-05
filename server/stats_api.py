"""
Statistics API endpoints for React Dashboard
API נקודות עבור סטטיסטיקות ודשבורד עם React
"""
from flask import Blueprint, request, jsonify
from app import db
from models import Business, CRMCustomer, CallLog, WhatsAppConversation, DigitalSignature, Proposal, Invoice, CRMTask
from auth import login_required, AuthService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Create Stats API Blueprint
stats_api_bp = Blueprint('stats_api', __name__, url_prefix='/api/stats')

@stats_api_bp.route('/overview', methods=['GET'])
@login_required
def get_overview_stats():
    """קבלת סטטיסטיקות כלליות עבור Dashboard"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה לגשת לסטטיסטיקות'}), 403
        
        # תאריכים לסטטיסטיקות
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        stats = {}
        
        if current_user.role == 'admin':
            # סטטיסטיקות מנהל - כל המערכת
            stats = {
                'businesses': {
                    'total': Business.query.count(),
                    'active': Business.query.filter_by(is_active=True).count()
                },
                'customers': {
                    'total': CRMCustomer.query.count(),
                    'this_month': CRMCustomer.query.filter(CRMCustomer.created_at >= month_ago).count()
                },
                'calls': {
                    'total': CallLog.query.count(),
                    'today': CallLog.query.filter(CallLog.created_at >= today).count(),
                    'this_week': CallLog.query.filter(CallLog.created_at >= week_ago).count()
                },
                'whatsapp': {
                    'conversations': WhatsAppConversation.query.count(),
                    'active': WhatsAppConversation.query.filter_by(status='active').count()
                },
                'signatures': {
                    'total': DigitalSignature.query.count(),
                    'signed': DigitalSignature.query.filter_by(status='signed').count(),
                    'pending': DigitalSignature.query.filter_by(status='pending').count()
                },
                'proposals': {
                    'total': Proposal.query.count(),
                    'accepted': Proposal.query.filter_by(status='accepted').count(),
                    'pending': Proposal.query.filter_by(status='pending').count()
                },
                'invoices': {
                    'total': Invoice.query.count(),
                    'paid': Invoice.query.filter_by(status='paid').count(),
                    'pending': Invoice.query.filter_by(status='pending').count()
                },
                'tasks': {
                    'total': CRMTask.query.count(),
                    'completed': CRMTask.query.filter_by(status='completed').count(),
                    'pending': CRMTask.query.filter_by(status='pending').count()
                }
            }
        else:
            # סטטיסטיקות עסק ספציפי
            business_id = current_user.business_id if current_user else None
            if not business_id:
                return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
            
            stats = {
                'customers': {
                    'total': CRMCustomer.query.filter_by(business_id=business_id).count(),
                    'this_month': CRMCustomer.query.filter(
                        CRMCustomer.business_id == business_id,
                        CRMCustomer.created_at >= month_ago
                    ).count()
                },
                'calls': {
                    'total': CallLog.query.filter_by(business_id=business_id).count(),
                    'today': CallLog.query.filter(
                        CallLog.business_id == business_id,
                        CallLog.created_at >= today
                    ).count(),
                    'this_week': CallLog.query.filter(
                        CallLog.business_id == business_id,
                        CallLog.created_at >= week_ago
                    ).count()
                },
                'whatsapp': {
                    'conversations': WhatsAppConversation.query.filter_by(business_id=business_id).count(),
                    'active': WhatsAppConversation.query.filter_by(
                        business_id=business_id, 
                        status='active'
                    ).count()
                },
                'signatures': {
                    'total': DigitalSignature.query.filter_by(business_id=business_id).count(),
                    'signed': DigitalSignature.query.filter_by(
                        business_id=business_id, 
                        status='signed'
                    ).count(),
                    'pending': DigitalSignature.query.filter_by(
                        business_id=business_id, 
                        status='pending'
                    ).count()
                },
                'proposals': {
                    'total': Proposal.query.filter_by(business_id=business_id).count(),
                    'accepted': Proposal.query.filter_by(
                        business_id=business_id, 
                        status='accepted'
                    ).count(),
                    'pending': Proposal.query.filter_by(
                        business_id=business_id, 
                        status='pending'
                    ).count()
                },
                'invoices': {
                    'total': Invoice.query.filter_by(business_id=business_id).count(),
                    'paid': Invoice.query.filter_by(
                        business_id=business_id, 
                        status='paid'
                    ).count(),
                    'pending': Invoice.query.filter_by(
                        business_id=business_id, 
                        status='pending'
                    ).count()
                },
                'tasks': {
                    'total': CRMTask.query.filter_by(business_id=business_id).count(),
                    'completed': CRMTask.query.filter_by(
                        business_id=business_id, 
                        status='completed'
                    ).count(),
                    'pending': CRMTask.query.filter_by(
                        business_id=business_id, 
                        status='pending'
                    ).count()
                }
            }
        
        # חישוב סכומים כספיים
        financial_stats = {}
        
        if current_user.role == 'admin':
            # סכומים כוללים
            invoices = Invoice.query.all()
            proposals = Proposal.query.filter_by(status='accepted').all()
        else:
            # סכומים לעסק ספציפי
            invoices = Invoice.query.filter_by(business_id=business_id).all()
            proposals = Proposal.query.filter_by(business_id=business_id, status='accepted').all()
        
        financial_stats = {
            'invoices': {
                'total_amount': sum([float(i.amount) for i in invoices if i.amount]),
                'paid_amount': sum([float(i.amount) for i in invoices if i.amount and i.status == 'paid']),
                'pending_amount': sum([float(i.amount) for i in invoices if i.amount and i.status == 'pending'])
            },
            'proposals': {
                'total_value': sum([float(p.amount) for p in proposals if p.amount])
            }
        }
        
        stats['financial'] = financial_stats
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting overview stats: {e}")
        return jsonify({'error': 'שגיאה בטעינת סטטיסטיקות'}), 500

@stats_api_bp.route('/trends', methods=['GET'])
@login_required
def get_trends():
    """קבלת נתוני מגמות לגרפים"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה לגשת למגמות'}), 403
        
        # נתונים לשבועיים האחרונים
        days = []
        today = datetime.utcnow().date()
        
        for i in range(14):
            day = today - timedelta(days=i)
            days.append(day)
        
        days.reverse()  # מיון מהישן לחדש
        
        trends = {
            'calls': [],
            'customers': [],
            'tasks': []
        }
        
        for day in days:
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            if current_user.role == 'admin':
                # נתונים כוללים
                daily_calls = CallLog.query.filter(
                    CallLog.created_at >= day_start,
                    CallLog.created_at <= day_end
                ).count()
                
                daily_customers = CRMCustomer.query.filter(
                    CRMCustomer.created_at >= day_start,
                    CRMCustomer.created_at <= day_end
                ).count()
                
                daily_tasks = CRMTask.query.filter(
                    CRMTask.created_at >= day_start,
                    CRMTask.created_at <= day_end
                ).count()
            else:
                # נתונים לעסק ספציפי
                business_id = current_user.business_id
                
                daily_calls = CallLog.query.filter(
                    CallLog.business_id == business_id,
                    CallLog.created_at >= day_start,
                    CallLog.created_at <= day_end
                ).count()
                
                daily_customers = CRMCustomer.query.filter(
                    CRMCustomer.business_id == business_id,
                    CRMCustomer.created_at >= day_start,
                    CRMCustomer.created_at <= day_end
                ).count()
                
                daily_tasks = CRMTask.query.filter(
                    CRMTask.business_id == business_id,
                    CRMTask.created_at >= day_start,
                    CRMTask.created_at <= day_end
                ).count()
            
            trends['calls'].append({
                'date': day.isoformat(),
                'count': daily_calls
            })
            
            trends['customers'].append({
                'date': day.isoformat(),
                'count': daily_customers
            })
            
            trends['tasks'].append({
                'date': day.isoformat(),
                'count': daily_tasks
            })
        
        return jsonify({
            'success': True,
            'trends': trends,
            'period': f"{days[0].isoformat()} to {days[-1].isoformat()}"
        })
        
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return jsonify({'error': 'שגיאה בטעינת מגמות'}), 500