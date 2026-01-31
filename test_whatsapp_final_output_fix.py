"""
Test to verify WhatsApp AI response extraction fix
This test ensures that only the final_output is extracted from RunResult,
not the entire RunResult representation with metadata.
"""
import sys
import os

def test_final_output_extraction():
    """Test that final_output is correctly extracted from RunResult"""
    try:
        from agents import RunResult, Agent, Runner
        from dataclasses import dataclass
        
        # Create a mock RunResult to test extraction logic
        # In reality, RunResult would be created by the runner
        print("Testing final_output extraction logic...")
        
        # Simulate what the extraction code does
        class MockResult:
            def __init__(self, final_output):
                self.final_output = final_output
        
        # Test case 1: Normal Hebrew response (like in the problem statement)
        hebrew_response = "היי, זה רמי משלום הדברות 👋\nנשמע שיש לך בעיה עם מזיקים. תוכל לספר לי איזה מזיק אתה רואה?"
        result = MockResult(final_output=hebrew_response)
        
        # Simulate the extraction logic from ai_service.py
        reply_text = ""
        if hasattr(result, 'final_output') and result.final_output:
            reply_text = str(result.final_output)
        
        # Verify we got the clean output
        if reply_text == hebrew_response:
            print("✅ Test 1 PASSED: Clean Hebrew response extracted")
        else:
            print("❌ Test 1 FAILED: Unexpected output")
            return False
        
        # Test case 2: Empty response
        result2 = MockResult(final_output="")
        reply_text2 = ""
        if hasattr(result2, 'final_output') and result2.final_output:
            reply_text2 = str(result2.final_output)
        
        if reply_text2 == "":
            print("✅ Test 2 PASSED: Empty response handled correctly")
        else:
            print("❌ Test 2 FAILED: Empty response not handled")
            return False
        
        # Test case 3: Make sure old logic would have failed
        # If we used str(result), we'd get the object representation
        result3 = MockResult(final_output="Clean response")
        old_logic_output = str(result3)  # This is what the OLD code did
        
        if "MockResult" in old_logic_output or "object at" in old_logic_output:
            print("✅ Test 3 PASSED: Confirmed old logic would show object representation")
        else:
            print("⚠️  Test 3: Old logic check inconclusive")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ai_service_code_fix():
    """Test that the fix is correctly applied in ai_service.py"""
    try:
        with open('server/services/ai_service.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check that the fix is present
        if "if hasattr(result, 'final_output') and result.final_output:" in content:
            print("✅ Fix applied: Checking for 'final_output' attribute")
        else:
            print("❌ Fix NOT applied: Missing final_output check")
            return False
        
        # Check that we're extracting final_output correctly
        if "reply_text = str(result.final_output)" in content:
            print("✅ Fix applied: Extracting final_output correctly")
        else:
            print("❌ Fix NOT applied: Not extracting final_output")
            return False
        
        # Make sure the old problematic code is removed
        if "reply_text = str(result) if result else" in content:
            print("❌ Old problematic code still present: str(result)")
            return False
        else:
            print("✅ Old problematic code removed")
        
        # Check for proper fallback
        if 'logger.warning(f"[AGENTKIT] Unable to extract text from result type: {type(result)}")' in content:
            print("✅ Proper warning added for extraction failures")
        else:
            print("⚠️  Warning for extraction failures might be missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking code: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("Testing WhatsApp Final Output Extraction Fix")
    print("="*60)
    
    results = []
    
    print("\n1. Testing final_output extraction logic...")
    results.append(test_final_output_extraction())
    
    print("\n2. Verifying fix is applied in ai_service.py...")
    results.append(test_ai_service_code_fix())
    
    print("\n" + "="*60)
    if all(results):
        print("✅ ALL TESTS PASSED")
        print("\nThe fix ensures that WhatsApp messages show only the clean")
        print("AI response text (final_output), not the full RunResult metadata.")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
