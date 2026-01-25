"""
Push Notifications API Routes

Endpoints for managing push notification subscriptions:
- GET /api/push/vapid-public-key - Get VAPID public key for client
- POST /api/push/subscribe - Register a new push subscription
- POST /api/push/unsubscribe - Unregister a push subscription
- POST /api/push/test - Send a test push notification
"""
from flask import Blueprint, jsonify, request, g
from server.auth_api import require_api_auth
from server.db import db
from server.models_sql import PushSubscription
from server.services.push.webpush_sender import get_webpush_sender, PushPayload
from server.services.notifications.dispatcher import dispatch_push_to_user
import logging
from datetime import datetime

log = logging.getLogger(__name__)

push_bp = Blueprint("push_bp", __name__)


@push_bp.route("/api/push/vapid-public-key", methods=["GET"])
@require_api_auth()
def get_vapid_public_key():
    """
    GET /api/push/vapid-public-key
    Returns the VAPID public key for client-side subscription
    """
    try:
        sender = get_webpush_sender()
        public_key = sender.get_public_key()
        
        if not public_key:
            return jsonify({
                "success": False,
                "error": "Push notifications not configured"
            }), 503
        
        return jsonify({
            "success": True,
            "publicKey": public_key
        })
        
    except Exception as e:
        log.error(f"Error getting VAPID key: {e}")
        return jsonify({"error": "Internal error"}), 500


@push_bp.route("/api/push/subscribe", methods=["POST"])
@require_api_auth()
def subscribe_push():
    """
    POST /api/push/subscribe
    Register a new push subscription
    
    Body:
    {
        "subscription": {
            "endpoint": "https://...",
            "keys": {
                "p256dh": "...",
                "auth": "..."
            }
        },
        "deviceInfo": "Mozilla/5.0..."  (optional)
    }
    """
    try:
        user = g.user
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        
        user_id = user.get('id')
        business_id = g.tenant
        
        if not business_id:
            return jsonify({"error": "No business context"}), 403
        
        data = request.get_json()
        if not data or 'subscription' not in data:
            return jsonify({"error": "Missing subscription data"}), 400
        
        subscription = data['subscription']
        endpoint = subscription.get('endpoint')
        keys = subscription.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')
        device_info = data.get('deviceInfo', '')[:512]  # Limit length
        
        if not endpoint:
            return jsonify({"error": "Missing endpoint"}), 400
        if not p256dh or not auth:
            return jsonify({"error": "Missing encryption keys"}), 400
        
        # Check if subscription already exists (upsert)
        existing = PushSubscription.query.filter_by(
            user_id=user_id,
            endpoint=endpoint
        ).first()
        
        if existing:
            # Update existing subscription
            existing.business_id = business_id
            existing.p256dh = p256dh
            existing.auth = auth
            existing.device_info = device_info
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            log.info(f"Updated push subscription {existing.id} for user {user_id}")
        else:
            # Create new subscription
            new_sub = PushSubscription(
                business_id=business_id,
                user_id=user_id,
                channel='webpush',
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                device_info=device_info,
                is_active=True
            )
            db.session.add(new_sub)
            log.info(f"Created new push subscription for user {user_id}")
        
        # Set user's push_enabled preference to True when subscribing
        from server.models_sql import User
        user_record = User.query.get(user_id)
        if user_record:
            user_record.push_enabled = True
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Push subscription registered"
        })
        
    except Exception as e:
        log.error(f"Error subscribing to push: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal error"}), 500


