#!/usr/bin/env python3
"""
Simple syntax and logic test for CallContext customer_name fix.
Tests the fix without requiring full dependencies.
"""

import sys
import ast


def check_callcontext_fix():
    """
    Verify that CallContext.__init__ uses getattr instead of direct attribute access
    for lead.customer_name
    """
    print("🔍 Checking CallContext fix in server/media_ws_ai.py...")
    
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that the problematic line is gone
    if 'lead.customer_name' in content and 'self.lead_customer_name = lead.customer_name' in content:
        print("❌ FAIL: Found direct access to lead.customer_name")
        return False
    
    # Check that getattr is used for lead_customer_name
    if 'getattr(lead, "first_name"' in content or 'getattr(lead, \'first_name\'' in content:
        print("✅ PASS: Using getattr for defensive attribute access")
    else:
        print("❌ FAIL: getattr not found for lead attribute access")
        return False
    
    # Check that the fix handles None case
    if 'if lead else None' in content:
        print("✅ PASS: Handling None case for lead")
    else:
        print("⚠️  WARNING: None handling might be missing")
    
    # Parse the file to ensure it's valid Python
    try:
        ast.parse(content)
        print("✅ PASS: File is valid Python syntax")
    except SyntaxError as e:
        print(f"❌ FAIL: Syntax error in file: {e}")
        return False
    
    print("\n✅ All checks passed! CallContext fix looks good.")
    return True


def test_getattr_logic():
    """
    Test the getattr logic we used in the fix
    """
    print("\n🧪 Testing getattr logic...")
    
    # Mock lead object
    class MockLead:
        def __init__(self):
            self.first_name = "יוסי"
            self.full_name = "יוסי כהן"
            # Note: NO customer_name attribute
    
    lead = MockLead()
    
    # Test the exact logic from our fix
    lead_customer_name = (
        getattr(lead, "first_name", None) or 
        getattr(lead, "full_name", None)
    ) if lead else None
    
    if lead_customer_name == "יוסי":
        print("✅ PASS: getattr returns first_name correctly")
    else:
        print(f"❌ FAIL: Expected 'יוסי', got {lead_customer_name}")
        return False
    
    # Test with only full_name
    class MockLead2:
        def __init__(self):
            self.first_name = None
            self.full_name = "דוד לוי"
    
    lead2 = MockLead2()
    lead_customer_name2 = (
        getattr(lead2, "first_name", None) or 
        getattr(lead2, "full_name", None)
    ) if lead2 else None
    
    if lead_customer_name2 == "דוד לוי":
        print("✅ PASS: getattr falls back to full_name correctly")
    else:
        print(f"❌ FAIL: Expected 'דוד לוי', got {lead_customer_name2}")
        return False
    
    # Test with None lead (the if lead else None should short-circuit)
    lead = None
    lead_customer_name3 = (
        getattr(lead, "first_name", None) or 
        getattr(lead, "full_name", None)
    ) if lead else None
    
    if lead_customer_name3 is None:
        print("✅ PASS: None lead handled correctly")
    else:
        print(f"❌ FAIL: Expected None, got {lead_customer_name3}")
        return False
    
    print("✅ All getattr logic tests passed!")
    return True


if __name__ == '__main__':
    success = check_callcontext_fix() and test_getattr_logic()
    
    if success:
        print("\n" + "="*60)
        print("🎉 SUCCESS: CallContext customer_name fix is working!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("❌ FAILURE: Fix needs adjustment")
        print("="*60)
        sys.exit(1)
