#!/usr/bin/env python3
"""
Test for BulkCall Request Context Fix

This test verifies that:
1. create_outbound_call() now accepts host parameter instead of using request context
2. Worker functions can call create_outbound_call() outside of request context
3. No request context dependencies remain in the call creation flow
"""

import unittest
from unittest.mock import Mock, patch, MagicMock


class TestBulkCallContextFix(unittest.TestCase):
    """Test that BulkCall worker doesn't depend on request context"""
    
    def test_create_outbound_call_signature_has_host_param(self):
        """Verify that create_outbound_call() accepts host as parameter"""
        from server.services.twilio_outbound_service import create_outbound_call
        import inspect
        
        # Get function signature
        sig = inspect.signature(create_outbound_call)
        params = list(sig.parameters.keys())
        
        # Verify host is a parameter
        self.assertIn('host', params, "create_outbound_call() must accept 'host' parameter")
        
        # Verify required parameters exist
        required_params = ['to_phone', 'from_phone', 'business_id', 'host']
        for param in required_params:
            self.assertIn(param, params, f"create_outbound_call() must accept '{param}' parameter")
    
    def test_no_request_import_in_service(self):
        """Verify that twilio_outbound_service.py doesn't import request"""
        import server.services.twilio_outbound_service as service_module
        
        # Check if 'request' is in the module's namespace
        # It should NOT be there after our fix
        self.assertFalse(
            hasattr(service_module, 'request'),
            "twilio_outbound_service should not import 'request' from flask"
        )
    
    @patch('server.services.twilio_outbound_service.get_twilio_client')
    @patch('server.services.twilio_outbound_service._check_and_mark_call')
    def test_create_outbound_call_works_without_request_context(self, mock_check, mock_client):
        """Test that create_outbound_call can be called outside request context"""
        from server.services.twilio_outbound_service import create_outbound_call
        
        # Setup mocks
        mock_check.return_value = None  # No duplicate
        mock_twilio_call = Mock()
        mock_twilio_call.sid = "CA1234567890abcdef"
        mock_client.return_value.calls.create.return_value = mock_twilio_call
        
        # Call without request context (this would fail before the fix)
        result = create_outbound_call(
            to_phone="+972501234567",
            from_phone="+972501111111",
            business_id=1,
            host="example.com",  # Now explicitly passed
            lead_id=123
        )
        
        # Verify call succeeded
        self.assertEqual(result['call_sid'], "CA1234567890abcdef")
        self.assertEqual(result['status'], 'initiated')
        self.assertFalse(result['is_duplicate'])
        
        # Verify Twilio client was called with correct webhook URL
        call_args = mock_client.return_value.calls.create.call_args
        self.assertIn('url', call_args.kwargs)
        webhook_url = call_args.kwargs['url']
        
        # Verify webhook URL contains host and business_id
        self.assertIn('example.com', webhook_url)
        self.assertIn('business_id=1', webhook_url)
        self.assertIn('lead_id=123', webhook_url)
    
    def test_all_worker_functions_use_get_public_host(self):
        """Verify worker functions use get_public_host() instead of request.host"""
        import server.routes_outbound as outbound_module
        import inspect
        
        # Get source code of worker functions
        fill_queue_source = inspect.getsource(outbound_module.fill_queue_slots_for_job)
        process_bulk_source = inspect.getsource(outbound_module.process_bulk_call_run)
        
        # Verify they don't use request context
        self.assertNotIn('request.', fill_queue_source, 
                         "fill_queue_slots_for_job should not use request context")
        self.assertNotIn('request.', process_bulk_source,
                         "process_bulk_call_run should not use request context")
        
        # Verify they use get_public_host()
        self.assertIn('get_public_host()', fill_queue_source,
                      "fill_queue_slots_for_job should use get_public_host()")
        self.assertIn('get_public_host()', process_bulk_source,
                      "process_bulk_call_run should use get_public_host()")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
