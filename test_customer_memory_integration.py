"""
Test Customer Memory Service
Validates unified memory management for WhatsApp + Calls
"""
from datetime import datetime, timedelta
from server.services.customer_memory_service import (
    get_customer_memory,
    format_memory_for_ai,
    should_ask_continue_or_fresh,
    is_customer_service_enabled,
    update_interaction_timestamp
)


def test_customer_memory_service_imports():
    """Test that all customer memory service functions are importable"""
    # Just importing successfully is a win
    assert get_customer_memory is not None
    assert format_memory_for_ai is not None
    assert should_ask_continue_or_fresh is not None
    assert is_customer_service_enabled is not None
    assert update_interaction_timestamp is not None
    print("✅ All customer memory service functions imported successfully")


def test_format_empty_memory():
    """Test formatting empty memory dict"""
    result = format_memory_for_ai({})
    assert result == ""
    print("✅ Empty memory formats to empty string")


def test_format_memory_with_profile():
    """Test formatting memory with customer profile"""
    memory = {
        'customer_profile': {
            'name': {'value': 'יוסי כהן', 'source': 'manual'},
            'city': {'value': 'תל אביב', 'source': 'ai_extraction'}
        }
    }
    result = format_memory_for_ai(memory)
    assert '📋 פרופיל לקוח:' in result
    assert 'יוסי כהן' in result
    assert 'תל אביב' in result
    print("✅ Memory with profile formats correctly")
    print(f"   Formatted output:\n{result}")


def test_format_memory_with_summary():
    """Test formatting memory with conversation summary"""
    memory = {
        'last_summary': 'הלקוח התעניין בשירות תספורת',
        'last_channel': 'whatsapp'
    }
    result = format_memory_for_ai(memory)
    assert '📝 סיכום שיחה אחרונה:' in result
    assert 'הלקוח התעניין בשירות תספורת' in result
    assert 'whatsapp' in result
    print("✅ Memory with summary formats correctly")
    print(f"   Formatted output:\n{result}")


def test_format_memory_with_notes():
    """Test formatting memory with recent notes"""
    memory = {
        'recent_notes': [
            {
                'content': 'לקוח רוצה לקבוע פגישה לשבוע הבא',
                'type': 'call_summary',
                'created_at': '2024-01-15T10:00:00'
            },
            {
                'content': 'לקוח שאל על מחירים',
                'type': 'manual',
                'created_at': '2024-01-14T15:30:00'
            }
        ]
    }
    result = format_memory_for_ai(memory)
    assert '📚 הערות אחרונות' in result
    assert 'לקוח רוצה לקבוע פגישה' in result
    assert 'לקוח שאל על מחירים' in result
    print("✅ Memory with notes formats correctly")
    print(f"   Formatted output:\n{result}")


def test_format_memory_complete():
    """Test formatting complete memory with all fields"""
    memory = {
        'customer_profile': {
            'name': {'value': 'דנה לוי', 'source': 'manual'},
            'service_interest': {'value': 'צביעת שיער', 'source': 'ai_extraction'}
        },
        'last_summary': 'לקוח ביקש פגישה למחר בבוקר',
        'last_channel': 'call',
        'recent_notes': [
            {
                'content': 'התקשר לברר מחירים',
                'type': 'call_summary',
                'created_at': '2024-01-15T09:00:00'
            }
        ]
    }
    result = format_memory_for_ai(memory)
    
    # Check all sections present
    assert '📋 פרופיל לקוח:' in result
    assert '📝 סיכום שיחה אחרונה:' in result
    assert '📚 הערות אחרונות' in result
    
    # Check content
    assert 'דנה לוי' in result
    assert 'צביעת שיער' in result
    assert 'לקוח ביקש פגישה למחר בבוקר' in result
    assert 'התקשר לברר מחירים' in result
    
    print("✅ Complete memory formats correctly")
    print(f"   Formatted output:\n{result}")


def test_migration_121_fields():
    """Test that migration 121 fields are defined in Lead model"""
    from server.models_sql import Lead
    
    # Check that the new fields exist in the model
    assert hasattr(Lead, 'customer_profile_json'), "customer_profile_json field missing"
    assert hasattr(Lead, 'last_summary'), "last_summary field missing"
    assert hasattr(Lead, 'summary_updated_at'), "summary_updated_at field missing"
    assert hasattr(Lead, 'last_interaction_at'), "last_interaction_at field missing"
    assert hasattr(Lead, 'last_channel'), "last_channel field missing"
    
    print("✅ All migration 121 fields exist in Lead model")


def test_whatsapp_session_helpers():
    """Test that WhatsApp session service has memory helper functions"""
    from server.services.whatsapp_session_service import (
        extract_memory_patch_from_messages,
        merge_customer_profile
    )
    
    assert extract_memory_patch_from_messages is not None
    assert merge_customer_profile is not None
    
    print("✅ WhatsApp session service has memory helper functions")


def test_merge_customer_profile_empty():
    """Test merging into empty profile"""
    from server.services.whatsapp_session_service import merge_customer_profile
    
    existing = {}
    patch = {
        'name': 'יעל כהן',
        'city': 'חיפה'
    }
    
    result = merge_customer_profile(existing, patch)
    
    assert 'name' in result
    assert result['name']['value'] == 'יעל כהן'
    assert result['name']['source'] == 'ai_extraction'
    assert 'city' in result
    assert result['city']['value'] == 'חיפה'
    
    print("✅ Merging into empty profile works correctly")


def test_merge_customer_profile_preserves_manual():
    """Test that manual data is preserved over AI extractions"""
    from server.services.whatsapp_session_service import merge_customer_profile
    
    existing = {
        'name': {
            'value': 'יוסי מנואל',
            'source': 'manual',
            'updated_at': '2024-01-10T10:00:00'
        }
    }
    patch = {
        'name': 'יוסף',  # AI extracted wrong name
        'city': 'תל אביב'
    }
    
    result = merge_customer_profile(existing, patch)
    
    # Manual name should be preserved
    assert result['name']['value'] == 'יוסי מנואל', "Manual name was overwritten!"
    assert result['name']['source'] == 'manual'
    
    # New city should be added
    assert 'city' in result
    assert result['city']['value'] == 'תל אביב'
    
    print("✅ Manual data preserved during merge")


if __name__ == '__main__':
    print("Running customer memory service tests...\n")
    
    test_customer_memory_service_imports()
    test_format_empty_memory()
    test_format_memory_with_profile()
    test_format_memory_with_summary()
    test_format_memory_with_notes()
    test_format_memory_complete()
    test_migration_121_fields()
    test_whatsapp_session_helpers()
    test_merge_customer_profile_empty()
    test_merge_customer_profile_preserves_manual()
    
    print("\n✅ All tests passed!")
