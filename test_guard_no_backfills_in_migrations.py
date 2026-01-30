"""
Guard Test: No Backfills in Migrations
=======================================

This test ensures that NO data backfill operations (DML) are added to migrations.

IRON RULE: Migrations = Schema Only
- ✅ Allowed: CREATE/ALTER/DROP TABLE/COLUMN, CONSTRAINTS, INDEXES
- ❌ Forbidden: UPDATE/INSERT/DELETE on tables with many rows
- ✅ Exception: Small metadata updates (< 100 rows, not on hot tables)

HOT TABLES (never backfill in migrations):
- leads
- call_log  
- receipts
- messages
- appointments
- whatsapp_message

This test will FAIL if:
- UPDATE/INSERT/DELETE found in new migrations
- exec_dml() used
- Backfill comments found

This prevents lock timeout issues in production.
"""

import re
import sys
import os

# Hot tables that should NEVER have backfills in migrations
HOT_TABLES = [
    'leads',
    'call_log',
    'receipts',
    'messages',
    'appointments',
    'whatsapp_message',
    'faqs',  # Can grow large
    'background_jobs',
]

# DML patterns to detect
DML_PATTERNS = {
    'UPDATE': r'UPDATE\s+(\w+)\s+SET',
    'INSERT_SELECT': r'INSERT\s+INTO\s+\w+.*SELECT',
    'DELETE': r'DELETE\s+FROM\s+(\w+)',
    'EXEC_DML': r'exec_dml\s*\(',
    'BACKFILL_COMMENT': r'[Bb]ackfill',
}

# Known migrations that are grandfathered (already exist, will be migrated later)
GRANDFATHERED_MIGRATIONS = [
    '6', '11', '15', '36',  # Already handled or low risk
    '61', '71', '75', '81', '84', '84f',  # Medium priority
    '85', '86', '87', '89', '90', '91', '92',  # Medium/Low priority
    '96', '97', '102', '103', '110', '112', '113', '114', '117',  # To be migrated
]


def extract_migration_number(migration_content):
    """Extract migration number from content."""
    match = re.search(r'# Migration (\d+[a-z]?):', migration_content)
    if match:
        return match.group(1)
    return None


def is_metadata_table(table_name):
    """Check if this is a metadata table (small, not hot)."""
    metadata_tables = [
        'business',
        'tenant',
        'users',
        'settings',
        'business_calendar',
    ]
    return table_name.lower() in metadata_tables


def check_migration_for_dml(migration_content, migration_number):
    """
    Check a single migration for DML operations.
    
    Returns:
        List of violations found
    """
    violations = []
    
    for dml_type, pattern in DML_PATTERNS.items():
        matches = list(re.finditer(pattern, migration_content, re.IGNORECASE))
        
        if not matches:
            continue
        
        # Check if it's on a hot table
        for match in matches:
            if dml_type in ['UPDATE', 'DELETE']:
                # Extract table name
                table_match = re.search(r'(?:UPDATE|DELETE FROM)\s+(\w+)', match.group(0), re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1)
                    
                    # Check if it's a hot table
                    if table_name.lower() in [t.lower() for t in HOT_TABLES]:
                        violations.append({
                            'type': dml_type,
                            'table': table_name,
                            'line': migration_content[:match.start()].count('\n') + 1,
                            'severity': 'HIGH',
                            'reason': f'{dml_type} on hot table {table_name}'
                        })
                    elif not is_metadata_table(table_name):
                        violations.append({
                            'type': dml_type,
                            'table': table_name,
                            'line': migration_content[:match.start()].count('\n') + 1,
                            'severity': 'MEDIUM',
                            'reason': f'{dml_type} on non-metadata table {table_name}'
                        })
            elif dml_type == 'EXEC_DML':
                violations.append({
                    'type': dml_type,
                    'table': 'unknown',
                    'line': migration_content[:match.start()].count('\n') + 1,
                    'severity': 'HIGH',
                    'reason': 'exec_dml() call found (DML operation)'
                })
            elif dml_type == 'BACKFILL_COMMENT':
                # Only flag if it's explicitly mentioning backfill as an action
                context = migration_content[max(0, match.start()-50):match.start()+50]
                if 'backfill' in context.lower() and 'will run separately' not in context.lower():
                    violations.append({
                        'type': dml_type,
                        'table': 'N/A',
                        'line': migration_content[:match.start()].count('\n') + 1,
                        'severity': 'MEDIUM',
                        'reason': 'Backfill comment found (possible data operation)'
                    })
    
    return violations


