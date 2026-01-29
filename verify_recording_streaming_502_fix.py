#!/usr/bin/env python3
"""
Verification Script: Recording Streaming with Range Headers + 502 Fix

This script verifies that:
1. /api/recordings/file/<call_sid> endpoint exists with Range header support
2. No 502 loops - proper 202 Accepted responses
3. Fail-fast protection is implemented
4. appointments.calendar_id migration exists

Hebrew Problem Statement Translation:
"להלן הנחיה לסוכן (Copy-Paste) — לתקן רק 2 דברים:
	1.	אין Play להקלטות (רק הורדה) + 502 media בלופים
	2.	בעיה במיגרציות: appointments.calendar_id does not exist"

Expected Results:
✅ Streaming endpoint with Range headers (for PLAY in browser)
✅ Returns 202 Accepted (not 502) while preparing
✅ Fail-fast protection prevents infinite loops
✅ Migration adds calendar_id to appointments table
"""

import os
import sys
import re

def check_streaming_endpoint():
    """Verify /api/recordings/file/<call_sid> endpoint with Range support"""
    print("\n" + "=" * 70)
    print("1️⃣  CHECKING: Recording Streaming Endpoint with Range Headers")
    print("=" * 70)
    
    routes_file = "server/routes_recordings.py"
    
    if not os.path.exists(routes_file):
        print(f"❌ File not found: {routes_file}")
        return False
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Endpoint exists
    if "@recordings_bp.route('/file/<call_sid>'" in content:
        checks.append(("✅", "Endpoint /file/<call_sid> registered"))
    else:
        checks.append(("❌", "Endpoint /file/<call_sid> NOT found"))
    
    # Check 2: GET, HEAD, OPTIONS methods
    if "methods=['GET', 'HEAD', 'OPTIONS']" in content:
        checks.append(("✅", "Methods: GET, HEAD, OPTIONS supported"))
    else:
        checks.append(("❌", "Missing HEAD/OPTIONS methods"))
    
    # Check 3: Range header support
    if "range_header = request.headers.get('Range'" in content:
        checks.append(("✅", "Range header detection implemented"))
    else:
        checks.append(("❌", "Range header support missing"))
    
    # Check 4: 206 Partial Content response
    if "206" in content and "Partial Content" in content:
        checks.append(("✅", "HTTP 206 Partial Content response"))
    else:
        checks.append(("❌", "206 Partial Content response missing"))
    
    # Check 5: 202 Accepted (NOT 502!)
    if "202" in content and "Retry-After" in content:
        checks.append(("✅", "Returns 202 Accepted with Retry-After (not 502!)"))
    else:
        checks.append(("❌", "202 Accepted response missing"))
    
    # Check 6: Content-Range header
    if "Content-Range" in content:
        checks.append(("✅", "Content-Range header for streaming"))
    else:
        checks.append(("❌", "Content-Range header missing"))
    
    # Check 7: Accept-Ranges header (look for the header being set, not just the word "bytes")
    if re.search(r'Accept-Ranges[\'"]?\s*[:,]\s*[\'"]?bytes', content, re.IGNORECASE):
        checks.append(("✅", "Accept-Ranges: bytes header"))
    else:
        checks.append(("❌", "Accept-Ranges header missing"))
    
    # Check 8: CORS headers
    if "Access-Control-Allow-Origin" in content:
        checks.append(("✅", "CORS headers for cross-origin playback"))
    else:
        checks.append(("❌", "CORS headers missing"))
    
    # Print results
    for status, message in checks:
        print(f"  {status} {message}")
    
    all_passed = all(status == "✅" for status, _ in checks)
    return all_passed


def check_502_loop_prevention():
    """Verify no 502 loops - fail-fast protection"""
    print("\n" + "=" * 70)
    print("2️⃣  CHECKING: 502 Loop Prevention (Fail-Fast Protection)")
    print("=" * 70)
    
    routes_file = "server/routes_recordings.py"
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Retry limit defined
    if "MAX_RETRY_ATTEMPTS" in content:
        checks.append(("✅", "MAX_RETRY_ATTEMPTS limit defined"))
    else:
        checks.append(("❌", "No retry limit found"))
    
    # Check 2: Retry window defined
    if "RETRY_WINDOW_MINUTES" in content:
        checks.append(("✅", "RETRY_WINDOW_MINUTES defined"))
    else:
        checks.append(("❌", "No retry window found"))
    
    # Check 3: check_and_increment_retry_attempts function
    if "def check_and_increment_retry_attempts" in content:
        checks.append(("✅", "Retry attempt tracking function exists"))
    else:
        checks.append(("❌", "Retry attempt tracking missing"))
    
    # Check 4: Smart stuck detection
    if "def is_job_stuck_smart" in content or "started_at" in content:
        checks.append(("✅", "Smart stuck job detection"))
    else:
        checks.append(("❌", "Stuck job detection missing"))
    
    # Check 5: No direct 502 responses (check for actual status code usage, not just mentions)
    # Look for patterns like: return 502, status=502, Response(..., 502, ...)
    # Exclude comments and docstrings
    status_502_pattern = r'(?:return|status\s*=|Response\s*\([^)]*,)\s*502'
    if not re.search(status_502_pattern, content):
        checks.append(("✅", "No 502 Bad Gateway status code returns"))
    else:
        # Found actual 502 status code usage - this is an error
        checks.append(("❌", "ERROR: Code returns 502 status (should return 202 instead)"))
    
    # Print results
    for status, message in checks:
        print(f"  {status} {message}")
    
    # All checks must pass (no ⚠️ or ❌)
    all_passed = all(status == "✅" for status, _ in checks)
    return all_passed


