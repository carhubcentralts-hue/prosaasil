#!/usr/bin/env python3
"""
Manual test script for verifying push notifications work correctly
Tests both lead status change notifications and appointment status change notifications
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.app_factory import create_app
from server.db import db
from server.models_sql import Lead, Appointment, Business, User, PushSubscription, LeadReminder
from server.services.unified_status_service import UnifiedStatusService, StatusUpdateRequest
from server.services.notifications.dispatcher import notify_business_owners
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_lead_status_notification():
    """Test that lead status change sends notification"""
    logger.info("=" * 80)
    logger.info("TEST 1: Lead Status Change Notification")
    logger.info("=" * 80)
    
    app = create_app()
    with app.app_context():
        # Find a test business and lead
        business = Business.query.first()
        if not business:
            logger.error("❌ No business found in database. Cannot test.")
            return False
        
        lead = Lead.query.filter_by(tenant_id=business.id).first()
        if not lead:
            logger.error("❌ No lead found for business. Cannot test.")
            return False
        
        logger.info(f"✅ Found test business: {business.business_name} (ID: {business.id})")
        logger.info(f"✅ Found test lead: {lead.name or lead.phone} (ID: {lead.id})")
        logger.info(f"   Current status: {lead.status}")
        
        # Get current status and choose a different status
        current_status = lead.status or 'new'
        new_status = 'contacted' if current_status != 'contacted' else 'interested'
        
        logger.info(f"\n📝 Updating lead status: {current_status} → {new_status}")
        
        # Update status using unified service
        service = UnifiedStatusService(business.id)
        request = StatusUpdateRequest(
            lead_id=lead.id,
            new_status=new_status,
            reason='Manual test of notification system',
            channel='manual',
            confidence=1.0
        )
        
        result = service.update_lead_status(request)
        
        if result.success:
            logger.info(f"✅ Status update successful")
            logger.info(f"   Old status: {result.old_status}")
            logger.info(f"   New status: {result.new_status}")
            logger.info(f"   Audit ID: {result.audit_id}")
            
            # Check if notification was created in LeadReminder
            recent_reminders = LeadReminder.query.filter_by(
                tenant_id=business.id,
                reminder_type='system_lead_status_change'
            ).order_by(LeadReminder.id.desc()).limit(1).all()
            
            if recent_reminders:
                reminder = recent_reminders[0]
                logger.info(f"✅ Notification created in bell:")
                logger.info(f"   Note: {reminder.note}")
                logger.info(f"   Description: {reminder.description}")
            else:
                logger.info("ℹ️  No bell notification found (might be expected)")
            
            logger.info("\n📱 Push notification should have been dispatched to business owners/admins")
            logger.info("   (Check logs for 'Enqueued push_send_job' or 'Dispatched push notification')")
            
            return True
        else:
            logger.error(f"❌ Status update failed: {result.message}")
            if result.skipped:
                logger.info(f"   Update was skipped (possibly same status)")
            return False


def test_appointment_status_notification():
    """Test that appointment status change sends notification"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Appointment Status Change Notification")
    logger.info("=" * 80)
    
    app = create_app()
    with app.app_context():
        # Find a test appointment
        appointment = Appointment.query.filter_by(
            status='scheduled'
        ).first()
        
        if not appointment:
            # Try any status
            appointment = Appointment.query.first()
        
        if not appointment:
            logger.error("❌ No appointment found in database. Cannot test.")
            return False
        
        business = Business.query.get(appointment.business_id)
        logger.info(f"✅ Found test appointment: {appointment.title} (ID: {appointment.id})")
        logger.info(f"   Business: {business.business_name if business else 'Unknown'}")
        logger.info(f"   Current status: {appointment.status}")
        logger.info(f"   Contact: {appointment.contact_name or 'N/A'}")
        
        # Import and call notification function directly
        from server.routes_calendar import _send_appointment_status_notification
        
        old_status = appointment.status
        new_status = 'confirmed' if old_status != 'confirmed' else 'completed'
        
        logger.info(f"\n📝 Simulating appointment status change: {old_status} → {new_status}")
        
        try:
            _send_appointment_status_notification(
                appointment=appointment,
                old_status=old_status,
                new_status=new_status,
                business_id=appointment.business_id
            )
            logger.info(f"✅ Notification function executed successfully")
            logger.info(f"\n📱 Push notification should have been dispatched to business owners/admins")
            logger.info("   (Check logs for 'Enqueued push_send_job' or 'Dispatched push notification')")
            return True
        except Exception as e:
            logger.error(f"❌ Error calling notification function: {e}")
            import traceback
            traceback.print_exc()
            return False


def check_push_configuration():
    """Check if push notification system is properly configured"""
    logger.info("\n" + "=" * 80)
    logger.info("CONFIGURATION CHECK: Push Notification System")
    logger.info("=" * 80)
    
    # Check environment variables
    vapid_public = os.getenv("VAPID_PUBLIC_KEY")
    vapid_private = os.getenv("VAPID_PRIVATE_KEY")
    vapid_subject = os.getenv("VAPID_SUBJECT")
    
    logger.info(f"VAPID_PUBLIC_KEY: {'✅ Set' if vapid_public else '❌ Not set'}")
    logger.info(f"VAPID_PRIVATE_KEY: {'✅ Set' if vapid_private else '❌ Not set'}")
    logger.info(f"VAPID_SUBJECT: {vapid_subject or '❌ Not set'}")
    
    # Check if pywebpush is available
    try:
        from pywebpush import webpush
        logger.info("pywebpush library: ✅ Installed")
    except ImportError:
        logger.error("pywebpush library: ❌ Not installed")
        logger.error("  Install with: pip install pywebpush")
    
    # Check if there are any push subscriptions
    app = create_app()
    with app.app_context():
        subscription_count = PushSubscription.query.filter_by(is_active=True).count()
        logger.info(f"Active push subscriptions: {subscription_count}")
        
        if subscription_count == 0:
            logger.warning("⚠️  No active push subscriptions found")
            logger.warning("   Users need to enable notifications in their browser")
        
        # Check users with owner/admin roles
        owner_admin_count = User.query.filter(
            User.is_active == True,
            User.role.in_(['owner', 'admin'])
        ).count()
        logger.info(f"Active owners/admins: {owner_admin_count}")
    
    return True


def main():
    """Run all tests"""
    logger.info("Starting push notification verification tests...")
    logger.info("This script tests that notifications are sent for status changes\n")
    
    # Check configuration first
    check_push_configuration()
    
    # Test lead status notifications
    lead_test_passed = test_lead_status_notification()
    
    # Test appointment status notifications
    appointment_test_passed = test_appointment_status_notification()
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Lead status notification: {'✅ PASSED' if lead_test_passed else '❌ FAILED'}")
    logger.info(f"Appointment status notification: {'✅ PASSED' if appointment_test_passed else '❌ FAILED'}")
    
    if lead_test_passed and appointment_test_passed:
        logger.info("\n🎉 All tests passed! Notifications should be working.")
        logger.info("\nTo verify notifications are actually received:")
        logger.info("1. Check server logs for 'Enqueued push_send_job' messages")
        logger.info("2. Check RQ worker logs for push delivery status")
        logger.info("3. Verify notifications appear in browser/device")
        logger.info("4. Check LeadReminder table for bell notifications")
    else:
        logger.error("\n❌ Some tests failed. Check the errors above.")
    
    return lead_test_passed and appointment_test_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
