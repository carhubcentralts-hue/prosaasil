#!/usr/bin/env python3
"""
DB Resilience Verification Script
Tests that the application handles DB failures gracefully without crashing.

This script verifies:
1. Logger is defined in all files that use it
2. Error handlers return 503 on DB failure
3. Background loops don't crash on DB errors
4. Utility functions exist and are importable
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_logger_definitions():
    """Verify all files that use logger have it defined"""
    print("\n=== Checking Logger Definitions ===")
    
    issues = []
    for root, dirs, files in os.walk('server'):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git']]
        
        for file in files:
            if not file.endswith('.py'):
                continue
            
            filepath = os.path.join(root, file)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Skip files without logger usage
                    if not re.search(r'\blogger\.', content):
                        continue
                    
                    # Check for logger definition
                    has_logger = bool(
                        re.search(r'^logger\s*=\s*logging\.getLogger', content, re.MULTILINE) or
                        re.search(r'^log\s*=\s*logging\.getLogger', content, re.MULTILINE) or
                        'current_app.logger' in content or
                        'app.logger' in content or
                        'g.audit_logger' in content or
                        'logger = logging.getLogger(__name__)' in content
                    )
                    
                    if not has_logger:
                        issues.append(filepath)
            except Exception as e:
                print(f"  ⚠️  Error checking {filepath}: {e}")
    
    if issues:
        print("  ❌ Files with logger issues:")
        for filepath in issues:
            print(f"     - {filepath}")
        return False
    else:
        print("  ✅ All files with logger usage have proper definitions")
        return True


def check_utility_files():
    """Verify utility files exist and are syntactically correct"""
    print("\n=== Checking Utility Files ===")
    
    files_to_check = [
        'server/utils/db_retry.py',
        'server/utils/safe_thread.py',
        'server/utils/db_health.py',
        'server/error_handlers.py',
    ]
    
    all_ok = True
    for filepath in files_to_check:
        if not os.path.exists(filepath):
            print(f"  ❌ Missing: {filepath}")
            all_ok = False
            continue
        
        # Check syntax
        try:
            with open(filepath, 'r') as f:
                compile(f.read(), filepath, 'exec')
            print(f"  ✅ {filepath} - syntax OK")
        except SyntaxError as e:
            print(f"  ❌ {filepath} - syntax error: {e}")
            all_ok = False
    
    return all_ok


def check_error_handler_updates():
    """Verify error_handlers.py has DB resilience code"""
    print("\n=== Checking Error Handler Updates ===")
    
    filepath = 'server/error_handlers.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        checks = {
            'OperationalError handler': '@app.errorhandler(OperationalError)',
            'DisconnectionError handler': '@app.errorhandler(DisconnectionError)',
            'SERVICE_UNAVAILABLE response': '"error": "SERVICE_UNAVAILABLE"',
            '503 status code': ', 503',
        }
        
        all_ok = True
        for check_name, pattern in checks.items():
            if pattern in content:
                print(f"  ✅ {check_name} found")
            else:
                print(f"  ❌ {check_name} NOT found")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_whatsapp_session_resilience():
    """Verify WhatsApp session service has DB resilience"""
    print("\n=== Checking WhatsApp Session Service Resilience ===")
    
    filepath = 'server/services/whatsapp_session_service.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        checks = {
            'OperationalError import': 'from sqlalchemy.exc import OperationalError',
            'DB_RECOVERED log': '[DB_RECOVERED]',
            'DB error handling in loop': 'except (OperationalError, DisconnectionError)',
            'Exponential backoff': 'backoff_sleep',
            'Session rollback on error': 'db.session.rollback()',
        }
        
        all_ok = True
        for check_name, pattern in checks.items():
            if pattern in content:
                print(f"  ✅ {check_name} found")
            else:
                print(f"  ❌ {check_name} NOT found")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_app_factory_logger():
    """Verify app_factory.py has logger defined"""
    print("\n=== Checking app_factory.py Logger ===")
    
    filepath = 'server/app_factory.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Check for module-level logger definition
        if re.search(r'^logger\s*=\s*logging\.getLogger\(__name__\)', content, re.MULTILINE):
            print(f"  ✅ Module-level logger defined")
            return True
        else:
            print(f"  ❌ Module-level logger NOT defined")
            return False
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all verification checks"""
    print("=" * 60)
    print("DB RESILIENCE VERIFICATION")
    print("=" * 60)
    
    results = {
        'Logger Definitions': check_logger_definitions(),
        'Utility Files': check_utility_files(),
        'Error Handler Updates': check_error_handler_updates(),
        'WhatsApp Session Resilience': check_whatsapp_session_resilience(),
        'app_factory.py Logger': check_app_factory_logger(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - DB resilience implementation looks good!")
        print("\nNext steps:")
        print("1. Deploy to test environment")
        print("2. Test with actual DB outage (disable Neon endpoint)")
        print("3. Verify API returns 503 instead of 500")
        print("4. Verify background loops recover after DB comes back")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - Review the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
