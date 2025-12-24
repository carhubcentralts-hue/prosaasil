#!/usr/bin/env python3
"""
🔍 Webhook Configuration Diagnostic Tool

This script checks webhook configuration for all businesses and helps diagnose
why webhooks might not be sent after calls complete.

Usage:
    python test_webhook_config.py [business_id]

If business_id is provided, shows detailed info for that business.
Otherwise, shows summary for all businesses.
"""

import os
import sys

# Setup Flask app context
from server.app_factory import create_app
app = create_app()

with app.app_context():
    from server.models_sql import Business, BusinessSettings, CallLog
    from sqlalchemy import desc
    
    def check_webhook_url(url, name):
        """Check if webhook URL is valid and configured"""
        if not url:
            return "❌ NOT SET"
        
        url_str = str(url).strip()
        if not url_str:
            return "❌ EMPTY STRING"
        
        if not (url_str.startswith('http://') or url_str.startswith('https://')):
            return f"❌ INVALID (must start with http:// or https://): {url_str}"
        
        return f"✅ CONFIGURED: {url_str}"
    
    def show_business_webhooks(business_id):
        """Show webhook configuration for a specific business"""
        business = Business.query.get(business_id)
        if not business:
            print(f"❌ Business {business_id} not found")
            return False
        
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if not settings:
            print(f"❌ No settings found for business {business_id}")
            return False
        
        print(f"\n{'='*80}")
        print(f"📊 WEBHOOK CONFIGURATION FOR BUSINESS {business_id}")
        print(f"{'='*80}")
        print(f"Business Name: {business.name}")
        print(f"Business ID: {business.id}")
        print(f"\n🔗 WEBHOOK URLs:")
        print(f"\n1️⃣ INBOUND Webhook (for incoming calls):")
        print(f"   {check_webhook_url(settings.inbound_webhook_url, 'inbound_webhook_url')}")
        
        print(f"\n2️⃣ OUTBOUND Webhook (for outgoing calls):")
        print(f"   {check_webhook_url(settings.outbound_webhook_url, 'outbound_webhook_url')}")
        
        print(f"\n3️⃣ GENERIC Webhook (fallback for inbound if inbound_webhook_url not set):")
        print(f"   {check_webhook_url(settings.generic_webhook_url, 'generic_webhook_url')}")
        
        print(f"\n4️⃣ STATUS Webhook (for lead status changes):")
        print(f"   {check_webhook_url(settings.status_webhook_url, 'status_webhook_url')}")
        
        # Check recent calls
        print(f"\n📞 RECENT CALLS (last 5):")
        recent_calls = CallLog.query.filter_by(business_id=business_id).order_by(desc(CallLog.created_at)).limit(5).all()
        
        if not recent_calls:
            print("   No calls found")
        else:
            for call in recent_calls:
                direction = call.direction or "unknown"
                has_transcript = "✅" if call.final_transcript else "❌"
                has_recording = "✅" if call.recording_url else "❌"
                print(f"   {call.call_sid}: direction={direction}, transcript={has_transcript}, recording={has_recording}")
        
        # Determine what webhook would be used
        print(f"\n🎯 WEBHOOK ROUTING:")
        print(f"\n   For INBOUND calls:")
        if settings.inbound_webhook_url:
            print(f"   ✅ Will use: inbound_webhook_url")
        elif settings.generic_webhook_url:
            print(f"   ⚠️  Will use: generic_webhook_url (fallback)")
        else:
            print(f"   ❌ NO webhook will be sent (no inbound or generic URL configured)")
        
        print(f"\n   For OUTBOUND calls:")
        if settings.outbound_webhook_url:
            print(f"   ✅ Will use: outbound_webhook_url")
        else:
            print(f"   ❌ NO webhook will be sent (outbound_webhook_url not configured)")
        
        print(f"\n{'='*80}\n")
        return True
    
    def show_all_businesses():
        """Show summary for all businesses"""
        businesses = Business.query.all()
        
        print(f"\n{'='*80}")
        print(f"📊 WEBHOOK CONFIGURATION SUMMARY (ALL BUSINESSES)")
        print(f"{'='*80}\n")
        
        for business in businesses:
            settings = BusinessSettings.query.filter_by(tenant_id=business.id).first()
            if not settings:
                print(f"❌ Business {business.id} ({business.name}): No settings found")
                continue
            
            # Check webhook status
            inbound_ok = bool(settings.inbound_webhook_url and settings.inbound_webhook_url.startswith('http'))
            generic_ok = bool(settings.generic_webhook_url and settings.generic_webhook_url.startswith('http'))
            outbound_ok = bool(settings.outbound_webhook_url and settings.outbound_webhook_url.startswith('http'))
            
            inbound_status = "✅ inbound" if inbound_ok else ("⚠️  generic" if generic_ok else "❌ none")
            outbound_status = "✅ set" if outbound_ok else "❌ not set"
            
            print(f"Business {business.id:3d} ({business.name[:30]:30s}): inbound={inbound_status:15s} | outbound={outbound_status}")
        
        print(f"\n{'='*80}\n")
    
    # Main execution
    if len(sys.argv) > 1:
        try:
            business_id = int(sys.argv[1])
            show_business_webhooks(business_id)
        except ValueError:
            print(f"❌ Invalid business_id: {sys.argv[1]}")
            sys.exit(1)
    else:
        show_all_businesses()
        print("\n💡 TIP: Run 'python test_webhook_config.py <business_id>' for detailed info on a specific business\n")
