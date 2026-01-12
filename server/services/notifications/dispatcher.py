"""
Notification Dispatcher - Send push notifications to user devices

This is the "additional channel" layer that wraps push notifications around
the existing in-app notification system (the "bell"/פעמון).

Usage:
    # After creating a notification/reminder in DB:
    dispatch_push_for_notification(notification_id, notification_type, title, body, url)
    
    # Or directly:
    dispatch_push_to_user(user_id, business_id, payload)
"""
import logging
import threading
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from server.services.push.webpush_sender import (
    get_webpush_sender, 
    PushPayload,
    WEBPUSH_AVAILABLE
)

log = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Result of a push dispatch operation"""
    total_subscriptions: int
    successful: int
    failed: int
    deactivated: int


def dispatch_push_to_user(
    user_id: int,
    business_id: int,
    payload: PushPayload,
    background: bool = True
) -> Optional[DispatchResult]:
    """
    Send push notification to all active subscriptions for a user
    
    Args:
        user_id: Target user ID
        business_id: Business context
        payload: Notification payload
        background: If True, dispatch in background thread (non-blocking)
        
    Returns:
        DispatchResult if synchronous, None if background
    """
    if background:
        # Fire and forget in background thread
        thread = threading.Thread(
            target=_dispatch_push_sync,
            args=(user_id, business_id, payload),
            daemon=True
        )
        thread.start()
        return None
    else:
        return _dispatch_push_sync(user_id, business_id, payload)


def _dispatch_push_sync(
    user_id: int,
    business_id: int,
    payload: PushPayload
) -> DispatchResult:
    """
    Internal synchronous dispatch - runs in background thread or directly
    """
    from flask import current_app, has_app_context
    from server.app_factory import get_process_app
    
    # Get app context
    if has_app_context():
        app = current_app._get_current_object()
    else:
        app = get_process_app()
    
    with app.app_context():
        return _do_dispatch(user_id, business_id, payload)


def _do_dispatch(
    user_id: int,
    business_id: int,
    payload: PushPayload
) -> DispatchResult:
    """
    Actual dispatch logic - must run inside app context
    """
    from server.db import db
    from server.models_sql import PushSubscription
    
    result = DispatchResult(
        total_subscriptions=0,
        successful=0,
        failed=0,
        deactivated=0
    )
    
    # Check if push is available
    sender = get_webpush_sender()
    if not sender.is_configured:
        log.debug("Push not configured, skipping dispatch")
        return result
    
    try:
        # Get all active subscriptions for this user
        subscriptions = PushSubscription.query.filter_by(
            user_id=user_id,
            business_id=business_id,
            is_active=True
        ).all()
        
        result.total_subscriptions = len(subscriptions)
        
        if not subscriptions:
            log.debug(f"No active push subscriptions for user {user_id}")
            return result
        
        log.info(f"Dispatching push to {len(subscriptions)} subscription(s) for user {user_id}")
        
        # Send to each subscription
        subscriptions_to_deactivate: List[int] = []
        
        for sub in subscriptions:
            try:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "p256dh": sub.p256dh,
                    "auth": sub.auth
                }
                
                send_result = sender.send(sub_info, payload)
                
                if send_result["success"]:
                    result.successful += 1
                else:
                    result.failed += 1
                    if send_result.get("should_deactivate"):
                        subscriptions_to_deactivate.append(sub.id)
                        
            except Exception as e:
                log.error(f"Error sending push to subscription {sub.id}: {e}")
                result.failed += 1
        
        # Deactivate invalid subscriptions
        if subscriptions_to_deactivate:
            try:
                PushSubscription.query.filter(
                    PushSubscription.id.in_(subscriptions_to_deactivate)
                ).update({PushSubscription.is_active: False}, synchronize_session=False)
                db.session.commit()
                result.deactivated = len(subscriptions_to_deactivate)
                log.info(f"Deactivated {result.deactivated} invalid subscriptions")
            except Exception as e:
                log.error(f"Error deactivating subscriptions: {e}")
                db.session.rollback()
        
        log.info(f"Push dispatch complete: {result.successful}/{result.total_subscriptions} successful")
        return result
        
    except Exception as e:
        log.error(f"Push dispatch error: {e}")
        return result


def dispatch_push_for_notification(
    user_id: int,
    business_id: int,
    notification_type: str,
    title: str,
    body: str,
    url: Optional[str] = None,
    entity_id: Optional[str] = None,
    tag: Optional[str] = None
) -> None:
    """
    High-level function to dispatch push for a notification event
    
    This is the main entry point to call after creating an in-app notification.
    
    Args:
        user_id: Target user ID
        business_id: Business context
        notification_type: Type of notification (appointment_reminder, whatsapp_disconnect, etc.)
        title: Notification title
        body: Notification body text
        url: Optional deep link URL
        entity_id: Optional related entity ID
        tag: Optional tag for deduplication
    """
    # Generate tag for deduplication
    if tag:
        notification_tag = tag
    elif entity_id:
        notification_tag = f"{notification_type}_{entity_id}"
    else:
        notification_tag = notification_type
    
    payload = PushPayload(
        title=title,
        body=body,
        url=url,
        notification_type=notification_type,
        entity_id=entity_id,
        business_id=business_id,
        tag=notification_tag
    )
    
    dispatch_push_to_user(user_id, business_id, payload, background=True)


def dispatch_push_sync(
    user_id: int,
    business_id: int,
    payload: PushPayload
) -> DispatchResult:
    """
    Public synchronous dispatch method.
    Use this when you need to wait for the result (e.g., test notifications).
    
    Args:
        user_id: Target user ID
        business_id: Business context
        payload: PushPayload with notification content
        
    Returns:
        DispatchResult with counts of successful/failed dispatches
    """
    return _dispatch_push_sync(user_id, business_id, payload)


def dispatch_push_to_business_owners(
    business_id: int,
    notification_type: str,
    title: str,
    body: str,
    url: Optional[str] = None,
    entity_id: Optional[str] = None
) -> None:
    """
    Send push notification to all owners/admins of a business
    
    Useful for system alerts like WhatsApp disconnect, agent failures, etc.
    """
    from server.models_sql import User
    
    try:
        # Get all owners and admins for this business
        owners = User.query.filter(
            User.business_id == business_id,
            User.is_active == True,
            User.role.in_(['owner', 'admin'])
        ).all()
        
        for owner in owners:
            dispatch_push_for_notification(
                user_id=owner.id,
                business_id=business_id,
                notification_type=notification_type,
                title=title,
                body=body,
                url=url,
                entity_id=entity_id
            )
            
    except Exception as e:
        log.error(f"Error dispatching push to business owners: {e}")
