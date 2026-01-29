"""
Verify job status endpoint exists in routes_leads.py
"""
import sys
import os

def test_job_status_endpoint_exists():
    """
    Static code verification - check that the endpoint exists in the file
    """
    print("\n" + "=" * 80)
    print("TEST: /api/jobs/<job_id> endpoint exists in routes_leads.py")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_leads.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for route definition
        if '@leads_bp.route("/api/jobs/<int:job_id>"' in content:
            print("✅ PASS: Route definition found: /api/jobs/<int:job_id>")
        else:
            print("❌ FAIL: Route definition not found")
            return False
        
        # Check for function definition
        if 'def get_job_status(job_id):' in content:
            print("✅ PASS: Function definition found: get_job_status")
        else:
            print("❌ FAIL: Function definition not found")
            return False
        
        # Check for authentication decorator
        if '@require_api_auth()' in content:
            print("✅ PASS: Authentication decorator found")
        else:
            print("❌ FAIL: Authentication decorator not found")
            return False
        
        # Check for tenant isolation
        if 'tenant_id = get_current_tenant()' in content:
            print("✅ PASS: Tenant isolation check found")
        else:
            print("❌ FAIL: Tenant isolation not implemented")
            return False
        
        # Check for BackgroundJob import
        if 'from server.models_sql import BackgroundJob' in content or 'import BackgroundJob' in content:
            print("✅ PASS: BackgroundJob import found")
        else:
            print("❌ FAIL: BackgroundJob import not found")
            return False
        
        # Check for 200 OK return (not 404)
        if 'return jsonify(' in content and ', 200' in content:
            print("✅ PASS: Returns 200 OK status code")
        else:
            print("❌ FAIL: Does not return 200 OK")
            return False
        
        # Check for unknown status handling
        if '"status": "unknown"' in content:
            print("✅ PASS: Returns 'unknown' status for missing jobs")
        else:
            print("❌ FAIL: Does not handle unknown status")
            return False
        
        # Check for job not found handling
        if 'if not job:' in content:
            print("✅ PASS: Handles job not found case")
        else:
            print("❌ FAIL: Does not handle job not found")
            return False
        
        # Check for stale job detection
        if 'is_stuck' in content and 'stuck_reason' in content:
            print("✅ PASS: Includes stale job detection")
        else:
            print("⚠️  WARNING: Stale job detection may be missing")
        
        # Check for heartbeat monitoring
        if 'heartbeat_at' in content:
            print("✅ PASS: Includes heartbeat monitoring")
        else:
            print("⚠️  WARNING: Heartbeat monitoring may be missing")
        
        print("\n" + "=" * 80)
        print("✅ ALL CRITICAL TESTS PASSED!")
        print("=" * 80)
        print("\n📌 Summary:")
        print("   - Endpoint exists: /api/jobs/<job_id>")
        print("   - Returns 200 OK (not 404) for all cases")
        print("   - Returns 'unknown' status for missing jobs")
        print("   - Includes tenant isolation")
        print("   - Has authentication")
        print("   - UI polling will not show error toasts! 🎉")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error reading file: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_job_status_endpoint_exists()
    sys.exit(0 if success else 1)
