"""
Test database URL configuration - Single Source of Truth
Tests the new get_database_url() function with various scenarios
"""
import os
import sys
import pytest

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.database_url import get_database_url


class TestDatabaseURL:
    """Test database URL configuration"""
    
    def setup_method(self):
        """Clear environment before each test"""
        # Save original env
        self.orig_env = {}
        for key in list(os.environ.keys()):
            if 'DATABASE' in key or 'DB_POSTGRESDB' in key:
                self.orig_env[key] = os.environ[key]
                del os.environ[key]
    
    def teardown_method(self):
        """Restore environment after each test"""
        # Clear test env
        for key in list(os.environ.keys()):
            if 'DATABASE' in key or 'DB_POSTGRESDB' in key:
                del os.environ[key]
        # Restore original
        for key, value in self.orig_env.items():
            os.environ[key] = value
    
    def test_database_url_priority(self):
        """Test that DATABASE_URL takes priority"""
        os.environ['DATABASE_URL'] = 'postgresql://user1:pass1@host1:5432/db1'
        os.environ['DB_POSTGRESDB_HOST'] = 'host2'
        os.environ['DB_POSTGRESDB_USER'] = 'user2'
        os.environ['DB_POSTGRESDB_PASSWORD'] = 'pass2'
        
        url = get_database_url()
        assert url == 'postgresql://user1:pass1@host1:5432/db1'
        assert 'host2' not in url
    
    def test_postgres_to_postgresql_conversion(self):
        """Test postgres:// gets converted to postgresql://"""
        os.environ['DATABASE_URL'] = 'postgres://user:pass@host:5432/db'
        
        url = get_database_url()
        assert url.startswith('postgresql://')
        assert 'postgres://' not in url
    
    def test_fallback_to_postgresdb_vars(self):
        """Test fallback to DB_POSTGRESDB_* variables"""
        os.environ['DB_POSTGRESDB_HOST'] = 'dbhost'
        os.environ['DB_POSTGRESDB_USER'] = 'dbuser'
        os.environ['DB_POSTGRESDB_PASSWORD'] = 'dbpass'
        os.environ['DB_POSTGRESDB_DATABASE'] = 'mydb'
        os.environ['DB_POSTGRESDB_PORT'] = '5433'
        os.environ['DB_POSTGRESDB_SSL'] = 'true'
        
        url = get_database_url()
        assert url == 'postgresql://dbuser:dbpass@dbhost:5433/mydb?sslmode=require'
    
    def test_fallback_with_defaults(self):
        """Test fallback uses default port and database"""
        os.environ['DB_POSTGRESDB_HOST'] = 'dbhost'
        os.environ['DB_POSTGRESDB_USER'] = 'dbuser'
        os.environ['DB_POSTGRESDB_PASSWORD'] = 'dbpass'
        # No PORT or DATABASE specified - should use defaults
        
        url = get_database_url()
        assert 'dbhost:5432/postgres' in url
    
    def test_fallback_ssl_disabled(self):
        """Test fallback without SSL"""
        os.environ['DB_POSTGRESDB_HOST'] = 'dbhost'
        os.environ['DB_POSTGRESDB_USER'] = 'dbuser'
        os.environ['DB_POSTGRESDB_PASSWORD'] = 'dbpass'
        os.environ['DB_POSTGRESDB_SSL'] = 'false'
        
        url = get_database_url()
        assert '?sslmode=require' not in url
        assert 'dbhost:5432' in url
    
    def test_no_config_raises_error(self):
        """Test that missing config raises RuntimeError"""
        with pytest.raises(RuntimeError) as exc_info:
            get_database_url()
        
        assert 'No database configuration found' in str(exc_info.value)
    
    def test_partial_postgresdb_vars_raises_error(self):
        """Test that partial DB_POSTGRESDB_* config raises error"""
        os.environ['DB_POSTGRESDB_HOST'] = 'dbhost'
        os.environ['DB_POSTGRESDB_USER'] = 'dbuser'
        # Missing PASSWORD
        
        with pytest.raises(RuntimeError):
            get_database_url()


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
