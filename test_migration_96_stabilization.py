#!/usr/bin/env python3
"""
Test Migration 96 Stabilization
================================

Tests the new run_migration wrapper and backfill system for Migration 96.

Tests:
1. run_migration wrapper with fingerprint detection
2. Migration 96 DDL-only execution
3. Backfill 96 for lead name migration
4. POOLER-safe batching and retry logic
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_run_migration_wrapper():
    """Test the run_migration wrapper with fingerprint detection"""
    print("=" * 80)
    print("TEST 1: run_migration wrapper")
    print("=" * 80)
    
    # Read the db_migrate.py file
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check that run_migration function exists with correct signature
    if "def run_migration(migration_id: str, fingerprint_fn, run_fn, engine):" in content or \
       "def run_migration(migration_id, fingerprint_fn, run_fn, engine):" in content:
        print("✅ run_migration function exists with correct signature")
        print("   Parameters: (migration_id, fingerprint_fn, run_fn, engine)")
    else:
        print("❌ run_migration function not found or has wrong signature")
        return False
    
    # Check for key functionality
    required_elements = [
        ("is_migration_applied", "Checks if migration already applied"),
        ("mark_migration_applied", "Marks migration as applied"),
        ("reconciled=True", "Supports reconciliation mode"),
        ('"SKIP"', "Returns SKIP status"),
        ('"RECONCILE"', "Returns RECONCILE status"),
        ('"RUN"', "Returns RUN status"),
    ]
    
    # Find the run_migration function
    start = content.find("def run_migration(migration_id")
    if start == -1:
        print("❌ Could not find run_migration function")
        return False
    
    # Find end of function (next def at same indentation level)
    end = content.find("\ndef ", start + 1)
    if end == -1:
        end = start + 2000  # Take next 2000 chars
    
    func_code = content[start:end]
    
    missing = []
    for element, description in required_elements:
        if element not in func_code:
            missing.append((element, description))
    
    if missing:
        print("⚠️  Missing functionality:")
        for elem, desc in missing:
            print(f"   - {desc} ({elem})")
        return False
    else:
        print("✅ run_migration has all required functionality")
        print("   - Checks if already applied")
        print("   - Supports fingerprint-based reconciliation")
        print("   - Returns status (SKIP/RECONCILE/RUN)")
    
    return True


def test_migration_96_structure():
    """Test Migration 96 structure (DDL only, no DML)"""
    print("\n" + "=" * 80)
    print("TEST 2: Migration 96 Structure")
    print("=" * 80)
    
    # Read migration 96 code
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find migration 96 section more precisely
    start = content.find("# Migration 96: WhatsApp Prompt-Only Mode")
    if start == -1:
        print("❌ Migration 96 not found")
        return False
    
    # Find the end (next migration or significant marker)
    end = content.find("# Migration 97:", start + 1)
    if end == -1:
        end = content.find("# ═══════════════", start + 500)
    
    migration_code = content[start:end]
    
    # Check for forbidden DML operations within migration 96 section
    # Be specific - check for UPDATE within the migration's run_96() function
    if "def run_96():" not in migration_code:
        print("❌ Migration 96 run_96() function not found")
        return False
    
    run_96_start = migration_code.find("def run_96():")
    run_96_end = migration_code.find("# Run migration 96", run_96_start)
    if run_96_end == -1:
        run_96_end = len(migration_code)
    
    run_96_code = migration_code[run_96_start:run_96_end]
    
    # Check for forbidden DML operations in run_96()
    forbidden_patterns = [
        ("UPDATE", "UPDATE statement"),
        ("INSERT INTO", "INSERT statement"),
        ("DELETE FROM", "DELETE statement"),
    ]
    
    violations = []
    for pattern, name in forbidden_patterns:
        if pattern in run_96_code and "# " not in run_96_code[run_96_code.find(pattern)-2:run_96_code.find(pattern)]:
            violations.append(name)
    
    if violations:
        print("❌ Migration 96 contains forbidden DML operations:")
        for v in violations:
            print(f"   - {v}")
        return False
    
    print("✅ Migration 96 contains NO DML operations (UPDATE/INSERT/DELETE)")
    
    # Check for required DDL operations
    required_ddl = [
        ("ALTER TABLE leads", "ALTER TABLE leads"),
        ("ALTER TABLE business", "ALTER TABLE business"),
        ("ADD COLUMN", "ADD COLUMN"),
        ("exec_ddl", "exec_ddl helper"),
    ]
    
    missing_ddl = []
    for pattern, name in required_ddl:
        if pattern not in run_96_code:
            missing_ddl.append(name)
    
    if missing_ddl:
        print("⚠️  Missing expected DDL operations:")
        for m in missing_ddl:
            print(f"   - {m}")
    else:
        print("✅ Migration 96 contains expected DDL operations")
    
    # Check for fingerprint function
    if "def fp_96():" in migration_code:
        print("✅ Migration 96 has fingerprint function")
        
        # Check fingerprint completeness
        fp_start = migration_code.find("def fp_96():")
        fp_end = migration_code.find("def run_96():", fp_start)
        fp_code = migration_code[fp_start:fp_end]
        
        required_checks = [
            "leads", "name",
            "name_source",
            "name_updated_at", 
            "business",
            "whatsapp_system_prompt",
        ]
        
        missing_checks = []
        for check in required_checks:
            if check not in fp_code:
                missing_checks.append(check)
        
        if missing_checks:
            print("⚠️  Fingerprint missing checks:")
            for m in missing_checks:
                print(f"   - {m}")
        else:
            print("✅ Fingerprint function checks all required columns")
    else:
        print("❌ Migration 96 missing fingerprint function")
        return False
    
    # Check for run_migration call
    if 'run_migration("096"' in migration_code or "run_migration('096'" in migration_code:
        print("✅ Migration 96 uses run_migration wrapper")
    else:
        print("❌ Migration 96 not using run_migration wrapper")
        return False
    
    return True


def test_backfill_96_structure():
    """Test Backfill 96 structure and registration"""
    print("\n" + "=" * 80)
    print("TEST 3: Backfill 96 Structure")
    print("=" * 80)
    
    # Check backfill function exists
    with open('server/db_backfills.py', 'r') as f:
        content = f.read()
    
    if "def backfill_96_lead_name" not in content:
        print("❌ Backfill function backfill_96_lead_name not found")
        return False
    
    print("✅ Backfill function backfill_96_lead_name exists")
    
    # Check for POOLER-safe patterns
    required_patterns = [
        "FOR UPDATE SKIP LOCKED",
        "SET lock_timeout",
        "batch_size",
        "OperationalError",
    ]
    
    missing_patterns = []
    for pattern in required_patterns:
        if pattern not in content:
            missing_patterns.append(pattern)
    
    if missing_patterns:
        print("⚠️  Missing POOLER-safe patterns:")
        for m in missing_patterns:
            print(f"   - {m}")
    else:
        print("✅ Backfill uses POOLER-safe patterns (SKIP LOCKED, timeouts, retry)")
    
    # Check registry
    if "'migration_96_lead_name'" in content:
        print("✅ Backfill registered in BACKFILL_DEFS")
    else:
        print("❌ Backfill not registered in BACKFILL_DEFS")
        return False
    
    # Check for UPDATE statement (should exist in backfill)
    if "UPDATE leads" in content and "SET name =" in content:
        print("✅ Backfill contains UPDATE statement for data migration")
    else:
        print("❌ Backfill missing UPDATE statement")
        return False
    
    return True


def test_backfill_runner():
    """Test backfill runner always exits 0"""
    print("\n" + "=" * 80)
    print("TEST 4: Backfill Runner Exit Codes")
    print("=" * 80)
    
    with open('server/db_run_backfills.py', 'r') as f:
        content = f.read()
    
    # Find all sys.exit calls
    import re
    exits = re.findall(r'sys\.exit\((\d+)\)', content)
    
    non_zero_exits = [e for e in exits if e != '0']
    
    if non_zero_exits:
        print(f"❌ Found {len(non_zero_exits)} non-zero exit codes")
        return False
    
    print(f"✅ All {len(exits)} exit points use sys.exit(0)")
    print("   Backfill runner never fails deployment")
    
    return True


def test_index_builder():
    """Test index builder always exits 0"""
    print("\n" + "=" * 80)
    print("TEST 5: Index Builder Exit Codes")
    print("=" * 80)
    
    with open('server/db_build_indexes.py', 'r') as f:
        content = f.read()
    
    # Find all sys.exit calls
    import re
    exits = re.findall(r'sys\.exit\((\d+)\)', content)
    
    non_zero_exits = [e for e in exits if e != '0']
    
    if non_zero_exits:
        print(f"❌ Found {len(non_zero_exits)} non-zero exit codes")
        return False
    
    print(f"✅ All {len(exits)} exit points use sys.exit(0)")
    print("   Index builder never fails deployment")
    
    return True


def test_documentation():
    """Test that documentation exists"""
    print("\n" + "=" * 80)
    print("TEST 6: Documentation")
    print("=" * 80)
    
    doc_file = 'MIGRATION_IRON_RULES.md'
    if not os.path.exists(doc_file):
        print(f"❌ Documentation file {doc_file} not found")
        return False
    
    with open(doc_file, 'r') as f:
        content = f.read()
    
    required_sections = [
        "run_migration",
        "fingerprint",
        "DDL vs DML",
        "Backfills",
        "POOLER",
        "schema_migrations",
    ]
    
    missing = []
    for section in required_sections:
        if section not in content:
            missing.append(section)
    
    if missing:
        print("⚠️  Documentation missing sections:")
        for m in missing:
            print(f"   - {m}")
    else:
        print("✅ Documentation contains all required sections")
    
    print(f"✅ Documentation file exists: {doc_file}")
    print(f"   Size: {len(content)} characters")
    
    return True


def main():
    """Run all tests"""
    print("Migration 96 Stabilization Test Suite")
    print("=" * 80)
    
    tests = [
        ("run_migration wrapper", test_run_migration_wrapper),
        ("Migration 96 structure", test_migration_96_structure),
        ("Backfill 96 structure", test_backfill_96_structure),
        ("Backfill runner exit codes", test_backfill_runner),
        ("Index builder exit codes", test_index_builder),
        ("Documentation", test_documentation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            # If function returns None, consider it passed
            if result is None:
                result = True
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test '{name}' raised exception: {e}")
            results.append((name, False))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 80)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 80)
    
    if passed == total:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