@push_bp.route("/api/push/unsubscribe", methods=["POST"])
@require_api_auth()
def unsubscribe_push():
    """
    POST /api/push/unsubscribe
    Unregister a push subscription
    
    Body:
    {
        "endpoint": "https://..."
    }
    """
    try:
        user = g.user
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        
        user_id = user.get('id')
        
        data = request.get_json()
        endpoint = data.get('endpoint') if data else None
        
        if not endpoint:
            return jsonify({"error": "Missing endpoint"}), 400
        
        # Find and deactivate the subscription
        subscription = PushSubscription.query.filter_by(
            user_id=user_id,
            endpoint=endpoint
        ).first()
        
        if subscription:
            subscription.is_active = False
            subscription.updated_at = datetime.utcnow()
            log.info(f"Deactivated push subscription {subscription.id} for user {user_id}")
        
        # Set user's push_enabled preference to False when unsubscribing
        from server.models_sql import User
        user_record = User.query.get(user_id)
        if user_record:
            user_record.push_enabled = False
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Push subscription unregistered"
        })
        
    except Exception as e:
        log.error(f"Error unsubscribing from push: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal error"}), 500


@push_bp.route("/api/push/toggle", methods=["POST"])
@require_api_auth()
def toggle_push():
    """
    POST /api/push/toggle
    Toggle user's push notification preference
    
    Body:
    {
        "enabled": true/false
    }
    
    This is separate from subscribe/unsubscribe:
    - subscribe/unsubscribe: Manage device subscriptions
    - toggle: Manage user preference
    
    If user toggles OFF: Deactivate all their subscriptions
    If user toggles ON: Set preference but require re-subscription
    """
    try:
        user = g.user
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        
        user_id = user.get('id')
        business_id = g.tenant
        
        if not business_id:
            return jsonify({"error": "No business context"}), 403
        
        data = request.get_json()
        if data is None or 'enabled' not in data:
            return jsonify({"error": "Missing 'enabled' field"}), 400
        
        enabled = bool(data['enabled'])
        
        # Get user record
        from server.models_sql import User
        user_record = User.query.get(user_id)
        if not user_record:
            return jsonify({"error": "User not found"}), 404
        
        # Update user's preference
        user_record.push_enabled = enabled
        
        # If disabling, deactivate all user's subscriptions for this business
        if not enabled:
            PushSubscription.query.filter_by(
                user_id=user_id,
                business_id=business_id,
                is_active=True
            ).update(
                {PushSubscription.is_active: False},
                synchronize_session=False
            )
            log.info(f"Disabled push for user {user_id} - deactivated subscriptions")
        else:
            log.info(f"Enabled push preference for user {user_id}")
        
        db.session.commit()
        
        # Count active subscriptions
        subscription_count = PushSubscription.query.filter_by(
            user_id=user_id,
            business_id=business_id,
            is_active=True
        ).count()
        
        # Compute effective enabled state
        effective_enabled = enabled and subscription_count > 0
        
        return jsonify({
            "success": True,
            "push_enabled": enabled,
            "active_subscriptions_count": subscription_count,
            "enabled": effective_enabled,
            "message": "התראות הופעלו" if enabled else "התראות בוטלו"
        })
        
    except Exception as e:
        log.error(f"Error toggling push: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal error"}), 500


