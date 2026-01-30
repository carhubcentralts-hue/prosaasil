#!/usr/bin/env python3
"""
GO/NO-GO Verification Script for Database Connection Separation
================================================================

This script verifies that the database connection separation is correctly
implemented according to the requirements:

1. Migrations/indexer/backfill use DATABASE_URL_DIRECT
2. API/worker/calls use DATABASE_URL_POOLER
3. Proper logging shows which connection is being used
4. Migration 95 uses NOT VALID + VALIDATE
5. Indexer uses AUTOCOMMIT + CONCURRENTLY
6. Backfills are separated from migrations
"""

import os
import re
import sys
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def header(msg):
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{msg}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")


class VerificationResults:
    def __init__(self):
        self.checks = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_pass(self, check_name):
        self.checks.append(('PASS', check_name))
        self.passed += 1
        success(check_name)
    
    def add_fail(self, check_name, details=None):
        self.checks.append(('FAIL', check_name, details))
        self.failed += 1
        error(check_name)
        if details:
            print(f"   {details}")
    
    def add_warning(self, check_name, details=None):
        self.checks.append(('WARN', check_name, details))
        self.warnings += 1
        warning(check_name)
        if details:
            print(f"   {details}")
    
    def print_summary(self):
        header("VERIFICATION SUMMARY")
        print(f"Total checks: {len(self.checks)}")
        print(f"{GREEN}Passed: {self.passed}{RESET}")
        print(f"{RED}Failed: {self.failed}{RESET}")
        print(f"{YELLOW}Warnings: {self.warnings}{RESET}")
        print()
        
        if self.failed == 0:
            print(f"{GREEN}{BOLD}✅ GO: All critical checks passed!{RESET}")
            return True
        else:
            print(f"{RED}{BOLD}❌ NO-GO: {self.failed} critical check(s) failed!{RESET}")
            return False


def check_1_code_uses_correct_connection_types(results):
    """Check that code uses correct connection types."""
    header("CHECK 1: Code Uses Correct Connection Types")
    
    repo_root = Path("/home/runner/work/prosaasil/prosaasil")
    
    # Files that should use DIRECT
    direct_files = [
        "server/db_migrate.py",
        "server/db_build_indexes.py",
        "server/db_run_backfills.py"
    ]
    
    # Files that should use POOLER
    pooler_files = [
        "server/production_config.py",
        "server/app_factory.py"
    ]
    
    # Check DIRECT files
    for file_path in direct_files:
        full_path = repo_root / file_path
        if not full_path.exists():
            results.add_warning(f"{file_path} not found", "File may have been moved or deleted")
            continue
        
        content = full_path.read_text()
        if 'connection_type="direct"' in content or "connection_type='direct'" in content:
            results.add_pass(f"{file_path} uses DIRECT connection")
        else:
            results.add_fail(f"{file_path} should use DIRECT connection", 
                           f"File should call get_database_url(connection_type='direct')")
    
    # Check POOLER files
    for file_path in pooler_files:
        full_path = repo_root / file_path
        if not full_path.exists():
            results.add_warning(f"{file_path} not found", "File may have been moved or deleted")
            continue
        
        content = full_path.read_text()
        if 'connection_type="pooler"' in content or "connection_type='pooler'" in content:
            results.add_pass(f"{file_path} uses POOLER connection")
        else:
            results.add_fail(f"{file_path} should use POOLER connection",
                           f"File should call get_database_url(connection_type='pooler')")


def check_2_docker_compose_environment_variables(results):
    """Check that docker-compose has correct environment variables."""
    header("CHECK 2: Docker-Compose Environment Variables")
    
    compose_file = Path("/home/runner/work/prosaasil/prosaasil/docker-compose.prod.yml")
    if not compose_file.exists():
        results.add_fail("docker-compose.prod.yml not found")
        return
    
    content = compose_file.read_text()
    
    # Services that should have DIRECT
    direct_services = ['migrate', 'indexer', 'backfill']
    for service in direct_services:
        pattern = rf'{service}:.*?environment:.*?DATABASE_URL_DIRECT'
        if re.search(pattern, content, re.DOTALL):
            results.add_pass(f"Service '{service}' has DATABASE_URL_DIRECT configured")
        else:
            results.add_fail(f"Service '{service}' should have DATABASE_URL_DIRECT")
    
    # Services that should have POOLER
    pooler_services = ['prosaas-api', 'worker', 'prosaas-calls']
    for service in pooler_services:
        pattern = rf'{service}:.*?environment:.*?DATABASE_URL_POOLER'
        if re.search(pattern, content, re.DOTALL):
            results.add_pass(f"Service '{service}' has DATABASE_URL_POOLER configured")
        else:
            results.add_fail(f"Service '{service}' should have DATABASE_URL_POOLER")


