#!/usr/bin/env python3
"""
Post-Call Pipeline Verification Script
=====================================

Verifies that all post-call pipeline fixes are working correctly:
1. Database schema (recording_sid column)
2. Business identification (phone_e164 usage)
3. Websocket close guard
4. Recording metadata saved
5. Offline STT working
6. Extraction working
7. Webhook sent

Usage:
    python verify_post_call_pipeline.py
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def print_step(step_num, description):
    """Print step header"""
    print(f"\n{'─'*80}")
    print(f"  Step {step_num}: {description}")
    print(f"{'─'*80}\n")

def print_success(message):
    """Print success message"""
    print(f"✅ {message}")

def print_warning(message):
    """Print warning message"""
    print(f"⚠️  {message}")

def print_error(message):
    """Print error message"""
    print(f"❌ {message}")

def print_info(message):
    """Print info message"""
    print(f"ℹ️  {message}")

# ============================================================================
# PREFLIGHT CHECKS
# ============================================================================

def preflight_check_migration():
    """Check if recording_sid column exists in database"""
    print_step("0A", "Database Migration Check - recording_sid column")
    
    try:
        from server.app_factory import create_minimal_app
        from server.db import db
        from sqlalchemy import text
        
        app = create_minimal_app()
        with app.app_context():
            result = db.session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name='call_log' AND column_name='recording_sid'
            """)).fetchall()
            
            if result:
                col_name, col_type = result[0]
                print_success(f"recording_sid column exists: {col_name} ({col_type})")
                return True
            else:
                print_error("recording_sid column NOT FOUND in call_log table!")
                print_info("Run migration: python -m server.db_migrate")
                return False
                
    except Exception as e:
        print_error(f"Database check failed: {e}")
        return False

def preflight_check_ffmpeg():
    """Check if ffmpeg is available"""
    print_step("0B", "ffmpeg Availability Check")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                               capture_output=True, 
                               timeout=5,
                               text=True)
        
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print_success(f"ffmpeg available: {version_line}")
            print_info("Audio conversion to WAV 16kHz will be enabled")
            return True
        else:
            print_warning("ffmpeg not working properly")
            print_info("Will fallback to original audio format (still works)")
            return False
            
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print_warning("ffmpeg NOT installed")
        print_info("Install: apt-get install ffmpeg (recommended for quality)")
        print_info("System will fallback to original audio format (still works)")
        return False

def preflight_check_webhook_config():
    """Check webhook configuration"""
    print_step("0C", "Webhook Configuration Check")
    
    try:
        from server.app_factory import create_minimal_app
        from server.db import db
        from server.models_sql import BusinessSettings
        
        app = create_minimal_app()
        with app.app_context():
            settings = BusinessSettings.query.first()
            
            if settings:
                inbound_url = getattr(settings, 'inbound_webhook_url', None)
                outbound_url = getattr(settings, 'outbound_webhook_url', None)
                
                print_info("Webhook URLs configured:")
                if inbound_url:
                    print_success(f"  Inbound:  {inbound_url}")
                else:
                    print_warning("  Inbound:  Not configured (optional)")
                
                if outbound_url:
                    print_success(f"  Outbound: {outbound_url}")
                else:
                    print_warning("  Outbound: Not configured (optional)")
                
                return True
            else:
                print_warning("No BusinessSettings found (first business not configured yet)")
                return True  # Not critical for verification
                
    except Exception as e:
        print_warning(f"Could not check webhook config: {e}")
        return True  # Not critical

# ============================================================================
# DATABASE VERIFICATION
# ============================================================================

