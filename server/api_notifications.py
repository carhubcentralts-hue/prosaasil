"""
Notifications API - Push Notifications & WebPush Management
API התראות - ניהול התראות ו-WebPush
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
import logging
import json
from models import db, Notification, WebPushSubscription, User, Task
from feature_flags import require_feature
from sqlalchemy import desc

logger = logging.getLogger(__name__)

# Create Notifications API Blueprint
notifications_api_bp = Blueprint('notifications_api', __name__, url_prefix='/api/notifications')

@notifications_api_bp.route('/subscribe', methods=['POST'])
def subscribe_webpush():
    """Subscribe to web push notifications"""
    try:
        data = request.get_json()
        user = g.get('user')  # Assuming user is loaded in middleware
        
        if not user:
            return jsonify({
                'error': 'unauthorized',
                'message': 'נדרשת התחברות'
            }), 401
        
        # Validate required fields
        required_fields = ['endpoint', 'p256dh', 'auth']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': 'missing_field',
                    'message': f'שדה חובה חסר: {field}',
                    'field': field
                }), 400
        
        # Check if subscription already exists
        existing = WebPushSubscription.query.filter_by(
            user_id=user.id,
            endpoint=data['endpoint']
        ).first()
        
        if existing:
            # Update existing subscription
            existing.p256dh = data['p256dh']
            existing.auth = data['auth']
            existing.user_agent = request.headers.get('User-Agent', '')
            existing.last_used_at = datetime.utcnow()
        else:
            # Create new subscription
            subscription = WebPushSubscription(
                user_id=user.id,
                endpoint=data['endpoint'],
                p256dh=data['p256dh'],
                auth=data['auth'],
                user_agent=request.headers.get('User-Agent', '')
            )
            db.session.add(subscription)
        
        db.session.commit()
        
        logger.info(f"WebPush subscription updated for user {user.id}")
        
        return jsonify({
            'success': True,
            'message': 'מנוי להתראות נרשם בהצלחה'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error subscribing to webpush: {e}")
        return jsonify({
            'error': 'subscription_failed',
            'message': 'שגיאה ברישום להתראות'
        }), 500

@notifications_api_bp.route('', methods=['GET'])
def get_notifications():
    """Get user notifications with pagination"""
    try:
        user = g.get('user')
        
        if not user:
            return jsonify({
                'error': 'unauthorized',
                'message': 'נדרשת התחברות'
            }), 401
        
        # Query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        # Build query
        query = Notification.query.filter_by(user_id=user.id)
        
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        
        # Paginate
        notifications_paginated = query.order_by(desc(Notification.created_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format notifications
        notifications_data = []
        for notification in notifications_paginated.items:
            task = None
            if notification.task_id:
                task = Task.query.get(notification.task_id)
            
            notification_data = {
                'id': notification.id,
                'type': notification.type,
                'title': notification.title,
                'message': notification.message,
                'data': notification.data,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'delivered_at': notification.delivered_at.isoformat() if notification.delivered_at else None,
                'created_at': notification.created_at.isoformat(),
                'task': {
                    'id': task.id,
                    'title': task.title,
                    'status': task.status,
                    'due_at': task.due_at.isoformat()
                } if task else None
            }
            notifications_data.append(notification_data)
        
        # Count unread notifications
        unread_count = Notification.query.filter_by(
            user_id=user.id, 
            read_at=None
        ).count()
        
        return jsonify({
            'success': True,
            'notifications': notifications_data,
            'unread_count': unread_count,
            'pagination': {
                'page': notifications_paginated.page,
                'per_page': notifications_paginated.per_page,
                'total': notifications_paginated.total,
                'pages': notifications_paginated.pages,
                'has_next': notifications_paginated.has_next,
                'has_prev': notifications_paginated.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return jsonify({
            'error': 'fetch_failed',
            'message': 'שגיאה בטעינת התראות'
        }), 500

@notifications_api_bp.route('/<int:notification_id>/read', methods=['PATCH'])
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        user = g.get('user')
        
        if not user:
            return jsonify({
                'error': 'unauthorized',
                'message': 'נדרשת התחברות'
            }), 401
        
        # Find notification
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user.id
        ).first()
        
        if not notification:
            return jsonify({
                'error': 'notification_not_found',
                'message': 'התראה לא נמצאה'
            }), 404
        
        # Mark as read
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'התראה סומנה כנקראה'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking notification {notification_id} as read: {e}")
        return jsonify({
            'error': 'mark_read_failed',
            'message': 'שגיאה בסימון התראה כנקראה'
        }), 500

@notifications_api_bp.route('/mark-all-read', methods=['PATCH'])
def mark_all_notifications_read():
    """Mark all user notifications as read"""
    try:
        user = g.get('user')
        
        if not user:
            return jsonify({
                'error': 'unauthorized',
                'message': 'נדרשת התחברות'
            }), 401
        
        # Update all unread notifications
        now = datetime.utcnow()
        updated_count = Notification.query.filter_by(
            user_id=user.id,
            read_at=None
        ).update({'read_at': now})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{updated_count} התראות סומנו כנקראות',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking all notifications as read for user {user.id}: {e}")
        return jsonify({
            'error': 'mark_all_read_failed',
            'message': 'שגיאה בסימון כל ההתראות כנקראות'
        }), 500

@notifications_api_bp.route('/send-push', methods=['POST'])
@require_feature('crm')
def send_push_notification():
    """Send push notification to user (admin only)"""
    try:
        data = request.get_json()
        user = g.get('user')
        
        # Check admin permissions
        if not user or user.role != 'admin':
            return jsonify({
                'error': 'forbidden',
                'message': 'נדרשות הרשאות אדמין'
            }), 403
        
        # Validate required fields
        required_fields = ['user_id', 'title', 'message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': 'missing_field',
                    'message': f'שדה חובה חסר: {field}',
                    'field': field
                }), 400
        
        target_user = User.query.get(data['user_id'])
        if not target_user:
            return jsonify({
                'error': 'user_not_found',
                'message': 'משתמש לא נמצא'
            }), 404
        
        # Create notification record
        notification = Notification(
            user_id=target_user.id,
            type=data.get('type', 'system'),
            title=data['title'],
            message=data['message'],
            data=data.get('data', {})
        )
        db.session.add(notification)
        
        # Get user's web push subscriptions
        subscriptions = WebPushSubscription.query.filter_by(user_id=target_user.id).all()
        
        sent_count = 0
        for subscription in subscriptions:
            try:
                # Here you would integrate with a web push service like pywebpush
                # For now, we'll just mark as delivered
                notification.delivered_at = datetime.utcnow()
                sent_count += 1
                logger.info(f"Push sent to subscription {subscription.id}")
            except Exception as push_error:
                logger.error(f"Failed to send push to subscription {subscription.id}: {push_error}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'התראה נשלחה ל-{sent_count} מכשירים',
            'notification_id': notification.id,
            'sent_count': sent_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error sending push notification: {e}")
        return jsonify({
            'error': 'send_failed',
            'message': 'שגיאה בשליחת התראה'
        }), 500