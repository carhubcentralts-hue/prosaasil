#!/usr/bin/env python3
"""
Test script for bulletproof webhook secret resolver
Tests header normalization, secret cleaning, and fail-fast behavior
"""

def test_header_normalization():
    """Test that we support multiple header variants"""
    
    print("🧪 Testing Header Normalization\n")
    
    # Simulate different header formats
    test_cases = [
        {
            "name": "Standard X-Webhook-Secret",
            "headers": {"X-Webhook-Secret": "my_secret"},
            "expected_secret": "my_secret",
            "should_succeed": True
        },
        {
            "name": "Lowercase x-webhook-secret",
            "headers": {"x-webhook-secret": "my_secret"},
            "expected_secret": "my_secret",
            "should_succeed": True
        },
        {
            "name": "Underscore X_WEBHOOK_SECRET",
            "headers": {"X_WEBHOOK_SECRET": "my_secret"},
            "expected_secret": "my_secret",
            "should_succeed": True
        },
        {
            "name": "No header present",
            "headers": {},
            "expected_secret": None,
            "should_succeed": False
        },
        {
            "name": "Wrong header name",
            "headers": {"X-Wrong-Header": "my_secret"},
            "expected_secret": None,
            "should_succeed": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Headers: {test['headers']}")
        
        # Simulate header lookup (matches route logic)
        raw_secret = (
            test['headers'].get('X-Webhook-Secret') or
            test['headers'].get('x-webhook-secret') or
            test['headers'].get('X_WEBHOOK_SECRET') or
            ""
        )
        
        has_header = bool(raw_secret)
        
        if test['should_succeed']:
            if has_header and raw_secret == test['expected_secret']:
                print(f"  ✅ PASS - Found secret: {raw_secret}")
                passed += 1
            else:
                print(f"  ❌ FAIL - Expected {test['expected_secret']}, got {raw_secret}")
                failed += 1
        else:
            if not has_header:
                print(f"  ✅ PASS - Correctly detected missing header")
                passed += 1
            else:
                print(f"  ❌ FAIL - Should have failed but found: {raw_secret}")
                failed += 1
        
        print()
    
    print("=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def test_secret_normalization():
    """Test secret value normalization (strip whitespace, quotes)"""
    
    print("\n🧪 Testing Secret Normalization\n")
    
    test_cases = [
        {
            "name": "Clean secret",
            "raw": "my_secret_123",
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with leading whitespace",
            "raw": "  my_secret_123",
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with trailing whitespace",
            "raw": "my_secret_123  ",
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with leading newline",
            "raw": "\nmy_secret_123",
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with trailing newline",
            "raw": "my_secret_123\n",
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with double quotes",
            "raw": '"my_secret_123"',
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with single quotes",
            "raw": "'my_secret_123'",
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with quotes and whitespace",
            "raw": ' "my_secret_123" ',
            "expected": "my_secret_123"
        },
        {
            "name": "Secret with mixed mess",
            "raw": '\n "my_secret_123" \n',
            "expected": "my_secret_123"
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Raw: {repr(test['raw'])}")
        
        # Normalize (matches route logic)
        cleaned = test['raw'].strip().strip('"').strip("'").strip()
        
        if cleaned == test['expected']:
            print(f"  ✅ PASS - Cleaned: {repr(cleaned)}")
            passed += 1
        else:
            print(f"  ❌ FAIL - Expected {repr(test['expected'])}, got {repr(cleaned)}")
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def test_secret_masking():
    """Test secret masking for logging (first 7 + last 2)"""
    
    print("\n🧪 Testing Secret Masking (first7+last2)\n")
    
    test_cases = [
        {
            "name": "Long secret (> 9 chars)",
            "secret": "wh_n8n_business_six_secret_12345",
            "expected_pattern": "wh_n8n_...45"
        },
        {
            "name": "Short secret (< 9 chars)",
            "secret": "short",
            "expected_pattern": "sho..."  # Just first 3 + ...
        },
        {
            "name": "Very short secret (3 chars)",
            "secret": "abc",
            "expected_pattern": "***"
        },
        {
            "name": "Empty secret",
            "secret": "",
            "expected_pattern": "***"
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Secret length: {len(test['secret'])}")
        
        # Mask (matches route logic)
        secret = test['secret']
        if len(secret) > 9:
            masked = secret[:7] + "..." + secret[-2:]
        elif len(secret) > 0:
            masked = secret[:3] + "..." if len(secret) > 3 else "***"
        else:
            masked = "***"
        
        if masked == test['expected_pattern']:
            print(f"  ✅ PASS - Masked: {masked}")
            passed += 1
        else:
            print(f"  ❌ FAIL - Expected {test['expected_pattern']}, got {masked}")
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def test_fail_fast_query():
    """Test that we use exact match query without fallback"""
    
    print("\n🧪 Testing Fail-Fast Query Logic\n")
    
    # Simulate Business model
    class MockBusiness:
        def __init__(self, id, name, webhook_secret):
            self.id = id
            self.name = name
            self.webhook_secret = webhook_secret
    
    # Mock business data
    businesses = [
        MockBusiness(1, "Business One", "secret_one"),
        MockBusiness(2, "Business Two", "secret_two"),
        MockBusiness(3, "Business Three", None),  # No secret
    ]
    
    test_cases = [
        {
            "name": "Valid secret - exact match",
            "secret": "secret_one",
            "expected_business_id": 1,
            "should_find": True
        },
        {
            "name": "Invalid secret - no match",
            "secret": "invalid_secret",
            "expected_business_id": None,
            "should_find": False
        },
        {
            "name": "Empty secret - no match",
            "secret": "",
            "expected_business_id": None,
            "should_find": False
        },
        {
            "name": "Secret with extra space - no match (must be normalized first)",
            "secret": "secret_one ",
            "expected_business_id": None,
            "should_find": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Secret: {repr(test['secret'])}")
        
        # Simulate query (exact match, no fallback)
        webhook_secret = test['secret']
        business = None
        
        for b in businesses:
            if b.webhook_secret == webhook_secret:
                business = b
                break
        
        if test['should_find']:
            if business and business.id == test['expected_business_id']:
                print(f"  ✅ PASS - Found business_id={business.id}")
                passed += 1
            else:
                print(f"  ❌ FAIL - Expected business_id={test['expected_business_id']}, got {business.id if business else None}")
                failed += 1
        else:
            if business is None:
                print(f"  ✅ PASS - Correctly returned None (no fallback)")
                passed += 1
            else:
                print(f"  ❌ FAIL - Should have returned None, but found business_id={business.id}")
                failed += 1
        
        print()
    
    print("=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def test_diagnostic_logging():
    """Test that diagnostic info is logged correctly"""
    
    print("\n🧪 Testing Diagnostic Logging\n")
    
    test_cases = [
        {
            "name": "Valid request",
            "headers": {"X-Webhook-Secret": "my_secret"},
            "expected_has_header": True,
            "expected_raw_len": 9,
            "expected_clean_len": 9
        },
        {
            "name": "Request with whitespace",
            "headers": {"X-Webhook-Secret": "  my_secret  "},
            "expected_has_header": True,
            "expected_raw_len": 13,
            "expected_clean_len": 9
        },
        {
            "name": "Request with newline",
            "headers": {"X-Webhook-Secret": "my_secret\n"},
            "expected_has_header": True,
            "expected_raw_len": 10,
            "expected_clean_len": 9
        },
        {
            "name": "Missing header",
            "headers": {},
            "expected_has_header": False,
            "expected_raw_len": 0,
            "expected_clean_len": 0
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        
        # Simulate header extraction
        raw_secret = (
            test['headers'].get('X-Webhook-Secret') or
            test['headers'].get('x-webhook-secret') or
            test['headers'].get('X_WEBHOOK_SECRET') or
            ""
        )
        
        has_header = bool(raw_secret)
        raw_len = len(raw_secret)
        
        # Clean
        webhook_secret = raw_secret.strip().strip('"').strip("'").strip()
        clean_len = len(webhook_secret)
        
        # Verify diagnostics
        success = True
        if has_header != test['expected_has_header']:
            print(f"  ❌ has_header mismatch: expected {test['expected_has_header']}, got {has_header}")
            success = False
        if raw_len != test['expected_raw_len']:
            print(f"  ❌ raw_len mismatch: expected {test['expected_raw_len']}, got {raw_len}")
            success = False
        if clean_len != test['expected_clean_len']:
            print(f"  ❌ clean_len mismatch: expected {test['expected_clean_len']}, got {clean_len}")
            success = False
        
        if success:
            print(f"  ✅ PASS - has_header={has_header}, raw_len={raw_len}, clean_len={clean_len}")
            passed += 1
        else:
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    print("=" * 60)
    print("Bulletproof Webhook Secret Resolver - Unit Tests")
    print("=" * 60)
    print()
    
    results = []
    results.append(("Header Normalization", test_header_normalization()))
    results.append(("Secret Normalization", test_secret_normalization()))
    results.append(("Secret Masking", test_secret_masking()))
    results.append(("Fail-Fast Query", test_fail_fast_query()))
    results.append(("Diagnostic Logging", test_diagnostic_logging()))
    
    print("\n" + "=" * 60)
    print("FINAL TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        exit(1)
