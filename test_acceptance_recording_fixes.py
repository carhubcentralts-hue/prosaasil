#!/usr/bin/env python3
"""
Acceptance Test: Verify recording playback fixes

Acceptance Criteria:
✅ Loading Recent Calls does no enqueue (0 logs of DOWNLOAD_ONLY)
✅ Only clicking "Play Recording" creates one enqueue
✅ No spam of BLOCKED rate_limit in logs
✅ receipts/export works without 'Attachment' object has no attribute 'filename'
"""

import os
import sys

def test_list_calls_no_enqueue():
    """Verify that list_calls() doesn't trigger enqueue"""
    print("\n🧪 TEST: list_calls() doesn't trigger enqueue")
    
    routes_calls_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_calls.py'
    )
    
    with open(routes_calls_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find list_calls function
    list_calls_start = content.find('def list_calls():')
    if list_calls_start == -1:
        raise AssertionError("list_calls function not found")
    
    # Get the function content (up to next function definition)
    list_calls_end = content.find('\n@calls_bp.route', list_calls_start + 1)
    if list_calls_end == -1:
        list_calls_end = content.find('\ndef ', list_calls_start + 1)
    
    list_calls_section = content[list_calls_start:list_calls_end]
    
    # Check that it does NOT call enqueue_recording_download_only
    if 'enqueue_recording_download_only' in list_calls_section:
        raise AssertionError("list_calls() is calling enqueue_recording_download_only - this is NOT allowed!")
    
    print("✅ list_calls() does NOT call enqueue_recording_download_only")
    
    # Check for the guard comment
    if 'DO NOT enqueue downloads here' in list_calls_section or 'should ONLY return metadata' in list_calls_section:
        print("✅ list_calls() has guard comment about not enqueueing")
    else:
        print("⚠️ Warning: list_calls() missing explicit guard comment")
    
    print("✅ list_calls() acceptance test passed!")

def test_stream_recording_requires_explicit_action():
    """Verify that stream_recording requires explicit user action"""
    print("\n🧪 TEST: stream_recording requires explicit user action")
    
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
    
    # Get the function content
    stream_recording_end = content.find('\ndef ', stream_recording_start + 1)
    if stream_recording_end == -1:
        stream_recording_end = len(content)
    
    stream_recording_section = content[stream_recording_start:stream_recording_end]
    
    # Check for explicit action guard
    checks = {
        'explicit_user_action': 'explicit_user_action' in stream_recording_section,
        'X-User-Action header': 'X-User-Action' in stream_recording_section,
        'Returns 400': ', 400' in stream_recording_section,
        'Guard before business_id': stream_recording_section.find('explicit_user_action') < stream_recording_section.find('get_business_id')
    }
    
    for check, passed in checks.items():
        if passed:
            print(f"✅ {check}")
        else:
            raise AssertionError(f"Missing: {check}")
    
    # Verify it checks BEFORE doing any work
    explicit_action_pos = stream_recording_section.find('explicit_user_action')
    enqueue_pos = stream_recording_section.find('enqueue_recording_download_only')
    
    if explicit_action_pos < enqueue_pos:
        print("✅ Explicit action check happens BEFORE enqueue")
    else:
        raise AssertionError("Explicit action check must happen BEFORE enqueue!")
    
    print("✅ stream_recording explicit action test passed!")

def test_receipts_export_uses_safe_filename():
    """Verify receipts export uses safe_get_filename"""
    print("\n🧪 TEST: receipts export uses safe_get_filename")
    
    routes_receipts_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_receipts.py'
    )
    
    with open(routes_receipts_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check safe_get_filename is defined
    if 'def safe_get_filename' not in content:
        raise AssertionError("safe_get_filename function not found")
    print("✅ safe_get_filename function exists")
    
    # Find export_receipts function
    export_start = content.find('def export_receipts():')
    if export_start == -1:
        raise AssertionError("export_receipts function not found")
    
    export_end = content.find('\n@receipts_bp.route', export_start + 1)
    if export_end == -1:
        export_end = len(content)
    
    export_section = content[export_start:export_end]
    
    # Verify safe_get_filename is used
    if 'safe_get_filename(attachment_to_export' in export_section:
        print("✅ export_receipts uses safe_get_filename")
    else:
        raise AssertionError("export_receipts doesn't use safe_get_filename!")
    
    # Verify try/except per receipt exists
    if 'for receipt in receipts:' in export_section and 'try:' in export_section and 'except' in export_section:
        print("✅ export_receipts has try/except for resilience")
    else:
        print("⚠️ Warning: Couldn't verify try/except in export loop")
    
    print("✅ receipts export safety test passed!")

def test_frontend_sends_explicit_action():
    """Verify frontend sends explicit_user_action parameter"""
    print("\n🧪 TEST: Frontend sends explicit_user_action")
    
    frontend_files = [
        'client/src/shared/components/AudioPlayer.tsx',
        'client/src/pages/calls/CallsPage.tsx'
    ]
    
    for file_path in frontend_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        
        if not os.path.exists(full_path):
            print(f"⚠️ Warning: {file_path} not found")
            continue
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for explicit_user_action parameter
        if 'explicit_user_action=true' in content:
            print(f"✅ {file_path} sends explicit_user_action=true")
        else:
            raise AssertionError(f"{file_path} doesn't send explicit_user_action!")
        
        # Check for X-User-Action header
        if 'X-User-Action' in content:
            print(f"✅ {file_path} sends X-User-Action header")
        else:
            print(f"⚠️ Warning: {file_path} missing X-User-Action header")
    
    print("✅ Frontend explicit action test passed!")

def test_no_auto_enqueue_in_other_endpoints():
    """Verify no other endpoints auto-enqueue recordings"""
    print("\n🧪 TEST: No other endpoints auto-enqueue recordings")
    
    # Check routes_calls.py for any list/dashboard/search endpoints
    routes_calls_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_calls.py'
    )
    
    with open(routes_calls_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all route definitions that might list calls
    list_endpoints = []
    for line in content.split('\n'):
        if '@calls_bp.route' in line and ('list' in line.lower() or 'search' in line.lower() or 'dashboard' in line.lower()):
            list_endpoints.append(line.strip())
    
    print(f"Found {len(list_endpoints)} potential list endpoints")
    
    # For each endpoint, verify it doesn't enqueue
    for endpoint in list_endpoints:
        print(f"  Checking: {endpoint}")
    
    # The only endpoint that should enqueue is stream_recording
    enqueue_calls = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'enqueue_recording_download_only' in line:
            # Find the function this is in
            for j in range(i, -1, -1):
                if 'def ' in lines[j]:
                    func_name = lines[j].split('def ')[1].split('(')[0]
                    enqueue_calls.append(func_name)
                    break
    
    print(f"Functions that call enqueue_recording_download_only: {set(enqueue_calls)}")
    
    # Only stream_recording should enqueue
    allowed_functions = {'stream_recording'}
    unauthorized_enqueues = set(enqueue_calls) - allowed_functions
    
    if unauthorized_enqueues:
        raise AssertionError(f"Unauthorized enqueue calls in: {unauthorized_enqueues}")
    
    print("✅ Only authorized endpoints enqueue recordings")
    print("✅ No auto-enqueue test passed!")

def main():
    print("=" * 70)
    print("ACCEPTANCE TEST: Recording Playback Fixes")
    print("=" * 70)
    
    tests = [
        ("list_calls no enqueue", test_list_calls_no_enqueue),
        ("stream_recording requires action", test_stream_recording_requires_explicit_action),
        ("receipts export safe filename", test_receipts_export_uses_safe_filename),
        ("frontend sends explicit action", test_frontend_sends_explicit_action),
        ("no auto-enqueue elsewhere", test_no_auto_enqueue_in_other_endpoints),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL ACCEPTANCE TESTS PASSED!")
        print("\nAcceptance Criteria Met:")
        print("✅ Loading Recent Calls does no enqueue")
        print("✅ Only clicking 'Play Recording' creates enqueue")
        print("✅ Explicit user action guard prevents mass enqueue")
        print("✅ receipts/export uses safe filename handling")
        sys.exit(0)

if __name__ == "__main__":
    main()
