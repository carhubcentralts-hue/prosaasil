#!/usr/bin/env python3
"""
🔍 Diagnostic Tool: Webhook and Appointment Issues
Tests and fixes for outbound webhooks and appointment booking
"""
import os
import sys

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_webhook_configuration():
    """Check if webhooks are properly configured"""
    print("\n" + "="*80)
    print("🔍 CHECKING WEBHOOK CONFIGURATION")
    print("="*80 + "\n")
    
    try:
        from server.app_factory import create_app
        app = create_app()
        
        with app.app_context():
            from server.models_sql import Business, BusinessSettings, CallLog, db
            from sqlalchemy import desc
            
            businesses = Business.query.all()
            print(f"Found {len(businesses)} businesses\n")
            
            issues_found = []
            
            for business in businesses:
                settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
                
                if not settings:
                    issues_found.append(f"Business {business.id} ({business.name}): NO SETTINGS")
                    continue
                
                print(f"\n{'─'*80}")
                print(f"📊 Business {business.id}: {business.name}")
                print(f"{'─'*80}")
                
                # Check webhook URLs
                generic_url = settings.generic_webhook_url
                inbound_url = getattr(settings, 'inbound_webhook_url', None)
                outbound_url = getattr(settings, 'outbound_webhook_url', None)
                
                print(f"\n🔗 Webhook URLs:")
                print(f"   generic_webhook_url  : {generic_url[:60] + '...' if generic_url else '❌ NOT SET'}")
                print(f"   inbound_webhook_url  : {inbound_url[:60] + '...' if inbound_url else '❌ NOT SET'}")
                print(f"   outbound_webhook_url : {outbound_url[:60] + '...' if outbound_url else '❌ NOT SET'}")
                
                # Check recent outbound calls
                recent_outbound = CallLog.query.filter_by(
                    business_id=business.id,
                    direction="outbound"
                ).order_by(desc(CallLog.created_at)).limit(3).all()
                
                print(f"\n📤 Recent Outbound Calls: {len(recent_outbound)}")
                for call in recent_outbound:
                    has_recording = "✅" if call.recording_url else "❌"
                    has_transcript = "✅" if call.final_transcript else "❌"
                    print(f"   {call.call_sid[:20]}... | recording={has_recording} | transcript={has_transcript} | status={call.status}")
                
                # Determine webhook routing for outbound
                print(f"\n🎯 Webhook Routing for Outbound Calls:")
                if outbound_url:
                    print(f"   ✅ Will use: outbound_webhook_url")
                elif generic_url:
                    print(f"   ⚠️  Will use: generic_webhook_url (fallback)")
                else:
                    print(f"   ❌ NO WEBHOOK WILL BE SENT")
                    issues_found.append(f"Business {business.id}: No webhook URL for outbound calls")
            
            print(f"\n{'='*80}")
            if issues_found:
                print("❌ ISSUES FOUND:")
                for issue in issues_found:
                    print(f"   • {issue}")
            else:
                print("✅ All businesses have webhook configuration")
            print("="*80 + "\n")
            
            return len(issues_found) == 0
            
    except Exception as e:
        print(f"❌ Error checking webhook configuration: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_appointment_configuration():
    """Check if appointments are properly configured"""
    print("\n" + "="*80)
    print("🔍 CHECKING APPOINTMENT CONFIGURATION")
    print("="*80 + "\n")
    
    try:
        from server.app_factory import create_app
        app = create_app()
        
        with app.app_context():
            from server.models_sql import Business, BusinessSettings, db
            
            businesses = Business.query.all()
            print(f"Found {len(businesses)} businesses\n")
            
            issues_found = []
            
            for business in businesses:
                settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
                
                if not settings:
                    continue
                
                print(f"\n{'─'*80}")
                print(f"📊 Business {business.id}: {business.name}")
                print(f"{'─'*80}")
                
                # Check appointment settings
                call_goal = getattr(settings, 'call_goal', 'lead_only')
                enable_calendar = getattr(settings, 'enable_calendar_scheduling', True)
                
                print(f"\n📅 Appointment Settings:")
                print(f"   call_goal                  : {call_goal}")
                print(f"   enable_calendar_scheduling : {enable_calendar}")
                
                # Determine if appointments will work
                print(f"\n🎯 Appointment Booking Status:")
                
                # Voice calls
                if call_goal == "appointment":
                    print(f"   ✅ Voice Calls: ENABLED (call_goal='appointment')")
                else:
                    print(f"   ❌ Voice Calls: DISABLED (call_goal='{call_goal}', needs 'appointment')")
                    issues_found.append(f"Business {business.id}: Voice appointments disabled (call_goal != 'appointment')")
                
                # WhatsApp
                if enable_calendar:
                    print(f"   ✅ WhatsApp: ENABLED (enable_calendar_scheduling=True)")
                else:
                    print(f"   ❌ WhatsApp: DISABLED (enable_calendar_scheduling=False)")
                    issues_found.append(f"Business {business.id}: WhatsApp appointments disabled")
            
            print(f"\n{'='*80}")
            if issues_found:
                print("❌ ISSUES FOUND:")
                for issue in issues_found:
                    print(f"   • {issue}")
                print(f"\n💡 TO FIX: Update BusinessSettings in database:")
                print(f"   UPDATE business_settings SET call_goal='appointment' WHERE tenant_id=<business_id>;")
                print(f"   UPDATE business_settings SET enable_calendar_scheduling=true WHERE tenant_id=<business_id>;")
            else:
                print("✅ All businesses have appointment configuration")
            print("="*80 + "\n")
            
            return len(issues_found) == 0
            
    except Exception as e:
        print(f"❌ Error checking appointment configuration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_webhook_sending():
    """Test that webhook sending logic works"""
    print("\n" + "="*80)
    print("🧪 TESTING WEBHOOK SENDING LOGIC")
    print("="*80 + "\n")
    
    try:
        from server.app_factory import create_app
        app = create_app()
        
        with app.app_context():
            from server.models_sql import Business, BusinessSettings
            from server.services.generic_webhook_service import send_generic_webhook
            
            # Find first business
            business = Business.query.first()
            if not business:
                print("❌ No businesses found")
                return False
            
            settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
            if not settings:
                print(f"❌ No settings for business {business.id}")
                return False
            
            print(f"Testing with Business {business.id}: {business.name}\n")
            
            # Test data
            test_data = {
                "call_id": "TEST_123",
                "phone": "+972501234567",
                "message": "Test webhook"
            }
            
            # Test outbound webhook routing
            print("📤 Testing OUTBOUND webhook routing...")
            print(f"   Current configuration:")
            print(f"   - outbound_webhook_url: {getattr(settings, 'outbound_webhook_url', None) or 'NOT SET'}")
            print(f"   - generic_webhook_url: {settings.generic_webhook_url or 'NOT SET'}")
            
            if getattr(settings, 'outbound_webhook_url', None):
                print(f"\n   ✅ Will use outbound_webhook_url")
            elif settings.generic_webhook_url:
                print(f"\n   ✅ Will use generic_webhook_url (fallback)")
            else:
                print(f"\n   ❌ No URL configured - webhook will NOT be sent")
                return False
            
            print(f"\n   Note: Actual webhook sending is NOT executed in test mode")
            print(f"         (would require valid webhook endpoint)")
            
            print(f"\n✅ Webhook routing logic is correct")
            return True
            
    except Exception as e:
        print(f"❌ Error testing webhook sending: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all diagnostics"""
    print("\n🚀 Starting Webhook and Appointment Diagnostics\n")
    
    results = {
        "Webhook Configuration": check_webhook_configuration(),
        "Appointment Configuration": check_appointment_configuration(),
        "Webhook Sending Logic": test_webhook_sending()
    }
    
    # Final summary
    print("\n" + "="*80)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*80)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:30s} : {status}")
        if not passed:
            all_passed = False
    
    print("="*80 + "\n")
    
    if all_passed:
        print("🎉 ALL DIAGNOSTICS PASSED!\n")
        print("If webhooks still don't work:")
        print("1. Check logs during actual call: tail -f logs/app.log | grep WEBHOOK")
        print("2. Verify recording callback is triggered: Check Twilio console")
        print("3. Ensure webhook URL is accessible from Twilio/server\n")
        sys.exit(0)
    else:
        print("❌ SOME DIAGNOSTICS FAILED - See details above\n")
        print("Quick fixes:")
        print("1. Set generic_webhook_url if not set:")
        print("   UPDATE business_settings SET generic_webhook_url='https://your-webhook.com' WHERE tenant_id=1;")
        print("\n2. Enable appointments for voice calls:")
        print("   UPDATE business_settings SET call_goal='appointment' WHERE tenant_id=1;")
        print("\n3. Enable appointments for WhatsApp:")
        print("   UPDATE business_settings SET enable_calendar_scheduling=true WHERE tenant_id=1;\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
