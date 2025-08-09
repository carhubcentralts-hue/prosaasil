from flask import Blueprint, jsonify, session
from .auth import admin_required
from .models import db, User, Business, CallLog

admin_stats_bp = Blueprint('admin_stats', __name__)

@admin_stats_bp.route('/api/admin/stats', methods=['GET'])
@admin_required
def get_admin_stats():
    try:
        # Get basic stats
        total_businesses = Business.query.count()
        total_users = User.query.count()
        total_calls = CallLog.query.count()
        active_users = User.query.filter_by(active=True).count() if hasattr(User, 'active') else total_users
        
        return jsonify({
            'totalBusinesses': total_businesses,
            'totalUsers': total_users,
            'totalCalls': total_calls,
            'activeUsers': active_users
        })
    except Exception as e:
        return jsonify({'error': 'Failed to fetch stats'}), 500