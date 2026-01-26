"""
Validate migration 109 production-safe implementation
Simple validation script that doesn't require pytest
"""
import os
import sys

def validate_migration_109():
    """
    Validate that migration 109 follows production-safe patterns
    """
    print("=" * 80)
    print("Validating Migration 109 Production-Safe Implementation")
    print("=" * 80)
    
    # Read the db_migrate.py file
    db_migrate_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'db_migrate.py'
    )
    
    if not os.path.exists(db_migrate_path):
        print(f"❌ ERROR: {db_migrate_path} not found")
        return False
    
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Find Migration 109 section
    migration_109_start = content.find('# Migration 109:')
    migration_109_end = content.find('# Migration 110:', migration_109_start)
    
    if migration_109_start == -1:
        print("❌ ERROR: Migration 109 not found in db_migrate.py")
        return False
    
    print("✅ Found Migration 109 in db_migrate.py")
    
    if migration_109_end == -1:
        # Migration 110 might not exist, find next migration or end of file
        migration_109_end = len(content)
    
    migration_109_code = content[migration_109_start:migration_109_end]
    
    # Validation checks
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: IF NOT EXISTS for idempotency
    print("\n📋 Check 1: Idempotency with IF NOT EXISTS")
    if_not_exists_count = migration_109_code.count('IF NOT EXISTS')
    if if_not_exists_count >= 3:  # Should have at least 3 (for 3 columns)
        print(f"✅ PASS: Found {if_not_exists_count} IF NOT EXISTS clauses")
        checks_passed += 1
    else:
        print(f"❌ FAIL: Found only {if_not_exists_count} IF NOT EXISTS clauses, expected at least 3")
        checks_failed += 1
    
    # Check 2: statement_timeout = 0
    print("\n📋 Check 2: Statement timeout disabled for DDL")
    if 'statement_timeout = 0' in migration_109_code:
        print("✅ PASS: statement_timeout = 0 is set")
        checks_passed += 1
    else:
        print("❌ FAIL: statement_timeout = 0 is NOT set")
        checks_failed += 1
    
    # Check 3: lock_timeout set
    print("\n📋 Check 3: Lock timeout configured")
    if 'lock_timeout' in migration_109_code:
        print("✅ PASS: lock_timeout is configured")
        checks_passed += 1
    else:
        print("❌ FAIL: lock_timeout is NOT configured")
        checks_failed += 1
    
    # Check 4: No heavy backfill in migration
    print("\n📋 Check 4: Backfill operations deferred")
    has_backfill_skip = ('Backfill skipped' in migration_109_code or 
                         'deferred to background job' in migration_109_code)
    
    # Also check that heavy UPDATE loops are not present
    has_heavy_updates = ('while True:' in migration_109_code and 
                        'UPDATE call_log' in migration_109_code and
                        'batch_size' in migration_109_code)
    
    if has_backfill_skip and not has_heavy_updates:
        print("✅ PASS: Backfill operations are skipped/deferred")
        checks_passed += 1
    elif has_heavy_updates:
        print("❌ FAIL: Heavy UPDATE loops still present in migration")
        checks_failed += 1
    else:
        print("⚠️  WARNING: Could not verify backfill deferral")
    
    # Check 5: Required columns
    print("\n📋 Check 5: All required columns present")
    has_started_at = 'started_at' in migration_109_code
    has_ended_at = 'ended_at' in migration_109_code
    has_duration_sec = 'duration_sec' in migration_109_code
    
    if has_started_at and has_ended_at and has_duration_sec:
        print("✅ PASS: All three columns (started_at, ended_at, duration_sec) are present")
        checks_passed += 1
    else:
        print(f"❌ FAIL: Missing columns - started_at:{has_started_at}, ended_at:{has_ended_at}, duration_sec:{has_duration_sec}")
        checks_failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Validation Summary: {checks_passed} passed, {checks_failed} failed")
    print("=" * 80)
    
    if checks_failed == 0:
        print("✅ SUCCESS: Migration 109 is production-safe!")
        return True
    else:
        print("❌ FAILURE: Migration 109 has issues that need to be fixed")
        return False


