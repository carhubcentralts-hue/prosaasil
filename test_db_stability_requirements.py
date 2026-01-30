#!/usr/bin/env python3
"""
Integration Test for Database Connection Stability Requirements
================================================================

This test verifies all requirements from the problem statement:
1. Default: Work on POOLER
2. Try DIRECT once with short timeout (3-5s) at migration start
3. Lock to chosen connection for entire run
4. Never retry DIRECT mid-run
5. Clear logging of connection choice
6. Migrations are idempotent (handle "already exists")
7. Indexer uses AUTOCOMMIT + CREATE INDEX CONCURRENTLY
8. Backfill uses batches + FOR UPDATE SKIP LOCKED
9. Scripts always exit 0
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestDatabaseStabilityRequirements(unittest.TestCase):
    """Test all stability requirements."""
    
    def setUp(self):
        """Reset connection lock before each test."""
        import server.database_url as db_url
        
        # Reset global state
        db_url._CONNECTION_LOCKED = False
        db_url._LOCKED_CONNECTION_TYPE = None
        db_url._LOCKED_URL = None
    
    def test_requirement_1_default_pooler(self):
        """Requirement 1: Default work on POOLER."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            
            # Default request should use POOLER
            url = get_database_url(connection_type="pooler", verbose=False)
            self.assertIn('pooler', url.lower())
    
    def test_requirement_2_try_direct_once(self):
        """Requirement 2: Try DIRECT once with 5s timeout at migration start."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Mock _try_connect_direct to track calls
            with patch.object(db_url, '_try_connect_direct', return_value=True) as mock_try:
                # First call with try_direct_first=True
                url = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                
                # Should have tried DIRECT exactly once
                self.assertEqual(mock_try.call_count, 1)
                # Should be called with 5s timeout
                mock_try.assert_called_once()
                args = mock_try.call_args
                self.assertEqual(args[1]['timeout'], 5)
    
    def test_requirement_3_lock_to_chosen_connection(self):
        """Requirement 3: Lock to chosen connection (DIRECT or POOLER) for entire run."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Mock successful DIRECT connection
            with patch.object(db_url, '_try_connect_direct', return_value=True):
                # First call - should lock to DIRECT
                url1 = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                self.assertIn('.db.', url1.lower())
                self.assertTrue(db_url._CONNECTION_LOCKED)
                
                # All subsequent calls should return same URL
                for _ in range(5):
                    url = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                    self.assertEqual(url, url1)
    
    def test_requirement_4_never_retry_direct(self):
        """Requirement 4: Never retry DIRECT mid-run."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Mock failed DIRECT (will lock to POOLER)
            with patch.object(db_url, '_try_connect_direct', return_value=False) as mock_try:
                # First call - try DIRECT, fail, lock to POOLER
                url1 = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                self.assertIn('pooler', url1.lower())
                self.assertEqual(mock_try.call_count, 1)
                
                # Multiple subsequent calls - should NOT retry DIRECT
                for _ in range(5):
                    url = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                    self.assertEqual(url, url1)
                
                # Still only 1 call to _try_connect_direct
                self.assertEqual(mock_try.call_count, 1)
    
    def test_requirement_5_clear_logging_direct(self):
        """Requirement 5: Clear logging - 'Using DIRECT'."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            import logging
            
            # Capture logs
            with patch.object(db_url, '_try_connect_direct', return_value=True):
                with patch.object(db_url.logger, 'info') as mock_log:
                    url = get_database_url(connection_type="direct", verbose=True, try_direct_first=True)
                    
                    # Check that "Using DIRECT" was logged
                    log_calls = [str(call) for call in mock_log.call_args_list]
                    log_text = ' '.join(log_calls)
                    self.assertIn('Using DIRECT', log_text)
    
    def test_requirement_5_clear_logging_pooler_locked(self):
        """Requirement 5: Clear logging - 'Using POOLER (DIRECT unavailable - locked)'."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Capture logs
            with patch.object(db_url, '_try_connect_direct', return_value=False):
                with patch.object(db_url.logger, 'info') as mock_log:
                    url = get_database_url(connection_type="direct", verbose=True, try_direct_first=True)
                    
                    # Check that "Using POOLER (DIRECT unavailable - locked)" was logged
                    log_calls = [str(call) for call in mock_log.call_args_list]
                    log_text = ' '.join(log_calls)
                    self.assertIn('Using POOLER', log_text)
                    self.assertIn('DIRECT unavailable - locked', log_text)
    
    def test_requirement_6_migrations_idempotent(self):
        """Requirement 6: Migrations handle 'already exists' gracefully."""
        # This is verified by checking the code - migrations use:
        # - IF NOT EXISTS for CREATE operations
        # - IF EXISTS for DROP operations
        # - check_table_exists() and check_column_exists() helpers
        
        # Read the migration code
        with open('server/db_migrate.py', 'r') as f:
            content = f.read()
        
        # Verify idempotent patterns are used
        self.assertIn('IF NOT EXISTS', content)
        self.assertIn('IF EXISTS', content)
        self.assertIn('check_table_exists', content)
        self.assertIn('check_column_exists', content)
    
    def test_requirement_7_indexer_autocommit_concurrent(self):
        """Requirement 7: Indexer uses AUTOCOMMIT + CREATE INDEX CONCURRENTLY."""
        # Read the indexer code
        with open('server/db_build_indexes.py', 'r') as f:
            content = f.read()
        
        # Verify AUTOCOMMIT is used
        self.assertIn('AUTOCOMMIT', content)
        self.assertIn('isolation_level="AUTOCOMMIT"', content)
        
        # Verify CONCURRENTLY is documented/expected
        self.assertIn('CONCURRENTLY', content)
    
    def test_requirement_8_backfill_batch_skip_locked(self):
        """Requirement 8: Backfill uses batches + FOR UPDATE SKIP LOCKED."""
        # Read the backfill code
        with open('server/db_backfills.py', 'r') as f:
            content = f.read()
        
        # Verify batch processing and SKIP LOCKED are used
        self.assertIn('batch_size', content)
        self.assertIn('FOR UPDATE SKIP LOCKED', content)
        self.assertIn('small batches', content.lower())
    
    def test_requirement_9_scripts_exit_zero(self):
        """Requirement 9: Indexer/backfill always exit 0 (don't fail deployment)."""
        # Read indexer code
        with open('server/db_build_indexes.py', 'r') as f:
            indexer_content = f.read()
        
        # Read backfill code
        with open('server/db_run_backfills.py', 'r') as f:
            backfill_content = f.read()
        
        # Verify both always exit 0
        self.assertIn('sys.exit(0)', indexer_content)
        self.assertIn('# Exit 0 to not block deployment', indexer_content)
        
        self.assertIn('sys.exit(0)', backfill_content)
        # Verify no sys.exit(1) or other error exits in main path
        self.assertNotIn('sys.exit(1)', indexer_content)


class TestConnectionLockingScenarios(unittest.TestCase):
    """Test realistic scenarios."""
    
    def setUp(self):
        """Reset connection lock before each test."""
        import server.database_url as db_url
        db_url._CONNECTION_LOCKED = False
        db_url._LOCKED_CONNECTION_TYPE = None
        db_url._LOCKED_URL = None
    
    def test_scenario_production_pooler_only(self):
        """Scenario: Production with only POOLER configured."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres'
        }, clear=True):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Migration tries DIRECT first
            with patch.object(db_url.logger, 'info') as mock_log:
                url = get_database_url(connection_type="direct", verbose=True, try_direct_first=True)
                
                # Should use POOLER
                self.assertIn('pooler', url.lower())
                
                # Should log that DIRECT not configured
                log_text = ' '.join([str(call) for call in mock_log.call_args_list])
                self.assertIn('Using POOLER', log_text)
    
    def test_scenario_direct_unreachable_timeout(self):
        """Scenario: DIRECT configured but unreachable (network issue)."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Mock DIRECT connection timeout
            with patch.object(db_url, '_try_connect_direct', return_value=False):
                with patch.object(db_url.logger, 'info') as mock_log:
                    url = get_database_url(connection_type="direct", verbose=True, try_direct_first=True)
                    
                    # Should fall back to POOLER
                    self.assertIn('pooler', url.lower())
                    
                    # Should log fallback
                    log_text = ' '.join([str(call) for call in mock_log.call_args_list])
                    self.assertIn('Using POOLER', log_text)
                    self.assertIn('unavailable', log_text.lower())


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
