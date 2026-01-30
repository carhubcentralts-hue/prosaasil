#!/usr/bin/env python3
"""
Backfill Audit Tool
===================

Scans db_migrate.py to find all DML operations (UPDATE, INSERT, DELETE)
that should be moved to the backfill system.
"""

import re
import sys

def parse_migrations(filename='server/db_migrate.py'):
    """Parse migrations and find DML operations."""
    with open(filename, 'r') as f:
        content = f.read()
    
    # Find all migrations
    migration_pattern = r'# Migration (\d+[a-z]?):(.*?)(?=# Migration \d+|$)'
    migrations = re.findall(migration_pattern, content, re.DOTALL)
    
    backfills = []
    
    for migration_num, migration_content in migrations:
        # Look for DML patterns
        dml_patterns = {
            'UPDATE': r'UPDATE\s+(\w+)\s+SET',
            'INSERT': r'INSERT\s+INTO.*SELECT',
            'DELETE': r'DELETE\s+FROM',
            'exec_dml': r'exec_dml\(',
            'backfill_comment': r'[Bb]ackfill',
        }
        
        found_dml = {}
        for dml_type, pattern in dml_patterns.items():
            matches = re.findall(pattern, migration_content, re.IGNORECASE)
            if matches:
                found_dml[dml_type] = matches
        
        if found_dml:
            # Extract description
            desc_match = re.search(r'# Migration \d+[a-z]?:\s*(.+)', migration_content.split('\n')[0])
            description = desc_match.group(1).strip() if desc_match else "No description"
            
            # Determine severity
            severity = "LOW"
            if 'UPDATE' in found_dml or 'exec_dml' in found_dml:
                # Check if it's a hot table
                hot_tables = ['leads', 'call_log', 'receipts', 'messages', 'appointments']
                for table in hot_tables:
                    if table in migration_content.lower():
                        severity = "HIGH"
                        break
                if severity == "LOW":
                    severity = "MEDIUM"
            
            # Extract tables affected
            table_matches = set()
            for match in re.findall(r'(?:UPDATE|FROM|INSERT INTO|DELETE FROM)\s+(\w+)', migration_content, re.IGNORECASE):
                if match not in ['text', 'information_schema', 'pg_', 'select']:
                    table_matches.add(match)
            
            backfills.append({
                'migration': migration_num,
                'description': description,
                'dml_types': list(found_dml.keys()),
                'tables': list(table_matches),
                'severity': severity,
                'content_preview': migration_content[:200].replace('\n', ' ')
            })
    
    return backfills

def generate_report(backfills):
    """Generate audit report."""
    print("=" * 80)
    print("BACKFILL AUDIT REPORT")
    print("=" * 80)
    print()
    print(f"Total migrations with DML operations: {len(backfills)}")
    print()
    
    # Group by severity
    by_severity = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
    for bf in backfills:
        by_severity[bf['severity']].append(bf)
    
    for severity in ['HIGH', 'MEDIUM', 'LOW']:
        if by_severity[severity]:
            print(f"\n{'=' * 80}")
            print(f"{severity} PRIORITY ({len(by_severity[severity])} migrations)")
            print('=' * 80)
            
            for bf in by_severity[severity]:
                print(f"\nMigration {bf['migration']}: {bf['description']}")
                print(f"  DML Types: {', '.join(bf['dml_types'])}")
                print(f"  Tables: {', '.join(bf['tables']) if bf['tables'] else 'Unknown'}")
                print(f"  Preview: {bf['content_preview'][:150]}...")
    
    # Generate markdown report
    with open('BACKFILL_AUDIT_REPORT.md', 'w') as f:
        f.write("# Backfill Audit Report\n\n")
        f.write(f"Generated: {__import__('datetime').datetime.now().isoformat()}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total migrations with DML: {len(backfills)}\n")
        f.write(f"- HIGH priority: {len(by_severity['HIGH'])}\n")
        f.write(f"- MEDIUM priority: {len(by_severity['MEDIUM'])}\n")
        f.write(f"- LOW priority: {len(by_severity['LOW'])}\n\n")
        
        f.write("## Priority Definitions\n\n")
        f.write("- **HIGH**: Operations on hot tables (leads, call_log, receipts, messages, appointments)\n")
        f.write("- **MEDIUM**: UPDATE/INSERT operations on other tables\n")
        f.write("- **LOW**: Metadata or small table operations\n\n")
        
        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            if by_severity[severity]:
                f.write(f"\n## {severity} Priority Backfills\n\n")
                f.write("| Migration | Description | Tables | DML Types |\n")
                f.write("|-----------|-------------|--------|----------|\n")
                
                for bf in by_severity[severity]:
                    tables = ', '.join(bf['tables'][:3]) if bf['tables'] else 'Unknown'
                    if len(bf['tables']) > 3:
                        tables += f" (+{len(bf['tables'])-3} more)"
                    dml = ', '.join(bf['dml_types'])
                    f.write(f"| {bf['migration']} | {bf['description'][:50]} | {tables} | {dml} |\n")
        
        f.write("\n## Next Steps\n\n")
        f.write("1. Review HIGH priority migrations first\n")
        f.write("2. Move each backfill to db_backfills.py registry\n")
        f.write("3. Test each backfill independently\n")
        f.write("4. Update migrations to be schema-only\n")
        f.write("5. Add guard test to prevent future backfills in migrations\n")
    
    print(f"\n\n✅ Report saved to BACKFILL_AUDIT_REPORT.md")

def main():
    print("Scanning db_migrate.py for backfill operations...")
    backfills = parse_migrations()
    generate_report(backfills)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
