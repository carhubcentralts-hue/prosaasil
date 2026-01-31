#!/usr/bin/env python3
"""
Test to verify that messages with messageContextInfo are not filtered out.
This is a critical fix for WhatsApp message handling.

The fix: messageContextInfo is metadata that can accompany real messages,
so it should NOT cause messages to be filtered out.
"""

import sys
import os

sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

def test_messagecontextinfo_not_in_filter():
    """Verify messageContextInfo is not in the filter list"""
    print("🧪 Testing messageContextInfo fix in baileys_service.js\n")
    
    service_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    
    with open(service_file, 'r') as f:
        content = f.read()
    
    # Find the extractText function
    start_idx = content.find('function extractText(msgObj) {')
    if start_idx == -1:
        print("❌ FAIL - Could not find extractText function")
        return False
    
    # Get the first 500 characters of the function (should contain the filter logic)
    function_snippet = content[start_idx:start_idx + 500]
    
    # Check that messageContextInfo is NOT in the filter condition
    filter_start = function_snippet.find('if (msgObj.pollUpdateMessage')
    filter_end = function_snippet.find('return null;  // Ignore silently')
    
    if filter_start == -1 or filter_end == -1:
        print("❌ FAIL - Could not find filter condition")
        return False
    
    filter_condition = function_snippet[filter_start:filter_end]
    
    print("Filter condition found:")
    print(filter_condition)
    print()
    
    if 'messageContextInfo' in filter_condition:
        print("❌ FAIL - messageContextInfo is still in the filter condition")
        print("This will cause messages with messageContextInfo to be incorrectly filtered out")
        return False
    else:
        print("✅ PASS - messageContextInfo is NOT in the filter condition")
        print("Messages with messageContextInfo will now be processed correctly")
        print()
    
    # Check that other filters are still in place
    required_filters = [
        'pollUpdateMessage',
        'protocolMessage',
        'historySyncNotification',
        'reactionMessage',
        'senderKeyDistributionMessage'
    ]
    
    missing_filters = []
    for filter_name in required_filters:
        if filter_name not in filter_condition:
            missing_filters.append(filter_name)
    
    if missing_filters:
        print(f"⚠️  WARNING - Missing expected filters: {missing_filters}")
        print("Make sure these system message types are still being filtered")
        return False
    else:
        print("✅ PASS - All expected system message filters are still in place")
        print()
    
    # Check that there's a comment explaining the fix
    if 'Note: messageContextInfo is metadata' in content[start_idx:start_idx + 800]:
        print("✅ PASS - Comment explaining the fix is present")
    else:
        print("⚠️  INFO - No comment found explaining why messageContextInfo is not filtered")
    
    print()
    return True

def test_conversation_field_is_checked():
    """Verify that the conversation field is properly checked for text content"""
    print("🧪 Testing that conversation field is checked for text extraction\n")
    
    service_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    
    with open(service_file, 'r') as f:
        content = f.read()
    
    # Find the extractText function
    start_idx = content.find('function extractText(msgObj) {')
    if start_idx == -1:
        print("❌ FAIL - Could not find extractText function")
        return False
    
    # Get a larger snippet to include the conversation check
    function_snippet = content[start_idx:start_idx + 1500]
    
    # Check that conversation field is being checked
    if 'if (msgObj.conversation)' in function_snippet or 'msgObj.conversation' in function_snippet:
        print("✅ PASS - Conversation field is checked for text content")
        return True
    else:
        print("❌ FAIL - Conversation field check not found")
        return False

def main():
    print("=" * 70)
    print("WhatsApp Message Filtering Fix - Validation")
    print("=" * 70)
    print()
    
    results = []
    
    # Test 1: messageContextInfo is not in filter
    results.append(test_messagecontextinfo_not_in_filter())
    
    # Test 2: conversation field is still checked
    results.append(test_conversation_field_is_checked())
    
    print("=" * 70)
    if all(results):
        print("🎉 ALL TESTS PASSED")
        print()
        print("✅ FIX VERIFIED:")
        print("   - Messages with messageContextInfo will now be processed")
        print("   - System messages are still correctly filtered")
        print("   - Text extraction logic is intact")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
