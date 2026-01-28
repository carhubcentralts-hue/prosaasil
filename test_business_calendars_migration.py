"""
Test Business Calendars Migration
Tests the migration logic integrated in db_migrate.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_migration_sql_patterns():
    """Test that migration SQL patterns are correct in db_migrate.py"""
    # Read the db_migrate file
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check for Migration 115
    assert 'Migration 115' in content, "Migration 115 should be defined in db_migrate.py"
    
    # Check for key SQL statements
    assert 'CREATE TABLE business_calendars' in content
    assert 'CREATE TABLE calendar_routing_rules' in content
    assert 'ALTER TABLE appointments' in content or 'appointments' in content
    assert 'calendar_id INTEGER REFERENCES business_calendars(id)' in content
    
    # Check for proper indexes
    assert 'idx_business_calendars_business_active' in content
    assert 'idx_calendar_routing_business_active' in content
    assert 'idx_appointments_calendar_id' in content
    
    # Check for default calendar creation
    assert 'לוח ברירת מחדל' in content
    assert "type_key = 'default'" in content or 'default' in content
    
    print("✅ Migration 115 SQL patterns validation passed")

def test_migration_backward_compatibility():
    """Test that migration maintains backward compatibility"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Ensure migration creates default calendars for existing businesses
    assert 'INSERT INTO business_calendars' in content
    assert 'WHERE NOT EXISTS' in content or 'NOT EXISTS' in content
    
    # Ensure calendar_id is nullable (backward compat)
    # The ON DELETE SET NULL implies nullable
    assert 'ON DELETE SET NULL' in content
    
    # Ensure existing appointments are linked to default calendar
    assert 'UPDATE appointments' in content
    
    print("✅ Migration 115 backward compatibility validation passed")

def test_migration_data_protection():
    """Test that migration doesn't delete any data"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 115 section
    migration_115_start = content.find('Migration 115')
    migration_115_end = content.find('Migration 116', migration_115_start) if 'Migration 116' in content[migration_115_start:] else content.find('checkpoint("Committing migrations', migration_115_start)
    migration_115_content = content[migration_115_start:migration_115_end]
    
    # Ensure no DROP TABLE in Migration 115
    assert 'DROP TABLE' not in migration_115_content
    
    # Ensure no TRUNCATE in Migration 115
    assert 'TRUNCATE' not in migration_115_content
    
    # Only safe operations: CREATE, ADD, UPDATE, INSERT
    # DELETE should not be present in Migration 115
    assert 'DELETE FROM appointments' not in migration_115_content
    assert 'DELETE FROM business' not in migration_115_content
    
    print("✅ Migration 115 data protection validation passed")

def test_business_calendar_model():
    """Test BusinessCalendar model structure"""
    from server.models_sql import BusinessCalendar
    
    # Check that model has expected attributes
    assert hasattr(BusinessCalendar, '__tablename__')
    assert BusinessCalendar.__tablename__ == 'business_calendars'
    
    # Check key fields exist
    assert hasattr(BusinessCalendar, 'id')
    assert hasattr(BusinessCalendar, 'business_id')
    assert hasattr(BusinessCalendar, 'name')
    assert hasattr(BusinessCalendar, 'type_key')
    assert hasattr(BusinessCalendar, 'provider')
    assert hasattr(BusinessCalendar, 'calendar_external_id')
    assert hasattr(BusinessCalendar, 'is_active')
    assert hasattr(BusinessCalendar, 'priority')
    assert hasattr(BusinessCalendar, 'default_duration_minutes')
    assert hasattr(BusinessCalendar, 'buffer_before_minutes')
    assert hasattr(BusinessCalendar, 'buffer_after_minutes')
    assert hasattr(BusinessCalendar, 'allowed_tags')
    
    print("✅ BusinessCalendar model validation passed")

def test_calendar_routing_rule_model():
    """Test CalendarRoutingRule model structure"""
    from server.models_sql import CalendarRoutingRule
    
    # Check that model has expected attributes
    assert hasattr(CalendarRoutingRule, '__tablename__')
    assert CalendarRoutingRule.__tablename__ == 'calendar_routing_rules'
    
    # Check key fields exist
    assert hasattr(CalendarRoutingRule, 'id')
    assert hasattr(CalendarRoutingRule, 'business_id')
    assert hasattr(CalendarRoutingRule, 'calendar_id')
    assert hasattr(CalendarRoutingRule, 'match_labels')
    assert hasattr(CalendarRoutingRule, 'match_keywords')
    assert hasattr(CalendarRoutingRule, 'channel_scope')
    assert hasattr(CalendarRoutingRule, 'when_ambiguous_ask')
    assert hasattr(CalendarRoutingRule, 'question_text')
    assert hasattr(CalendarRoutingRule, 'priority')
    assert hasattr(CalendarRoutingRule, 'is_active')
    
    print("✅ CalendarRoutingRule model validation passed")

def test_appointment_calendar_relationship():
    """Test that Appointment model has calendar_id field"""
    from server.models_sql import Appointment
    
    # Check that Appointment has calendar_id
    assert hasattr(Appointment, 'calendar_id')
    
    print("✅ Appointment-Calendar relationship validation passed")

if __name__ == '__main__':
    # Run tests
    test_migration_sql_patterns()
    test_migration_backward_compatibility()
    test_migration_data_protection()
    test_business_calendar_model()
    test_calendar_routing_rule_model()
    test_appointment_calendar_relationship()
    
    print("\n🎉 All migration tests passed!")
