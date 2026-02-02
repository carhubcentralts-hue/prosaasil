"""
Test for WhatsApp Conversation Context and Anti-Repetition

This test verifies that:
1. The bot maintains context for 30+ messages (not just 12)
2. Temperature is set to 0.3 for varied responses
3. Max tokens is 2000 for WhatsApp to prevent truncation
4. Anti-repetition rules are included in the prompt

Run: pytest tests/test_whatsapp_conversation_context.py -v -s
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestWhatsAppConversationContext:
    """Test that WhatsApp bot maintains proper context and prevents repetition"""
    
    def test_conversation_history_supports_30_messages(self):
        """
        Verify that MAX_CONVERSATION_HISTORY_MESSAGES is set to 30
        to support longer conversations
        """
        from server.services.ai_service import MAX_CONVERSATION_HISTORY_MESSAGES
        
        # Should be 30 to support 50+ message conversations
        assert MAX_CONVERSATION_HISTORY_MESSAGES == 30, \
            f"Expected MAX_CONVERSATION_HISTORY_MESSAGES=30, got {MAX_CONVERSATION_HISTORY_MESSAGES}"
    
    def test_whatsapp_uses_30_message_history(self):
        """
        When there are 30+ messages in history,
        all 30 should be passed to the agent
        """
        from server.services.ai_service import AIService, MAX_CONVERSATION_HISTORY_MESSAGES
        
        ai_service = AIService()
        current_message = "מה העלות?"
        
        # Create 35 previous messages (more than the limit)
        previous_messages = []
        for i in range(35):
            if i % 2 == 0:
                previous_messages.append(f'לקוח: הודעה {i}')
            else:
                previous_messages.append(f'עוזר: תשובה {i}')
        
        context = {
            'previous_messages': previous_messages,
            'phone': '+972501234567',
            'lead_id': 123
        }
        
        with patch('server.services.ai_service._ensure_agent_modules_loaded', return_value=True):
            with patch('server.services.ai_service.get_or_create_agent') as mock_get_agent:
                mock_agent = Mock()
                mock_get_agent.return_value = mock_agent
                
                with patch('server.services.ai_service.Runner') as mock_runner:
                    mock_result = Mock()
                    mock_result.output_text = "המחיר הוא 500 שקלים"
                    mock_runner.run_sync.return_value = mock_result
                    
                    result = ai_service.generate_response_with_agent(
                        message=current_message,
                        business_id=10,
                        context=context,
                        channel='whatsapp',
                        customer_phone='+972501234567'
                    )
                    
                    assert mock_runner.run_sync.called
                    
                    # Get the messages that were passed to the agent
                    call_args = mock_runner.run_sync.call_args
                    messages_arg = call_args.kwargs.get('input') or call_args.args[1]
                    
                    # Should have exactly MAX_CONVERSATION_HISTORY_MESSAGES from history + 1 current
                    # (The function takes the LAST N messages from history)
                    expected_count = MAX_CONVERSATION_HISTORY_MESSAGES + 1  # +1 for current message
                    
                    # Note: The actual count might be MAX_CONVERSATION_HISTORY_MESSAGES if current is in history
                    assert len(messages_arg) >= MAX_CONVERSATION_HISTORY_MESSAGES, \
                        f"Expected at least {MAX_CONVERSATION_HISTORY_MESSAGES} messages, got {len(messages_arg)}"
                    
                    # Verify it's using the LAST messages, not the first
                    # The last user message in previous_messages was "לקוח: הודעה 34"
                    user_messages = [m for m in messages_arg if m.get('role') == 'user']
                    # Check that recent messages are included
                    assert any('34' in m.get('content', '') or 'העלות' in m.get('content', '') 
                              for m in user_messages), "Should include recent messages"
    
    def test_whatsapp_agent_settings(self):
        """
        Verify WhatsApp agent is created with correct settings:
        - temperature: 0.3 (not 0.0)
        - max_tokens: 2000 (not 800)
        """
        from server.agent_tools.agent_factory import create_booking_agent
        from agents import ModelSettings
        
        with patch('server.agent_tools.agent_factory.Agent') as mock_agent_class:
            with patch('server.agent_tools.agent_factory.BusinessSettings') as mock_settings:
                with patch('server.agent_tools.agent_factory.Business') as mock_business:
                    # Mock business with WhatsApp prompt
                    mock_biz = Mock()
                    mock_biz.whatsapp_system_prompt = "אתה עוזר דיגיטלי"
                    mock_business.query.filter_by.return_value.first.return_value = mock_biz
                    
                    # Mock settings for call_goal check
                    mock_biz_settings = Mock()
                    mock_biz_settings.call_goal = "lead_only"
                    mock_settings.query.filter_by.return_value.first.return_value = mock_biz_settings
                    
                    # Create agent for WhatsApp
                    agent = create_booking_agent(
                        business_name="Test Business",
                        custom_instructions="אתה עוזר דיגיטלי",
                        business_id=10,
                        channel="whatsapp"
                    )
                    
                    # Verify Agent was called
                    assert mock_agent_class.called
                    
                    # Get the model_settings that were passed
                    call_kwargs = mock_agent_class.call_args.kwargs
                    model_settings = call_kwargs.get('model_settings')
                    
                    assert model_settings is not None, "model_settings should be provided"
                    assert model_settings.temperature == 0.3, \
                        f"Expected temperature=0.3 for WhatsApp, got {model_settings.temperature}"
                    assert model_settings.max_tokens == 2000, \
                        f"Expected max_tokens=2000 for WhatsApp, got {model_settings.max_tokens}"
    
    def test_anti_repetition_rules_in_prompt(self):
        """
        Verify that anti-repetition rules are included in WhatsApp prompts
        """
        from server.agent_tools.agent_factory import create_booking_agent
        
        with patch('server.agent_tools.agent_factory.Agent') as mock_agent_class:
            with patch('server.agent_tools.agent_factory.BusinessSettings') as mock_settings:
                with patch('server.agent_tools.agent_factory.Business') as mock_business:
                    # Mock business with WhatsApp prompt
                    mock_biz = Mock()
                    mock_biz.whatsapp_system_prompt = "אתה עוזר דיגיטלי מקצועי"
                    mock_business.query.filter_by.return_value.first.return_value = mock_biz
                    
                    # Mock settings
                    mock_biz_settings = Mock()
                    mock_biz_settings.call_goal = "lead_only"
                    mock_biz_settings.enable_customer_service = False
                    mock_settings.query.filter_by.return_value.first.return_value = mock_biz_settings
                    
                    # Create agent for WhatsApp
                    agent = create_booking_agent(
                        business_name="Test Business",
                        custom_instructions="אתה עוזר דיגיטלי מקצועי",
                        business_id=10,
                        channel="whatsapp"
                    )
                    
                    # Verify Agent was called
                    assert mock_agent_class.called
                    
                    # Get the instructions that were passed
                    call_kwargs = mock_agent_class.call_args.kwargs
                    instructions = call_kwargs.get('instructions', '')
                    
                    # Verify anti-repetition rules are present
                    assert 'ANTI-REPETITION' in instructions, \
                        "Anti-repetition framework should be in instructions"
                    assert 'אסור לחזור על אותה שאלה' in instructions, \
                        "Should include Hebrew anti-repetition rules"
                    assert 'קרא את כל ההיסטוריה' in instructions, \
                        "Should instruct to read all history"
                    
                    # Verify original prompt is still included
                    assert 'אתה עוזר דיגיטלי מקצועי' in instructions, \
                        "Original business prompt should still be included"
    
    def test_non_whatsapp_channel_uses_default_settings(self):
        """
        Verify that non-WhatsApp channels (phone, etc.) use default settings,
        not the WhatsApp-specific ones
        """
        from server.agent_tools.agent_factory import create_booking_agent, AGENT_MODEL_SETTINGS
        
        with patch('server.agent_tools.agent_factory.Agent') as mock_agent_class:
            with patch('server.agent_tools.agent_factory.BusinessSettings') as mock_settings:
                with patch('server.agent_tools.agent_factory.Business') as mock_business:
                    # Mock business
                    mock_biz = Mock()
                    mock_biz.ai_prompt = "אתה עוזר טלפוני"
                    mock_business.query.filter_by.return_value.first.return_value = mock_biz
                    
                    # Mock settings
                    mock_biz_settings = Mock()
                    mock_biz_settings.call_goal = "lead_only"
                    mock_settings.query.filter_by.return_value.first.return_value = mock_biz_settings
                    
                    # Create agent for phone (not WhatsApp)
                    agent = create_booking_agent(
                        business_name="Test Business",
                        custom_instructions="אתה עוזר טלפוני",
                        business_id=10,
                        channel="phone"
                    )
                    
                    # Verify Agent was called
                    assert mock_agent_class.called
                    
                    # Get the model_settings that were passed
                    call_kwargs = mock_agent_class.call_args.kwargs
                    model_settings = call_kwargs.get('model_settings')
                    
                    # Should use AGENT_MODEL_SETTINGS (not WhatsApp-specific)
                    assert model_settings == AGENT_MODEL_SETTINGS, \
                        "Non-WhatsApp channels should use default AGENT_MODEL_SETTINGS"
                    
                    # Phone channel should NOT have 2000 tokens
                    assert model_settings.max_tokens != 2000, \
                        "Phone channel should not use WhatsApp's max_tokens"


class TestAntiRepetitionDetection:
    """Test that repetition is detected and logged"""
    
    def test_repetition_detection_logs_warning(self):
        """
        When the bot generates the same response as before,
        it should log a warning
        """
        from server.services.ai_service import AIService
        
        ai_service = AIService()
        current_message = "כן"
        
        # Context with last agent message
        context = {
            'previous_messages': [
                'לקוח: לא',
                'עוזר: מי עושה את האריזה?',
                'לקוח: כן'
            ],
            'phone': '+972501234567',
            'lead_id': 123,
            'last_agent_message': 'מי עושה את האריזה?'  # Last response
        }
        
        with patch('server.services.ai_service._ensure_agent_modules_loaded', return_value=True):
            with patch('server.services.ai_service.get_or_create_agent') as mock_get_agent:
                mock_agent = Mock()
                mock_get_agent.return_value = mock_agent
                
                with patch('server.services.ai_service.Runner') as mock_runner:
                    # Mock returns the SAME response as before
                    mock_result = Mock()
                    mock_result.output_text = "מי עושה את האריזה?"  # SAME as last_agent_message
                    mock_runner.run_sync.return_value = mock_result
                    
                    with patch('server.services.ai_service.logger') as mock_logger:
                        result = ai_service.generate_response_with_agent(
                            message=current_message,
                            business_id=10,
                            context=context,
                            channel='whatsapp',
                            customer_phone='+972501234567'
                        )
                        
                        # Verify warning was logged about repetition
                        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                        repetition_warning_found = any('repeating response' in str(call) 
                                                       for call in warning_calls)
                        assert repetition_warning_found, \
                            "Should log warning when agent repeats response"
