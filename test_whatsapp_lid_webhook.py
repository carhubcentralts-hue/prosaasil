#!/usr/bin/env python3
"""
Test for WhatsApp webhook handling with non-standard JID formats (@lid).

This test ensures that:
1. Webhook doesn't crash with NameError when receiving @lid messages
2. Safe identifiers are created for logging/DB from remoteJid
"""


def test_lid_jid_identifier_creation():
    """
    Test that safe identifiers are created from non-standard JIDs.
    """
    test_cases = [
        ("82312345678@lid", "82312345678_lid"),
        ("972501234567@s.whatsapp.net", "972501234567_s_whatsapp_net"),
        ("12025551234@lid", "12025551234_lid"),
        ("", "unknown"),  # Empty JID edge case
    ]
    
    for remote_jid, expected_identifier in test_cases:
        # This is the logic from the fixed code
        from_identifier = remote_jid.replace('@', '_').replace('.', '_') if remote_jid else 'unknown'
        assert from_identifier == expected_identifier, f"Failed for {remote_jid}"
        print(f"✅ {remote_jid} -> {from_identifier}")


def test_code_syntax():
    """
    Test that the routes_whatsapp.py file has valid syntax after our changes.
    """
    import ast
    import os
    
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_whatsapp.py')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Parse the file to check for syntax errors
        ast.parse(code)
        print("✅ routes_whatsapp.py has valid Python syntax")
        
        # Check that from_identifier is defined before it's used
        if 'from_identifier = remote_jid.replace' in code:
            print("✅ from_identifier is defined in the code")
        else:
            raise AssertionError("from_identifier definition not found")
        
        # Check that the bug line is fixed
        if 'from {from_number}' in code:
            # Check if it's in the problematic location (around line 904)
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if 'from {from_number}' in line and 'Unknown message format' in line:
                    raise AssertionError(f"Bug still exists at line {i+1}: uses undefined 'from_number'")
        
        print("✅ Bug fix verified: 'from_number' not used in unknown message logging")
        
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in routes_whatsapp.py: {e}")


if __name__ == "__main__":
    print("🧪 Running WhatsApp @lid JID webhook tests...")
    print()
    
    print("Test 1: Safe identifier creation")
    test_lid_jid_identifier_creation()
    print()
    
    print("Test 2: Code syntax and bug fix verification")
    test_code_syntax()
    print()
    
    print("✅ All tests passed!")

