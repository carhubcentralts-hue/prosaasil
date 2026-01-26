#!/usr/bin/env python3
"""
Test to verify both recording job import fixes:
1. process_recording_download_job exists in server.jobs.recording_job
2. enqueue_recording_job exists in server.tasks_recording

This test verifies the fixes for both import errors reported:
- cannot import name 'process_recording_download_job' from 'server.jobs.recording_job'
- cannot import name 'enqueue_recording_job' from 'server.tasks_recording'
"""
import ast
import sys


def test_process_recording_download_job_exists():
    """Verify that process_recording_download_job exists in recording_job.py"""
    with open('server/jobs/recording_job.py', 'r') as f:
        tree = ast.parse(f.read())
    
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    
    assert 'process_recording_download_job' in functions, \
        "process_recording_download_job function not found in recording_job.py"
    
    print("✅ process_recording_download_job exists in recording_job.py")


def test_enqueue_recording_job_exists():
    """Verify that enqueue_recording_job exists in tasks_recording.py"""
    with open('server/tasks_recording.py', 'r') as f:
        tree = ast.parse(f.read())
    
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    
    assert 'enqueue_recording_job' in functions, \
        "enqueue_recording_job function not found in tasks_recording.py"
    
    print("✅ enqueue_recording_job exists in tasks_recording.py")


def test_enqueue_recording_job_signature():
    """Verify that enqueue_recording_job has the correct signature"""
    with open('server/tasks_recording.py', 'r') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'enqueue_recording_job':
            args = [arg.arg for arg in node.args.args]
            expected_args = ['call_sid', 'recording_url', 'business_id', 'from_number', 'to_number', 'retry_count', 'recording_sid']
            
            assert args == expected_args, \
                f"Function signature mismatch. Expected {expected_args}, got {args}"
            
            print(f"✅ enqueue_recording_job signature correct: {args}")
            return
    
    raise AssertionError("enqueue_recording_job function not found")


def test_routes_twilio_import():
    """Verify that routes_twilio.py imports enqueue_recording_job correctly"""
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Check that the import statement exists
    assert 'from server.tasks_recording import enqueue_recording_job' in content, \
        "Import statement not found in routes_twilio.py"
    
    print("✅ Import statement exists in routes_twilio.py")


def test_enqueue_recording_rq_complete():
    """Verify that enqueue_recording_rq creates RecordingRun"""
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the function
    func_start = content.find('def enqueue_recording_rq(')
    if func_start == -1:
        raise AssertionError("enqueue_recording_rq function not found")
    
    # Find the next function to get the boundary
    next_func = content.find('\ndef enqueue_recording_download_only', func_start)
    func_content = content[func_start:next_func] if next_func != -1 else content[func_start:]
    
    # Check that it creates a RecordingRun
    assert 'RecordingRun(' in func_content, "Function should create a RecordingRun"
    assert 'run_id = run.id' in func_content, "Function should set run_id from RecordingRun"
    assert 'process_recording_rq_job' in func_content, "Function should call process_recording_rq_job"
    
    print("✅ enqueue_recording_rq creates RecordingRun and enqueues properly")


def test_enqueue_recording_job_delegates():
    """Verify that enqueue_recording_job delegates to enqueue_recording_rq"""
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the function
    func_start = content.find('def enqueue_recording_job(')
    if func_start == -1:
        raise AssertionError("enqueue_recording_job function not found")
    
    # Find the next function to get the boundary
    next_func = content.find('\ndef enqueue_recording(', func_start)
    func_content = content[func_start:next_func] if next_func != -1 else content[func_start:]
    
    # Check that it delegates to enqueue_recording_rq
    assert 'enqueue_recording_rq(' in func_content, "Function should call enqueue_recording_rq"
    assert "job_type='full'" in func_content, "Function should use job_type='full'"
    
    print("✅ enqueue_recording_job delegates to enqueue_recording_rq with job_type='full'")


if __name__ == '__main__':
    print("Testing recording job import fixes...")
    print()
    
    try:
        test_process_recording_download_job_exists()
        test_enqueue_recording_job_exists()
        test_enqueue_recording_job_signature()
        test_routes_twilio_import()
        test_enqueue_recording_rq_complete()
        test_enqueue_recording_job_delegates()
        
        print()
        print("=" * 60)
        print("✅ All tests passed! Both import errors are fixed.")
        print("=" * 60)
        print()
        print("Fixed imports:")
        print("  1. process_recording_download_job (recording_job.py)")
        print("  2. enqueue_recording_job (tasks_recording.py)")
        sys.exit(0)
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Unexpected error: {e}")
        print("=" * 60)
        sys.exit(1)
