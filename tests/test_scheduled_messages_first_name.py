"""
Test for first_name variable in scheduled messages
"""
import pytest
from server.services import scheduled_messages_service


class MockLead:
    def __init__(self, first_name=None, last_name=None, full_name=None, name=None, phone_e164=None, phone_raw=None):
        self.first_name = first_name
        self.last_name = last_name
        self.full_name = full_name
        self.name = name
        self.phone_e164 = phone_e164
        self.phone_raw = phone_raw


class MockBusiness:
    def __init__(self, name=None):
        self.name = name


def test_first_name_variable_extraction():
    """Test that {first_name} variable is correctly extracted and used"""
    # Test with explicit first_name field
    lead = MockLead(first_name="John", last_name="Doe", full_name="John Doe", phone_e164="+972501234567")
    business = MockBusiness(name="Test Business")
    
    template = "שלום {first_name}, ברוך הבא ל-{business_name}"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business, 
        status_name="new", 
        status_label="חדש"
    )
    
    assert rendered == "שלום John, ברוך הבא ל-Test Business"


def test_first_name_fallback_to_full_name():
    """Test that first_name falls back to first word of full_name if first_name is not set"""
    lead = MockLead(full_name="Jane Smith", phone_e164="+972501234567")
    business = MockBusiness(name="Test Business")
    
    template = "היי {first_name}!"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business,
        status_name="new",
        status_label="חדש"
    )
    
    assert rendered == "היי Jane!"


def test_first_name_with_hebrew_placeholder():
    """Test Hebrew placeholder {{שם פרטי}} for first name"""
    lead = MockLead(first_name="David", full_name="David Cohen", phone_e164="+972501234567")
    business = MockBusiness(name="Test Business")
    
    template = "שלום {{שם פרטי}}, מה שלומך?"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business,
        status_name="new",
        status_label="חדש"
    )
    
    assert rendered == "שלום David, מה שלומך?"


def test_all_variables_including_first_name():
    """Test that all variables including first_name work together"""
    lead = MockLead(
        first_name="Sarah",
        full_name="Sarah Johnson",
        phone_e164="+972501234567"
    )
    business = MockBusiness(name="My Business")
    
    template = "היי {first_name}, זה {lead_name} מ-{business_name}. הטלפון שלך: {phone}. סטטוס: {status}"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business,
        status_name="contacted",
        status_label="צור קשר"
    )
    
    assert "Sarah" in rendered
    assert "Sarah Johnson" in rendered
    assert "My Business" in rendered
    assert "+972501234567" in rendered
    assert "צור קשר" in rendered


def test_first_name_with_empty_string():
    """Test that first_name handles empty strings correctly"""
    lead = MockLead(first_name="", full_name="", phone_e164="+972501234567")
    business = MockBusiness(name="Test Business")
    
    template = "שלום {first_name}"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business,
        status_name="new",
        status_label="חדש"
    )
    
    assert rendered == "שלום Customer"


def test_first_name_with_spaces_only():
    """Test that first_name handles whitespace-only names"""
    lead = MockLead(full_name="   ", phone_e164="+972501234567")
    business = MockBusiness(name="Test Business")
    
    template = "היי {first_name}!"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business,
        status_name="new",
        status_label="חדש"
    )
    
    assert rendered == "היי Customer!"


def test_first_name_fallback_to_customer():
    """Test that first_name falls back to 'Customer' when no name is available"""
    lead = MockLead(phone_e164="+972501234567")
    business = MockBusiness(name="Test Business")
    
    template = "שלום {first_name}"
    rendered = scheduled_messages_service.render_message_template(
        template, lead, business,
        status_name="new",
        status_label="חדש"
    )
    
    assert rendered == "שלום Customer"
