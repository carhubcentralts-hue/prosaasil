from flask import Blueprint, request, jsonify
import json
# Note: Auth middleware should be imported based on your actual auth system

admin_advanced_bp = Blueprint('admin_advanced', __name__)

@admin_advanced_bp.route('/api/admin/customers', methods=['GET'])
def get_all_customers():
    """Get all customers across all businesses for admin"""
    try:
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        source = request.args.get('source', '')
        
        # Mock data for all customers - replace with actual database query
        mock_customers = [
            {
                'id': 1,
                'name': 'יוסי כהן',
                'phone': '050-1234567',
                'email': 'yossi@example.com',
                'source': 'WhatsApp',
                'status': 'active',
                'business_id': 1,
                'business_name': 'מכון היופי של שרה',
                'created_at': '2024-08-01T12:00:00Z'
            },
            {
                'id': 2,
                'name': 'רחל לוי',
                'phone': '052-7654321',
                'email': 'rachel@example.com',
                'source': 'טלפון',
                'status': 'pending',
                'business_id': 2,
                'business_name': 'חברת הביטוח הישראלית',
                'created_at': '2024-08-02T14:30:00Z'
            },
            {
                'id': 3,
                'name': 'דוד ישראלי',
                'phone': '054-9876543',
                'email': 'david@example.com',
                'source': 'אתר',
                'status': 'completed',
                'business_id': 1,
                'business_name': 'מכון היופי של שרה',
                'created_at': '2024-08-03T09:15:00Z'
            }
        ]
        
        # Apply filters
        filtered_customers = mock_customers
        if search:
            filtered_customers = [c for c in filtered_customers 
                                if search.lower() in c['name'].lower() or 
                                   search in c['phone'] or 
                                   search.lower() in c['email'].lower()]
        if status:
            filtered_customers = [c for c in filtered_customers if c['status'] == status]
        if source:
            filtered_customers = [c for c in filtered_customers if c['source'] == source]
        
        return jsonify({
            'customers': filtered_customers,
            'total': len(filtered_customers)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_advanced_bp.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Get comprehensive stats for admin across all businesses"""
    try:
        from utils import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # תיקון מוחלט: שליפה ישירה של נתוני העסקים
        cur.execute("SELECT name, business_type, COALESCE(is_active, true) as is_active FROM business")
        business_rows = cur.fetchall()
        
        totalBusinesses = len(business_rows)
        activeBusinesses = sum(1 for row in business_rows if row[2])  # Count active businesses
        
        # לוג לבדיקה
        logger.info(f"Admin stats: Found {totalBusinesses} total, {activeBusinesses} active businesses")
        
        # אולוז לבדוק שהחיבור עובד
        conn.commit()
        
        # אין צורך בעדכון - הנתונים נמצאים
        
        # ספירת שיחות (בדיקה אם הטבלה קיימת)
        try:
            cur.execute("SELECT COUNT(*) FROM call_log")
            calls_result = cur.fetchone()
            totalCalls = calls_result[0] if calls_result else 0
        except Exception:
            try:
                cur.execute("SELECT COUNT(*) FROM call_logs") 
                calls_result = cur.fetchone()
                totalCalls = calls_result[0] if calls_result else 0
            except Exception:
                totalCalls = 0
        
        # ספירת משתמשים
        cur.execute("SELECT COUNT(*) FROM users")
        users_result = cur.fetchone()
        totalUsers = users_result[0] if users_result else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'activeBusinesses': activeBusinesses,
            'totalBusinesses': totalBusinesses,
            'totalCalls': totalCalls,
            'totalUsers': totalUsers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_advanced_bp.route('/api/admin/business/<int:business_id>/takeover', methods=['POST'])
def takeover_business(business_id):
    """Allow admin to takeover a business context"""
    try:
        # In a real implementation, this would:
        # 1. Validate admin permissions
        # 2. Create an impersonation session
        # 3. Log the takeover action
        # 4. Return business context data
        
        mock_business_data = {
            'business_id': business_id,
            'name': f'עסק מספר {business_id}',
            'access_token': 'mock_business_token',
            'permissions': ['crm', 'whatsapp', 'calls'],
            'takeover_timestamp': '2024-08-04T10:00:00Z'
        }
        
        return jsonify({
            'success': True,
            'business': mock_business_data,
            'message': f'השתלטות על עסק {business_id} הושלמה בהצלחה'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_advanced_bp.route('/api/admin/return', methods=['POST'])
def return_to_admin():
    """Return from business context to admin context"""
    try:
        # Clear business impersonation and return to admin
        return jsonify({
            'success': True,
            'message': 'חזרה למצב מנהל הושלמה בהצלחה'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500