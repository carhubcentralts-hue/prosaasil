#!/usr/bin/env python3
"""
Manual validation of recording download fix
Checks that all 5 critical requirements are in place
בדיקה שכל 5 הדברים הקריטיים קיימים
"""
import os
import sys

def check_nginx_config():
    """Verify nginx.conf has streaming support"""
    print("🔍 בדיקה 1: Nginx Configuration")
    print("----------------------------------------")
    
    nginx_path = os.path.join(os.path.dirname(__file__), 'docker', 'nginx.conf')
    
    if not os.path.exists(nginx_path):
        print("❌ nginx.conf not found")
        return False
    
    with open(nginx_path, 'r') as f:
        content = f.read()
    
    required = [
        ('proxy_buffering off', 'Buffering disabled for streaming'),
        ('proxy_request_buffering off', 'Request buffering disabled'),
        ('proxy_read_timeout', 'Read timeout configured'),
        ('proxy_send_timeout', 'Send timeout configured'),
        ('Range $http_range', 'Range header forwarding'),
        ('If-Range $http_if_range', 'If-Range header forwarding'),
        ('proxy_http_version 1.1', 'HTTP/1.1 configured'),
        ('Connection ""', 'Connection header cleared for keepalive'),
    ]
    
    all_ok = True
    for setting, description in required:
        if setting in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ Missing: {description} ({setting})")
            all_ok = False
    
    # Check for problematic WebSocket upgrade in /api/ location
    # Extract /api/ location block
    api_location_start = content.find('location /api/ {')
    if api_location_start != -1:
        api_location_end = content.find('}', api_location_start)
        api_block = content[api_location_start:api_location_end]
        
        if 'Upgrade' in api_block or 'connection_upgrade' in api_block:
            print(f"  ⚠️  WARNING: WebSocket upgrade headers found in /api/ location")
            print(f"     This can break keepalive/streaming for audio downloads")
            print(f"     WebSocket should only be in dedicated location blocks (e.g., /ws/)")
            all_ok = False
        else:
            print(f"  ✅ No WebSocket upgrade in /api/ location (correct!)")
    
    return all_ok


def check_backend_timeout():
    """Verify backend has adequate timeout"""
    print("\n🔍 בדיקה 2: Backend Timeout Configuration")
    print("----------------------------------------")
    
    dockerfile_path = os.path.join(os.path.dirname(__file__), 'Dockerfile.backend')
    
    if not os.path.exists(dockerfile_path):
        print("❌ Dockerfile.backend not found")
        return False
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    if 'uvicorn' in content:
        print("  ✅ Using Uvicorn")
        if 'timeout-keep-alive' in content and '75' in content:
            print("  ✅ timeout-keep-alive configured (75+ seconds)")
        else:
            print("  ⚠️  timeout-keep-alive should be 75+ seconds")
    elif 'gunicorn' in content:
        print("  ✅ Using Gunicorn")
        if '--timeout' in content and '300' in content:
            print("  ✅ --timeout configured (300 seconds)")
        else:
            print("  ❌ --timeout should be 300+ seconds")
            return False
    else:
        print("  ⚠️  Could not detect Uvicorn or Gunicorn")
    
    return True


def check_206_support():
    """Verify endpoint returns 206 Partial Content"""
    print("\n🔍 בדיקה 3: 206 Partial Content Support (critical for iOS)")
    print("----------------------------------------")
    
    routes_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_calls.py')
    
    if not os.path.exists(routes_path):
        print("❌ routes_calls.py not found")
        return False
    
    with open(routes_path, 'r') as f:
        content = f.read()
    
    checks = [
        ('206', 'Returns 206 status code'),
        ('Content-Range', 'Sets Content-Range header'),
        ('Accept-Ranges', 'Sets Accept-Ranges header'),
        ('range_header', 'Handles Range header'),
    ]
    
    all_ok = True
    for check, description in checks:
        if check in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ Missing: {description}")
            all_ok = False
    
    return all_ok


def check_error_handling():
    """Verify routes_calls.py has comprehensive error handling"""
    print("\n🔍 בדיקה 4: Error Handling (prevents crashes)")
    print("----------------------------------------")
    
    routes_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_calls.py')
    
    if not os.path.exists(routes_path):
        print("❌ routes_calls.py not found")
        return False
    
    with open(routes_path, 'r') as f:
        content = f.read()
    
    checks = [
        ('if not call.recording_url:', 'Checks for recording_url'),
        ('try:', 'Has try-except blocks'),
        ('except Exception', 'Catches exceptions'),
        ('os.path.exists(audio_path)', 'Verifies file exists'),
        ('log.warning', 'Has warning logging'),
        ('log.error', 'Has error logging'),
    ]
    
    all_ok = True
    for check, description in checks:
        if check in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ Missing: {description}")
            all_ok = False
    
    return all_ok


def check_recording_service():
    """Verify recording_service.py has resilience"""
    print("\n🔍 בדיקה 5: Recording Service Resilience")
    print("----------------------------------------")
    
    service_path = os.path.join(os.path.dirname(__file__), 'server', 'services', 'recording_service.py')
    
    if not os.path.exists(service_path):
        print("❌ recording_service.py not found")
        return False
    
    with open(service_path, 'r') as f:
        content = f.read()
    
    # Required checks
    required_checks = [
        ('try:', 'Has try-except blocks'),
        ('except Exception', 'Catches exceptions'),
        ('timeout', 'Has timeout for Twilio requests'),
        ('log.error', 'Has error logging'),
    ]
    
    # Optional but recommended
    optional_checks = [
        ('status_code == 401', 'Handles 401 errors'),
        ('status_code == 403', 'Handles 403 errors'),
        ('status_code >= 500', 'Handles 5xx errors'),
        ('os.path.exists(local_path)', 'Checks for local cache'),
    ]
    
    all_ok = True
    
    for check, description in required_checks:
        if check in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ Missing: {description}")
            all_ok = False
    
    for check, description in optional_checks:
        if check in content:
            print(f"  ✅ {description} (recommended)")
        else:
            print(f"  ⚠️  Missing: {description} (optional)")
    
    return all_ok


def main():
    print("=" * 60)
    print("תיקון 502 - אימות 5 דברים קריטיים")
    print("Recording Download Fix - 5 Critical Checks")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(('Nginx streaming config', check_nginx_config()))
    results.append(('Backend timeout', check_backend_timeout()))
    results.append(('206 Partial Content support', check_206_support()))
    results.append(('Error handling', check_error_handling()))
    results.append(('Recording service resilience', check_recording_service()))
    
    print("\n" + "=" * 60)
    print("Summary / סיכום")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ כל 5 הבדיקות עברו בהצלחה!")
        print("✅ All 5 critical checks passed!")
        print()
        print("Next steps / צעדים הבאים:")
        print("1. docker compose build --no-cache backend frontend")
        print("2. docker compose restart nginx backend")
        print("3. Test in browser / בדוק בדפדפן")
        print("4. If 502 persists / אם עדיין 502:")
        print("   ./verify_502_fix.sh  (comprehensive live test)")
        print("   docker compose logs -f nginx backend")
        return 0
    else:
        print("❌ חלק מהבדיקות נכשלו")
        print("❌ Some checks failed. Please review the changes.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
