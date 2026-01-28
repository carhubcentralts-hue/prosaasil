"""
Push Notification Send Job

This job sends push notifications to user devices asynchronously.
Replaces threading.Thread approach with proper RQ queue processing.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def push_send_job(user_id: int, business_id: int, title: str, body: str, url: Optional[str] = None, data: Optional[dict] = None):
    """
    Send push notification to all active subscriptions for a user
    
    Args:
        user_id: Target user ID
        business_id: Business context
        title: Notification title
        body: Notification body
        url: Optional URL to navigate to
        data: Optional additional data
    
    This job is idempotent - duplicate notifications are handled by client-side deduplication.
    """
    logger.info(f"📬 [PUSH_JOB] Sending to user_id={user_id} business_id={business_id}")
    
    try:
        from server.services.push.webpush_sender import get_webpush_sender, PushPayload
        from flask import current_app
        
        # Create payload
        payload = PushPayload(
            title=title,
            body=body,
            url=url,
            data=data or {}
        )
        
        # Send in app context
        with current_app.app_context():
            from server.db import db
            from server.models_sql import PushSubscription
            
            # Get all active subscriptions for user
            subscriptions = PushSubscription.query.filter_by(
                user_id=user_id,
                business_id=business_id,
                is_active=True
            ).all()
            
            if not subscriptions:
                logger.info(f"📬 [PUSH_JOB] No active subscriptions for user_id={user_id}")
                return {'total': 0, 'successful': 0, 'failed': 0, 'deactivated': 0}
            
            logger.info(f"📬 [PUSH_JOB] Found {len(subscriptions)} subscriptions")
            
            sender = get_webpush_sender()
            successful = 0
            failed = 0
            deactivated = 0
            
            for subscription in subscriptions:
                try:
                    # Send push notification
                    sender.send(subscription, payload)
                    successful += 1
                    logger.debug(f"✅ Sent to subscription {subscription.id}")
                except Exception as e:
                    error_str = str(e).lower()
                    
                    # Deactivate subscription if it's invalid
                    if 'gone' in error_str or '410' in error_str or 'expired' in error_str or 'unsubscribed' in error_str:
                        subscription.is_active = False
                        deactivated += 1
                        logger.info(f"🗑️ Deactivated invalid subscription {subscription.id}: {e}")
                    else:
                        failed += 1
                        logger.warning(f"⚠️ Failed to send to subscription {subscription.id}: {e}")
            
            # Commit deactivations
            if deactivated > 0:
                db.session.commit()
            
            result = {
                'total': len(subscriptions),
                'successful': successful,
                'failed': failed,
                'deactivated': deactivated
            }
            
            logger.info(f"✅ [PUSH_JOB] Completed: {result}")
            return result
            
    except Exception as e:
        logger.error(f"❌ [PUSH_JOB] Failed: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise for RQ to handle retry