def validate_docker_compose():
    """
    Validate docker-compose.yml has migration service
    """
    print("\n" + "=" * 80)
    print("Validating Docker Compose Configuration")
    print("=" * 80)
    
    docker_compose_path = os.path.join(
        os.path.dirname(__file__),
        'docker-compose.yml'
    )
    
    if not os.path.exists(docker_compose_path):
        print(f"❌ ERROR: {docker_compose_path} not found")
        return False
    
    with open(docker_compose_path, 'r') as f:
        content = f.read()
    
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: Migrate service exists
    print("\n📋 Check 1: Migration service defined")
    if 'migrate:' in content:
        print("✅ PASS: migrate service is defined")
        checks_passed += 1
    else:
        print("❌ FAIL: migrate service is NOT defined")
        checks_failed += 1
    
    # Check 2: Migration command
    print("\n📋 Check 2: Migration command configured")
    if 'python", "-m", "server.db_migrate' in content:
        print("✅ PASS: Migration command is correct")
        checks_passed += 1
    else:
        print("❌ FAIL: Migration command is incorrect or missing")
        checks_failed += 1
    
    # Check 3: Services depend on migrate
    print("\n📋 Check 3: Services depend on migration completion")
    has_api_dependency = 'prosaas-api:' in content and 'migrate:' in content.split('prosaas-api:')[1].split('prosaas-calls:')[0]
    has_calls_dependency = 'prosaas-calls:' in content and 'migrate:' in content.split('prosaas-calls:')[1].split('# =====')[0]
    
    if has_api_dependency and has_calls_dependency:
        print("✅ PASS: prosaas-api and prosaas-calls depend on migrate")
        checks_passed += 1
    else:
        print(f"❌ FAIL: Not all services depend on migrate (api:{has_api_dependency}, calls:{has_calls_dependency})")
        checks_failed += 1
    
    # Check 4: restart: no for migrate service
    print("\n📋 Check 4: Migration service runs once")
    migrate_section_start = content.find('migrate:')
    if migrate_section_start != -1:
        migrate_section = content[migrate_section_start:migrate_section_start+500]
        if 'restart: "no"' in migrate_section or "restart: 'no'" in migrate_section:
            print("✅ PASS: migrate service configured to run once")
            checks_passed += 1
        else:
            print("❌ FAIL: migrate service should have restart: no")
            checks_failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Docker Compose Validation: {checks_passed} passed, {checks_failed} failed")
    print("=" * 80)
    
    if checks_failed == 0:
        print("✅ SUCCESS: Docker Compose is configured correctly!")
        return True
    else:
        print("❌ FAILURE: Docker Compose has configuration issues")
        return False


def validate_production_compose():
    """
    Validate docker-compose.prod.yml has migration service
    """
    print("\n" + "=" * 80)
    print("Validating Production Docker Compose Configuration")
    print("=" * 80)
    
    docker_compose_path = os.path.join(
        os.path.dirname(__file__),
        'docker-compose.prod.yml'
    )
    
    if not os.path.exists(docker_compose_path):
        print(f"❌ ERROR: {docker_compose_path} not found")
        return False
    
    with open(docker_compose_path, 'r') as f:
        content = f.read()
    
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: Migrate service configuration
    print("\n📋 Check 1: Migration service configured in production")
    if 'migrate:' in content:
        print("✅ PASS: migrate service is defined in production")
        checks_passed += 1
    else:
        print("❌ FAIL: migrate service is NOT defined in production")
        checks_failed += 1
    
    # Check 2: Production API doesn't run migrations
    print("\n📋 Check 2: API service doesn't run migrations")
    api_section_start = content.find('prosaas-api:')
    if api_section_start != -1:
        api_section = content[api_section_start:api_section_start+2000]
        if 'RUN_MIGRATIONS_ON_START: 0' in api_section or 'RUN_MIGRATIONS: "0"' in api_section:
            print("✅ PASS: API service has migrations disabled")
            checks_passed += 1
        else:
            print("❌ FAIL: API service should have migrations disabled")
            checks_failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Production Docker Compose Validation: {checks_passed} passed, {checks_failed} failed")
    print("=" * 80)
    
    if checks_failed == 0:
        print("✅ SUCCESS: Production Docker Compose is configured correctly!")
        return True
    else:
        print("❌ FAILURE: Production Docker Compose has configuration issues")
        return False


if __name__ == '__main__':
    results = []
    
    # Run all validations
    results.append(("Migration 109", validate_migration_109()))
    results.append(("Docker Compose", validate_docker_compose()))
    results.append(("Production Compose", validate_production_compose()))
    
    # Final summary
    print("\n" + "=" * 80)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED! Migration 109 is production-safe!")
        sys.exit(0)
    else:
        print("\n❌ SOME VALIDATIONS FAILED! Please review the output above.")
        sys.exit(1)
