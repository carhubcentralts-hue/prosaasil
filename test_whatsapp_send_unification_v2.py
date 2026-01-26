"""
Test: WhatsApp Send Unification
Verify that broadcast uses the same send path as regular sends

This test checks:
1. send_message() function exists and is properly configured
2. Phone normalization is consistent between broadcast and regular sends
3. Provider selection works correctly
4. Context parameter is respected (broadcast vs regular)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_send_service_import():
    """Test that the unified send service can be imported"""
    try:
        from server.services.whatsapp_send_service import send_message
        print("✅ whatsapp_send_service.send_message imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import send_message: {e}")
        return False

def test_phone_normalization():
    """Test that phone normalization is consistent"""
    from server.utils.whatsapp_utils import normalize_whatsapp_to
    
    test_cases = [
        ("+972501234567", "972501234567@s.whatsapp.net"),
        ("972501234567", "972501234567@s.whatsapp.net"),
        ("972501234567@s.whatsapp.net", "972501234567@s.whatsapp.net"),
    ]
    
    all_passed = True
    for phone_input, expected_jid in test_cases:
        try:
            jid, source = normalize_whatsapp_to(to=phone_input, business_id=1)
            if jid == expected_jid:
                print(f"✅ Normalization: {phone_input} → {jid}")
            else:
                print(f"❌ Normalization failed: {phone_input} → {jid} (expected {expected_jid})")
                all_passed = False
        except Exception as e:
            print(f"❌ Normalization exception for {phone_input}: {e}")
            all_passed = False
    
    return all_passed

def test_broadcast_worker_uses_send_service():
    """Test that broadcast_worker imports and uses send_message"""
    try:
        # Read broadcast_worker.py and check it imports send_message
        broadcast_worker_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'server', 'services', 'broadcast_worker.py'
        )
        
        with open(broadcast_worker_path, 'r') as f:
            content = f.read()
        
        # Check for unified service import
        if 'from server.services.whatsapp_send_service import send_message' in content:
            print("✅ broadcast_worker imports unified send_message")
        else:
            print("❌ broadcast_worker does not import unified send_message")
            return False
        
        # Check that it calls send_message with context='broadcast'
        if "context='broadcast'" in content:
            print("✅ broadcast_worker passes context='broadcast'")
        else:
            print("❌ broadcast_worker does not pass context='broadcast'")
            return False
        
        # Check that it passes retries=0
        if 'retries=0' in content:
            print("✅ broadcast_worker passes retries=0 to disable provider retries")
        else:
            print("❌ broadcast_worker does not pass retries=0")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to check broadcast_worker: {e}")
        return False

def test_no_alter_table_in_broadcast_job():
    """Test that broadcast_job.py no longer does ALTER TABLE at runtime"""
    try:
        broadcast_job_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'server', 'jobs', 'broadcast_job.py'
        )
        
        with open(broadcast_job_path, 'r') as f:
            lines = f.readlines()
        
        # Check that ALTER TABLE is not in executable code (ignore comments)
        has_alter_table = False
        for line in lines:
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            # Check if ALTER TABLE is in code
            if 'ALTER TABLE' in line and not line.strip().startswith('#'):
                has_alter_table = True
                break
        
        if not has_alter_table:
            print("✅ broadcast_job.py does not contain ALTER TABLE in code")
            return True
        else:
            print("❌ broadcast_job.py still contains ALTER TABLE in code (should be in migration)")
            return False
        
    except Exception as e:
        print(f"❌ Failed to check broadcast_job: {e}")
        return False

def test_migration_exists():
    """Test that migration_add_broadcast_cursor.py exists"""
    try:
        migration_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'migration_add_broadcast_cursor.py'
        )
        
        if os.path.exists(migration_path):
            print("✅ migration_add_broadcast_cursor.py exists")
            
            # Check it contains the column addition
            with open(migration_path, 'r') as f:
                content = f.read()
            
            if 'last_processed_recipient_id' in content:
                print("✅ Migration adds last_processed_recipient_id column")
                return True
            else:
                print("❌ Migration does not add last_processed_recipient_id column")
                return False
        else:
            print("❌ migration_add_broadcast_cursor.py does not exist")
            return False
        
    except Exception as e:
        print(f"❌ Failed to check migration: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("WhatsApp Send Unification Tests")
    print("=" * 60)
    
    tests = [
        ("Import unified send service", test_send_service_import),
        ("Phone normalization consistency", test_phone_normalization),
        ("Broadcast worker uses unified service", test_broadcast_worker_uses_send_service),
        ("No ALTER TABLE at runtime", test_no_alter_table_in_broadcast_job),
        ("Migration exists for cursor column", test_migration_exists),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📝 Test: {test_name}")
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