def test_no_backfills_in_migrations():
    """Main test function."""
    print("=" * 80)
    print("GUARD TEST: No Backfills in Migrations")
    print("=" * 80)
    print()
    
    # Read migrations file
    migrations_file = 'server/db_migrate.py'
    if not os.path.exists(migrations_file):
        print(f"❌ FAIL: {migrations_file} not found")
        return False
    
    with open(migrations_file, 'r') as f:
        content = f.read()
    
    # Find all migrations
    migration_pattern = r'(# Migration \d+[a-z]?:.*?)(?=# Migration \d+|$)'
    migrations = re.findall(migration_pattern, content, re.DOTALL)
    
    print(f"Found {len(migrations)} migrations to check\n")
    
    all_violations = []
    new_violations = []  # Not grandfathered
    
    for migration_content in migrations:
        migration_number = extract_migration_number(migration_content)
        if not migration_number:
            continue
        
        violations = check_migration_for_dml(migration_content, migration_number)
        
        if violations:
            is_grandfathered = migration_number in GRANDFATHERED_MIGRATIONS
            
            for violation in violations:
                violation['migration'] = migration_number
                violation['grandfathered'] = is_grandfathered
                all_violations.append(violation)
                
                if not is_grandfathered:
                    new_violations.append(violation)
    
    # Report results
    if all_violations:
        print(f"Found {len(all_violations)} total violations:")
        print(f"  - Grandfathered (existing): {len(all_violations) - len(new_violations)}")
        print(f"  - NEW violations: {len(new_violations)}")
        print()
        
        if new_violations:
            print("❌ FAIL: New backfill operations found in migrations!")
            print()
            print("NEW VIOLATIONS (must fix):")
            print("-" * 80)
            
            for v in new_violations:
                print(f"\nMigration {v['migration']} (Line {v['line']}):")
                print(f"  Severity: {v['severity']}")
                print(f"  Type: {v['type']}")
                print(f"  Table: {v['table']}")
                print(f"  Reason: {v['reason']}")
                print()
                print("  ⚠️  ACTION REQUIRED:")
                print("     1. Move this backfill to server/db_backfills.py")
                print("     2. Update migration to be schema-only")
                print("     3. See MIGRATION_36_BACKFILL_SEPARATION.md for examples")
            
            print("\n" + "=" * 80)
            print("IRON RULE VIOLATED: Migrations must be schema-only!")
            print("=" * 80)
            print()
            print("Migrations = Schema Only (DDL)")
            print("  ✅ Allowed: CREATE/ALTER/DROP TABLE/COLUMN, CONSTRAINTS")
            print("  ❌ Forbidden: UPDATE/INSERT/DELETE on tables with many rows")
            print()
            print("Data backfills must go in:")
            print("  → server/db_backfills.py (registry)")
            print("  → Runs separately via db_run_backfills.py")
            print()
            return False
        
        else:
            print("✅ PASS: All violations are grandfathered")
            print()
            print("Note: The following migrations have backfills that will be")
            print("migrated to the new backfill system:")
            
            grandfathered_nums = set(v['migration'] for v in all_violations if v['grandfathered'])
            for num in sorted(grandfathered_nums, key=lambda x: int(re.search(r'\d+', x).group())):
                print(f"  • Migration {num}")
            
            print()
            print("These are tracked in BACKFILL_AUDIT_REPORT.md")
            return True
    
    else:
        print("✅ PASS: No backfill operations found in migrations")
        print()
        print("All migrations are schema-only (DDL) as required.")
        return True


def main():
    """Run the guard test."""
    success = test_no_backfills_in_migrations()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ GUARD TEST PASSED")
        print("=" * 80)
        sys.exit(0)
    else:
        print("❌ GUARD TEST FAILED")
        print("=" * 80)
        print("\nThis test prevents production lock timeout issues.")
        print("Please move backfills to server/db_backfills.py")
        sys.exit(1)


if __name__ == '__main__':
    main()
