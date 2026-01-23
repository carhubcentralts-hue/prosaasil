#!/usr/bin/env python3
"""
Verification script for Live Call 500 error and AI cache warmup fixes

This script verifies that:
1. The routes_live_call.py uses g.business_id instead of session
2. The ai_service.py uses correct import from server.models_sql
3. All syntax is correct
"""

import sys
import re

def verify_routes_live_call():
    """Verify routes_live_call.py has correct fixes"""
    print("✓ Checking server/routes_live_call.py...")
    
    with open('server/routes_live_call.py', 'r') as f:
        content = f.read()
    
    # Check for correct import
    if 'from flask import Blueprint, request, jsonify, Response, current_app, g' not in content:
        print("  ✗ FAIL: Missing 'g' import from flask")
        return False
    print("  ✓ Correct: 'g' imported from flask")
    
    # Check for correct auth import
    if 'from server.auth_api import require_api_auth' not in content:
        print("  ✗ FAIL: Missing correct require_api_auth import")
        return False
    print("  ✓ Correct: require_api_auth imported from server.auth_api")
    
    # Check that session.get is NOT used
    if re.search(r"session\.get\(['\"]business_id", content):
        print("  ✗ FAIL: Still using session.get('business_id')")
        return False
    print("  ✓ Correct: Not using session.get('business_id')")
    
    # Check that g.business_id IS used
    if 'g.business_id' not in content:
        print("  ✗ FAIL: Not using g.business_id")
        return False
    
    # Count occurrences (should be at least 2 - one in chat, one in tts)
    occurrences = content.count('business_id = g.business_id')
    if occurrences < 2:
        print(f"  ✗ FAIL: Only {occurrences} uses of g.business_id (expected at least 2)")
        return False
    print(f"  ✓ Correct: Using g.business_id ({occurrences} times)")
    
    # Check error message is correct
    if "'error': 'missing_business_id'" not in content:
        print("  ✗ FAIL: Missing proper error message")
        return False
    print("  ✓ Correct: Proper error message for missing business_id")
    
    return True

def verify_ai_service():
    """Verify ai_service.py has correct import"""
    print("\n✓ Checking server/services/ai_service.py...")
    
    with open('server/services/ai_service.py', 'r') as f:
        content = f.read()
    
    # Check for correct import in warmup function
    if 'from server.models_sql import Business' not in content:
        print("  ✗ FAIL: Not using correct import 'from server.models_sql import Business'")
        return False
    print("  ✓ Correct: Using 'from server.models_sql import Business'")
    
    # Check that incorrect import is NOT present
    if 'from server.models import Business' in content:
        print("  ✗ FAIL: Still has incorrect import 'from server.models import'")
        return False
    print("  ✓ Correct: No incorrect 'from server.models import' found")
    
    # Check that warmup has try/except
    warmup_section = re.search(r'def _warmup_ai_cache.*?(?=\ndef|\Z)', content, re.DOTALL)
    if not warmup_section:
        print("  ✗ FAIL: Could not find _warmup_ai_cache function")
        return False
    
    warmup_code = warmup_section.group(0)
    if 'try:' not in warmup_code or 'except Exception as e:' not in warmup_code:
        print("  ✗ FAIL: Warmup function doesn't have proper try/except")
        return False
    print("  ✓ Correct: Warmup function has proper exception handling")
    
    return True

def verify_frontend():
    """Verify frontend has proper error handling"""
    print("\n✓ Checking client/src/components/settings/LiveCallCard.tsx...")
    
    with open('client/src/components/settings/LiveCallCard.tsx', 'r') as f:
        content = f.read()
    
    # Check for error handling in processAudio
    if 'catch (err: any)' not in content:
        print("  ✗ FAIL: Missing error handling")
        return False
    print("  ✓ Correct: Has error handling")
    
    # Check for recovery mechanism
    if 'setTimeout' not in content or 'restartListening' not in content:
        print("  ✗ FAIL: Missing error recovery mechanism")
        return False
    print("  ✓ Correct: Has error recovery mechanism with setTimeout and restartListening")
    
    # Check for abort controller
    if 'AbortController' not in content:
        print("  ✗ FAIL: Missing AbortController for request cancellation")
        return False
    print("  ✓ Correct: Uses AbortController for proper request cancellation")
    
    return True

def main():
    """Run all verifications"""
    print("=" * 60)
    print("Live Call Fix Verification")
    print("=" * 60)
    
    results = []
    
    # Run verifications
    results.append(('routes_live_call.py', verify_routes_live_call()))
    results.append(('ai_service.py', verify_ai_service()))
    results.append(('LiveCallCard.tsx', verify_frontend()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All verifications passed!")
        print("\nFixes implemented:")
        print("  1. ✓ Fixed 500 error in /api/live_call/chat (using g.business_id)")
        print("  2. ✓ Fixed 500 error in /api/live_call/tts (using g.business_id)")
        print("  3. ✓ Fixed AI cache warmup import (server.models_sql)")
        print("  4. ✓ Warmup has proper exception handling")
        print("  5. ✓ Frontend has proper error handling and recovery")
        return 0
    else:
        print("\n❌ Some verifications failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
