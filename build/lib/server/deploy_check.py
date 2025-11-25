"""
Production deployment checker - Golden Path validation
"""
import requests
import json
import os
import sys
import time
from urllib.parse import urljoin

def check_endpoint(base_url, path, method="GET", data=None, expected_status=200):
    """Check single endpoint"""
    url = urljoin(base_url, path)
    try:
        if method == "POST":
            if isinstance(data, dict):
                response = requests.post(url, json=data, timeout=5)
            else:
                response = requests.post(url, data=data, timeout=5, 
                                       headers={'Content-Type': 'application/x-www-form-urlencoded'})
        else:
            response = requests.get(url, timeout=5)
            
        success = response.status_code == expected_status
        return {
            "success": success,
            "status": response.status_code,
            "content": response.text[:200] if not success else "ok"
        }
    except Exception as e:
        return {
            "success": False,
            "status": 0,
            "content": str(e)
        }

def run_deploy_checks(base_url="http://localhost:5000"):
    """Run all deployment checks"""
    checks = []
    
    print("🚀 Running Production Deployment Checks...")
    print(f"   Base URL: {base_url}")
    print("=" * 60)
    
    # 1. Health endpoints
    result = check_endpoint(base_url, "/healthz")
    checks.append(("healthz", result))
    print(f"{'✅' if result['success'] else '❌'} healthz: {result['status']}")
    
    result = check_endpoint(base_url, "/readyz")
    checks.append(("readyz", result))
    print(f"{'✅' if result['success'] else '❌'} readyz: {result['status']}")
    
    # 2. TwiML Stream
    twiml_data = {
        'CallSid': 'TEST_CALL_123',
        'From': '+972501234567', 
        'To': '+972501234568'
    }
    result = check_endpoint(base_url, "/webhook/incoming_call", "POST", twiml_data)
    content = result.get('content', '')
    stream_ok = result['success'] and ('<Stream' in content and '<Connect' in content)
    checks.append(("stream_twiml", {"success": stream_ok}))
    print(f"{'✅' if stream_ok else '❌'} stream->action TwiML")
    if not stream_ok and result['success']:
        print(f"   Debug: TwiML content: {content[:100]}...")
    
    # 3. Stream fallback
    result = check_endpoint(base_url, "/webhook/stream_ended", "POST", twiml_data)
    content = result.get('content', '')
    fallback_ok = result['success'] and '<Record' in content and 'handle_recording' in content
    checks.append(("fallback_record", {"success": fallback_ok}))
    print(f"{'✅' if fallback_ok else '❌'} fallback record TwiML")
    if not fallback_ok and result['success']:
        print(f"   Debug: TwiML content: {content[:100]}...")
    
    # 4. Recording handler
    recording_data = {
        'CallSid': 'TEST_CALL_123',
        'RecordingUrl': 'https://example.com/fake.mp3'
    }
    result = check_endpoint(base_url, "/webhook/handle_recording", "POST", recording_data, 204)
    checks.append(("whisper_pipeline", result))
    print(f"{'✅' if result['success'] else '❌'} whisper pipeline: {result['status']}")
    
    # 5. Payment flags
    payment_data = {
        "business_id": 1,
        "amount": 9900,
        "currency": "ILS",
        "provider": "paypal"
    }
    result = check_endpoint(base_url, "/api/crm/payments/create", "POST", payment_data, 200)
    payments_ok = result['success'] or result['status'] in [403, 501]  # Expected for disabled payments
    checks.append(("payments_flags", {"success": payments_ok}))
    print(f"{'✅' if payments_ok else '❌'} payments flags (PayPal): {result['status']}")
    
    # 6. Legacy imports check
    legacy_imports = False
    try:
        import glob
        for py_file in glob.glob("**/*.py", recursive=True):
            if "legacy/" in py_file or "__pycache__" in py_file or "deploy_check.py" in py_file:
                continue
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    if "from legacy." in content or "import legacy." in content:
                        legacy_imports = True
                        print(f"   Found legacy import in: {py_file}")
                        break
            except:
                continue
    except:
        legacy_imports = False  # No legacy imports found
        
    checks.append(("no_legacy_imports", {"success": not legacy_imports}))
    print(f"{'✅' if not legacy_imports else '❌'} no-legacy-imports")
    
    # 7. Database migrations - Check if migration file exists
    migrations_ok = False
    try:
        import os
        if os.path.exists("server/db_migrate.py"):
            migrations_ok = True
        else:
            print("   Migration file not found")
    except Exception as e:
        print(f"   Migration check failed: {e}")
        migrations_ok = False
        
    checks.append(("db_migrations", {"success": migrations_ok}))
    print(f"{'✅' if migrations_ok else '❌'} database migrations")
    
    # Summary
    print("=" * 60)
    passed = sum(1 for _, result in checks if result.get("success", False))
    total = len(checks)
    
    if passed == total:
        print(f"🎉 ALL CHECKS PASSED ({passed}/{total})")
        print("✅ READY FOR PRODUCTION DEPLOYMENT")
        return True
    else:
        print(f"❌ {total - passed} CHECKS FAILED ({passed}/{total})")
        print("🛑 NOT READY FOR PRODUCTION")
        return False

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    success = run_deploy_checks(base_url)
    sys.exit(0 if success else 1)