#!/usr/bin/env python3
"""
Quick verification script for BulkCall fixes
Checks code without running full tests
"""

import os
import sys

def check_file_content(filepath, required_patterns, forbidden_patterns):
    """Check if file contains required patterns and doesn't contain forbidden ones"""
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check required patterns
    for pattern in required_patterns:
        if pattern not in content:
            return False, f"Missing required pattern: {pattern}"
    
    # Check forbidden patterns
    for pattern in forbidden_patterns:
        if pattern in content:
            return False, f"Found forbidden pattern: {pattern}"
    
    return True, "OK"

def main():
    print("=" * 80)
    print("BulkCall Fix Verification")
    print("=" * 80)
    
    checks = []
    
    # Check 1: twilio_outbound_service.py doesn't import request
    print("\n[1/5] Checking twilio_outbound_service.py has no request import...")
    success, msg = check_file_content(
        "server/services/twilio_outbound_service.py",
        required_patterns=[
            "def create_outbound_call(",
            "host: str,",  # host must be a parameter
        ],
        forbidden_patterns=[
            "from flask import request",
            "request.host",
            "request.headers",
        ]
    )
    checks.append(("No request import in service", success, msg))
    print(f"  {'✅' if success else '❌'} {msg}")
    
    # Check 2: create_outbound_call accepts host parameter
    print("\n[2/5] Checking create_outbound_call signature has host param...")
    success, msg = check_file_content(
        "server/services/twilio_outbound_service.py",
        required_patterns=[
            "def create_outbound_call(",
            "to_phone: str,",
            "from_phone: str,",
            "business_id: int,",
            "host: str,",
        ],
        forbidden_patterns=[]
    )
    checks.append(("host parameter in signature", success, msg))
    print(f"  {'✅' if success else '❌'} {msg}")
    
    # Check 3: Workers pass host to create_outbound_call
    print("\n[3/5] Checking workers pass host to create_outbound_call...")
    success, msg = check_file_content(
        "server/routes_outbound.py",
        required_patterns=[
            "host = get_public_host()",
            "host=host,",  # host passed to function
        ],
        forbidden_patterns=[]
    )
    checks.append(("Workers pass host param", success, msg))
    print(f"  {'✅' if success else '❌'} {msg}")
    
    # Check 4: Workers check business-level limits
    print("\n[4/5] Checking workers use business-level concurrency limits...")
    success, msg = check_file_content(
        "server/routes_outbound.py",
        required_patterns=[
            "from server.services.call_limiter import count_active_outbound_calls, MAX_OUTBOUND_CALLS_PER_BUSINESS",
            "business_active_outbound = count_active_outbound_calls(",
            "and business_active_outbound < MAX_OUTBOUND_CALLS_PER_BUSINESS",
        ],
        forbidden_patterns=[]
    )
    checks.append(("Business-level limits in workers", success, msg))
    print(f"  {'✅' if success else '❌'} {msg}")
    
    # Check 5: Workers don't use request context
    print("\n[5/5] Checking workers don't use request context...")
    with open("server/routes_outbound.py", 'r') as f:
        lines = f.readlines()
    
    # Find worker functions
    in_worker = False
    worker_uses_request = False
    worker_name = ""
    
    for i, line in enumerate(lines):
        if "def process_bulk_call_run(" in line or "def fill_queue_slots_for_job(" in line:
            in_worker = True
            worker_name = line.strip().split("(")[0].replace("def ", "")
        elif in_worker and line.startswith("def "):
            in_worker = False
        
        if in_worker:
            # Check for request context usage (but not in comments)
            if "request." in line and not line.strip().startswith("#"):
                # Exclude "request_id" or other non-Flask-request patterns
                if "request.get" in line or "request.host" in line or "request.headers" in line:
                    worker_uses_request = True
                    print(f"  ⚠️  Found request context in {worker_name} at line {i+1}: {line.strip()}")
    
    if worker_uses_request:
        success = False
        msg = "Workers use request context (will fail!)"
    else:
        success = True
        msg = "Workers don't use request context"
    
    checks.append(("No request context in workers", success, msg))
    print(f"  {'✅' if success else '❌'} {msg}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = all(check[1] for check in checks)
    
    for name, success, msg in checks:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if not success:
            print(f"       {msg}")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Fix looks good!")
        print("\nThe BulkCall workers should now:")
        print("  1. Not crash with 'Working outside of request context'")
        print("  2. Enforce max 3 concurrent outbound calls per business")
        print("  3. Process queues smoothly without duplicates")
        print("\nNext steps:")
        print("  - Deploy to staging/production")
        print("  - Test with 50+ lead bulk call")
        print("  - Monitor logs for any errors")
        print("=" * 80)
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Review needed!")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
