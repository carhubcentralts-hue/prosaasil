"""
AgentLocator v42 - Analytics & Reports Routes
דוחות ואנליטיקות מתקדמת למערכת
"""

from flask import Blueprint, jsonify, request, Response
import logging
from datetime import datetime, timedelta, date
from utils import get_db_connection
import csv
from io import StringIO
import json

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/business/<int:business_id>/analytics', methods=['GET'])
def get_business_analytics(business_id):
    """אנליטיקות מקיפה עבור עסק"""
    try:
        # פרמטרים מהקוואיסטרינג
        period = request.args.get('period', '30d')  # 7d, 30d, 90d, 1y
        
        # חישוב תאריכים
        end_date = datetime.now()
        if period == '7d':
            start_date = end_date - timedelta(days=7)
        elif period == '30d':
            start_date = end_date - timedelta(days=30)
        elif period == '90d':
            start_date = end_date - timedelta(days=90)
        elif period == '1y':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        analytics = {}
        
        # סטטיסטיקות לקוחות
        cur.execute("""
            SELECT 
                COUNT(*) as total_customers,
                COUNT(CASE WHEN created_at >= %s THEN 1 END) as new_customers,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_customers
            FROM customers 
            WHERE business_id = %s
        """, (start_date, business_id))
        
        customer_stats = cur.fetchone()
        analytics['customers'] = {
            'total': customer_stats[0],
            'new_in_period': customer_stats[1],
            'active': customer_stats[2],
            'conversion_rate': round((customer_stats[2] / customer_stats[0] * 100), 2) if customer_stats[0] > 0 else 0
        }
        
        # סטטיסטיקות שיחות
        try:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_calls,
                    AVG(duration) as avg_duration,
                    COUNT(CASE WHEN ai_response IS NOT NULL THEN 1 END) as ai_handled
                FROM call_log 
                WHERE business_id = %s AND created_at BETWEEN %s AND %s
            """, (business_id, start_date, end_date))
            
            call_stats = cur.fetchone()
            analytics['calls'] = {
                'total': call_stats[0] or 0,
                'avg_duration': round(float(call_stats[1]), 2) if call_stats[1] else 0,
                'ai_handled': call_stats[2] or 0,
                'ai_success_rate': round((call_stats[2] / call_stats[0] * 100), 2) if call_stats[0] > 0 else 0
            }
        except Exception as e:
            logger.warning(f"Call stats error: {e}")
            analytics['calls'] = {'total': 0, 'avg_duration': 0, 'ai_handled': 0, 'ai_success_rate': 0}
        
        # סטטיסטיקות הודעות WhatsApp
        try:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(CASE WHEN direction = 'inbound' THEN 1 END) as inbound,
                    COUNT(CASE WHEN direction = 'outbound' THEN 1 END) as outbound
                FROM whatsapp_messages 
                WHERE business_id = %s AND created_at BETWEEN %s AND %s
            """, (business_id, start_date, end_date))
            
            msg_stats = cur.fetchone()
            analytics['whatsapp'] = {
                'total_messages': msg_stats[0] or 0,
                'inbound': msg_stats[1] or 0,
                'outbound': msg_stats[2] or 0,
                'response_rate': round((msg_stats[2] / msg_stats[1] * 100), 2) if msg_stats[1] > 0 else 0
            }
        except Exception as e:
            logger.warning(f"WhatsApp stats error: {e}")
            analytics['whatsapp'] = {'total_messages': 0, 'inbound': 0, 'outbound': 0, 'response_rate': 0}
        
        # טרנד יומי
        cur.execute("""
            SELECT 
                DATE(created_at) as day,
                COUNT(*) as customers_count
            FROM customers 
            WHERE business_id = %s AND created_at BETWEEN %s AND %s
            GROUP BY DATE(created_at)
            ORDER BY day
        """, (business_id, start_date, end_date))
        
        daily_trend = []
        for row in cur.fetchall():
            daily_trend.append({
                'date': row[0].isoformat(),
                'customers': row[1]
            })
        
        analytics['daily_trend'] = daily_trend
        
        # מקורות הגעה
        cur.execute("""
            SELECT source, COUNT(*) as count
            FROM customers 
            WHERE business_id = %s AND created_at BETWEEN %s AND %s
            GROUP BY source
            ORDER BY count DESC
        """, (business_id, start_date, end_date))
        
        sources = {}
        for row in cur.fetchall():
            sources[row[0] or 'unknown'] = row[1]
        
        analytics['sources'] = sources
        
        cur.close()
        conn.close()
        
        return jsonify({
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'analytics': analytics
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        return jsonify({'error': 'שגיאה ביצירת הדוח'}), 500

@reports_bp.route('/customers/export', methods=['GET'])
def export_customers():
    """ייצוא רשימת לקוחות ל-CSV"""
    try:
        business_id = request.args.get('business_id')
        format_type = request.args.get('format', 'csv')  # csv, json, xlsx
        
        if not business_id:
            return jsonify({'error': 'נדרש מזהה עסק'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT name, email, phone, source, status, created_at,
                   last_contact, notes
            FROM customers 
            WHERE business_id = %s
            ORDER BY created_at DESC
        """, (business_id,))
        
        customers = cur.fetchall()
        cur.close()
        conn.close()
        
        if format_type == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # כותרות עבריות
            writer.writerow(['שם', 'אימייל', 'טלפון', 'מקור', 'סטטוס', 'תאריך יצירה', 'קשר אחרון', 'הערות'])
            
            for customer in customers:
                writer.writerow([
                    customer[0] or '',
                    customer[1] or '',
                    customer[2] or '',
                    customer[3] or '',
                    customer[4] or '',
                    customer[5].strftime('%Y-%m-%d') if customer[5] else '',
                    customer[6].strftime('%Y-%m-%d') if customer[6] else '',
                    customer[7] or ''
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                csv_content,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=customers_{business_id}.csv'}
            )
            
        elif format_type == 'json':
            customers_json = []
            for customer in customers:
                customers_json.append({
                    'name': customer[0],
                    'email': customer[1],
                    'phone': customer[2],
                    'source': customer[3],
                    'status': customer[4],
                    'created_at': customer[5].isoformat() if customer[5] else None,
                    'last_contact': customer[6].isoformat() if customer[6] else None,
                    'notes': customer[7]
                })
            
            return Response(
                json.dumps(customers_json, ensure_ascii=False, indent=2),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename=customers_{business_id}.json'}
            )
        
        else:
            return jsonify({'error': 'פורמט לא נתמך'}), 400
        
    except Exception as e:
        logger.error(f"Error exporting customers: {e}")
        return jsonify({'error': 'שגיאה בייצוא הנתונים'}), 500

@reports_bp.route('/revenue/<int:business_id>', methods=['GET'])
def revenue_report(business_id):
    """דוח הכנסות"""
    try:
        period = request.args.get('period', '12m')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # דוח הכנסות לפי חודשים
        cur.execute("""
            SELECT 
                DATE_TRUNC('month', created_at) as month,
                SUM(amount) as revenue,
                COUNT(*) as invoices_count
            FROM invoices 
            WHERE business_id = %s 
            AND status = 'paid'
            AND created_at >= NOW() - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY month
        """, (business_id,))
        
        monthly_revenue = []
        total_revenue = 0
        
        for row in cur.fetchall():
            month_revenue = float(row[1]) if row[1] else 0
            total_revenue += month_revenue
            
            monthly_revenue.append({
                'month': row[0].strftime('%Y-%m'),
                'revenue': month_revenue,
                'invoices_count': row[2]
            })
        
        # הכנסות חזויות
        cur.execute("""
            SELECT SUM(amount) as pending_revenue
            FROM invoices 
            WHERE business_id = %s 
            AND status IN ('pending', 'sent')
        """, (business_id,))
        
        pending_result = cur.fetchone()
        pending_revenue = float(pending_result[0]) if pending_result[0] else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'total_revenue': total_revenue,
            'pending_revenue': pending_revenue,
            'monthly_breakdown': monthly_revenue,
            'average_monthly': total_revenue / 12 if total_revenue > 0 else 0
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating revenue report: {e}")
        return jsonify({'error': 'שגיאה ביצירת דוח הכנסות'}), 500

@reports_bp.route('/performance/<int:business_id>', methods=['GET'])
def performance_metrics(business_id):
    """מדדי ביצוע ו-KPIs"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # זמן מענה ממוצע
        cur.execute("""
            SELECT AVG(EXTRACT(EPOCH FROM (first_response_at - created_at))/60) as avg_response_time
            FROM customers 
            WHERE business_id = %s 
            AND first_response_at IS NOT NULL
            AND created_at >= NOW() - INTERVAL '30 days'
        """, (business_id,))
        
        avg_response = cur.fetchone()
        avg_response_time = round(float(avg_response[0]), 2) if avg_response[0] else 0
        
        # שביעות רצון לקוחות
        cur.execute("""
            SELECT AVG(rating) as avg_rating, COUNT(*) as rating_count
            FROM customer_feedback 
            WHERE business_id = %s
            AND created_at >= NOW() - INTERVAL '30 days'
        """, (business_id,))
        
        rating_result = cur.fetchone()
        avg_rating = round(float(rating_result[0]), 2) if rating_result[0] else 0
        rating_count = rating_result[1] if rating_result[1] else 0
        
        # שיעור המרה
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(*) as total
            FROM customers 
            WHERE business_id = %s
            AND created_at >= NOW() - INTERVAL '30 days'
        """, (business_id,))
        
        conversion_result = cur.fetchone()
        conversion_rate = round((conversion_result[0] / conversion_result[1] * 100), 2) if conversion_result[1] > 0 else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'avg_response_time_minutes': avg_response_time,
            'customer_satisfaction': {
                'avg_rating': avg_rating,
                'total_ratings': rating_count
            },
            'conversion_rate_percent': conversion_rate,
            'performance_grade': calculate_performance_grade(avg_response_time, avg_rating, conversion_rate)
        }), 200
        
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        return jsonify({'error': 'שגיאה בחישוב מדדי ביצוע'}), 500

def calculate_performance_grade(response_time, rating, conversion_rate):
    """חישוב ציון ביצוע כללי"""
    score = 0
    
    # זמן מענה (עד 40 נקודות)
    if response_time <= 5:
        score += 40
    elif response_time <= 15:
        score += 30
    elif response_time <= 30:
        score += 20
    else:
        score += 10
    
    # שביעות רצון (עד 40 נקודות)
    score += (rating / 5.0) * 40
    
    # שיעור המרה (עד 20 נקודות)
    if conversion_rate >= 50:
        score += 20
    elif conversion_rate >= 30:
        score += 15
    elif conversion_rate >= 20:
        score += 10
    else:
        score += 5
    
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    else:
        return 'D'