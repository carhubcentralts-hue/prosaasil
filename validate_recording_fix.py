#!/usr/bin/env python3
"""
Manual validation of recording download fix
Checks that all required changes are in place
"""
import os
import sys

def check_nginx_config():
    """Verify nginx.conf has streaming support"""
    print("🔍 Checking nginx.conf...")
    
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
    ]
    
    all_ok = True
    for setting, description in required:
        if setting in content:
            print(f"  ✅ {description}: {setting}")
        else:
            print(f"  ❌ Missing: {description} ({setting})")
            all_ok = False
    
    return all_ok


def check_routes_calls():
    """Verify routes_calls.py has error handling"""
    print("\n🔍 Checking routes_calls.py error handling...")
    
    routes_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_calls.py')
    
    if not os.path.exists(routes_path):
        print("❌ routes_calls.py not found")
        return False
    
    with open(routes_path, 'r') as f:
        content = f.read()
    
    checks = [
        ('FIX 502', 'Has fix comments'),
        ('if not call.recording_url:', 'Checks for recording_url before download'),
        ('try:', 'Has try-except blocks'),
        ('get_recording_file_for_call(call)', 'Calls recording service'),
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
    """Verify recording_service.py has error handling"""
    print("\n🔍 Checking recording_service.py error handling...")
    
    service_path = os.path.join(os.path.dirname(__file__), 'server', 'services', 'recording_service.py')
    
    if not os.path.exists(service_path):
        print("❌ recording_service.py not found")
        return False
    
    with open(service_path, 'r') as f:
        content = f.read()
    
    # Required checks - must be present
    required_checks = [
        ('FIX 502', 'Has fix comments'),
        ('try:', 'Has try-except blocks'),
        ('except Exception', 'Catches exceptions'),
        ('log.error', 'Has error logging'),
    ]
    
    # Optional but recommended checks
    optional_checks = [
        ('status_code == 401', 'Handles 401 errors'),
        ('status_code == 403', 'Handles 403 errors'),
        ('status_code >= 500', 'Handles 5xx errors'),
        ('requests.Timeout', 'Handles timeout errors'),
    ]
    
    all_ok = True
    
    # Check required items
    for check, description in required_checks:
        if check in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ Missing: {description}")
            all_ok = False
    
    # Check optional items (don't affect pass/fail)
    for check, description in optional_checks:
        if check in content:
            print(f"  ✅ {description} (recommended)")
        else:
            print(f"  ⚠️  Missing: {description} (optional)")
    
    return all_ok


def main():
    print("=" * 60)
    print("Recording Download Fix Validation")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(('nginx.conf', check_nginx_config()))
    results.append(('routes_calls.py', check_routes_calls()))
    results.append(('recording_service.py', check_recording_service()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ All validations passed!")
        print()
        print("Next steps:")
        print("1. Rebuild Docker containers: docker compose build")
        print("2. Restart services: docker compose restart nginx backend")
        print("3. Test recording playback in browser")
        print("4. Check logs: docker compose logs -f nginx backend")
        return 0
    else:
        print("❌ Some validations failed. Please review the changes.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
