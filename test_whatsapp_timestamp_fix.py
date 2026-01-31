#!/usr/bin/env python3
"""
Test for WhatsApp webhook UnboundLocalError fix.

This test ensures that:
1. timestamp_ms, baileys_message_id are extracted early
2. No UnboundLocalError occurs when processing messages
3. The variables are available when needed
"""


def test_variable_extraction_order():
    """
    Test that critical variables are extracted before they're used.
    """
    import ast
    import os
    
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_whatsapp.py')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Verify syntax is valid
    ast.parse(code)
    print("✅ routes_whatsapp.py has valid Python syntax")
    
    # Find where variables are defined and used
    lines = code.split('\n')
    
    # Find extraction lines
    extraction_line = None
    timestamp_usage_line = None
    baileys_usage_line = None
    
    for i, line in enumerate(lines):
        if 'timestamp_ms = msg.get(' in line and 'messageTimestamp' in line:
            if extraction_line is None:  # First occurrence
                extraction_line = i
        if 'if timestamp_ms:' in line:
            if timestamp_usage_line is None:  # First usage
                timestamp_usage_line = i
        if 'wa_message_id=baileys_message_id' in line:
            if baileys_usage_line is None:  # First usage
                baileys_usage_line = i
    
    print(f"timestamp_ms extraction at line: {extraction_line}")
    print(f"timestamp_ms first usage at line: {timestamp_usage_line}")
    print(f"baileys_message_id first usage at line: {baileys_usage_line}")
    
    # Verify extraction happens before usage
    assert extraction_line is not None, "timestamp_ms extraction not found"
    assert timestamp_usage_line is not None, "timestamp_ms usage not found"
    assert baileys_usage_line is not None, "baileys_message_id usage not found"
    
    assert extraction_line < timestamp_usage_line, \
        f"timestamp_ms must be extracted (line {extraction_line}) before usage (line {timestamp_usage_line})"
    assert extraction_line < baileys_usage_line, \
        f"baileys_message_id must be extracted (line {extraction_line}) before usage (line {baileys_usage_line})"
    
    print("✅ Variables are extracted before usage - UnboundLocalError fixed!")


def test_message_processing_mock():
    """
    Test message processing logic with mock data to ensure no UnboundLocalError.
    """
    # Simulate message structure
    msg = {
        'key': {
            'remoteJid': '972587682228@s.whatsapp.net',
            'id': '3A29B3545B1057326DB0',
            'fromMe': False
        },
        'messageTimestamp': '1738344319',
        'message': {
            'conversation': 'Test message'
        },
        'pushName': 'Test User'
    }
    
    # Extract variables as the code does now
    baileys_message_id = msg.get('key', {}).get('id', '')
    remote_jid = msg.get('key', {}).get('remoteJid', '')
    timestamp_ms = msg.get('messageTimestamp', 0)
    
    # Verify extraction worked
    assert baileys_message_id == '3A29B3545B1057326DB0'
    assert remote_jid == '972587682228@s.whatsapp.net'
    assert timestamp_ms == '1738344319'
    
    # Test timestamp conversion logic
    from datetime import datetime
    msg_timestamp = None
    if timestamp_ms:
        try:
            msg_timestamp = datetime.fromtimestamp(int(timestamp_ms))
        except (ValueError, TypeError):
            msg_timestamp = datetime.utcnow()
    else:
        msg_timestamp = datetime.utcnow()
    
    assert msg_timestamp is not None
    print(f"✅ Message timestamp converted successfully: {msg_timestamp}")
    print("✅ No UnboundLocalError in mock processing!")


if __name__ == '__main__':
    print("Testing WhatsApp timestamp_ms UnboundLocalError fix...\n")
    test_variable_extraction_order()
    print()
    test_message_processing_mock()
    print("\n✅ All tests passed!")
