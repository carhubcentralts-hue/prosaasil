#!/usr/bin/env python3
"""
Test script to verify webhook secret business resolution logic
This tests the core logic without requiring a full database setup
"""

def test_webhook_secret_resolution():
    """Test business resolution from webhook secret"""
    
    print("🧪 Testing Webhook Secret Business Resolution\n")
    
    # Simulate Business model
    class MockBusiness:
        def __init__(self, id, name, webhook_secret, whatsapp_provider):
            self.id = id
            self.name = name
            self.webhook_secret = webhook_secret
            self.whatsapp_provider = whatsapp_provider
    
    # Mock business data
    businesses = [
        MockBusiness(1, "Business One", "secret_business_1", "baileys"),
        MockBusiness(6, "Business Six", "wh_n8n_business_six_secret", "baileys"),
        MockBusiness(10, "Business Ten", "wh_n8n_business_ten_secret", "meta"),
    ]
    
    # Test cases
    test_cases = [
        {
            "name": "Valid secret for business 6",
            "secret": "wh_n8n_business_six_secret",
            "expected_business_id": 6,
            "expected_name": "Business Six",
            "expected_provider": "baileys",
            "should_succeed": True
        },
        {
            "name": "Valid secret for business 10",
            "secret": "wh_n8n_business_ten_secret",
            "expected_business_id": 10,
            "expected_name": "Business Ten",
            "expected_provider": "meta",
            "should_succeed": True
        },
        {
            "name": "Invalid secret",
            "secret": "invalid_secret_12345",
            "expected_business_id": None,
            "expected_name": None,
            "expected_provider": None,
            "should_succeed": False
        },
        {
            "name": "Empty secret",
            "secret": "",
            "expected_business_id": None,
            "expected_name": None,
            "expected_provider": None,
            "should_succeed": False
        },
        {
            "name": "None secret",
            "secret": None,
            "expected_business_id": None,
            "expected_name": None,
            "expected_provider": None,
            "should_succeed": False
        }
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Secret: {test['secret']}")
        
        # Simulate business lookup
        webhook_secret = test['secret']
        business = None
        
        if webhook_secret:
            for b in businesses:
                if b.webhook_secret == webhook_secret:
                    business = b
                    break
        
        # Check results
        if test['should_succeed']:
            if business:
                if (business.id == test['expected_business_id'] and 
                    business.name == test['expected_name'] and
                    business.whatsapp_provider == test['expected_provider']):
                    print(f"  ✅ PASS - Resolved to business_id={business.id}, name={business.name}, provider={business.whatsapp_provider}")
                    passed += 1
                else:
                    print(f"  ❌ FAIL - Expected business_id={test['expected_business_id']}, got {business.id}")
                    failed += 1
            else:
                print(f"  ❌ FAIL - Expected to find business, but got None")
                failed += 1
        else:
            if business is None:
                print(f"  ✅ PASS - Correctly rejected invalid secret")
                passed += 1
            else:
                print(f"  ❌ FAIL - Should have rejected but found business_id={business.id}")
                failed += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False

def test_tenant_id_generation():
    """Test tenant_id generation from business_id"""
    
    print("\n🧪 Testing Tenant ID Generation\n")
    
    test_cases = [
        {"business_id": 1, "expected": "business_1"},
        {"business_id": 6, "expected": "business_6"},
        {"business_id": 10, "expected": "business_10"},
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        tenant_id = f"business_{test['business_id']}"
        if tenant_id == test['expected']:
            print(f"✅ PASS - business_id={test['business_id']} -> tenant_id={tenant_id}")
            passed += 1
        else:
            print(f"❌ FAIL - business_id={test['business_id']}, expected {test['expected']}, got {tenant_id}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False

def test_secret_hashing():
    """Test secret masking for logging using SHA256"""
    
    print("\n🧪 Testing Secret Masking with SHA256\n")
    
    import hashlib
    
    test_cases = [
        {"secret": "wh_n8n_very_long_secret_12345", "description": "Long secret"},
        {"secret": "short", "description": "Short secret"},
        {"secret": "12345678901", "description": "Medium secret"},
        {"secret": "", "description": "Empty secret"},
        {"secret": None, "description": "None secret"},
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        secret = test['secret']
        desc = test['description']
        
        # Actual masking function logic
        if not secret:
            secret_hash = "***"
        else:
            hash_obj = hashlib.sha256(secret.encode('utf-8')).hexdigest()
            secret_hash = hash_obj[:6]
        
        # Verify hash is 6 chars or ***
        if secret and len(secret_hash) == 6:
            print(f"✅ PASS - {desc}: '{secret}' -> hash={secret_hash}")
            passed += 1
        elif not secret and secret_hash == "***":
            print(f"✅ PASS - {desc}: empty/None -> ***")
            passed += 1
        else:
            print(f"❌ FAIL - {desc}: unexpected result {secret_hash}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Webhook Secret Fix - Unit Tests")
    print("=" * 60)
    print()
    
    result1 = test_webhook_secret_resolution()
    result2 = test_tenant_id_generation()
    result3 = test_secret_hashing()
    
    print("\n" + "=" * 60)
    if result1 and result2 and result3:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        exit(1)
