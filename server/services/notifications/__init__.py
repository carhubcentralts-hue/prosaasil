# Notification services

# Export unified notification functions
from server.services.notifications.dispatcher import (
    notify_user,
    notify_business_owners,
    dispatch_push_for_notification,
    dispatch_push_to_user,
    dispatch_push_to_business_owners,
    dispatch_push_for_reminder,
    dispatch_push_sync
)

# Export scheduler functions
from server.services.notifications.reminder_scheduler import (
    # start_reminder_scheduler,  # DEPRECATED - Use scheduler service instead
    # stop_reminder_scheduler,    # DEPRECATED
    check_and_send_reminder_notifications
)

__all__ = [
    'notify_user',
    'notify_business_owners',
    'dispatch_push_for_notification',
    'dispatch_push_to_user',
    'dispatch_push_to_business_owners',
    'dispatch_push_for_reminder',
    'dispatch_push_sync',
    # 'start_reminder_scheduler',  # DEPRECATED
    # 'stop_reminder_scheduler',    # DEPRECATED
    'check_and_send_reminder_notifications'
]
