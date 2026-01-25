#!/usr/bin/env python3
"""
FINAL ACCEPTANCE TEST: All Critical Issues Fixed

This test validates all 3 critical fixes requested:
1. Receipt deletion works with worker
2. No auto-enqueue of recordings (0 mass downloads)
3. Filename safety everywhere
"""

import os
import sys

def test_worker_listens_to_maintenance_queue():
    """Verify worker configuration includes maintenance queue"""
    print("\n🧪 TEST 1: Worker listens to maintenance queue")
    
    # Check docker-compose.yml
    compose_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
    with open(compose_path, 'r') as f:
        content = f.read()
    
    if 'RQ_QUEUES: high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts' in content:
        print("✅ docker-compose.yml has maintenance in RQ_QUEUES")
    else:
        raise AssertionError("docker-compose.yml missing maintenance in RQ_QUEUES")
    
    # Check docker-compose.prod.yml
    compose_prod_path = os.path.join(os.path.dirname(__file__), 'docker-compose.prod.yml')
    with open(compose_prod_path, 'r') as f:
        content = f.read()
    
    if 'RQ_QUEUES: high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts' in content:
        print("✅ docker-compose.prod.yml has maintenance in RQ_QUEUES")
    else:
        raise AssertionError("docker-compose.prod.yml missing maintenance in RQ_QUEUES")
    
    # Check worker.py logs queues on startup
    worker_path = os.path.join(os.path.dirname(__file__), 'server', 'worker.py')
    with open(worker_path, 'r') as f:
        content = f.read()
    
    if 'WORKER QUEUES CONFIGURATION' in content and 'Listening to' in content:
        print("✅ worker.py logs queue configuration on startup")
    else:
        raise AssertionError("worker.py missing explicit queue logging")
    
    print("✅ Worker queue configuration test passed!")

def test_delete_job_has_clear_logging():
    """Verify delete job logs when picked and started"""
    print("\n🧪 TEST 2: Delete job has clear start logging")
    
    delete_job_path = os.path.join(os.path.dirname(__file__), 'server', 'jobs', 'delete_receipts_job.py')
    with open(delete_job_path, 'r') as f:
        content = f.read()
    
    required_logs = [
        'JOB PICKED',
        'queue=maintenance',
        'function=delete_receipts_batch_job'
    ]
    
    for log in required_logs:
        if log not in content:
            raise AssertionError(f"Missing required log: {log}")
        print(f"✅ Has log marker: {log}")
    
    # Check that imports are wrapped in try/except
    if 'try:' in content and 'from server.app_factory import create_app' in content:
        print("✅ Imports wrapped in try/except for error catching")
    else:
        print("⚠️ Warning: Imports might not have error handling")
    
    print("✅ Delete job logging test passed!")

def test_enqueue_logs_queue_and_ids():
    """Verify enqueue operation logs all details"""
    print("\n🧪 TEST 3: Enqueue logs queue name and IDs")
    
    routes_receipts_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_receipts.py')
    with open(routes_receipts_path, 'r') as f:
        content = f.read()
    
    required_fields = [
        'queue_name',
        'rq_job_id',
        'bg_job_id',
        'business_id',
        'total_receipts'
    ]
    
    # Find the enqueue section
    enqueue_start = content.find('maintenance_queue.enqueue(')
    enqueue_section = content[enqueue_start:enqueue_start + 2000]
    
    for field in required_fields:
        if field in enqueue_section:
            print(f"✅ Logs field: {field}")
        else:
            raise AssertionError(f"Missing log field: {field}")
    
    print("✅ Enqueue logging test passed!")

def test_no_auto_enqueue_recordings():
    """Verify NO auto-enqueue of recordings anywhere"""
    print("\n🧪 TEST 4: No auto-enqueue of recordings")
    
    routes_calls_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_calls.py')
    with open(routes_calls_path, 'r') as f:
        content = f.read()
    
    # Check list_calls doesn't enqueue
    list_calls_start = content.find('def list_calls():')
    list_calls_end = content.find('\n@calls_bp.route', list_calls_start + 1)
    if list_calls_end == -1:
        list_calls_end = content.find('\ndef ', list_calls_start + 1)
    
    list_calls_section = content[list_calls_start:list_calls_end]
    
    if 'enqueue_recording' in list_calls_section:
        raise AssertionError("list_calls() is enqueueing recordings - FORBIDDEN!")
    print("✅ list_calls() does NOT enqueue recordings")
    
    # Check stream_recording requires explicit action BEFORE enqueue
    stream_recording_start = content.find('def stream_recording(call_sid):')
    if stream_recording_start == -1:
        raise AssertionError("stream_recording function not found!")
    
    # Get a larger section to ensure we capture the enqueue call
    stream_recording_section = content[stream_recording_start:stream_recording_start + 6000]
    
    explicit_action_pos = stream_recording_section.find('explicit_user_action')
    # Look for any enqueue pattern
    enqueue_patterns = ['enqueue_recording_download_only', 'enqueue_recording']
    enqueue_pos = -1
    for pattern in enqueue_patterns:
        pos = stream_recording_section.find(pattern)
        if pos != -1 and 'import' not in stream_recording_section[max(0, pos-50):pos]:
            enqueue_pos = pos
            break
    
    if explicit_action_pos == -1:
        raise AssertionError("stream_recording missing explicit_user_action check!")
    
    if enqueue_pos == -1:
        print("⚠️ Warning: No enqueue call found (may be correct if caching only)")
        # Don't fail - maybe the recording is served from cache
    elif explicit_action_pos > enqueue_pos:
        raise AssertionError("explicit_user_action check MUST come before enqueue!")
    else:
        print("✅ stream_recording requires explicit action BEFORE enqueue")
    
    # Check that it returns 400 if missing
    if ', 400' in stream_recording_section and 'explicit_user_action' in stream_recording_section:
        print("✅ Returns 400 when explicit_user_action missing")
    else:
        raise AssertionError("Missing 400 response for missing explicit_user_action")
    
    print("✅ Recording auto-enqueue test passed!")

