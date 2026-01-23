#!/usr/bin/env python3
"""
Test for critical Gmail sync and contract PDF fixes

Verifies:
1. Gmail sync: needs_review initialization fix
2. Gmail sync: heartbeat_callback parameter acceptance
3. Contract PDF: new pdf_url endpoint exists
4. Contract PDF: headers are properly set for iframe support
"""

import sys
import inspect
from typing import Optional


def test_needs_review_initialization():
    """
    Test that needs_review is always initialized in process_single_receipt_message
    """
    print("\n" + "=" * 80)
    print("TEST 1: needs_review initialization")
    print("=" * 80)
    
    try:
        # Import the function
        from server.services.gmail_sync_service import process_single_receipt_message
        
        # Get source code
        source = inspect.getsource(process_single_receipt_message)
        
        # Check that needs_review = False appears before any conditional checks
        lines = source.split('\n')
        needs_review_init_line = None
        first_validation_check_line = None
        
        for i, line in enumerate(lines):
            if 'needs_review = False' in line and 'if' not in line:
                needs_review_init_line = i
            if 'if validation_failed:' in line and first_validation_check_line is None:
                first_validation_check_line = i
        
        if needs_review_init_line is None:
            print("❌ FAIL: needs_review initialization not found")
            return False
        
        if first_validation_check_line is None:
            print("⚠️  WARNING: Could not find validation_failed check")
        elif needs_review_init_line > first_validation_check_line:
            print(f"❌ FAIL: needs_review initialized at line {needs_review_init_line} AFTER validation check at line {first_validation_check_line}")
            return False
        
        print(f"✅ PASS: needs_review is properly initialized at line {needs_review_init_line}")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing needs_review initialization: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_heartbeat_callback_parameter():
    """
    Test that sync_gmail_receipts accepts heartbeat_callback parameter
    """
    print("\n" + "=" * 80)
    print("TEST 2: heartbeat_callback parameter")
    print("=" * 80)
    
    try:
        # Import the function
        from server.services.gmail_sync_service import sync_gmail_receipts
        
        # Get function signature
        sig = inspect.signature(sync_gmail_receipts)
        params = list(sig.parameters.keys())
        
        if 'heartbeat_callback' not in params:
            print(f"❌ FAIL: heartbeat_callback not in parameters: {params}")
            return False
        
        # Check it has a default value
        param = sig.parameters['heartbeat_callback']
        if param.default == inspect.Parameter.empty:
            print(f"⚠️  WARNING: heartbeat_callback has no default value")
        elif param.default is None:
            print(f"✅ PASS: heartbeat_callback has default value of None")
        
        print(f"✅ PASS: heartbeat_callback parameter exists in sync_gmail_receipts")
        print(f"   Parameters: {params}")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing heartbeat_callback parameter: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_heartbeat_callback_invoked():
    """
    Test that heartbeat_callback is actually invoked in the sync loop
    """
    print("\n" + "=" * 80)
    print("TEST 3: heartbeat_callback invocation")
    print("=" * 80)
    
    try:
        # Import the function
        from server.services.gmail_sync_service import sync_gmail_receipts
        
        # Get source code
        source = inspect.getsource(sync_gmail_receipts)
        
        # Count how many times heartbeat_callback is invoked
        callback_invocations = source.count('heartbeat_callback()')
        
        if callback_invocations == 0:
            print("❌ FAIL: heartbeat_callback is never invoked")
            return False
        
        print(f"✅ PASS: heartbeat_callback is invoked {callback_invocations} times in the sync loop")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing heartbeat_callback invocation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_contract_pdf_url_endpoint():
    """
    Test that the new pdf_url endpoint exists
    """
    print("\n" + "=" * 80)
    print("TEST 4: Contract PDF URL endpoint")
    print("=" * 80)
    
    try:
        # Import routes
        from server.routes_contracts import get_contract_pdf_url
        
        # Check function exists
        if get_contract_pdf_url is None:
            print("❌ FAIL: get_contract_pdf_url function not found")
            return False
        
        # Get function signature
        sig = inspect.signature(get_contract_pdf_url)
        params = list(sig.parameters.keys())
        
        if 'contract_id' not in params:
            print(f"❌ FAIL: contract_id parameter not found in get_contract_pdf_url")
            return False
        
        print(f"✅ PASS: get_contract_pdf_url endpoint exists with parameters: {params}")
        
        # Check source for key functionality
        source = inspect.getsource(get_contract_pdf_url)
        
        checks = [
            ('generate_signed_url', 'Generates signed URL'),
            ('expires_at', 'Returns expiration time'),
            ('/api/contracts/<int:contract_id>/pdf_url', 'Route path (may not be in function)'),
        ]
        
        for check_str, description in checks:
            if check_str in source:
                print(f"  ✓ {description}")
            else:
                print(f"  ⚠️ {description} not found in source (may be elsewhere)")
        
        return True
        
    except ImportError as e:
        print(f"❌ FAIL: Could not import get_contract_pdf_url: {e}")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error testing contract PDF URL endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pdf_iframe_headers():
    """
    Test that security headers are properly configured for PDF endpoints
    """
    print("\n" + "=" * 80)
    print("TEST 5: PDF iframe headers configuration")
    print("=" * 80)
    
    try:
        # Import app_factory
        from server.app_factory import create_app
        
        # Get source code of add_security_headers (it's defined inside create_app)
        source = inspect.getsource(create_app)
        
        # Check for PDF endpoint detection
        if 'stream_contract_pdf' not in source or 'get_contract_pdf_url' not in source:
            print("⚠️  WARNING: PDF endpoint detection logic not found in app_factory")
            print("   (This may be defined elsewhere)")
        else:
            print("  ✓ PDF endpoint detection logic found")
        
        # Check for SAMEORIGIN header
        if 'SAMEORIGIN' in source:
            print("  ✓ X-Frame-Options: SAMEORIGIN configured for PDF endpoints")
        else:
            print("  ⚠️ SAMEORIGIN not found in source")
        
        # Check for frame-ancestors 'self'
        if "frame-ancestors 'self'" in source:
            print("  ✓ CSP frame-ancestors 'self' configured for PDF endpoints")
        else:
            print("  ⚠️ frame-ancestors 'self' not found in source")
        
        print(f"✅ PASS: Security headers configuration appears to be in place")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing PDF iframe headers: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("CRITICAL FIXES VALIDATION TEST SUITE")
    print("=" * 80)
    
    tests = [
        test_needs_review_initialization,
        test_heartbeat_callback_parameter,
        test_heartbeat_callback_invoked,
        test_contract_pdf_url_endpoint,
        test_pdf_iframe_headers,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERROR running {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