@push_bp.route("/api/push/test", methods=["POST"])
@require_api_auth()
def send_test_push():
    """
    POST /api/push/test
    Send a test push notification to the current user
    
    For testing/debugging purposes
    
    Returns:
    - success: true if at least one notification sent
    - error: specific error code if failed:
      - "no_active_subscription": User has no active subscriptions
      - "subscription_expired_need_resubscribe": All subscriptions expired (410)
      - "push_disabled": User has disabled push notifications
    """
    try:
        user = g.user
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        
        user_id = user.get('id')
        business_id = g.tenant
        
        if not business_id:
            return jsonify({"error": "No business context"}), 403
        
        # Check if user has enabled push notifications
        from server.models_sql import User
        user_record = User.query.get(user_id)
        if not user_record or not user_record.push_enabled:
            return jsonify({
                "success": False,
                "error": "push_disabled",
                "message": "התראות מבוטלות. אנא הפעל אותן בהגדרות."
            }), 400
        
        # Check if user has any active subscriptions
        subscription_count = PushSubscription.query.filter_by(
            user_id=user_id,
            business_id=business_id,
            is_active=True
        ).count()
        
        if subscription_count == 0:
            return jsonify({
                "success": False,
                "error": "no_active_subscription",
                "message": "לא נמצאו מכשירים פעילים. אנא אשר התראות בדפדפן."
            }), 400
        
        # Send test notification
        payload = PushPayload(
            title="🔔 בדיקת התראות",
            body="ההתראות פועלות! תקבל התראות על פגישות, שיחות ועדכונים חשובים.",
            url="/app/settings",
            notification_type="test",
            business_id=business_id,
            tag="test_notification"
        )
        
        # Dispatch synchronously to get result
        from server.services.notifications.dispatcher import dispatch_push_sync
        result = dispatch_push_sync(user_id, business_id, payload)
        
        # If all subscriptions were deactivated due to 410, return specific error
        if result.deactivated > 0 and result.successful == 0:
            return jsonify({
                "success": False,
                "error": "subscription_expired_need_resubscribe",
                "message": "המנוי להתראות פג תוקף. אנא אשר מחדש התראות בדפדפן.",
                "result": {
                    "total": result.total_subscriptions,
                    "successful": result.successful,
                    "failed": result.failed,
                    "deactivated": result.deactivated
                }
            }), 400
        
        return jsonify({
            "success": result.successful > 0,
            "message": f"התראת בדיקה נשלחה ל-{result.successful} מתוך {result.total_subscriptions} מכשירים",
            "result": {
                "total": result.total_subscriptions,
                "successful": result.successful,
                "failed": result.failed,
                "deactivated": result.deactivated
            }
        })
        
    except Exception as e:
        log.error(f"Error sending test push: {e}")
        return jsonify({"error": "Internal error"}), 500


@push_bp.route("/api/push/status", methods=["GET"])
@require_api_auth()
def get_push_status():
    """
    GET /api/push/status
    Get push notification status for current user
    
    Returns comprehensive diagnostic info:
    - supported: True (backend always supports push)
    - vapid_configured: Whether VAPID keys are set
    - push_enabled: User's preference (True/False)
    - subscribed: Whether user has active subscriptions
    - active_subscriptions_count: Number of active subscriptions
    - enabled: Computed as push_enabled AND has_active_subscriptions
    - user_id: Current user ID
    - business_id: Current business ID
    """
    try:
        user = g.user
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        
        user_id = user.get('id')
        business_id = g.tenant
        
        # Get user's push preference from DB
        from server.models_sql import User
        user_record = User.query.get(user_id)
        push_enabled = user_record.push_enabled if user_record else True
        
        # Check if push is configured (VAPID keys present)
        sender = get_webpush_sender()
        vapid_configured = sender.is_configured
        
        # Count active subscriptions for this user in this business
        subscription_count = 0
        all_user_subscriptions = 0
        if business_id:
            subscription_count = PushSubscription.query.filter_by(
                user_id=user_id,
                business_id=business_id,
                is_active=True
            ).count()
        
        # Also count all user subscriptions (across businesses)
        all_user_subscriptions = PushSubscription.query.filter_by(
            user_id=user_id,
            is_active=True
        ).count()
        
        # Compute effective enabled state
        # enabled = user wants push AND has working subscription
        enabled = push_enabled and subscription_count > 0
        
        return jsonify({
            "success": True,
            "supported": True,  # Backend always supports push
            "vapid_configured": vapid_configured,
            "push_enabled": push_enabled,  # User preference
            "subscribed": subscription_count > 0,  # Has device subscription
            "active_subscriptions_count": subscription_count,
            "all_user_subscriptions": all_user_subscriptions,
            "enabled": enabled,  # Computed: preference AND subscription
            "user_id": user_id,
            "business_id": business_id,
            # Backwards compatibility (old field names for existing clients)
            "configured": vapid_configured,
            "subscriptionCount": subscription_count  # Same as active_subscriptions_count
        })
        
    except Exception as e:
        log.error(f"Error getting push status: {e}")
        return jsonify({"error": "Internal error"}), 500
