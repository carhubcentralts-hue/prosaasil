#!/usr/bin/env python3
"""
Verification Script for Call Recording Pipeline
Run this BEFORE making any changes to understand what's actually broken
"""
import os
import sys
import requests
from datetime import datetime, timedelta

def check_webhook_routes():
    """Verify webhook routes are accessible"""
    print("\n🔍 STEP 1: Checking Webhook Routes")
    print("=" * 80)
    
    base_url = os.getenv("PUBLIC_HOST", "").replace("https://", "").replace("http://", "")
    if not base_url:
        print("⚠️  PUBLIC_HOST not set - using localhost")
        base_url = "localhost:5000"
    
    base_url = f"https://{base_url}" if not base_url.startswith("http") else base_url
    
    routes_to_check = [
        "/webhook/handle_recording",
        "/webhook/call_status",
        "/webhook/stream_ended",
        "/webhook/stream_status",
        "/webhook/incoming_call",
        "/webhook/outbound_call"
    ]
    
    print(f"Base URL: {base_url}")
    print(f"\nChecking {len(routes_to_check)} webhook endpoints:\n")
    
    results = {}
    for route in routes_to_check:
        url = f"{base_url}{route}"
        try:
            # Just check if route exists (may return 401/403 which is OK)
            response = requests.get(url, timeout=5, allow_redirects=False)
            status = response.status_code
            
            # 200, 401, 403, 405 are all OK (means route exists)
            if status in [200, 401, 403, 405]:
                print(f"  ✅ {route} - Route exists (status {status})")
                results[route] = "OK"
            elif status == 404:
                print(f"  ❌ {route} - NOT FOUND (404)")
                results[route] = "MISSING"
            else:
                print(f"  ⚠️  {route} - Unexpected status {status}")
                results[route] = f"STATUS_{status}"
        except Exception as e:
            print(f"  ❌ {route} - Error: {e}")
            results[route] = f"ERROR"
    
    missing = [r for r, s in results.items() if s == "MISSING"]
    if missing:
        print(f"\n❌ MISSING ROUTES: {', '.join(missing)}")
        return False
    else:
        print(f"\n✅ All {len(routes_to_check)} webhook routes are registered")
        return True

