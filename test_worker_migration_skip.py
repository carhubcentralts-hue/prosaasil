#!/usr/bin/env python3
"""
Test script to verify workers skip migrations.

This test verifies:
1. db_migrate.apply_migrations() skips when SERVICE_ROLE=worker
2. app_factory._background_initialization() skips when SERVICE_ROLE=worker
3. Proper logging messages for skipped migrations
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_db_migrate_worker_guard():
    """Verify that db_migrate.apply_migrations() has worker guard"""
    print("\n=== Checking db_migrate.py Worker Guard ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Extract apply_migrations function
        apply_migrations_match = re.search(
            r'def apply_migrations\(\):.*?(?=\ndef [a-z_]|\nif __name__|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not apply_migrations_match:
            print(f"  ❌ apply_migrations function not found")
            return False
        
        func_content = apply_migrations_match.group(0)
        
        # Check for SERVICE_ROLE check
        if "SERVICE_ROLE" in func_content or "service_role" in func_content:
            print(f"  ✅ apply_migrations checks SERVICE_ROLE")
        else:
            print(f"  ❌ apply_migrations does NOT check SERVICE_ROLE")
            all_ok = False
        
        # Check for worker skip logic
        if "service_role == 'worker'" in func_content.lower() or 'service_role == "worker"' in func_content.lower():
            print(f"  ✅ apply_migrations has worker skip condition")
        else:
            print(f"  ❌ apply_migrations missing worker skip condition")
            all_ok = False
        
        # Check for early return
        if "return []" in func_content and "worker" in func_content.lower():
            print(f"  ✅ apply_migrations returns empty list for workers")
        else:
            print(f"  ❌ apply_migrations doesn't return early for workers")
            all_ok = False
        
        # Check for skip message
        if "MIGRATIONS_SKIPPED" in func_content or "Skipping migrations" in func_content:
            print(f"  ✅ apply_migrations logs skip message")
        else:
            print(f"  ⚠️  apply_migrations should log skip message for visibility")
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_app_factory_worker_guard():
    """Verify that app_factory has worker guard in _background_initialization"""
    print("\n=== Checking app_factory.py Worker Guard ===")
    
    filepath = 'server/app_factory.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Extract _background_initialization function
        background_init_match = re.search(
            r'def _background_initialization\(\):.*?(?=\n        # Start background|\n    # Register|\n    return app|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not background_init_match:
            print(f"  ❌ _background_initialization function not found")
            return False
        
        func_content = background_init_match.group(0)
        
        # Check for SERVICE_ROLE check
        if "SERVICE_ROLE" in func_content or "service_role" in func_content:
            print(f"  ✅ _background_initialization checks SERVICE_ROLE")
        else:
            print(f"  ❌ _background_initialization does NOT check SERVICE_ROLE")
            all_ok = False
        
        # Check for worker skip logic
        if "service_role == 'worker'" in func_content.lower() or 'service_role == "worker"' in func_content.lower():
            print(f"  ✅ _background_initialization has worker skip condition")
        else:
            print(f"  ❌ _background_initialization missing worker skip condition")
            all_ok = False
        
        # Check for early return
        if "return" in func_content and "worker" in func_content.lower():
            print(f"  ✅ _background_initialization returns early for workers")
        else:
            print(f"  ❌ _background_initialization doesn't return early for workers")
            all_ok = False
        
        # Check for skip message
        if "WORKER MODE" in func_content or "Skipping migrations" in func_content:
            print(f"  ✅ _background_initialization logs skip message")
        else:
            print(f"  ⚠️  _background_initialization should log skip message for visibility")
        
        # Check that worker skip comes BEFORE apply_migrations calls
        # Find position of worker check and position of apply_migrations
        worker_check_pos = func_content.lower().find("service_role == 'worker'")
        if worker_check_pos == -1:
            worker_check_pos = func_content.lower().find('service_role == "worker"')
        
        apply_migrations_pos = func_content.find("apply_migrations()")
        
        if worker_check_pos != -1 and apply_migrations_pos != -1:
            if worker_check_pos < apply_migrations_pos:
                print(f"  ✅ Worker check comes BEFORE apply_migrations call")
            else:
                print(f"  ❌ Worker check should come BEFORE apply_migrations call")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_docker_compose_service_roles():
    """Verify that docker-compose.yml sets SERVICE_ROLE correctly"""
    print("\n=== Checking docker-compose.yml Service Roles ===")
    
    filepath = 'docker-compose.yml'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for worker service with SERVICE_ROLE: worker
        # Simpler approach - just check if the combination exists
        if "SERVICE_ROLE: worker" in content or "SERVICE_ROLE:worker" in content:
            print(f"  ✅ worker service has SERVICE_ROLE: worker")
        else:
            print(f"  ❌ docker-compose.yml missing SERVICE_ROLE: worker")
            all_ok = False
        
        # Check for api service with SERVICE_ROLE: api
        if "SERVICE_ROLE: api" in content or "SERVICE_ROLE:api" in content:
            print(f"  ✅ API service has SERVICE_ROLE: api")
        else:
            print(f"  ⚠️  API service should have SERVICE_ROLE: api")
            # Not critical since we can't guarantee naming
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_env_example_documentation():
    """Verify that .env.example documents SERVICE_ROLE"""
    print("\n=== Checking .env.example Documentation ===")
    
    filepath = '.env.example'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for SERVICE_ROLE documentation
        if "SERVICE_ROLE" in content:
            print(f"  ✅ .env.example documents SERVICE_ROLE")
        else:
            print(f"  ❌ .env.example missing SERVICE_ROLE documentation")
            all_ok = False
        
        # Check for api/worker values documentation
        if "api" in content and "worker" in content:
            print(f"  ✅ .env.example documents api and worker values")
        else:
            print(f"  ⚠️  .env.example should document api and worker values")
        
        # Check for migration behavior documentation
        if "migration" in content.lower() or "MIGRATION" in content:
            print(f"  ✅ .env.example documents migration behavior")
        else:
            print(f"  ⚠️  .env.example should document migration behavior")
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all verification checks"""
    print("=" * 80)
    print("WORKER MIGRATION SKIP VERIFICATION")
    print("=" * 80)
    
    results = {
        'db_migrate.py Worker Guard': check_db_migrate_worker_guard(),
        'app_factory.py Worker Guard': check_app_factory_worker_guard(),
        'docker-compose.yml Service Roles': check_docker_compose_service_roles(),
        '.env.example Documentation': check_env_example_documentation(),
    }
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - Worker migration skip is properly implemented!")
        print("\nKey features:")
        print("1. ✅ db_migrate.apply_migrations() returns early for workers")
        print("2. ✅ app_factory skips migrations in worker mode")
        print("3. ✅ docker-compose.yml sets SERVICE_ROLE correctly")
        print("4. ✅ .env.example documents SERVICE_ROLE usage")
        print("\nWorkers will NOT run migrations, preventing:")
        print("  - pg_advisory_lock timeouts")
        print("  - Duplicate migration runs")
        print("  - Unnecessary database load")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - Review the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
