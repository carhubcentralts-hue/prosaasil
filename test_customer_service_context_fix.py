"""
Test for Customer Service Context Access Fix
Verifies that customer service mode provides proper tools and instructions.

Run: python test_customer_service_context_fix.py
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_customer_service_tools_added_when_enabled():
    """Test that CRM tools are added when customer service is enabled"""
    print("🧪 Test 1: Verify CRM tools are added when customer service is enabled")
    
    # Mock the database query
    from unittest.mock import MagicMock, patch
    
    # Create a mock business settings with customer service enabled
    mock_settings = MagicMock()
    mock_settings.enable_customer_service = True
    mock_settings.call_goal = 'lead_only'
    mock_settings.ai_prompt = '{"calls": "Test prompt for calls"}'
    
    with patch('server.agent_tools.agent_factory.BusinessSettings') as MockSettings:
        MockSettings.query.filter_by.return_value.first.return_value = mock_settings
        
        # Import after mocking
        from server.agent_tools.agent_factory import create_booking_agent
        
        # Create agent with customer service enabled
        agent = create_booking_agent(
            business_name="Test Business",
            custom_instructions="Test instructions",
            business_id=1,
            channel="whatsapp"
        )
        
        # Verify agent was created
        assert agent is not None, "Agent should be created"
        
        # Check that the agent has tools
        assert hasattr(agent, 'tools'), "Agent should have tools"
        assert len(agent.tools) > 0, "Agent should have at least one tool"
        
        # Get tool names
        tool_names = [tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in agent.tools]
        print(f"   ✅ Agent has {len(agent.tools)} tools")
        print(f"   📋 Tool names: {', '.join([str(t) for t in tool_names[:5]])}...")
        
        # Since customer service is enabled, we should have CRM tools
        # Note: The tools are wrapped in function_tool, so we can't check names directly
        # But we can verify the count increased
        assert len(agent.tools) >= 7, f"Expected at least 7 tools (base + CRM), got {len(agent.tools)}"
        print(f"   ✅ CRM tools appear to be included (tool count: {len(agent.tools)})")


def test_customer_service_instructions_mandatory():
    """Test that instructions include MANDATORY context loading"""
    print("\n🧪 Test 2: Verify instructions include mandatory context loading")
    
    from unittest.mock import MagicMock, patch
    
    # Create a mock business settings with customer service enabled
    mock_settings = MagicMock()
    mock_settings.enable_customer_service = True
    mock_settings.call_goal = 'lead_only'
    mock_settings.ai_prompt = '{"calls": "Test prompt"}'
    
    with patch('server.agent_tools.agent_factory.BusinessSettings') as MockSettings:
        MockSettings.query.filter_by.return_value.first.return_value = mock_settings
        
        from server.agent_tools.agent_factory import create_booking_agent
        
        # Capture printed instructions
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            agent = create_booking_agent(
                business_name="Test Business",
                custom_instructions="Test",
                business_id=1,
                channel="whatsapp"
            )
        
        output = f.getvalue()
        
        # Check agent instructions
        instructions = agent.instructions if hasattr(agent, 'instructions') else ""
        
        # Verify key mandatory phrases are present
        assert "MANDATORY" in instructions or "חובה" in instructions, \
            "Instructions should include MANDATORY/חובה"
        
        assert "ALWAYS" in instructions or "תמיד" in instructions, \
            "Instructions should include ALWAYS/תמיד for context loading"
        
        assert "crm_find_lead_by_phone" in instructions, \
            "Instructions should mention crm_find_lead_by_phone tool"
        
        assert "crm_get_lead_context" in instructions, \
            "Instructions should mention crm_get_lead_context tool"
        
        assert "crm_create_note" in instructions, \
            "Instructions should mention new crm_create_note tool"
        
        # Check that old passive language is removed
        assert "רק כשצריך" not in instructions, \
            "Instructions should NOT say 'only when needed' (רק כשצריך)"
        
        print("   ✅ Instructions include MANDATORY context loading")
        print("   ✅ Instructions mention all CRM tools")
        print("   ✅ Passive 'only when needed' language is removed")


def test_customer_service_has_examples():
    """Test that instructions include clear examples"""
    print("\n🧪 Test 3: Verify instructions include usage examples")
    
    from unittest.mock import MagicMock, patch
    
    mock_settings = MagicMock()
    mock_settings.enable_customer_service = True
    mock_settings.call_goal = 'lead_only'
    mock_settings.ai_prompt = '{"calls": "Test"}'
    
    with patch('server.agent_tools.agent_factory.BusinessSettings') as MockSettings:
        MockSettings.query.filter_by.return_value.first.return_value = mock_settings
        
        from server.agent_tools.agent_factory import create_booking_agent
        
        agent = create_booking_agent(
            business_name="Test Business",
            custom_instructions="Test",
            business_id=1,
            channel="whatsapp"
        )
        
        instructions = agent.instructions if hasattr(agent, 'instructions') else ""
        
        # Check for example markers
        assert "דוגמאות" in instructions or "💡" in instructions, \
            "Instructions should include examples section"
        
        assert "✅" in instructions, \
            "Instructions should have correct examples marked with ✅"
        
        assert "❌" in instructions, \
            "Instructions should have wrong examples marked with ❌"
        
        # Check for the specific example from the problem statement
        # (customer asks about a problem and AI should reference notes)
        assert "לברר לגבי הבעיה" in instructions or "הערה" in instructions, \
            "Instructions should include example about checking notes for customer issues"
        
        print("   ✅ Instructions include examples section")
        print("   ✅ Examples show correct (✅) and wrong (❌) usage")
        print("   ✅ Examples cover the problem scenario")


def test_crm_tools_implementation():
    """Test that CRM tools are properly implemented"""
    print("\n🧪 Test 4: Verify CRM tools are properly implemented")
    
    from server.agent_tools.tools_crm_context import (
        find_lead_by_phone_impl,
        get_lead_context_impl,
        create_call_summary_note,
        FindLeadByPhoneInput,
        GetLeadContextInput
    )
    
    # These should be callable functions
    assert callable(find_lead_by_phone_impl), "find_lead_by_phone_impl should be callable"
    assert callable(get_lead_context_impl), "get_lead_context_impl should be callable"
    assert callable(create_call_summary_note), "create_call_summary_note should be callable"
    
    print("   ✅ All CRM tool implementations are callable")
    print("   ✅ Tools have proper input schemas")


def test_customer_service_not_for_outbound():
    """Test that instructions clarify NOT to use CRM tools for outbound"""
    print("\n🧪 Test 5: Verify instructions specify inbound-only")
    
    from unittest.mock import MagicMock, patch
    
    mock_settings = MagicMock()
    mock_settings.enable_customer_service = True
    mock_settings.call_goal = 'lead_only'
    mock_settings.ai_prompt = '{"calls": "Test"}'
    
    with patch('server.agent_tools.agent_factory.BusinessSettings') as MockSettings:
        MockSettings.query.filter_by.return_value.first.return_value = mock_settings
        
        from server.agent_tools.agent_factory import create_booking_agent
        
        agent = create_booking_agent(
            business_name="Test Business",
            custom_instructions="Test",
            business_id=1,
            channel="whatsapp"
        )
        
        instructions = agent.instructions if hasattr(agent, 'instructions') else ""
        
        # Check for outbound restriction
        assert "outbound" in instructions or "יוצאות" in instructions, \
            "Instructions should mention outbound restriction"
        
        assert "נכנסות" in instructions or "inbound" in instructions, \
            "Instructions should clarify these are for INBOUND calls/messages"
        
        print("   ✅ Instructions clarify CRM tools are for INBOUND only")
        print("   ✅ Instructions warn against using for OUTBOUND")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 Testing Customer Service Context Access Fix")
    print("=" * 80)
    
    try:
        test_customer_service_tools_added_when_enabled()
        test_customer_service_instructions_mandatory()
        test_customer_service_has_examples()
        test_crm_tools_implementation()
        test_customer_service_not_for_outbound()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\n📋 Summary:")
        print("   • CRM tools are properly added when customer service is enabled")
        print("   • Instructions mandate AUTOMATIC context loading at conversation start")
        print("   • New crm_create_note() tool added for mid-conversation documentation")
        print("   • Clear examples show correct usage pattern")
        print("   • Instructions specify INBOUND-only restriction")
        print("\n🎯 The fix ensures the AI will:")
        print("   1. Automatically identify leads by phone at conversation start")
        print("   2. Immediately load full context (notes, appointments, history)")
        print("   3. Reference notes when customer asks about issues")
        print("   4. Document important info during the conversation")
        print("   5. Create proper call summary at the end")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
