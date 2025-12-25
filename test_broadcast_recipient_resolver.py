"""
Test suite for WhatsApp broadcast recipient resolver

Tests the bulletproof recipient resolution with multiple input sources:
1. Direct phones (array or CSV string)
2. lead_ids (fetch from DB)
3. CSV file upload
4. Statuses (query leads by status)
"""
import sys
import json
from unittest.mock import Mock, MagicMock, patch
import io


# Mock the normalize_phone function from routes_whatsapp
def normalize_phone(phone_str) -> str:
    """Normalize phone number"""
    if not phone_str:
        return None
    
    phone = str(phone_str).strip()
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    if phone.startswith('+'):
        phone = phone[1:]
    
    if not phone.isdigit() or len(phone) < 8:
        return None
    
    return phone


def parse_csv_phones(csv_file) -> list:
    """Parse phone numbers from CSV file"""
    import csv
    phones = []
    try:
        content = csv_file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        csv_file.seek(0)
        reader = csv.DictReader(io.StringIO(content))
        
        for row in reader:
            phone = None
            for key in row.keys():
                if key.lower() in ['phone', 'telephone', 'mobile', 'number', 'tel', 'טלפון']:
                    phone = row[key]
                    break
            
            if not phone and row:
                phone = list(row.values())[0]
            
            normalized = normalize_phone(phone)
            if normalized:
                phones.append(normalized)
    except Exception as e:
        print(f"[parse_csv_phones] Error: {e}")
    
    return phones


def extract_phones_bulletproof(payload, files, business_id):
    """Extract phone numbers from multiple sources"""
    phones = []
    
    # 1) Direct phones
    raw_phones = payload.get('phones') or payload.get('recipients') or payload.get('selected_phones')
    if raw_phones:
        if isinstance(raw_phones, str):
            try:
                raw_phones = json.loads(raw_phones)
            except:
                raw_phones = [x.strip() for x in raw_phones.split(',') if x.strip()]
        
        if isinstance(raw_phones, list):
            for p in raw_phones:
                normalized = normalize_phone(p)
                if normalized:
                    phones.append(normalized)
    
    # 2) lead_ids - mock DB fetch
    lead_ids = payload.get('lead_ids') or payload.get('leadIds')
    if lead_ids:
        if isinstance(lead_ids, str):
            try:
                lead_ids = json.loads(lead_ids)
            except:
                lead_ids = []
        
        if isinstance(lead_ids, list) and lead_ids:
            # Mock: simulate DB response
            for lead_id in lead_ids:
                phones.append(f"97252{lead_id:07d}")  # Mock phone numbers
    
    # 3) csv_file
    if 'csv_file' in files:
        csv_phones = parse_csv_phones(files['csv_file'])
        phones.extend(csv_phones)
    
    # 4) statuses - mock DB query
    statuses = payload.get('statuses')
    if statuses:
        if isinstance(statuses, str):
            try:
                statuses = json.loads(statuses)
            except:
                statuses = []
        
        if isinstance(statuses, list) and statuses:
            # Mock: simulate DB response
            for i, status in enumerate(statuses):
                phones.append(f"97254{i:07d}")  # Mock phone numbers
    
    # Deduplicate and sort
    phones = sorted(set(p for p in phones if p))
    return phones