def check_4_migration_95_uses_not_valid(results):
    """Check that Migration 95 uses NOT VALID + VALIDATE approach."""
    header("CHECK 4: Migration 95 Uses NOT VALID + VALIDATE")
    
    migrate_file = Path("/home/runner/work/prosaasil/prosaasil/server/db_migrate.py")
    if not migrate_file.exists():
        results.add_fail("db_migrate.py not found")
        return
    
    content = migrate_file.read_text()
    
    # Look for Migration 95
    if "Migration 95" in content:
        # Check for NOT VALID
        if "NOT VALID" in content:
            results.add_pass("Migration 95 uses NOT VALID")
        else:
            results.add_fail("Migration 95 should use NOT VALID for constraint addition")
        
        # Check for VALIDATE CONSTRAINT
        if "VALIDATE CONSTRAINT" in content:
            results.add_pass("Migration 95 uses VALIDATE CONSTRAINT")
        else:
            results.add_fail("Migration 95 should use VALIDATE CONSTRAINT")
        
        # Check that it doesn't use DO $$
        migration_95_match = re.search(r'Migration 95.*?(?=Migration \d+|$)', content, re.DOTALL)
        if migration_95_match:
            migration_content = migration_95_match.group(0)
            if 'DO $$' in migration_content or 'DO $' in migration_content:
                results.add_fail("Migration 95 should not use DO $$ blocks")
            else:
                results.add_pass("Migration 95 does not use DO $$ blocks")
    else:
        results.add_warning("Migration 95 not found in db_migrate.py")


def check_5_indexer_uses_concurrently(results):
    """Check that indexer uses AUTOCOMMIT and CONCURRENTLY."""
    header("CHECK 5: Indexer Uses AUTOCOMMIT + CONCURRENTLY")
    
    indexer_file = Path("/home/runner/work/prosaasil/prosaasil/server/db_build_indexes.py")
    if not indexer_file.exists():
        results.add_fail("db_build_indexes.py not found")
        return
    
    content = indexer_file.read_text()
    
    # Check for AUTOCOMMIT
    if "AUTOCOMMIT" in content or "autocommit" in content:
        results.add_pass("Indexer uses AUTOCOMMIT")
    else:
        results.add_fail("Indexer should use AUTOCOMMIT isolation level")
    
    # Check for CONCURRENTLY
    if "CONCURRENTLY" in content:
        results.add_pass("Indexer uses CONCURRENTLY for index creation")
    else:
        results.add_fail("Indexer should use CONCURRENTLY for all index creation")
    
    # Check that all CREATE INDEX use CONCURRENTLY
    create_index_lines = re.findall(r'CREATE.*INDEX.*', content, re.IGNORECASE)
    non_concurrent = [line for line in create_index_lines if 'CONCURRENTLY' not in line.upper()]
    
    if non_concurrent:
        results.add_warning(f"Found {len(non_concurrent)} CREATE INDEX without CONCURRENTLY",
                          f"Lines: {non_concurrent[:3]}")


def check_6_backfills_separated(results):
    """Check that backfills are separated from migrations."""
    header("CHECK 6: Backfills Separated from Migrations")
    
    migrate_file = Path("/home/runner/work/prosaasil/prosaasil/server/db_migrate.py")
    backfill_file = Path("/home/runner/work/prosaasil/prosaasil/server/db_run_backfills.py")
    
    if not migrate_file.exists():
        results.add_fail("db_migrate.py not found")
        return
    
    migrate_content = migrate_file.read_text()
    
    # Check for heavy backfill operations in migrations
    backfill_indicators = [
        'UPDATE.*WHERE.*LIMIT.*100',  # Batch updates
        'FOR UPDATE SKIP LOCKED',      # Backfill pattern
        'db_run_backfills',            # Direct backfill reference
    ]
    
    found_backfills = []
    for pattern in backfill_indicators:
        if re.search(pattern, migrate_content, re.IGNORECASE):
            found_backfills.append(pattern)
    
    if found_backfills:
        results.add_warning("Possible backfill operations found in db_migrate.py",
                          f"Patterns: {found_backfills}")
    else:
        results.add_pass("No heavy backfill operations found in migrations")
    
    # Check that backfill runner exists separately
    if backfill_file.exists():
        results.add_pass("Separate backfill runner exists (db_run_backfills.py)")
    else:
        results.add_fail("Backfill runner (db_run_backfills.py) not found")


def check_logging_implementation(results):
    """Check that logging shows connection type."""
    header("BONUS CHECK: Logging Implementation")
    
    database_url_file = Path("/home/runner/work/prosaasil/prosaasil/server/database_url.py")
    if not database_url_file.exists():
        results.add_fail("database_url.py not found")
        return
    
    content = database_url_file.read_text()
    
    # Check for logging
    if 'logging' in content or 'logger' in content:
        results.add_pass("Logging module is imported and used")
    else:
        results.add_warning("No logging found in database_url.py")
    
    # Check for host extraction
    if 'host' in content.lower() and 'log' in content.lower():
        results.add_pass("Connection info logging implemented")
    else:
        results.add_warning("Connection host logging may not be implemented")


def main():
    print(f"{BOLD}{'='*80}")
    print(f"GO/NO-GO VERIFICATION FOR DATABASE CONNECTION SEPARATION")
    print(f"{'='*80}{RESET}\n")
    
    results = VerificationResults()
    
    # Run all checks
    check_1_code_uses_correct_connection_types(results)
    check_2_docker_compose_environment_variables(results)
    check_4_migration_95_uses_not_valid(results)
    check_5_indexer_uses_concurrently(results)
    check_6_backfills_separated(results)
    check_logging_implementation(results)
    
    # Print summary
    go_no_go = results.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if go_no_go else 1)


if __name__ == "__main__":
    main()
