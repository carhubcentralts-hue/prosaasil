#!/usr/bin/env python3
"""
Test to verify that process_recording_download_job can be imported
and has the correct signature.

This test verifies the fix for the import error:
  cannot import name 'process_recording_download_job' from 'server.jobs.recording_job'
"""
import ast
import sys


def test_function_exists():
    """Verify that process_recording_download_job function exists"""
    with open('server/jobs/recording_job.py', 'r') as f:
        tree = ast.parse(f.read())
    
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    
    assert 'process_recording_download_job' in functions, \
        "process_recording_download_job function not found in recording_job.py"
    
    print("✅ process_recording_download_job function exists")


def test_function_signature():
    """Verify that process_recording_download_job has the correct signature"""
    with open('server/jobs/recording_job.py', 'r') as f:
        content = f.read()
        tree = ast.parse(content)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'process_recording_download_job':
            args = [arg.arg for arg in node.args.args]
            expected_args = ['call_sid', 'recording_url', 'business_id', 'from_number', 'to_number', 'recording_sid']
            
            assert args == expected_args, \
                f"Function signature mismatch. Expected {expected_args}, got {args}"
            
            print(f"✅ Function signature correct: {args}")
            return
    
    raise AssertionError("process_recording_download_job function not found")


def test_imports_from_enqueue():
    """Verify that enqueue_recording_download_only can import the function"""
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Check that the import statement exists
    assert 'from server.jobs.recording_job import process_recording_download_job' in content, \
        "Import statement not found in tasks_recording.py"
    
    print("✅ Import statement exists in tasks_recording.py")


def test_enqueue_parameters_match():
    """Verify that enqueue call parameters match function signature"""
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the enqueue call
    enqueue_start = content.find('queue.enqueue(\n            process_recording_download_job,')
    if enqueue_start == -1:
        raise AssertionError("enqueue call not found")
    
    # Extract the parameters section
    enqueue_section = content[enqueue_start:enqueue_start + 500]
    
    # Check for expected parameters
    expected_params = ['call_sid=', 'recording_url=', 'business_id=', 'from_number=', 'to_number=', 'recording_sid=']
    
    for param in expected_params:
        assert param in enqueue_section, f"Parameter {param} not found in enqueue call"
    
    print(f"✅ Enqueue parameters match: {expected_params}")


def test_function_creates_recording_run():
    """Verify that the function creates a RecordingRun"""
    with open('server/jobs/recording_job.py', 'r') as f:
        content = f.read()
    
    # Find the function
    func_start = content.find('def process_recording_download_job')
    if func_start == -1:
        raise AssertionError("Function not found")
    
    # Find the next function to get the boundary
    next_func = content.find('\ndef process_recording_rq_job', func_start)
    func_content = content[func_start:next_func] if next_func != -1 else content[func_start:]
    
    # Check that it creates a RecordingRun
    assert 'RecordingRun(' in func_content, "Function should create a RecordingRun"
    assert 'process_recording_rq_job(run.id)' in func_content, "Function should call process_recording_rq_job"
    
    print("✅ Function creates RecordingRun and delegates to process_recording_rq_job")


if __name__ == '__main__':
    print("Testing recording job import fix...")
    print()
    
    try:
        test_function_exists()
        test_function_signature()
        test_imports_from_enqueue()
        test_enqueue_parameters_match()
        test_function_creates_recording_run()
        
        print()
        print("=" * 60)
        print("✅ All tests passed! The import error fix is correct.")
        print("=" * 60)
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