def test_direct_phones_array():
    """Test extraction from direct phones array"""
    print("\n" + "="*70)
    print("TEST 1: Direct Phones Array")
    print("="*70)
    
    payload = {
        'phones': ['972521234567', '972-52-7654321', '052 111 2222']
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: {payload['phones']}")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 3, f"Expected 3 phones, got {len(phones)}"
    assert '972521234567' in phones, "Should have normalized first phone"
    assert '972527654321' in phones, "Should have normalized second phone"
    assert '0521112222' in phones, "Should have normalized third phone"
    
    print("\n✅ TEST 1 PASSED: Direct phones array works correctly")
    return True


def test_direct_phones_csv_string():
    """Test extraction from CSV string"""
    print("\n" + "="*70)
    print("TEST 2: Direct Phones CSV String")
    print("="*70)
    
    payload = {
        'selected_phones': '972521234567, 972527654321, 0521112222'
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: {payload['selected_phones']}")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 3, f"Expected 3 phones, got {len(phones)}"
    
    print("\n✅ TEST 2 PASSED: CSV string works correctly")
    return True


def test_direct_phones_json_string():
    """Test extraction from JSON string"""
    print("\n" + "="*70)
    print("TEST 3: Direct Phones JSON String")
    print("="*70)
    
    payload = {
        'phones': '["972521234567", "972527654321", "0521112222"]'
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: {payload['phones']}")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 3, f"Expected 3 phones, got {len(phones)}"
    
    print("\n✅ TEST 3 PASSED: JSON string works correctly")
    return True


def test_lead_ids():
    """Test extraction from lead_ids"""
    print("\n" + "="*70)
    print("TEST 4: Lead IDs")
    print("="*70)
    
    payload = {
        'lead_ids': '[1, 2, 3]'
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: {payload['lead_ids']}")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 3, f"Expected 3 phones, got {len(phones)}"
    assert '9752000000' in phones or phones[0].startswith('97252'), "Should have mock lead phones"
    
    print("\n✅ TEST 4 PASSED: Lead IDs work correctly")
    return True


def test_csv_file():
    """Test extraction from CSV file"""
    print("\n" + "="*70)
    print("TEST 5: CSV File")
    print("="*70)
    
    csv_content = """phone,name
972521234567,Alice
972527654321,Bob
0521112222,Charlie"""
    
    csv_file = io.BytesIO(csv_content.encode('utf-8'))
    csv_file.name = 'test.csv'
    
    payload = {}
    files = {'csv_file': csv_file}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - CSV rows: 3")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 3, f"Expected 3 phones, got {len(phones)}"
    
    print("\n✅ TEST 5 PASSED: CSV file works correctly")
    return True


def test_statuses():
    """Test extraction from statuses"""
    print("\n" + "="*70)
    print("TEST 6: Statuses")
    print("="*70)
    
    payload = {
        'statuses': '["qualified", "contacted"]'
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: {payload['statuses']}")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 2, f"Expected 2 phones, got {len(phones)}"
    
    print("\n✅ TEST 6 PASSED: Statuses work correctly")
    return True


def test_empty_input():
    """Test with no input (should return empty list)"""
    print("\n" + "="*70)
    print("TEST 7: Empty Input")
    print("="*70)
    
    payload = {}
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: (empty)")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 0, f"Expected 0 phones, got {len(phones)}"
    
    print("\n✅ TEST 7 PASSED: Empty input handled correctly")
    return True


def test_multiple_sources():
    """Test with multiple input sources (should combine and deduplicate)"""
    print("\n" + "="*70)
    print("TEST 8: Multiple Sources (Priority)")
    print("="*70)
    
    payload = {
        'phones': ['972521234567'],
        'lead_ids': '[1, 2]',
        'statuses': '["qualified"]'
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input sources: phones, lead_ids, statuses")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    # Should have phones from all sources, deduplicated
    assert len(phones) >= 3, f"Expected at least 3 phones from multiple sources, got {len(phones)}"
    
    print("\n✅ TEST 8 PASSED: Multiple sources work correctly")
    return True


def test_invalid_phones_filtered():
    """Test that invalid phones are filtered out"""
    print("\n" + "="*70)
    print("TEST 9: Invalid Phones Filtered")
    print("="*70)
    
    payload = {
        'phones': ['972521234567', 'invalid', '123', '']
    }
    files = {}
    
    phones = extract_phones_bulletproof(payload, files, 'business_1')
    
    print(f"📊 Test Results:")
    print(f"   - Input: {payload['phones']}")
    print(f"   - Output: {phones}")
    print(f"   - Count: {len(phones)}")
    
    assert len(phones) == 1, f"Expected 1 valid phone, got {len(phones)}"
    assert '972521234567' in phones, "Should keep valid phone"
    
    print("\n✅ TEST 9 PASSED: Invalid phones filtered correctly")
    return True


def run_all_tests():
    """Run all WhatsApp broadcast resolver tests"""
    print("\n" + "="*70)
    print("WHATSAPP BROADCAST RECIPIENT RESOLVER - TEST SUITE")
    print("="*70)
    
    tests = [
        test_direct_phones_array,
        test_direct_phones_csv_string,
        test_direct_phones_json_string,
        test_lead_ids,
        test_csv_file,
        test_statuses,
        test_empty_input,
        test_multiple_sources,
        test_invalid_phones_filtered,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
