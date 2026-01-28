"""
Background Jobs Module
Contains job handlers for Redis queue (RQ)
"""

# Export job functions to ensure consistent import paths
# This prevents RQ worker import path mismatches
from .gmail_sync_job import sync_gmail_receipts_job
from .delete_receipts_job import delete_receipts_batch_job
from .broadcast_job import process_broadcast_job
from .delete_leads_job import delete_leads_batch_job
from .update_leads_job import update_leads_batch_job
from .delete_imported_leads_job import delete_imported_leads_batch_job
from .enqueue_outbound_calls_job import enqueue_outbound_calls_batch_job
from .cleanup_recordings_job import cleanup_old_recordings_job
from .warmup_agents_job import warmup_agents_job
from .whatsapp_session_job import process_whatsapp_sessions_job
from .reminder_notification_job import send_reminder_notifications_job

__all__ = [
    'sync_gmail_receipts_job',
    'delete_receipts_batch_job',
    'process_broadcast_job',
    'delete_leads_batch_job',
    'update_leads_batch_job',
    'delete_imported_leads_batch_job',
    'enqueue_outbound_calls_batch_job',
    'cleanup_old_recordings_job',
    'warmup_agents_job',
    'process_whatsapp_sessions_job',
    'send_reminder_notifications_job'
]
