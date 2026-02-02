"""
Test for AI Service Duplicate Message Fix

This test verifies that the AI service properly handles the case where
the current message is already included in the conversation history,
preventing duplicate messages that cause the bot to repeat itself.

Run: pytest tests/test_ai_service_duplicate_message_fix.py -v -s
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestDuplicateMessagePrevention:
    """Test that duplicate messages are prevented in conversation history"""
    
    def test_current_message_already_in_history(self):
        """
        When current message is already the last message in history,
        it should not be added again
        """
        from server.services.ai_service import AIService
        
        # Setup: Create a mock scenario where message is already in history
        ai_service = AIService()
        current_message = "נמלים"
        
        # Context with previous messages including the current one
        context = {
            'previous_messages': [
                'לקוח: היי',
                'עוזר: היי, זה רמי משלום הדברות 👋 איזה מזיק אתם רואים?',
                'לקוח: נמלים'  # Current message is already here
            ],
            'phone': '+972501234567',
            'lead_id': 123
        }
        
        # Mock the agent and its dependencies
        with patch('server.services.ai_service._ensure_agent_modules_loaded', return_value=True):
            with patch('server.services.ai_service.get_or_create_agent') as mock_get_agent:
                mock_agent = Mock()
                mock_get_agent.return_value = mock_agent
                
                with patch('server.services.ai_service.Runner') as mock_runner:
                    # Mock the agent response
                    mock_result = Mock()
                    mock_result.output_text = "בסדר, נמלים. באיזה חדר אתם רואים אותן?"
                    mock_runner.run_sync.return_value = mock_result
                    
                    with patch('server.services.ai_service.logger') as mock_logger:
                        # Call the method
                        result = ai_service.generate_response_with_agent(
                            message=current_message,
                            business_id=10,
                            context=context,
                            channel='whatsapp',
                            customer_phone='+972501234567'
                        )
                        
                        # Verify the agent was called
                        assert mock_runner.run_sync.called
                        
                        # Get the messages that were passed to the agent
                        call_args = mock_runner.run_sync.call_args
                        messages_arg = call_args.kwargs.get('input') or call_args.args[1]
                        
                        # Count how many times "נמלים" appears
                        user_messages = [m for m in messages_arg if m.get('role') == 'user']
                        ants_messages = [m for m in user_messages if m.get('content', '').strip() == 'נמלים']
                        
                        # Should only appear ONCE, not twice
                        assert len(ants_messages) == 1, f"Expected 1 occurrence of 'נמלים', found {len(ants_messages)}"
                        
                        # Verify the log message about skipping duplicate
                        log_calls = [str(call) for call in mock_logger.info.call_args_list]
                        duplicate_log_found = any('already in history' in str(call) or 'Using existing message' in str(call) 
                                                 for call in log_calls)
                        assert duplicate_log_found, "Should log that duplicate was skipped"
    
    def test_current_message_not_in_history(self):
        """
        When current message is NOT in history,
        it should be added
        """
        from server.services.ai_service import AIService
        
        ai_service = AIService()
        current_message = "נמלים"
        
        # Context with previous messages NOT including the current one
        context = {
            'previous_messages': [
                'לקוח: היי',
                'עוזר: היי, זה רמי משלום הדברות 👋 איזה מזיק אתם רואים?'
                # Current message is NOT here
            ],
            'phone': '+972501234567',
            'lead_id': 123
        }
        
        with patch('server.services.ai_service._ensure_agent_modules_loaded', return_value=True):
            with patch('server.services.ai_service.get_or_create_agent') as mock_get_agent:
                mock_agent = Mock()
                mock_get_agent.return_value = mock_agent
                
                with patch('server.services.ai_service.Runner') as mock_runner:
                    mock_result = Mock()
                    mock_result.output_text = "בסדר, נמלים. באיזה חדר אתם רואים אותן?"
                    mock_runner.run_sync.return_value = mock_result
                    
                    with patch('server.services.ai_service.logger') as mock_logger:
                        result = ai_service.generate_response_with_agent(
                            message=current_message,
                            business_id=10,
                            context=context,
                            channel='whatsapp',
                            customer_phone='+972501234567'
                        )
                        
                        assert mock_runner.run_sync.called
                        
                        call_args = mock_runner.run_sync.call_args
                        messages_arg = call_args.kwargs.get('input') or call_args.args[1]
                        
                        # Should have 3 messages total: 2 from history + 1 current
                        assert len(messages_arg) >= 3
                        
                        # Last message should be the current user message
                        last_msg = messages_arg[-1]
                        assert last_msg.get('role') == 'user'
                        assert last_msg.get('content', '').strip() == 'נמלים'
                        
                        # Verify the log message about adding current message
                        log_calls = [str(call) for call in mock_logger.info.call_args_list]
                        added_log_found = any('Added current message' in str(call) for call in log_calls)
                        assert added_log_found, "Should log that message was added"
    
    def test_first_message_no_history(self):
        """
        When there's no history (first message),
        current message should be added
        """
        from server.services.ai_service import AIService
        
        ai_service = AIService()
        current_message = "היי"
        
        # Context with NO previous messages
        context = {
            'previous_messages': [],
            'phone': '+972501234567',
            'lead_id': 123
        }
        
        with patch('server.services.ai_service._ensure_agent_modules_loaded', return_value=True):
            with patch('server.services.ai_service.get_or_create_agent') as mock_get_agent:
                mock_agent = Mock()
                mock_get_agent.return_value = mock_agent
                
                with patch('server.services.ai_service.Runner') as mock_runner:
                    mock_result = Mock()
                    mock_result.output_text = "היי, זה רמי משלום הדברות 👋"
                    mock_runner.run_sync.return_value = mock_result
                    
                    result = ai_service.generate_response_with_agent(
                        message=current_message,
                        business_id=10,
                        context=context,
                        channel='whatsapp',
                        customer_phone='+972501234567'
                    )
                    
                    assert mock_runner.run_sync.called
                    
                    call_args = mock_runner.run_sync.call_args
                    messages_arg = call_args.kwargs.get('input') or call_args.args[1]
                    
                    # Should have exactly 1 message (the current one)
                    assert len(messages_arg) == 1
                    assert messages_arg[0].get('role') == 'user'
                    assert messages_arg[0].get('content', '').strip() == 'היי'