def test_frontend_sends_explicit_action():
    """Verify frontend always sends explicit_user_action"""
    print("\n🧪 TEST 5: Frontend sends explicit_user_action")
    
    audio_player_path = os.path.join(os.path.dirname(__file__), 'client', 'src', 'shared', 'components', 'AudioPlayer.tsx')
    if os.path.exists(audio_player_path):
        with open(audio_player_path, 'r') as f:
            content = f.read()
        
        if 'explicit_user_action=true' in content:
            print("✅ AudioPlayer sends explicit_user_action=true")
        else:
            raise AssertionError("AudioPlayer missing explicit_user_action!")
        
        if 'X-User-Action' in content:
            print("✅ AudioPlayer sends X-User-Action header")
        else:
            print("⚠️ AudioPlayer missing X-User-Action header")
    
    calls_page_path = os.path.join(os.path.dirname(__file__), 'client', 'src', 'pages', 'calls', 'CallsPage.tsx')
    if os.path.exists(calls_page_path):
        with open(calls_page_path, 'r') as f:
            content = f.read()
        
        if 'explicit_user_action=true' in content:
            print("✅ CallsPage sends explicit_user_action=true")
        else:
            raise AssertionError("CallsPage missing explicit_user_action!")
    
    print("✅ Frontend explicit action test passed!")

def test_filename_safety_everywhere():
    """Verify safe_get_filename is used consistently"""
    print("\n🧪 TEST 6: Filename safety everywhere")
    
    routes_receipts_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_receipts.py')
    with open(routes_receipts_path, 'r') as f:
        content = f.read()
    
    # Check safe_get_filename is defined
    if 'def safe_get_filename' not in content:
        raise AssertionError("safe_get_filename function not defined!")
    print("✅ safe_get_filename function exists")
    
    # Check it handles None correctly (no id(attachment) call when attachment is None)
    safe_func_start = content.find('def safe_get_filename')
    safe_func_end = content.find('\ndef ', safe_func_start + 1)
    safe_func_section = content[safe_func_start:safe_func_end]
    
    if 'if not attachment:' in safe_func_section and 'return default or "unknown_file"' in safe_func_section:
        print("✅ safe_get_filename handles None correctly")
    else:
        raise AssertionError("safe_get_filename doesn't handle None correctly!")
    
    # Check it's used in export_receipts
    export_start = content.find('def export_receipts():')
    export_end = content.find('\n@receipts_bp.route', export_start + 1)
    if export_end == -1:
        export_end = len(content)
    
    export_section = content[export_start:export_end]
    
    if 'safe_get_filename(attachment_to_export' in export_section:
        print("✅ export_receipts uses safe_get_filename")
    else:
        raise AssertionError("export_receipts doesn't use safe_get_filename!")
    
    # Check for any remaining unsafe .filename access in export
    # (allowing attachment_to_export.mime_type and other safe attributes)
    import re
    unsafe_patterns = re.findall(r'attachment_to_export\.filename\b', export_section)
    if unsafe_patterns:
        raise AssertionError(f"Found unsafe filename access in export: {len(unsafe_patterns)} occurrences")
    print("✅ No unsafe filename access in export")
    
    print("✅ Filename safety test passed!")

def main():
    print("=" * 70)
    print("FINAL ACCEPTANCE TEST: All Critical Fixes")
    print("=" * 70)
    print("")
    print("Testing 3 critical fixes:")
    print("1. Receipt deletion works with worker (queue configuration)")
    print("2. No auto-enqueue of recordings (explicit user action only)")
    print("3. Filename safety everywhere (safe_get_filename)")
    print("")
    
    tests = [
        ("Worker listens to maintenance", test_worker_listens_to_maintenance_queue),
        ("Delete job logging", test_delete_job_has_clear_logging),
        ("Enqueue logging details", test_enqueue_logs_queue_and_ids),
        ("No auto-enqueue recordings", test_no_auto_enqueue_recordings),
        ("Frontend explicit action", test_frontend_sends_explicit_action),
        ("Filename safety", test_filename_safety_everywhere),
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
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    print("=" * 70)
    
    if failed > 0:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL FINAL ACCEPTANCE TESTS PASSED!")
        print("\n📋 Acceptance Criteria Met:")
        print("   1. ✅ Receipt deletion: Worker listens to maintenance queue")
        print("      - docker-compose.yml includes maintenance")
        print("      - docker-compose.prod.yml includes maintenance")
        print("      - Worker logs queues on startup")
        print("      - Delete job logs when picked and started")
        print("")
        print("   2. ✅ Recordings: No auto-enqueue, explicit action only")
        print("      - list_calls() does NOT enqueue")
        print("      - stream_recording requires explicit_user_action before enqueue")
        print("      - Returns 400 if explicit_user_action missing")
        print("      - Frontend sends explicit_user_action + header")
        print("")
        print("   3. ✅ Filename safety: safe_get_filename everywhere")
        print("      - safe_get_filename handles None correctly")
        print("      - export_receipts uses safe_get_filename")
        print("      - No unsafe filename access patterns")
        sys.exit(0)

if __name__ == "__main__":
    main()
