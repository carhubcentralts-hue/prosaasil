#!/usr/bin/env python3
"""
Test for Lead phone attribute fix in CallContext

This test verifies that:
1. CallContext correctly accesses lead.phone_e164 instead of lead.phone
2. CallContext handles None lead gracefully
3. lead_phone attribute is properly populated
"""

import unittest
from unittest.mock import Mock


class TestLeadPhoneFix(unittest.TestCase):
    """Test that CallContext properly uses lead.phone_e164"""
    
    def test_callcontext_with_lead_phone_e164(self):
        """Verify that CallContext accesses lead.phone_e164 correctly"""
        # Import CallContext from media_ws_ai
        from server.media_ws_ai import CallContext
        
        # Create mock objects
        mock_call_log = Mock()
        mock_call_log.call_sid = "CA123456"
        mock_call_log.id = 1
        mock_call_log.lead_id = 100
        mock_call_log.customer_name = "Test Customer"
        
        mock_lead = Mock()
        mock_lead.full_name = "John Doe"
        mock_lead.first_name = "John"
        mock_lead.phone_e164 = "+972501234567"  # This is the correct attribute
        mock_lead.customer_name = "John"
        mock_lead.gender = "male"
        mock_lead.tenant_id = 1
        
        mock_business = Mock()
        mock_business.id = 1
        mock_business.name = "Test Business"
        
        mock_settings = Mock()
        mock_settings.opening_hours_json = None
        mock_settings.working_hours = "08:00-18:00"
        
        # Create CallContext - this should NOT raise AttributeError
        try:
            ctx = CallContext(mock_call_log, mock_lead, mock_business, mock_settings)
            
            # Verify lead_phone is correctly populated
            self.assertEqual(ctx.lead_phone, "+972501234567")
            self.assertEqual(ctx.lead_full_name, "John Doe")
            self.assertEqual(ctx.lead_first_name, "John")
            self.assertEqual(ctx.lead_gender, "male")
            self.assertEqual(ctx.lead_tenant_id, 1)
            
            print("✅ CallContext created successfully with lead.phone_e164")
            
        except AttributeError as e:
            self.fail(f"CallContext raised AttributeError: {e}")
    
    def test_callcontext_with_none_lead(self):
        """Verify that CallContext handles None lead gracefully"""
        from server.media_ws_ai import CallContext
        
        # Create mock objects (lead is None)
        mock_call_log = Mock()
        mock_call_log.call_sid = "CA123456"
        mock_call_log.id = 1
        mock_call_log.lead_id = None
        mock_call_log.customer_name = None
        
        mock_business = Mock()
        mock_business.id = 1
        mock_business.name = "Test Business"
        
        mock_settings = Mock()
        mock_settings.opening_hours_json = None
        mock_settings.working_hours = "08:00-18:00"
        
        # Create CallContext with None lead
        try:
            ctx = CallContext(mock_call_log, None, mock_business, mock_settings)
            
            # Verify lead attributes are None
            self.assertIsNone(ctx.lead_phone)
            self.assertIsNone(ctx.lead_full_name)
            self.assertIsNone(ctx.lead_first_name)
            self.assertIsNone(ctx.lead_gender)
            
            print("✅ CallContext handles None lead correctly")
            
        except AttributeError as e:
            self.fail(f"CallContext raised AttributeError with None lead: {e}")
    
    def test_callcontext_with_lead_without_phone(self):
        """Verify that CallContext handles lead without phone_e164 gracefully"""
        from server.media_ws_ai import CallContext
        
        # Create mock objects
        mock_call_log = Mock()
        mock_call_log.call_sid = "CA123456"
        mock_call_log.id = 1
        mock_call_log.lead_id = 100
        mock_call_log.customer_name = "Test Customer"
        
        mock_lead = Mock()
        mock_lead.full_name = "Jane Doe"
        mock_lead.first_name = "Jane"
        mock_lead.phone_e164 = None  # No phone
        mock_lead.customer_name = "Jane"
        mock_lead.gender = "female"
        mock_lead.tenant_id = 1
        
        mock_business = Mock()
        mock_business.id = 1
        mock_business.name = "Test Business"
        
        mock_settings = Mock()
        mock_settings.opening_hours_json = None
        mock_settings.working_hours = "08:00-18:00"
        
        # Create CallContext
        try:
            ctx = CallContext(mock_call_log, mock_lead, mock_business, mock_settings)
            
            # Verify lead_phone is None
            self.assertIsNone(ctx.lead_phone)
            self.assertEqual(ctx.lead_full_name, "Jane Doe")
            
            print("✅ CallContext handles lead without phone correctly")
            
        except AttributeError as e:
            self.fail(f"CallContext raised AttributeError: {e}")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
