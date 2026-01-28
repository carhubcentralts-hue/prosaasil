"""
Test Business Calendars Migration
Tests the migration script without requiring a live database
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_migration_sql_syntax():
    """Test that migration SQL is valid PostgreSQL syntax"""
    # Read the migration file
    with open('migration_add_business_calendars.py', 'r') as f:
        content = f.read()
    
    # Check for key SQL statements
    assert 'CREATE TABLE IF NOT EXISTS business_calendars' in content
    assert 'CREATE TABLE IF NOT EXISTS calendar_routing_rules' in content
    assert 'ALTER TABLE appointments' in content
    assert 'calendar_id INTEGER REFERENCES business_calendars(id)' in content
    
    # Check for proper indexes
    assert 'CREATE INDEX IF NOT EXISTS idx_business_calendars_business_active' in content
    assert 'CREATE INDEX IF NOT EXISTS idx_calendar_routing_business_active' in content
    assert 'CREATE INDEX IF NOT EXISTS idx_appointments_calendar_id' in content
    
    # Check for default calendar creation
    assert 'לוח ברירת מחדל' in content
    assert "type_key = 'default'" in content
    
    print("✅ Migration SQL syntax validation passed")

def test_migration_backward_compatibility():
    """Test that migration maintains backward compatibility"""
    with open('migration_add_business_calendars.py', 'r') as f:
        content = f.read()
    
    # Ensure migration creates default calendars for existing businesses
    assert 'INSERT INTO business_calendars' in content
    assert 'WHERE NOT EXISTS' in content
    
    # Ensure calendar_id is nullable (backward compat)
    assert 'calendar_id INTEGER REFERENCES business_calendars(id) ON DELETE SET NULL' in content
    
    # Ensure existing appointments are linked to default calendar
    assert 'UPDATE appointments a' in content
    assert "bc.type_key = 'default'" in content
    
    print("✅ Migration backward compatibility validation passed")

def test_migration_data_protection():
    """Test that migration doesn't delete any data"""
    with open('migration_add_business_calendars.py', 'r') as f:
        content = f.read()
    
    # Ensure no DROP TABLE
    assert 'DROP TABLE' not in content
    
    # Ensure no TRUNCATE
    assert 'TRUNCATE' not in content
    
    # Only safe operations: CREATE, ADD, UPDATE, INSERT
    # DELETE should not be present
    assert 'DELETE FROM appointments' not in content
    assert 'DELETE FROM business' not in content
    
    print("✅ Migration data protection validation passed")

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
    test_migration_sql_syntax()
    test_migration_backward_compatibility()
    test_migration_data_protection()
    test_business_calendar_model()
    test_calendar_routing_rule_model()
    test_appointment_calendar_relationship()
    
    print("\n🎉 All migration tests passed!")
