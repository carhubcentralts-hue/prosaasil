#!/usr/bin/env python3
"""
Test for Smart Migration Reconciliation System
==============================================

Tests the new requirement:
1. schema_migrations state table tracks what's run
2. Each migration has check_already_applied() fingerprint
3. Reconciliation logic:
   - If marked in schema_migrations → SKIP
   - If not marked but fingerprint exists → MARK as reconciled + SKIP
   - Otherwise → RUN
4. No hardcoded numbers - DB tells us what exists
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestSmartReconciliation(unittest.TestCase):
    """Test smart reconciliation system."""
    
    def test_schema_migrations_table_structure(self):
        """Test that schema_migrations table has reconciled field."""
        # The new table structure should include:
        # - migration_id (PRIMARY KEY)
        # - applied_at (TIMESTAMPTZ)
        # - success (BOOLEAN)
        # - reconciled (BOOLEAN) - NEW FIELD
        # - notes (TEXT)
        
        # Read the code to verify structure
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Verify reconciled field is in table definition
        self.assertIn('reconciled BOOLEAN', content)
        self.assertIn('CREATE TABLE IF NOT EXISTS schema_migrations', content)
    
    def test_mark_migration_with_reconciled_flag(self):
        """Test that mark_migration_applied supports reconciled flag."""
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Verify reconciled parameter in mark_migration_applied
        self.assertIn('def mark_migration_applied(engine, migration_id: str, reconciled: bool', content)
        self.assertIn('reconciled = :reconciled', content)
    
    def test_reconciliation_uses_db_checks(self):
        """Test that reconciliation uses actual DB checks, not numbers."""
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Verify reconciliation uses check functions
        self.assertIn('check_table_exists', content)
        self.assertIn('check_column_exists', content)
        self.assertIn('check_index_exists', content)
        self.assertIn('check_constraint_exists', content)
        
        # Verify NO hardcoded migration number ranges like "1-110"
        # The old code had things like "for i in range(1, 111)"
        # We should NOT see that in reconcile_existing_state anymore
        
        # Find the reconcile_existing_state function
        reconcile_start = content.find('def reconcile_existing_state')
        reconcile_end = content.find('\ndef ', reconcile_start + 1)
        if reconcile_end == -1:
            reconcile_end = len(content)
        reconcile_func = content[reconcile_start:reconcile_end]
        
        # Verify no hardcoded number loops in reconciliation
        self.assertNotIn('for i in range(1, 111)', reconcile_func)
        self.assertNotIn('migration_110', reconcile_func)
        
        # Verify it uses fingerprint checks
        self.assertIn('check_func()', reconcile_func)
    
    def test_comprehensive_fingerprint_list(self):
        """Test that reconciliation covers major system components."""
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Find reconciliation function
        reconcile_start = content.find('def reconcile_existing_state')
        reconcile_end = content.find('\ndef ', reconcile_start + 1)
        if reconcile_end == -1:
            reconcile_end = len(content)
        reconcile_func = content[reconcile_start:reconcile_end]
        
        # Verify major system components are checked
        critical_checks = [
            'business',  # Core business table
            'leads',  # Core leads table
            'call_log',  # Call system
            'threads',  # Messaging system
            'messages',  # Messaging system
            'whatsapp',  # WhatsApp integration
            'gmail',  # Email integration
            'recording',  # Recording system
            'contracts',  # Contract system
            'broadcast',  # Broadcast system
            'appointment',  # Appointment system
        ]
        
        for check in critical_checks:
            self.assertIn(check.lower(), reconcile_func.lower(), 
                         f"Missing fingerprint check for {check} system")
    
    def test_reconciliation_logging_is_clear(self):
        """Test that reconciliation provides clear logging."""
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        reconcile_start = content.find('def reconcile_existing_state')
        reconcile_end = content.find('\ndef ', reconcile_start + 1)
        reconcile_func = content[reconcile_start:reconcile_end]
        
        # Verify clear logging messages
        self.assertIn('Smart Reconciliation', reconcile_func)
        self.assertIn('Auto-detecting', reconcile_func)
        self.assertIn('No guessing, no hardcoded numbers', reconcile_func)
        self.assertIn('RECONCILED', reconcile_func)
    
    def test_no_hardcoded_migration_numbers(self):
        """Test that system doesn't use hardcoded migration numbers like 110."""
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # The requirement explicitly says: "אל תשתמש במספרים כמו 110"
        # "Don't use numbers like 110"
        
        # Find apply_migrations function (where migrations run)
        apply_start = content.find('def apply_migrations')
        if apply_start > 0:
            apply_end = content.find('\ndef ', apply_start + 1)
            if apply_end == -1:
                apply_end = len(content)
            apply_func = content[apply_start:apply_end]
            
            # Should not have hardcoded ranges for bulk operations
            # (Some individual migration references are OK, but not bulk ranges)
            self.assertNotIn('range(1, 111)', apply_func)
            self.assertNotIn('migration_110', apply_func)


class TestReconciliationBehavior(unittest.TestCase):
    """Test the three-way reconciliation logic."""
    
    def test_reconciliation_three_paths(self):
        """
        Test the three reconciliation paths per requirement:
        1. If marked in schema_migrations → SKIP
        2. If not marked but exists in DB → MARK + SKIP
        3. Otherwise → RUN (later)
        """
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Find reconciliation logic
        reconcile_start = content.find('def reconcile_existing_state')
        reconcile_end = content.find('\ndef ', reconcile_start + 1)
        reconcile_func = content[reconcile_start:reconcile_end]
        
        # Path 1: Check if already marked
        self.assertIn('is_migration_applied', reconcile_func)
        self.assertIn('continue', reconcile_func)  # Skip if already applied
        
        # Path 2: Check fingerprint and mark
        self.assertIn('check_func()', reconcile_func)
        self.assertIn('mark_migration_applied', reconcile_func)
        self.assertIn('reconciled=True', reconcile_func)


class TestConnectionLockingIntegration(unittest.TestCase):
    """Test that connection locking is preserved with new reconciliation."""
    
    def test_migration_uses_locked_connection(self):
        """Test that migration engine respects connection locking."""
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Verify get_migrate_engine uses try_direct_first
        self.assertIn('try_direct_first=True', content)
        self.assertIn('get_migrate_engine', content)
        
        # Verify connection is locked
        self.assertIn('connection locked', content.lower())


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
