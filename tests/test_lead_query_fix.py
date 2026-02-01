"""
Test to verify Lead model queries use correct tenant_id field
This test addresses the AttributeError: type object 'Lead' has no attribute 'business_id'
"""
import pytest
import os


def test_lead_model_has_tenant_id():
    """
    Verify Lead model has tenant_id attribute (not business_id)
    """
    # Set migration mode to avoid DB initialization during tests
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.models_sql import Lead
    
    # Lead model should have tenant_id
    assert hasattr(Lead, 'tenant_id'), "Lead model should have tenant_id attribute"
    
    # Lead model should NOT have business_id
    assert not hasattr(Lead, 'business_id'), "Lead model should NOT have business_id attribute"
    
    print("✅ Lead model correctly uses tenant_id (not business_id)")


def test_lead_query_filter_works():
    """
    Verify that Lead.query.filter_by(tenant_id=...) works syntactically
    This ensures the fix in send_scheduled_whatsapp_job.py is correct
    """
    # Set migration mode to avoid DB initialization during tests
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.models_sql import Lead
    
    # This should not raise AttributeError
    try:
        # Build the query (don't execute it since we don't have a DB connection)
        query = Lead.query.filter_by(tenant_id=1, id=1)
        
        # Verify the query object was created successfully
        assert query is not None
        print("✅ Lead.query.filter_by(tenant_id=...) works correctly")
    except AttributeError as e:
        pytest.fail(f"Lead.query.filter_by(tenant_id=...) raised AttributeError: {e}")


def test_job_file_uses_tenant_id():
    """
    Verify send_scheduled_whatsapp_job.py uses tenant_id (not business_id)
    """
    import re
    
    with open('/home/runner/work/prosaasil/prosaasil/server/jobs/send_scheduled_whatsapp_job.py', 'r') as f:
        content = f.read()
    
    # Check that the fix is in place
    # Should have: Lead.query.filter_by(... tenant_id=message.business_id ...)
    assert 'tenant_id=message.business_id' in content, \
        "send_scheduled_whatsapp_job.py should use tenant_id=message.business_id"
    
    # Should NOT have: Lead.query.filter_by(... business_id=message.business_id ...)
    # Use regex to match the exact problematic pattern
    bad_pattern = r'Lead\.query\.filter_by\([^)]*business_id\s*=\s*message\.business_id'
    match = re.search(bad_pattern, content)
    assert match is None, \
        f"send_scheduled_whatsapp_job.py should NOT use Lead.query.filter_by(business_id=...)"
    
    print("✅ send_scheduled_whatsapp_job.py correctly uses tenant_id")


def test_cleanup_job_uses_tenant_id():
    """
    Verify whatsapp_sessions_cleanup_job.py uses tenant_id (not business_id)
    """
    import re
    
    with open('/home/runner/work/prosaasil/prosaasil/server/jobs/whatsapp_sessions_cleanup_job.py', 'r') as f:
        content = f.read()
    
    # Should have: Lead.query.filter_by(tenant_id=...)
    assert 'tenant_id=session.business_id' in content, \
        "whatsapp_sessions_cleanup_job.py should use tenant_id"
    
    # Should NOT have the bad pattern
    bad_pattern = r'Lead\.query\.filter_by\([^)]*business_id\s*=\s*session\.business_id'
    match = re.search(bad_pattern, content)
    assert match is None, \
        "whatsapp_sessions_cleanup_job.py should NOT use Lead.query.filter_by(business_id=...)"
    
    print("✅ whatsapp_sessions_cleanup_job.py correctly uses tenant_id")


if __name__ == '__main__':
    # Run tests manually
    test_lead_model_has_tenant_id()
    test_lead_query_filter_works()
    test_job_file_uses_tenant_id()
    test_cleanup_job_uses_tenant_id()
    print("\n✅ All tests passed!")
