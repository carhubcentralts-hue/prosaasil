#!/usr/bin/env python3
"""
Test for Database Connection Locking Logic
==========================================

This test verifies that:
1. DIRECT is tried once with timeout
2. Connection is locked for entire run
3. POOLER is used as fallback when DIRECT unavailable
4. No retrying DIRECT mid-run
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestDatabaseConnectionLocking(unittest.TestCase):
    """Test connection locking behavior."""
    
    def setUp(self):
        """Reset connection lock before each test."""
        # Import after path is set
        import server.database_url as db_url
        
        # Reset global state
        db_url._CONNECTION_LOCKED = False
        db_url._LOCKED_CONNECTION_TYPE = None
        db_url._LOCKED_URL = None
    
    def test_pooler_no_direct_attempt(self):
        """Test that pooler requests don't try DIRECT."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            
            # Request pooler without try_direct_first
            url = get_database_url(connection_type="pooler", verbose=False, try_direct_first=False)
            
            # Should get pooler URL
            self.assertIn('pooler', url.lower())
    
    def test_direct_with_try_first_success(self):
        """Test DIRECT attempt succeeds and locks."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url, _try_connect_direct
            import server.database_url as db_url
            
            # Mock successful DIRECT connection
            with patch.object(db_url, '_try_connect_direct', return_value=True):
                url = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                
                # Should get DIRECT URL
                self.assertIn('.db.', url.lower())
                
                # Verify connection is locked
                self.assertTrue(db_url._CONNECTION_LOCKED)
                self.assertEqual(db_url._LOCKED_CONNECTION_TYPE, 'direct')
                
                # Second call should return same URL without trying again
                url2 = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                self.assertEqual(url, url2)
    
    def test_direct_with_try_first_failure(self):
        """Test DIRECT attempt fails and falls back to POOLER."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Mock failed DIRECT connection
            with patch.object(db_url, '_try_connect_direct', return_value=False):
                url = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                
                # Should get POOLER URL as fallback
                self.assertIn('pooler', url.lower())
                
                # Verify connection is locked to POOLER
                self.assertTrue(db_url._CONNECTION_LOCKED)
                self.assertEqual(db_url._LOCKED_CONNECTION_TYPE, 'pooler')
                
                # Second call should return same POOLER URL without trying DIRECT again
                url2 = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                self.assertEqual(url, url2)
                self.assertIn('pooler', url2.lower())
    
    def test_direct_not_configured(self):
        """Test behavior when DIRECT not configured."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres'
        }, clear=True):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Request DIRECT with try_first when DIRECT not configured
            url = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
            
            # Should fall back to POOLER
            self.assertIn('pooler', url.lower())
            
            # Verify connection is locked to POOLER
            self.assertTrue(db_url._CONNECTION_LOCKED)
            self.assertEqual(db_url._LOCKED_CONNECTION_TYPE, 'pooler')
    
    def test_no_retry_after_lock(self):
        """Test that DIRECT is never retried after locking to POOLER."""
        with patch.dict(os.environ, {
            'DATABASE_URL_POOLER': 'postgresql://user:pass@db.pooler.supabase.com:5432/postgres',
            'DATABASE_URL_DIRECT': 'postgresql://user:pass@db.db.supabase.com:5432/postgres'
        }):
            from server.database_url import get_database_url
            import server.database_url as db_url
            
            # Mock failed DIRECT connection (will lock to POOLER)
            with patch.object(db_url, '_try_connect_direct', return_value=False) as mock_try:
                # First call - should try DIRECT
                url1 = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                self.assertEqual(mock_try.call_count, 1)
                self.assertIn('pooler', url1.lower())
                
                # Second call - should NOT try DIRECT again (locked to POOLER)
                url2 = get_database_url(connection_type="direct", verbose=False, try_direct_first=True)
                self.assertEqual(mock_try.call_count, 1)  # Still 1, no second attempt
                self.assertEqual(url1, url2)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
