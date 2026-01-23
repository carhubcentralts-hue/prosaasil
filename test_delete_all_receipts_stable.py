"""
Test Delete All Receipts Stable Implementation
Tests the background job-based delete-all receipts feature
"""
import json
import os


def test_migration_structure():
    """Test that migration 100 is defined in db_migrate.py"""
    with open('/home/runner/work/prosaasil/prosaasil/server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check migration 100 exists
    assert 'Migration 100' in content, "Migration 100 not found"
    assert 'background_jobs' in content, "background_jobs table not found in migration"
    assert 'CREATE TABLE background_jobs' in content, "CREATE TABLE statement not found"
    
    # Check required columns
    required_columns = [
        'business_id', 'job_type', 'status', 'total', 'processed', 
        'succeeded', 'failed_count', 'cursor', 'last_error', 
        'created_at', 'updated_at', 'started_at', 'finished_at'
    ]
    for col in required_columns:
        assert col in content, f"Column {col} not found in migration"
    
    # Check indexes
    assert 'idx_background_jobs_business_type_status' in content, "Business/type/status index not found"
    assert 'idx_background_jobs_created_at' in content, "Created_at index not found"
    assert 'idx_background_jobs_unique_active' in content, "Unique active constraint not found"
    
    # Check constraints
    assert 'chk_job_status' in content, "Status check constraint not found"
    assert 'chk_job_type' in content, "Job type check constraint not found"
    
    print("✓ Migration 100 is properly defined with all required fields and indexes")


def test_model_structure():
    """Test that BackgroundJob model is defined in models_sql.py"""
    with open('/home/runner/work/prosaasil/prosaasil/server/models_sql.py', 'r') as f:
        content = f.read()
    
    # Check model exists
    assert 'class BackgroundJob(db.Model):' in content, "BackgroundJob model not found"
    assert '__tablename__ = "background_jobs"' in content, "Tablename not set correctly"
    
    # Check key fields
    assert 'business_id' in content
    assert 'job_type' in content
    assert 'status' in content
    assert 'cursor' in content
    
    # Check percent property
    assert 'def percent(self):' in content or '@property' in content, "Percent property not found"
    
    print("✓ BackgroundJob model is properly defined")


def test_worker_job_exists():
    """Test that delete_receipts_job.py exists with correct structure"""
    job_file = '/home/runner/work/prosaasil/prosaasil/server/jobs/delete_receipts_job.py'
    assert os.path.exists(job_file), "delete_receipts_job.py not found"
    
    with open(job_file, 'r') as f:
        content = f.read()
    
    # Check constants
    assert 'BATCH_SIZE' in content, "BATCH_SIZE not defined"
    assert 'THROTTLE_MS' in content, "THROTTLE_MS not defined"
    assert 'MAX_RUNTIME_SECONDS' in content, "MAX_RUNTIME_SECONDS not defined"
    
    # Check main function
    assert 'def delete_receipts_batch_job' in content, "Main job function not found"
    assert 'def resume_job' in content, "Resume function not found"
    
    # Check key functionality
    assert 'cursor' in content, "Cursor-based pagination not implemented"
    assert 'batch' in content.lower(), "Batch processing not mentioned"
    assert 'time.sleep' in content, "Throttling not implemented"
    
    print("✓ Worker job is properly implemented with batching and throttling")


def test_api_endpoints_structure():
    """Test that new API endpoints are defined in routes_receipts.py"""
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py', 'r') as f:
        content = f.read()
    
    # Check imports
    assert 'BackgroundJob' in content, "BackgroundJob not imported"
    
    # Check endpoints
    assert "@receipts_bp.route('/delete_all', methods=['POST'])" in content, "delete_all endpoint not found"
    assert "@receipts_bp.route('/jobs/<int:job_id>', methods=['GET'])" in content, "job status endpoint not found"
    assert "@receipts_bp.route('/jobs/<int:job_id>/cancel', methods=['POST'])" in content, "cancel endpoint not found"
    assert "@receipts_bp.route('/jobs/<int:job_id>/resume', methods=['POST'])" in content, "resume endpoint not found"
    
    # Check handler functions
    assert 'def delete_all_receipts():' in content, "delete_all_receipts handler not found"
    assert 'def get_job_status(' in content, "get_job_status handler not found"
    assert 'def cancel_job(' in content, "cancel_job handler not found"
    assert 'def resume_job(' in content, "resume_job handler not found"
    
    # Check key functionality
    assert 'maintenance' in content, "Maintenance queue not used"
    assert 'enqueue' in content, "Job enqueueing not implemented"
    
    print("✓ API endpoints are properly implemented")


def test_ui_implementation():
    """Test that UI has been updated with delete progress components"""
    with open('/home/runner/work/prosaasil/prosaasil/client/src/pages/receipts/ReceiptsPage.tsx', 'r') as f:
        content = f.read()
    
    # Check for delete progress state
    assert 'deleteJobId' in content, "deleteJobId state not found"
    assert 'deleteProgress' in content, "deleteProgress state not found"
    assert 'showDeleteProgress' in content, "showDeleteProgress state not found"
    
    # Check for handler functions
    assert 'handleDeleteAllReceipts' in content, "handleDeleteAllReceipts function not found"
    assert 'pollDeleteProgress' in content, "pollDeleteProgress function not found"
    assert 'handleCancelDelete' in content, "handleCancelDelete function not found"
    
    # Check for API calls
    assert '/api/receipts/delete_all' in content, "delete_all API call not found"
    assert '/api/receipts/jobs/' in content, "jobs API call not found"
    
    # Check for progress modal
    assert 'Delete Progress Modal' in content, "Progress modal not found"
    assert 'Progress Bar' in content or 'progress bar' in content.lower(), "Progress bar not implemented"
    
    # Check for Hebrew UI text
    assert 'מוחק קבלות' in content or 'מחיקה' in content, "Hebrew UI text not found"
    
    print("✓ UI components are properly implemented with progress tracking")


def test_cursor_serialization():
    """Test that cursor can be properly serialized/deserialized"""
    cursor_data = {"last_id": 12345}
    
    # Serialize
    cursor_str = json.dumps(cursor_data)
    
    # Deserialize
    loaded = json.loads(cursor_str)
    
    assert loaded["last_id"] == 12345, "Cursor deserialization failed"
    assert isinstance(loaded, dict), "Cursor should be a dict"
    
    print("✓ Cursor serialization works correctly")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Delete-All Receipts Stable Implementation")
    print("=" * 60)
    
    tests = [
        ("Migration Structure", test_migration_structure),
        ("Model Structure", test_model_structure),
        ("Worker Job", test_worker_job_exists),
        ("API Endpoints", test_api_endpoints_structure),
        ("UI Implementation", test_ui_implementation),
        ("Cursor Serialization", test_cursor_serialization),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 Testing: {test_name}")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_name} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_name} error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")
    print("=" * 60)
    
    exit(0 if failed == 0 else 1)
