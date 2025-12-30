#!/usr/bin/env python3
"""
Test for CallContext customer_name AttributeError Fix

This test verifies that:
1. CallContext.__init__ handles Lead objects without customer_name attribute
2. The defensive getattr approach correctly falls back to first_name or full_name
3. No AttributeError is raised when accessing lead fields
"""

import unittest
from unittest.mock import Mock, MagicMock


class TestCallContextCustomerNameFix(unittest.TestCase):
    """Test that CallContext doesn't crash on lead.customer_name"""
    
    def setUp(self):
        """Set up test mocks"""
        # Import CallContext
        from server.media_ws_ai import CallContext
        self.CallContext = CallContext
    
    def test_callcontext_with_lead_first_name(self):
        """Test CallContext with lead that has first_name"""
        # Create mock objects
        call_log = Mock()
        call_log.call_sid = "CA123"
        call_log.id = 1
        call_log.lead_id = 100
        call_log.customer_name = None
        
        lead = Mock()
        lead.first_name = "יוסי"
        lead.last_name = "כהן"
        lead.full_name = "יוסי כהן"
        lead.phone_e164 = "+972501234567"
        lead.gender = "male"
        lead.tenant_id = 1
        # Note: NO customer_name attribute - this is what caused the bug
        
        business = Mock()
        business.id = 1
        business.name = "Test Business"
        
        settings = Mock()
        settings.opening_hours_json = None
        settings.working_hours = "09:00-17:00"
        
        # This should NOT raise AttributeError
        context = self.CallContext(call_log, lead, business, settings)
        
        # Verify attributes are set correctly
        self.assertEqual(context.lead_first_name, "יוסי")
        self.assertEqual(context.lead_full_name, "יוסי כהן")
        self.assertEqual(context.lead_customer_name, "יוסי")  # Should use first_name
        self.assertEqual(context.lead_phone, "+972501234567")
        self.assertEqual(context.lead_gender, "male")
    
    def test_callcontext_with_lead_only_full_name(self):
        """Test CallContext with lead that only has full_name (no first_name)"""
        call_log = Mock()
        call_log.call_sid = "CA456"
        call_log.id = 2
        call_log.lead_id = 200
        call_log.customer_name = None
        
        lead = Mock()
        lead.first_name = None  # No first name
        lead.last_name = None
        lead.full_name = "דוד לוי"
        lead.phone_e164 = "+972507654321"
        lead.gender = None
        lead.tenant_id = 1
        
        business = Mock()
        business.id = 1
        business.name = "Test Business"
        
        settings = Mock()
        settings.opening_hours_json = None
        settings.working_hours = "09:00-17:00"
        
        # This should NOT raise AttributeError
        context = self.CallContext(call_log, lead, business, settings)
        
        # Verify lead_customer_name falls back to full_name
        self.assertEqual(context.lead_customer_name, "דוד לוי")
        self.assertIsNone(context.lead_first_name)
    
    def test_callcontext_with_no_lead(self):
        """Test CallContext with no lead (None)"""
        call_log = Mock()
        call_log.call_sid = "CA789"
        call_log.id = 3
        call_log.lead_id = None
        call_log.customer_name = "אורח"
        
        business = Mock()
        business.id = 1
        business.name = "Test Business"
        
        settings = Mock()
        settings.opening_hours_json = None
        settings.working_hours = "09:00-17:00"
        
        # This should NOT raise AttributeError
        context = self.CallContext(call_log, lead=None, business=business, settings=settings)
        
        # Verify lead attributes are None when no lead
        self.assertIsNone(context.lead_customer_name)
        self.assertIsNone(context.lead_first_name)
        self.assertIsNone(context.lead_full_name)
        self.assertEqual(context.customer_name, "אורח")  # From call_log
    
    def test_callcontext_get_customer_name_method(self):
        """Test get_customer_name() method returns correct fallback"""
        call_log = Mock()
        call_log.call_sid = "CA999"
        call_log.id = 4
        call_log.lead_id = 400
        call_log.customer_name = None
        
        lead = Mock()
        lead.first_name = "משה"
        lead.last_name = None
        lead.full_name = "משה"
        lead.phone_e164 = "+972501111111"
        lead.gender = None
        lead.tenant_id = 1
        
        business = Mock()
        business.id = 1
        business.name = "Test Business"
        
        settings = Mock()
        settings.opening_hours_json = None
        settings.working_hours = "09:00-17:00"
        
        context = self.CallContext(call_log, lead, business, settings)
        
        # Test get_customer_name() method
        customer_name = context.get_customer_name()
        self.assertEqual(customer_name, "משה")
    
    def test_no_attributeerror_on_lead_without_customer_name(self):
        """
        Main test: Verify no AttributeError when Lead doesn't have customer_name
        This is the core bug we're fixing
        """
        call_log = Mock()
        call_log.call_sid = "CA_MAIN"
        call_log.id = 999
        call_log.lead_id = 999
        call_log.customer_name = None
        
        # Create a more realistic Lead mock (like SQLAlchemy model)
        lead = Mock(spec=['first_name', 'last_name', 'full_name', 'phone_e164', 'gender', 'tenant_id'])
        lead.first_name = "רחל"
        lead.last_name = "אברהם"
        lead.full_name = "רחל אברהם"
        lead.phone_e164 = "+972502222222"
        lead.gender = "female"
        lead.tenant_id = 1
        # Note: customer_name is NOT in spec - accessing it would raise AttributeError
        
        business = Mock()
        business.id = 1
        business.name = "Test Business"
        
        settings = Mock()
        settings.opening_hours_json = None
        settings.working_hours = "09:00-17:00"
        
        # This is the critical test - should NOT raise AttributeError
        try:
            context = self.CallContext(call_log, lead, business, settings)
            # If we get here, the fix works!
            self.assertIsNotNone(context.lead_customer_name)
            self.assertEqual(context.lead_customer_name, "רחל")
        except AttributeError as e:
            self.fail(f"CallContext raised AttributeError: {e}")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
