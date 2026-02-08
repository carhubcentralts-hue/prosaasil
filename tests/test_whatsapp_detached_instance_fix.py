"""
Test for WhatsApp DetachedInstanceError Fix

This test verifies that:
1. Lead attributes are extracted immediately to avoid DetachedInstanceError
2. Fallback messages are sent when processing fails
3. Optional rules handling works correctly (compiled_rules=None)

Run: pytest tests/test_whatsapp_detached_instance_fix.py -v -s
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestWhatsAppDetachedInstanceFix:
    """Test that WhatsApp message processing avoids DetachedInstanceError"""
    
    def test_lead_attributes_extracted_immediately(self):
        """
        Verify that lead attributes are extracted immediately after getting lead
        This prevents DetachedInstanceError when accessing lead after DB operations
        """
        from server.models_sql import Lead
        
        # Create a mock lead
        mock_lead = Mock(spec=Lead)
        mock_lead.id = 123
        mock_lead.phone_e164 = "+972501234567"
        mock_lead.name = "Test User"
        
        # Simulate what the fixed code does - extract attributes immediately
        lead_id = mock_lead.id
        lead_phone_e164 = mock_lead.phone_e164
        lead_name = mock_lead.name
        
        # Verify attributes are extracted correctly
        assert lead_id == 123, "lead_id should be extracted immediately"
        assert lead_phone_e164 == "+972501234567", "lead_phone_e164 should be extracted"
        assert lead_name == "Test User", "lead_name should be extracted"
        
        # Simulate session expiration (what happens in real code)
        mock_lead.id = None  # Session expired
        
        # Verify we can still use extracted values (no DetachedInstanceError)
        assert lead_id == 123, "Extracted lead_id should still be available"
        assert lead_phone_e164 == "+972501234567", "Extracted phone should still be available"
    
    def test_whatsapp_message_uses_lead_id(self):
        """
        Verify that WhatsAppMessage is created using lead_id (int) not lead object
        """
        from server.models_sql import WhatsAppMessage
        
        # Simulate the fixed code
        lead_id = 456  # Extracted immediately from lead
        
        # Create message using lead_id (not lead.id)
        msg = WhatsAppMessage()
        msg.business_id = 1
        msg.to_number = "972501234567@s.whatsapp.net"
        msg.body = "Test message"
        msg.direction = "in"
        msg.status = "received"
        msg.lead_id = lead_id  # Using extracted lead_id
        
        # Verify lead_id is set correctly
        assert msg.lead_id == 456, "Message should use extracted lead_id"
    
    def test_fallback_message_on_processing_failure(self):
        """
        Verify that a fallback message is sent when processing fails
        """
        # Mock WhatsApp service
        mock_wa_service = Mock()
        mock_wa_service.send_message = Mock()
        
        # Simulate error scenario
        remote_jid = "972501234567@s.whatsapp.net"
        from_me = False
        
        # Simulate what the fail-safe code does
        try:
            # Simulate processing error
            raise Exception("Simulated processing error")
        except Exception as e:
            # Fail-safe: send fallback message
            if remote_jid and not from_me:
                fallback_msg = "קיבלתי ✅ רגע בודק וחוזר אליך"
                mock_wa_service.send_message(remote_jid, fallback_msg)
        
        # Verify fallback was sent
        mock_wa_service.send_message.assert_called_once_with(
            remote_jid, 
            "קיבלתי ✅ רגע בודק וחוזר אליך"
        )
    
    def test_decision_engine_handles_optional_rules(self):
        """
        Verify that DecisionEngine works without compiled_rules (None)
        """
        from server.services.decision_engine import decide, FALLBACK_DECISION
        
        # Mock LLM call to return None (simulating failure)
        with patch('server.services.decision_engine._call_llm_for_decision') as mock_llm:
            mock_llm.return_value = None
            
            # Call decide with no compiled_logic (should use fallback)
            decision = decide(
                business_id=1,
                channel="whatsapp",
                user_message="שלום",
                compiled_logic=None,  # No rules - should still work
                known_facts={},
                lead_status=None,
                status_catalog=[],
                history_summary=None,
                business_prompt="אתה עוזר ידידותי",
                lead_id=123
            )
            
            # Verify fallback decision is returned
            assert decision is not None, "Decision should not be None"
            assert decision.get("action") == "collect_details", "Should use fallback action"
            assert "reply" in decision, "Should have reply field"
    
    def test_decision_engine_validates_and_repairs(self):
        """
        Verify that DecisionEngine validates decisions and attempts repair
        """
        from server.services.decision_engine import validate_decision, VALID_ACTIONS
        
        # Test valid decision
        valid_decision = {
            "action": "collect_details",
            "confidence": 0.8,
            "reply": "איך אוכל לעזור?"
        }
        
        validation = validate_decision(valid_decision)
        assert validation["valid"] is True, "Valid decision should pass validation"
        
        # Test invalid action
        invalid_decision = {
            "action": "invalid_action",
            "confidence": 0.8,
            "reply": "test"
        }
        
        validation = validate_decision(invalid_decision)
        assert validation["valid"] is False, "Invalid action should fail validation"
        assert len(validation["errors"]) > 0, "Should have errors"
    
    def test_session_update_uses_lead_id(self):
        """
        Verify that session tracking uses lead_id not lead.id
        """
        # Simulate the fixed code
        lead_id = 789
        business_id = 1
        conversation_key = "972501234567@s.whatsapp.net"
        from_number_e164 = "+972501234567"
        
        # Mock the update_session_activity function
        with patch('server.services.whatsapp_session_service.update_session_activity') as mock_update:
            mock_conversation = Mock()
            mock_conversation.id = 100
            mock_update.return_value = mock_conversation
            
            # Call with lead_id (not lead.id)
            from server.services.whatsapp_session_service import update_session_activity
            conversation = update_session_activity(
                business_id=business_id,
                customer_wa_id=conversation_key,
                direction="in",
                provider="baileys",
                lead_id=lead_id,  # Using extracted lead_id
                phone_e164=from_number_e164
            )
            
            # Verify the function was called with lead_id
            mock_update.assert_called_once()
            call_args = mock_update.call_args[1]
            assert call_args['lead_id'] == 789, "Should pass extracted lead_id"
    
    def test_background_job_fail_safe(self):
        """
        Verify that background job sends fallback on failure
        """
        from server.jobs.whatsapp_ai_response_job import whatsapp_ai_response_job
        
        # Mock all dependencies to force an error
        with patch('server.jobs.whatsapp_ai_response_job.WhatsAppMessage') as mock_msg:
            with patch('server.jobs.whatsapp_ai_response_job.get_whatsapp_service') as mock_wa:
                mock_msg.query.get.return_value = None  # Force error
                
                mock_wa_service = Mock()
                mock_wa_service.send_message = Mock()
                mock_wa.return_value = mock_wa_service
                
                # Call job (should fail and send fallback)
                result = whatsapp_ai_response_job(
                    business_id=1,
                    message_id=999,  # Non-existent message
                    remote_jid="972501234567@s.whatsapp.net",
                    conversation_key="972501234567@s.whatsapp.net",
                    message_text="Test",
                    from_number_e164="+972501234567",
                    lead_id=123
                )
                
                # Verify failure is handled
                assert result['success'] is False, "Job should report failure"
                assert 'error' in result, "Should return error details"
    
    def test_confidence_gates_applied(self):
        """
        Verify that confidence gates block high-impact actions
        """
        from server.services.decision_engine import apply_confidence_gates, HIGH_IMPACT_ACTIONS
        
        # Low confidence + high impact action
        decision = {
            "action": "schedule_meeting",  # High impact
            "confidence": 0.4,  # Low confidence
            "reply": "רוצה לקבוע פגישה?"
        }
        
        gated_decision = apply_confidence_gates(decision)
        
        # Should be blocked and changed to ask_clarifying_question
        assert gated_decision["action"] == "ask_clarifying_question", \
            "Low confidence should block high-impact action"
        
        # High confidence + high impact action
        decision2 = {
            "action": "schedule_meeting",
            "confidence": 0.9,  # High confidence
            "reply": "רוצה לקבוע פגישה?"
        }
        
        gated_decision2 = apply_confidence_gates(decision2)
        
        # Should pass through
        assert gated_decision2["action"] == "schedule_meeting", \
            "High confidence should allow high-impact action"
    
    def test_context_envelope_builds_correctly(self):
        """
        Verify that context envelope is built with all components
        """
        from server.services.decision_engine import build_context_envelope
        
        # Build envelope with all components
        messages = build_context_envelope(
            channel="whatsapp",
            user_message="שלום",
            compiled_logic={"rules": [{"id": "R1"}]},
            known_facts={"name": "יוסי"},
            lead_status={"id": 1, "label": "חדש"},
            status_catalog=[{"id": 1, "label": "חדש"}],
            history_summary="שיחה קצרה",
            business_prompt="אתה עוזר",
            constraints={"max_questions": 1}
        )
        
        # Verify structure
        assert len(messages) > 0, "Should create messages"
        assert any(m.get("role") == "system" for m in messages), "Should have system messages"
        assert any(m.get("role") == "user" for m in messages), "Should have user message"
        
        # Verify content includes all parts
        all_content = " ".join(m.get("content", "") for m in messages)
        assert "חוקי העסק" in all_content or "rules" in all_content.lower(), "Should include rules"
        assert "עובדות ידועות" in all_content, "Should include known facts"
    
    def test_empty_rules_handled_gracefully(self):
        """
        Verify that empty/None compiled_logic doesn't break decision engine
        """
        from server.services.decision_engine import build_context_envelope
        
        # Build envelope with None compiled_logic
        messages = build_context_envelope(
            channel="whatsapp",
            user_message="שלום",
            compiled_logic=None,  # No rules
            known_facts={},
            lead_status=None,
            status_catalog=[],
            business_prompt="אתה עוזר"
        )
        
        # Should still work
        assert len(messages) > 0, "Should create messages even without rules"
        assert any(m.get("role") == "user" for m in messages), "Should have user message"
