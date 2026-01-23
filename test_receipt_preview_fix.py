#!/usr/bin/env python3
"""
Test for receipt preview fix - verifies full HTML extraction and preview generation
"""

import sys
import base64

def test_html_extraction():
    """
    Test that extract_email_html_full returns full HTML while extract_email_html truncates
    """
    print("=" * 80)
    print("TEST: Full HTML extraction vs truncated snippet")
    print("=" * 80)
    
    # Import the functions
    from server.services.gmail_sync_service import extract_email_html_full, extract_email_html
    
    # Create a mock Gmail message with large HTML content
    large_html = "<html><body>" + ("X" * 20000) + "</body></html>"  # 20KB HTML
    
    # Encode as base64 (Gmail format)
    html_b64 = base64.urlsafe_b64encode(large_html.encode('utf-8')).decode('utf-8')
    
    mock_message = {
        'payload': {
            'parts': [
                {
                    'mimeType': 'text/html',
                    'body': {
                        'data': html_b64
                    }
                }
            ]
        }
    }
    
    # Test full HTML extraction
    full_html = extract_email_html_full(mock_message)
    truncated_html = extract_email_html(mock_message)
    
    print(f"\n📊 Results:")
    print(f"  Original HTML size: {len(large_html)} bytes")
    print(f"  Full HTML size: {len(full_html)} bytes")
    print(f"  Truncated HTML size: {len(truncated_html)} bytes")
    
    # Verify full HTML is complete
    if len(full_html) == len(large_html):
        print(f"✅ PASS: Full HTML extraction returns complete content")
    else:
        print(f"❌ FAIL: Full HTML extraction truncated (expected {len(large_html)}, got {len(full_html)})")
        return False
    
    # Verify truncated HTML is limited to 10KB
    if len(truncated_html) <= 10000:
        print(f"✅ PASS: Truncated HTML is limited to 10KB")
    else:
        print(f"❌ FAIL: Truncated HTML exceeds 10KB limit ({len(truncated_html)} bytes)")
        return False
    
    # Verify truncated is a subset of full
    if truncated_html == full_html[:10000]:
        print(f"✅ PASS: Truncated HTML is first 10KB of full HTML")
    else:
        print(f"❌ FAIL: Truncated HTML is not first 10KB of full HTML")
        return False
    
    return True


def test_preview_function_signature():
    """
    Test that the new preview function has the correct signature
    """
    print("\n" + "=" * 80)
    print("TEST: PNG preview generation function signature")
    print("=" * 80)
    
    from server.services.gmail_sync_service import generate_receipt_preview_png
    import inspect
    
    # Get function signature
    sig = inspect.signature(generate_receipt_preview_png)
    params = list(sig.parameters.keys())
    
    print(f"\n📋 Function parameters: {params}")
    
    expected_params = ['email_html', 'business_id', 'receipt_id', 'viewport_width', 'viewport_height', 'retry_attempt']
    
    if params == expected_params:
        print(f"✅ PASS: Function signature matches expected parameters")
        return True
    else:
        print(f"❌ FAIL: Function signature mismatch")
        print(f"   Expected: {expected_params}")
        print(f"   Got: {params}")
        return False


def test_improvements_documented():
    """
    Verify that key improvements are documented in code
    """
    print("\n" + "=" * 80)
    print("TEST: Code documentation for improvements")
    print("=" * 80)
    
    import os
    
    # Get the directory of this test file
    test_dir = os.path.dirname(os.path.abspath(__file__))
    gmail_sync_path = os.path.join(test_dir, 'server', 'services', 'gmail_sync_service.py')
    
    with open(gmail_sync_path, 'r') as f:
        content = f.read()
    
    improvements = [
        ('Full HTML extraction', 'extract_email_html_full'),
        ('PNG preview generation', 'generate_receipt_preview_png'),
        ('Font loading wait', 'document.fonts'),
        ('Image loading wait', 'document.images'),
        ('Screen media emulation', 'emulate_media'),
        ('Viewport size', 'viewport'),
        ('10KB threshold', '10 * 1024'),
        ('Retry logic', 'retry_attempt'),
    ]
    
    all_found = True
    for description, keyword in improvements:
        if keyword in content:
            print(f"✅ {description}: Found '{keyword}'")
        else:
            print(f"❌ {description}: Missing '{keyword}'")
            all_found = False
    
    return all_found


if __name__ == '__main__':
    print("\n🧪 Receipt Preview Fix - Test Suite\n")
    
    results = []
    
    try:
        results.append(("HTML Extraction", test_html_extraction()))
    except Exception as e:
        print(f"❌ HTML Extraction test failed with error: {e}")
        results.append(("HTML Extraction", False))
    
    try:
        results.append(("Function Signature", test_preview_function_signature()))
    except Exception as e:
        print(f"❌ Function Signature test failed with error: {e}")
        results.append(("Function Signature", False))
    
    try:
        results.append(("Documentation", test_improvements_documented()))
    except Exception as e:
        print(f"❌ Documentation test failed with error: {e}")
        results.append(("Documentation", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)
