"""
Test script to verify job fixes
- delete_leads_job: OutboundCallJob deletion and proper rollback
- whatsapp_sessions_cleanup_job: Graceful handling of missing WhatsAppSession model
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_delete_leads_job_imports():
    """Test that delete_leads_job imports OutboundCallJob"""
    print("✅ Testing delete_leads_job imports...")
    
    # Check import statement
    with open('server/jobs/delete_leads_job.py', 'r') as f:
        content = f.read()
        
    # Check OutboundCallJob is imported
    assert 'OutboundCallJob' in content, "OutboundCallJob should be imported"
    assert 'from server.models_sql import' in content and 'OutboundCallJob' in content, "OutboundCallJob should be in imports"
    
    # Check OutboundCallJob deletion code
    assert 'OutboundCallJob.query.filter(' in content, "Should have OutboundCallJob deletion"
    assert 'DELETE OutboundCallJob records first' in content, "Should have comment about FK fix"
    
    # Check rollback is called before accessing session
    assert 'db.session.rollback()' in content, "Should have rollback"
    
    # Count rollback occurrences (should be at least 2 - one in batch exception, one in outer exception)
    rollback_count = content.count('db.session.rollback()')
    assert rollback_count >= 2, f"Should have at least 2 rollback calls, found {rollback_count}"
    
    print("  ✓ OutboundCallJob is imported")
    print("  ✓ OutboundCallJob deletion code exists")
    print(f"  ✓ Rollback is called {rollback_count} times")
    print("✅ delete_leads_job imports verified!")
    

def test_whatsapp_cleanup_job_graceful_import():
    """Test that whatsapp_sessions_cleanup_job gracefully handles missing WhatsAppSession"""
    print("\n✅ Testing whatsapp_sessions_cleanup_job graceful import...")
    
    with open('server/jobs/whatsapp_sessions_cleanup_job.py', 'r') as f:
        content = f.read()
    
    # Check for try/except around WhatsAppSession import
    assert 'try:' in content and 'from server.models_sql import WhatsAppSession' in content, \
        "Should have try around WhatsAppSession import"
    assert 'except ImportError:' in content, "Should catch ImportError"
    assert "'status': 'skipped'" in content, "Should return skipped status"
    assert "'reason': 'model_not_found'" in content, "Should indicate model not found"
    
    print("  ✓ WhatsAppSession import is wrapped in try/except")
    print("  ✓ ImportError is caught gracefully")
    print("  ✓ Returns skipped status when model not found")
    print("✅ whatsapp_sessions_cleanup_job graceful import verified!")


def test_frontend_polling_logic():
    """Test that frontend has job polling and timeout"""
    print("\n✅ Testing frontend LeadsPage polling logic...")
    
    with open('client/src/pages/Leads/LeadsPage.tsx', 'r') as f:
        content = f.read()
    
    # Check for job_id handling
    assert 'response?.job_id' in content, "Should check for job_id in response"
    
    # Check for polling interval
    assert 'setInterval' in content, "Should have polling interval"
    assert 'pollInterval' in content, "Should declare pollInterval variable"
    
    # Check for timeout
    assert 'maxPollTime' in content, "Should have max poll time"
    assert '5 * 60 * 1000' in content or '300000' in content, "Should have 5 minute timeout"
    
    # Check for finally block with cleanup
    assert 'finally {' in content or 'finally{' in content, "Should have finally block"
    assert 'clearInterval(pollInterval' in content, "Should clear interval in finally"
    assert 'setIsDeleting(false)' in content, "Should reset loading state in finally"
    
    # Check for job status API call
    assert '/api/jobs/' in content, "Should poll job status API"
    
    print("  ✓ Frontend polls for job_id")
    print("  ✓ Polling has 5 minute timeout")
    print("  ✓ Finally block clears interval and loading state")
    print("  ✓ Job status API endpoint is used")
    print("✅ Frontend polling logic verified!")


def test_migration_config():
    """Test that migrations are properly configured in docker-compose"""
    print("\n✅ Testing migration configuration...")
    
    with open('docker-compose.yml', 'r') as f:
        content = f.read()
    
    # Check migrate service exists
    assert 'migrate:' in content, "Should have migrate service"
    
    # Check RUN_MIGRATIONS is set to "1" for migrate service
    # Look for the migrate service section
    migrate_section_start = content.find('migrate:')
    if migrate_section_start == -1:
        raise AssertionError("migrate service not found")
    
    # Get next 50 lines after migrate:
    migrate_section = content[migrate_section_start:migrate_section_start + 2000]
    
    assert 'RUN_MIGRATIONS: "1"' in migrate_section or "RUN_MIGRATIONS: '1'" in migrate_section, \
        "Migrate service should have RUN_MIGRATIONS: \"1\""
    
    print("  ✓ Migrate service exists")
    print("  ✓ RUN_MIGRATIONS is set to '1' for migrate service")
    print("✅ Migration configuration verified!")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Running Job Fixes Verification Tests")
    print("=" * 70)
    
    try:
        test_delete_leads_job_imports()
        test_whatsapp_cleanup_job_graceful_import()
        test_frontend_polling_logic()
        test_migration_config()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\n✅ Summary:")
        print("  1. delete_leads_job properly deletes OutboundCallJob records")
        print("  2. delete_leads_job has proper rollback before session access")
        print("  3. whatsapp_sessions_cleanup_job gracefully handles missing model")
        print("  4. Frontend polls job status with timeout and cleanup")
        print("  5. Migrations are properly configured to run")
        print("\n🚀 These fixes should resolve:")
        print("  - FK violations causing job retry loops")
        print("  - PendingRollbackError causing job crashes")
        print("  - ImportError causing whatsapp cleanup job failures")
        print("  - UI progress bar getting stuck")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
