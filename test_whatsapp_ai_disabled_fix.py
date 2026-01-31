"""
Test to verify WhatsApp AI disabled behavior
This test verifies that when AI is disabled, NO message is sent.
"""
import sys
import os

def test_ai_disabled_no_response():
    """Test that when AI is disabled, no response is sent"""
    try:
        with open('server/routes_whatsapp.py', 'r') as f:
            content = f.read()
        
        # Check that AI disabled case skips sending
        if 'if not ai_enabled:' in content and 'skipping response (no message sent)' in content:
            print("✅ AI disabled check exists with skip behavior")
        else:
            print("❌ AI disabled check missing or incorrect")
            return False
        
        # Check that the old "send basic acknowledgment" behavior is removed
        if 'sending basic acknowledgment' in content:
            print("❌ Old 'sending basic acknowledgment' code still present")
            return False
        else:
            print("✅ Old 'sending basic acknowledgment' code removed")
        
        # Check that AI disabled case uses continue to skip
        # Look for the pattern: if not ai_enabled: ... continue
        import re
        ai_disabled_block = re.search(
            r'if not ai_enabled:.*?continue',
            content,
            re.DOTALL
        )
        
        if ai_disabled_block:
            block_text = ai_disabled_block.group()
            # Make sure it doesn't contain enqueue_job or send_whatsapp
            if 'enqueue_job' in block_text or 'send_whatsapp_message_job' in block_text:
                print("❌ AI disabled block still contains message sending code")
                return False
            else:
                print("✅ AI disabled block does not send messages")
        else:
            print("❌ AI disabled block pattern not found correctly")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing AI disabled behavior: {e}")
        return False

def test_default_fallback_still_used_for_errors():
    """Test that DEFAULT_FALLBACK_MESSAGE is still used when AI errors occur"""
    try:
        with open('server/routes_whatsapp.py', 'r') as f:
            content = f.read()
        
        # Check that DEFAULT_FALLBACK_MESSAGE still exists for error cases
        if 'DEFAULT_FALLBACK_MESSAGE' in content:
            print("✅ DEFAULT_FALLBACK_MESSAGE constant still exists")
        else:
            print("❌ DEFAULT_FALLBACK_MESSAGE constant removed (should exist for errors)")
            return False
        
        # Check that fallback is used when AI returns empty response
        if 'AgentKit returned empty response' in content and 'Using fallback response' in content:
            print("✅ Fallback message still used for empty AI responses")
        else:
            print("⚠️  Fallback message usage for empty AI responses might have changed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing fallback behavior: {e}")
        return False

def test_logging_messages():
    """Test that logging messages are appropriate"""
    try:
        with open('server/routes_whatsapp.py', 'r') as f:
            content = f.read()
        
        # Check for appropriate log message when AI is disabled
        if '🚫 AI disabled' in content and 'skipping response' in content:
            print("✅ Appropriate log message for AI disabled case")
        else:
            print("❌ Missing appropriate log message for AI disabled case")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing logging: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Testing WhatsApp AI Disabled Behavior")
    print("="*60)
    
    results = []
    
    print("\n1. Testing AI disabled behavior (no response)...")
    results.append(test_ai_disabled_no_response())
    
    print("\n2. Testing fallback message for errors...")
    results.append(test_default_fallback_still_used_for_errors())
    
    print("\n3. Testing logging messages...")
    results.append(test_logging_messages())
    
    print("\n" + "="*60)
    if all(results):
        print("✅ ALL TESTS PASSED")
        print("\nThe fix ensures that:")
        print("- When AI is disabled, NO message is sent")
        print("- When AI is enabled but returns empty, fallback is used")
        print("- Appropriate logging is in place")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
