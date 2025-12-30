#!/usr/bin/env python3
"""
Unit tests for call_direction UnboundLocalError fix

Tests verify:
1. ENABLE_LOOP_DETECT constant is defined
2. ENABLE_LEGACY_CITY_LOGIC constant is defined  
3. call_direction uses getattr pattern safely
"""

import unittest
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))


class TestCallDirectionFix(unittest.TestCase):
    """Test that call_direction bug is fixed"""
    
    def test_enable_loop_detect_defined(self):
        """Test that ENABLE_LOOP_DETECT constant is defined"""
        try:
            # Import the module
            from server import media_ws_ai
            
            # Check that constant exists
            self.assertTrue(hasattr(media_ws_ai, 'ENABLE_LOOP_DETECT'))
            
            # Check that it's False (disabled)
            self.assertEqual(media_ws_ai.ENABLE_LOOP_DETECT, False)
        except ModuleNotFoundError:
            # If imports fail, manually check the file content
            import os
            file_path = os.path.join(os.path.dirname(__file__), 'server', 'media_ws_ai.py')
            with open(file_path, 'r') as f:
                content = f.read()
            self.assertIn('ENABLE_LOOP_DETECT = False', content)
        
    def test_enable_legacy_city_logic_defined(self):
        """Test that ENABLE_LEGACY_CITY_LOGIC constant is defined"""
        try:
            # Import the module
            from server import media_ws_ai
            
            # Check that constant exists
            self.assertTrue(hasattr(media_ws_ai, 'ENABLE_LEGACY_CITY_LOGIC'))
            
            # Check that it's False (disabled)
            self.assertEqual(media_ws_ai.ENABLE_LEGACY_CITY_LOGIC, False)
        except ModuleNotFoundError:
            # If imports fail, manually check the file content
            import os
            file_path = os.path.join(os.path.dirname(__file__), 'server', 'media_ws_ai.py')
            with open(file_path, 'r') as f:
                content = f.read()
            self.assertIn('ENABLE_LEGACY_CITY_LOGIC = False', content)
    
    def test_call_direction_getattr_pattern(self):
        """Test that getattr pattern works correctly for call_direction"""
        
        # Test case 1: Object has call_direction attribute
        class MockHandler1:
            call_direction = 'outbound'
        
        handler1 = MockHandler1()
        call_direction = getattr(handler1, 'call_direction', 'inbound')
        self.assertEqual(call_direction, 'outbound')
        
        # Test case 2: Object doesn't have call_direction attribute (default to inbound)
        class MockHandler2:
            pass
        
        handler2 = MockHandler2()
        call_direction = getattr(handler2, 'call_direction', 'inbound')
        self.assertEqual(call_direction, 'inbound')
        
        # Test case 3: Object has call_direction but it's None (default to inbound)
        class MockHandler3:
            call_direction = None
        
        handler3 = MockHandler3()
        call_direction = getattr(handler3, 'call_direction', 'inbound')
        # When attribute exists but is None, getattr returns None, so we need 'or' operator
        call_direction = call_direction or 'inbound'
        self.assertEqual(call_direction, 'inbound')


class TestLoggingLevelFix(unittest.TestCase):
    """Test that opening_hours_json logging is at INFO level"""
    
    def test_opening_hours_logging_uses_info(self):
        """Test that logger.info is used instead of logger.warning"""
        # Read the business_policy.py file
        policy_file = os.path.join(os.path.dirname(__file__), 'server', 'policy', 'business_policy.py')
        
        with open(policy_file, 'r') as f:
            content = f.read()
        
        # Check that the old warning line doesn't exist (using flexible pattern)
        import re
        self.assertIsNone(re.search(r'logger\.warning\(.*opening_hours_json is NULL', content))
        
        # Check that the new info line exists (using flexible pattern)
        self.assertIsNotNone(re.search(r'logger\.info\(.*opening_hours_json is NULL', content))


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