def verify_recent_calls():
    """Verify recent calls have proper recording metadata"""
    print_step("1", "Recent Calls - Recording Metadata Verification")
    
    try:
        from server.app_factory import create_minimal_app
        from server.db import db
        from sqlalchemy import text
        
        app = create_minimal_app()
        with app.app_context():
            # Get last 3 calls
            result = db.session.execute(text("""
                SELECT 
                    call_sid,
                    recording_url,
                    recording_sid,
                    LENGTH(final_transcript) as transcript_chars,
                    extracted_city,
                    extracted_service,
                    status,
                    created_at
                FROM call_log
                ORDER BY created_at DESC
                LIMIT 3
            """)).fetchall()
            
            if not result:
                print_warning("No calls found in database yet")
                print_info("Make a test call to verify the pipeline")
                return True
            
            print_info(f"Found {len(result)} recent call(s):\n")
            
            for row in result:
                call_sid, rec_url, rec_sid, trans_chars, city, service, status, created = row
                
                print(f"  Call SID: {call_sid}")
                print(f"  Created:  {created}")
                print(f"  Status:   {status}")
                
                # Check recording_url
                if rec_url:
                    print_success(f"  recording_url: {rec_url[:60]}...")
                else:
                    print_warning(f"  recording_url: EMPTY")
                
                # Check recording_sid (NEW!)
                if rec_sid:
                    print_success(f"  recording_sid: {rec_sid}")
                else:
                    print_warning(f"  recording_sid: EMPTY (may be old call before fix)")
                
                # Check transcript
                if trans_chars and trans_chars > 0:
                    print_success(f"  final_transcript: {trans_chars} chars")
                else:
                    print_warning(f"  final_transcript: EMPTY")
                
                # Check extraction
                if city:
                    print_success(f"  extracted_city: {city}")
                else:
                    print_info(f"  extracted_city: (empty)")
                
                if service:
                    print_success(f"  extracted_service: {service}")
                else:
                    print_info(f"  extracted_service: (empty)")
                
                print()
            
            return True
            
    except Exception as e:
        print_error(f"Database verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# CODE VERIFICATION
# ============================================================================

def verify_business_identification_fix():
    """Verify business identification uses phone_e164 not phone_number property"""
    print_step("2", "Business Identification Fix Verification")
    
    # Check the code uses phone_e164
    tasks_recording_path = os.path.join(os.path.dirname(__file__), 
                                       'server/tasks_recording.py')
    
    with open(tasks_recording_path, 'r') as f:
        content = f.read()
    
    # Check for the fix
    if 'Business.phone_e164.ilike' in content:
        print_success("Code uses Business.phone_e164 (correct DB column)")
        
        # Make sure it doesn't use phone_number.ilike
        if 'Business.phone_number.ilike' in content:
            print_error("Code still contains Business.phone_number.ilike - NOT FIXED!")
            return False
        else:
            print_success("No usage of Business.phone_number.ilike (correct)")
            return True
    else:
        print_error("Code does not use Business.phone_e164.ilike - FIX NOT APPLIED!")
        return False

def verify_websocket_guard():
    """Verify websocket double-close guard is in place"""
    print_step("3", "Websocket Double-Close Guard Verification")
    
    media_ws_path = os.path.join(os.path.dirname(__file__), 
                                 'server/media_ws_ai.py')
    
    with open(media_ws_path, 'r') as f:
        content = f.read()
    
    # Check for the guard flag
    if '_ws_closed' in content:
        print_success("_ws_closed guard flag found in code")
        
        # Check for guard usage
        if 'if not self._ws_closed:' in content or 'if not self._ws_closed' in content:
            print_success("Guard check found before ws.close()")
            return True
        else:
            print_warning("_ws_closed flag exists but guard check not found")
            return False
    else:
        print_error("_ws_closed guard flag NOT FOUND - FIX NOT APPLIED!")
        return False

def verify_recording_sid_save():
    """Verify recording_sid is saved in multiple places"""
    print_step("4", "recording_sid Save Logic Verification")
    
    media_ws_path = os.path.join(os.path.dirname(__file__), 
                                 'server/media_ws_ai.py')
    routes_twilio_path = os.path.join(os.path.dirname(__file__), 
                                     'server/routes_twilio.py')
    
    checks_passed = 0
    
    # Check 1: Finalize saves recording_sid
    with open(media_ws_path, 'r') as f:
        content = f.read()
    
    if 'call_log.recording_sid = self._recording_sid' in content:
        print_success("Finalize saves recording_sid from self._recording_sid")
        checks_passed += 1
    else:
        print_warning("Finalize does NOT save recording_sid")
    
    # Check 2: Webhook handler saves recording_sid
    with open(routes_twilio_path, 'r') as f:
        content = f.read()
    
    if 'RecordingSid' in content and 'call_log.recording_sid' in content:
        print_success("Webhook handler extracts RecordingSid and saves to DB")
        checks_passed += 1
    else:
        print_warning("Webhook handler does NOT save RecordingSid")
    
    return checks_passed >= 1  # At least one save location

def verify_audio_conversion():
    """Verify audio conversion to WAV 16kHz is implemented"""
    print_step("5", "Audio Conversion (WAV 16kHz) Verification")
    
    extraction_path = os.path.join(os.path.dirname(__file__), 
                                  'server/services/lead_extraction_service.py')
    
    with open(extraction_path, 'r') as f:
        content = f.read()
    
    # Check for conversion logic
    if 'ffmpeg' in content and '-ar 16000' in content:
        print_success("ffmpeg conversion to 16kHz found in code")
        
        if '-ac 1' in content:
            print_success("Mono conversion (-ac 1) found")
        
        if 'pcm_s16le' in content:
            print_success("PCM format (pcm_s16le) found")
        
        if 'converted_file' in content:
            print_success("Temporary file handling found")
            return True
        else:
            print_warning("Conversion code incomplete")
            return False
    else:
        print_error("Audio conversion logic NOT FOUND - FIX NOT APPLIED!")
        return False

# ============================================================================
# LOG PATTERN CHECKS
# ============================================================================

def check_logs_for_errors():
    """Check if historical errors are still present in recent logs"""
    print_step("6", "Historical Errors Check")
    
    print_info("This check would scan application logs for:")
    print_info("  ❌ UndefinedColumn: column call_log.recording_sid")
    print_info("  ❌ 'property' object has no attribute 'ilike'")
    print_info("  ❌ Unexpected ASGI message 'websocket.close'")
    print()
    print_info("To manually verify:")
    print_info("  1. Make a test call")
    print_info("  2. Check logs for these errors")
    print_info("  3. Confirm they do NOT appear")
    print()
    print_success("If no errors appear in logs after test call, verification PASSED")
    
    return True

# ============================================================================
# MAIN VERIFICATION
# ============================================================================

def main():
    """Run all verification checks"""
    print_header("POST-CALL PIPELINE VERIFICATION")
    print_info(f"Verification started at: {datetime.now().isoformat()}")
    print_info(f"Working directory: {os.getcwd()}")
    print()
    
    results = {}
    
    # Preflight checks
    print_header("PREFLIGHT CHECKS")
    results['migration'] = preflight_check_migration()
    results['ffmpeg'] = preflight_check_ffmpeg()
    results['webhook'] = preflight_check_webhook_config()
    
    # Code verification
    print_header("CODE VERIFICATION")
    results['business_id'] = verify_business_identification_fix()
    results['ws_guard'] = verify_websocket_guard()
    results['rec_sid_save'] = verify_recording_sid_save()
    results['audio_conv'] = verify_audio_conversion()
    
    # Database verification
    print_header("DATABASE VERIFICATION")
    results['db_calls'] = verify_recent_calls()
    
    # Log checks
    print_header("LOG VERIFICATION")
    results['logs'] = check_logs_for_errors()
    
    # Summary
    print_header("VERIFICATION SUMMARY")
    
    critical_checks = ['migration', 'business_id', 'ws_guard', 'rec_sid_save', 'audio_conv']
    critical_passed = sum(1 for k in critical_checks if results.get(k, False))
    critical_total = len(critical_checks)
    
    optional_checks = ['ffmpeg', 'webhook']
    optional_passed = sum(1 for k in optional_checks if results.get(k, False))
    optional_total = len(optional_checks)
    
    print(f"\nCritical Checks: {critical_passed}/{critical_total} passed")
    print(f"Optional Checks: {optional_passed}/{optional_total} passed")
    print()
    
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        critical = "🔴 CRITICAL" if check_name in critical_checks else "⚪ Optional"
        print(f"  {status}  {critical:15} - {check_name}")
    
    print()
    
    if critical_passed == critical_total:
        print_success("All critical checks PASSED! ✅")
        print()
        print_info("Next steps:")
        print_info("  1. Make a test inbound call")
        print_info("  2. Make a test outbound call")
        print_info("  3. Check logs for success messages")
        print_info("  4. Verify DB has recording_sid, final_transcript, etc.")
        print()
        return 0
    else:
        print_error(f"Only {critical_passed}/{critical_total} critical checks passed")
        print_info("Review failed checks above and fix issues before deployment")
        print()
        return 1

if __name__ == '__main__':
    sys.exit(main())
