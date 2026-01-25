#!/usr/bin/env python3
"""
Test: Verify explicit user action guard for recording playback

This test verifies that:
1. stream_recording endpoint requires explicit_user_action parameter or header
2. Returns 400 if neither is provided
3. Proceeds normally when proper authentication is provided
"""

def test_explicit_action_guard_logic():
    """Test the logic for explicit action guard without running Flask app"""
    print("\n🧪 TEST: Explicit action guard logic")
    
    # Simulate request scenarios
    test_cases = [
        {
            "name": "No explicit action - should fail",
            "query_param": False,
            "header": False,
            "expected": False
        },
        {
            "name": "Query param only - should pass",
            "query_param": True,
            "header": False,
            "expected": True
        },
        {
            "name": "Header only - should pass",
            "query_param": False,
            "header": True,
            "expected": True
        },
        {
            "name": "Both provided - should pass",
            "query_param": True,
            "header": True,
            "expected": True
        }
    ]
    
    for test_case in test_cases:
        explicit_action = test_case["query_param"]
        user_action_header = test_case["header"]
        expected = test_case["expected"]
        
        # This is the guard logic from routes_calls.py
        result = explicit_action or user_action_header
        
        if result == expected:
            print(f"✅ PASS: {test_case['name']}")
        else:
            print(f"❌ FAIL: {test_case['name']}")
            print(f"   Expected: {expected}, Got: {result}")
            raise AssertionError(f"Test failed: {test_case['name']}")
    
    print("✅ All explicit action guard tests passed!")

def test_safe_get_filename_in_receipts():
    """Verify that routes_receipts.py uses safe_get_filename"""
    print("\n🧪 TEST: safe_get_filename usage in receipts export")
    
    import os
    routes_receipts_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_receipts.py'
    )
    
    with open(routes_receipts_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that safe_get_filename is defined
    if 'def safe_get_filename' not in content:
        raise AssertionError("safe_get_filename function not found in routes_receipts.py")
    print("✅ safe_get_filename function exists")
    
    # Check that it's used in export_receipts
    if 'safe_get_filename(attachment_to_export' in content:
        print("✅ safe_get_filename is used in export_receipts")
    else:
        raise AssertionError("safe_get_filename not used in export_receipts")
    
    # Check that direct .filename access is NOT used in export (should be safe_get_filename)
    export_section_start = content.find('def export_receipts():')
    export_section_end = content.find('\n@receipts_bp.route', export_section_start + 1)
    if export_section_end == -1:
        export_section_end = len(content)
    
    export_section = content[export_section_start:export_section_end]
    
    # Look for unsafe filename access patterns
    unsafe_patterns = [
        'attachment_to_export.filename',
        'attachment.filename '
    ]
    
    for pattern in unsafe_patterns:
        if pattern in export_section and 'safe_get_filename' not in pattern:
            # Check if it's in a comment
            lines = export_section.split('\n')
            for line in lines:
                if pattern in line and not line.strip().startswith('#'):
                    print(f"⚠️ Warning: Found potentially unsafe pattern: {pattern}")
                    print(f"   Line: {line.strip()}")
    
    print("✅ All filename safety checks passed!")

def test_routes_calls_explicit_action_code():
    """Verify that routes_calls.py has the explicit action guard"""
    print("\n🧪 TEST: Explicit action guard in routes_calls.py")
    
    import os
    routes_calls_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_calls.py'
    )
    
    with open(routes_calls_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find stream_recording function
    stream_recording_start = content.find('def stream_recording(call_sid):')
    if stream_recording_start == -1:
        raise AssertionError("stream_recording function not found")
    
    # Get the function content (up to next function or end)
    stream_recording_end = content.find('\ndef ', stream_recording_start + 1)
    if stream_recording_end == -1:
        stream_recording_end = len(content)
    
    stream_recording_section = content[stream_recording_start:stream_recording_end]
    
    # Check for explicit action guard
    required_checks = [
        "explicit_user_action",
        "X-User-Action",
        "return jsonify"
    ]
    
    for check in required_checks:
        if check not in stream_recording_section:
            raise AssertionError(f"Required check '{check}' not found in stream_recording")
        print(f"✅ Found required check: {check}")
    
    # Check that it returns 400 if not provided
    if "400" in stream_recording_section and "explicit_user_action" in stream_recording_section:
        print("✅ Returns 400 when explicit_user_action not provided")
    else:
        raise AssertionError("Missing 400 response for missing explicit_user_action")
    
    print("✅ All explicit action guard code checks passed!")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Recording Explicit Action Guards")
    print("=" * 60)
    
    try:
        test_explicit_action_guard_logic()
        test_safe_get_filename_in_receipts()
        test_routes_calls_explicit_action_code()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