def check_database_schema():
    """Verify database has required fields"""
    print("\n🔍 STEP 2: Checking Database Schema")
    print("=" * 80)
    
    try:
        # Try to import and check if fields exist
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        print("Checking if new status fields exist in CallLog model...")
        
        from server.models_sql import CallLog
        
        # Check if model has the new fields
        required_fields = [
            'recording_status',
            'transcript_status', 
            'summary_status',
            'last_error',
            'retry_count'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not hasattr(CallLog, field):
                missing_fields.append(field)
                print(f"  ❌ {field} - MISSING from model")
            else:
                print(f"  ✅ {field} - exists in model")
        
        if missing_fields:
            print(f"\n❌ Missing fields: {', '.join(missing_fields)}")
            print("   Run: python -m server.db_migrate")
            return False
        else:
            print(f"\n✅ All {len(required_fields)} status fields exist in model")
            return True
            
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        print("   This is OK if database is not accessible from here")
        return None

def check_recent_calls():
    """Check recent calls in database"""
    print("\n🔍 STEP 3: Checking Recent Calls")
    print("=" * 80)
    
    try:
        from server.app_factory import create_minimal_app
        from server.models_sql import CallLog, db
        from sqlalchemy import desc
        
        app = create_minimal_app()
        with app.app_context():
            # Get last 5 calls
            recent_calls = CallLog.query.order_by(desc(CallLog.created_at)).limit(5).all()
            
            if not recent_calls:
                print("⚠️  No calls found in database")
                return None
            
            print(f"Found {len(recent_calls)} recent calls:\n")
            
            for i, call in enumerate(recent_calls, 1):
                print(f"Call #{i}:")
                print(f"  CallSid: {call.call_sid}")
                print(f"  Business ID: {call.business_id}")
                print(f"  Direction: {call.direction}")
                print(f"  From: {call.from_number}")
                print(f"  To: {call.to_number}")
                
                # Check new fields if they exist
                if hasattr(call, 'recording_status'):
                    rec_emoji = "✅" if call.recording_status == "completed" else "⚠️"
                    trans_emoji = "✅" if call.transcript_status == "completed" else "⚠️"
                    summ_emoji = "✅" if call.summary_status == "completed" else "⚠️"
                    
                    print(f"  {rec_emoji} Recording: {call.recording_status}")
                    print(f"  {trans_emoji} Transcript: {call.transcript_status}")
                    print(f"  {summ_emoji} Summary: {call.summary_status}")
                    
                    if call.last_error:
                        print(f"  ❌ Last Error: {call.last_error[:100]}...")
                
                print(f"  Recording URL: {'✅ Yes' if call.recording_url else '❌ No'}")
                print(f"  Recording SID: {call.recording_sid or 'N/A'}")
                print(f"  Lead ID: {call.lead_id or 'Not linked'}")
                print(f"  Created: {call.created_at}")
                print()
            
            # Check for stuck calls
            if hasattr(recent_calls[0], 'recording_status'):
                stuck_recording = [c for c in recent_calls if c.recording_status == 'recording']
                stuck_transcript = [c for c in recent_calls if c.transcript_status == 'processing']
                
                if stuck_recording:
                    print(f"⚠️  {len(stuck_recording)} calls stuck in 'recording' status")
                if stuck_transcript:
                    print(f"⚠️  {len(stuck_transcript)} calls stuck in 'processing' status")
                
                if not stuck_recording and not stuck_transcript:
                    print("✅ No stuck calls found")
            
            return True
            
    except Exception as e:
        print(f"❌ Error checking calls: {e}")
        print("   This is OK if database is not accessible from here")
        return None

def print_twilio_config():
    """Print exact Twilio webhook configuration"""
    print("\n📋 STEP 4: Twilio Webhook Configuration")
    print("=" * 80)
    
    base_url = os.getenv("PUBLIC_HOST", "").replace("https://", "").replace("http://", "")
    if not base_url:
        print("⚠️  PUBLIC_HOST not set - cannot generate config")
        return
    
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    
    print("Configure these exact URLs in Twilio Console:\n")
    
    print("1️⃣  Voice Configuration (Phone Numbers → Active Number → Configure):")
    print(f"   A CALL COMES IN: {base_url}/webhook/incoming_call")
    print(f"   METHOD: POST")
    print()
    
    print("2️⃣  Call Status Callback (same page, scroll down):")
    print(f"   PRIMARY HANDLER REQUEST URL: {base_url}/webhook/call_status")
    print(f"   METHOD: POST")
    print(f"   EVENTS: Initiated, Ringing, Answered, Completed")
    print()
    
    print("3️⃣  Recording Configuration (in code - auto-configured):")
    print(f"   recordingStatusCallback: {base_url}/webhook/handle_recording")
    print(f"   recordingStatusCallbackEvent: ['completed']")
    print(f"   recordingStatusCallbackMethod: POST")
    print()
    
    print("4️⃣  Stream Configuration (in code - auto-configured):")
    print(f"   Stream action: {base_url}/webhook/stream_ended")
    print(f"   Stream statusCallback: {base_url}/webhook/stream_status")
    print()

def main():
    print("\n" + "=" * 80)
    print("🔍 CALL RECORDING PIPELINE VERIFICATION")
    print("=" * 80)
    print("This script checks if the recording pipeline is working correctly")
    print("Run this BEFORE making any changes to understand what's broken")
    print("=" * 80)
    
    # Run checks
    routes_ok = check_webhook_routes()
    schema_ok = check_database_schema()
    calls_ok = check_recent_calls()
    
    # Print Twilio config
    print_twilio_config()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 80)
    
    status_emoji = lambda x: "✅" if x else ("⚠️" if x is None else "❌")
    
    print(f"{status_emoji(routes_ok)} Webhook Routes: {'OK' if routes_ok else ('UNKNOWN' if routes_ok is None else 'MISSING')}")
    print(f"{status_emoji(schema_ok)} Database Schema: {'OK' if schema_ok else ('UNKNOWN' if schema_ok is None else 'MISSING')}")
    print(f"{status_emoji(calls_ok)} Recent Calls: {'OK' if calls_ok else ('UNKNOWN' if calls_ok is None else 'NO DATA')}")
    
    print("\n" + "=" * 80)
    print("📝 NEXT STEPS")
    print("=" * 80)
    
    if not routes_ok:
        print("❌ Fix missing webhook routes first")
    elif schema_ok == False:
        print("❌ Run migration: python -m server.db_migrate")
    else:
        print("✅ System appears ready")
        print("👉 Make a test call and check logs for:")
        print("   - [REC_START] Recording started")
        print("   - [REC_CB] Recording webhook received")
        print("   - [TRANSCRIPT] Transcription started")
        print("   - [SUMMARY] Summary generated")
    
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
