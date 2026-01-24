"""
Test for Prompt Builder Chat backend routes
Verifies that the system prompt and endpoints are properly configured
"""
import sys
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

def test_system_prompt_defined():
    """Test that the system prompt is properly defined"""
    from server.routes_prompt_builder_chat import PROMPT_BUILDER_CHAT_SYSTEM
    
    # Verify system prompt is not empty
    assert PROMPT_BUILDER_CHAT_SYSTEM, "System prompt should not be empty"
    
    # Verify key elements are present
    assert "מחולל פרומפטים" in PROMPT_BUILDER_CHAT_SYSTEM, "Should mention prompt generation"
    assert "שיחה חופשית" in PROMPT_BUILDER_CHAT_SYSTEM, "Should mention free conversation"
    assert "חוסן ויציבות" in PROMPT_BUILDER_CHAT_SYSTEM, "Should mention resilience"
    assert "אין כישלון" in PROMPT_BUILDER_CHAT_SYSTEM, "Should mention no failure"
    assert "תמיד יש תוצאה" in PROMPT_BUILDER_CHAT_SYSTEM, "Should mention always produce result"
    
    print("✅ System prompt is properly defined with all key elements")
    return True

def test_blueprint_registration():
    """Test that blueprint is properly configured"""
    from server.routes_prompt_builder_chat import prompt_builder_chat_bp
    
    # Verify blueprint exists
    assert prompt_builder_chat_bp, "Blueprint should exist"
    assert prompt_builder_chat_bp.name == 'prompt_builder_chat', "Blueprint should have correct name"
    
    # Count registered routes
    route_count = len(list(prompt_builder_chat_bp.deferred_functions))
    print(f"✅ Blueprint has {route_count} deferred functions registered")
    
    return True

def test_max_conversation_history():
    """Test that conversation history limit is defined"""
    from server.routes_prompt_builder_chat import MAX_CONVERSATION_HISTORY
    
    assert MAX_CONVERSATION_HISTORY > 0, "Should have positive conversation history limit"
    assert MAX_CONVERSATION_HISTORY <= 50, "Should have reasonable conversation history limit"
    
    print(f"✅ Conversation history limit is set to {MAX_CONVERSATION_HISTORY}")
    return True

if __name__ == "__main__":
    print("Testing Prompt Builder Chat Backend...")
    print()
    
    try:
        test_system_prompt_defined()
        test_blueprint_registration()
        test_max_conversation_history()
        
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