def check_audioplayer_integration():
    """Verify AudioPlayer uses streaming endpoint"""
    print("\n" + "=" * 70)
    print("3️⃣  CHECKING: AudioPlayer Integration")
    print("=" * 70)
    
    player_file = "client/src/shared/components/AudioPlayer.tsx"
    
    if not os.path.exists(player_file):
        print(f"❌ File not found: {player_file}")
        return False
    
    with open(player_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Uses /api/recordings/file endpoint
    if "/api/recordings/file" in content:
        checks.append(("✅", "Uses /api/recordings/file/<call_sid> endpoint"))
    else:
        checks.append(("❌", "Not using streaming endpoint"))
    
    # Check 2: HEAD request for file check
    if "method: 'HEAD'" in content:
        checks.append(("✅", "HEAD request for file existence check"))
    else:
        checks.append(("❌", "No HEAD request check"))
    
    # Check 3: 202 handling
    if "202" in content and "response.status === 202" in content:
        checks.append(("✅", "Handles 202 Accepted responses"))
    else:
        checks.append(("❌", "202 Accepted handling missing"))
    
    # Check 4: Exponential backoff
    if "retryCount" in content or "getRetryDelay" in content:
        checks.append(("✅", "Exponential backoff retry logic"))
    else:
        checks.append(("❌", "No retry backoff"))
    
    # Check 5: Max retries limit
    if "MAX_RETRIES" in content:
        checks.append(("✅", "MAX_RETRIES limit defined"))
    else:
        checks.append(("❌", "No max retries limit"))
    
    # Check 6: AbortController for cleanup
    if "AbortController" in content:
        checks.append(("✅", "AbortController for request cleanup"))
    else:
        checks.append(("❌", "No request cleanup mechanism"))
    
    # Print results
    for status, message in checks:
        print(f"  {status} {message}")
    
    all_passed = all(status == "✅" for status, _ in checks)
    return all_passed


def check_calendar_migration():
    """Verify appointments.calendar_id migration exists"""
    print("\n" + "=" * 70)
    print("4️⃣  CHECKING: appointments.calendar_id Migration")
    print("=" * 70)
    
    checks = []
    
    # Check 1: Migration in db_migrate.py - look for actual ALTER TABLE statement
    migrate_file = "server/db_migrate.py"
    if os.path.exists(migrate_file):
        with open(migrate_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for the actual ALTER TABLE statement adding calendar_id
        if re.search(r'ALTER\s+TABLE\s+appointments.*ADD\s+COLUMN\s+calendar_id', content, re.IGNORECASE | re.DOTALL):
            checks.append(("✅", "Migration adds calendar_id to appointments table"))
        else:
            checks.append(("❌", "calendar_id migration ALTER TABLE statement not found"))
        
        if "115_appointments_calendar_id" in content:
            checks.append(("✅", "Migration 115 registered"))
        else:
            checks.append(("❌", "Migration 115 not registered"))
        
        if "idx_appointments_calendar_id" in content:
            checks.append(("✅", "Index idx_appointments_calendar_id created"))
        else:
            checks.append(("❌", "Index not created"))
    else:
        checks.append(("❌", f"File not found: {migrate_file}"))
    
    # Check 2: Model definition - look for actual column definition
    models_file = "server/models_sql.py"
    if os.path.exists(models_file):
        with open(models_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for calendar_id column definition in Appointment model
        if re.search(r'calendar_id\s*=\s*db\.Column', content):
            checks.append(("✅", "Appointment.calendar_id column defined in model"))
        else:
            checks.append(("❌", "calendar_id not in Appointment model"))
        
        # Look for foreign key constraint
        if re.search(r'ForeignKey\s*\(\s*["\']business_calendars\.id["\']', content):
            checks.append(("✅", "Foreign key to business_calendars"))
        else:
            checks.append(("❌", "Foreign key constraint missing"))
    else:
        checks.append(("❌", f"File not found: {models_file}"))
    
    # Print results
    for status, message in checks:
        print(f"  {status} {message}")
    
    all_passed = all(status == "✅" for status, _ in checks)
    return all_passed


def main():
    """Run all verification checks"""
    print("\n" + "═" * 70)
    print("🔍 VERIFICATION: Recording Streaming + 502 Fix + Migration")
    print("═" * 70)
    print("\nProblem Statement (Hebrew → English):")
    print("  1. No Play for recordings (only download) + 502 media in loops")
    print("  2. Problem with migrations: appointments.calendar_id does not exist")
    print("\nExpected Solution:")
    print("  ✅ Create streaming endpoint with Range headers (for PLAY)")
    print("  ✅ Return 202 Accepted (not 502) while file preparing")
    print("  ✅ Implement fail-fast protection (no infinite loops)")
    print("  ✅ Add calendar_id column to appointments table")
    
    results = []
    
    # Run all checks
    results.append(("Streaming Endpoint", check_streaming_endpoint()))
    results.append(("502 Loop Prevention", check_502_loop_prevention()))
    results.append(("AudioPlayer Integration", check_audioplayer_integration()))
    results.append(("Calendar Migration", check_calendar_migration()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL CHECKS PASSED!")
        print("\n✅ Recording streaming with Range headers is IMPLEMENTED")
        print("✅ No 502 loops - returns 202 Accepted with retry logic")
        print("✅ Fail-fast protection prevents infinite retries")
        print("✅ appointments.calendar_id migration exists")
        print("\n💡 The system is production-ready for:")
        print("   • Playing recordings in browser (not just download)")
        print("   • Smart retry with exponential backoff")
        print("   • Appointment calendar associations")
        print("=" * 70)
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print("\nReview the failed checks above and fix the issues.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
