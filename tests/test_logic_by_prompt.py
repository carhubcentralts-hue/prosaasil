"""
Tests for Logic-by-Prompt system: Rules Compiler + Decision Engine + Status Logic
═══════════════════════════════════════════════════════════════════════════════════

24 tests:
- 10 tests for rules compilation
- 9 tests for decision engine
- 5 tests for status-based logic
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# ─── Rules Compiler Tests ─────────────────────────────────────────────


class TestRulesCompiler:
    """Test suite for the rules compiler service"""
    
    def test_empty_text_returns_error(self):
        """Empty input should return compile error"""
        from server.services.rules_compiler import compile_business_rules
        
        result = compile_business_rules("")
        assert result["success"] is False
        assert result["error"] is not None
        assert "טקסט" in result["error"]

    def test_whitespace_text_returns_error(self):
        """Whitespace-only input should return compile error"""
        from server.services.rules_compiler import compile_business_rules
        
        result = compile_business_rules("   \n\t  ")
        assert result["success"] is False

    def test_validate_compiled_rules_valid(self):
        """Valid compiled rules pass validation"""
        from server.services.rules_compiler import validate_compiled_rules
        
        compiled = {
            "rules": [
                {"id": "R1", "priority": 100, "action": "collect_details"},
                {"id": "R2", "priority": 200, "action": "schedule_meeting"}
            ],
            "constraints": {"one_question_at_a_time": True},
            "entities_schema": {"fields": []}
        }
        
        result = validate_compiled_rules(compiled)
        assert result["valid"] is True

    def test_validate_compiled_rules_missing_rules(self):
        """Missing 'rules' field fails validation"""
        from server.services.rules_compiler import validate_compiled_rules
        
        compiled = {"constraints": {}}
        result = validate_compiled_rules(compiled)
        assert result["valid"] is False
        assert "rules" in result["error"]

    def test_validate_compiled_rules_invalid_action(self):
        """Invalid action type fails validation"""
        from server.services.rules_compiler import validate_compiled_rules
        
        compiled = {
            "rules": [
                {"id": "R1", "priority": 100, "action": "invalid_action"}
            ]
        }
        
        result = validate_compiled_rules(compiled)
        assert result["valid"] is False
        assert "invalid_action" in result["error"]

    def test_validate_compiled_rules_missing_id(self):
        """Rule without id fails validation"""
        from server.services.rules_compiler import validate_compiled_rules
        
        compiled = {
            "rules": [
                {"priority": 100, "action": "collect_details"}
            ]
        }
        
        result = validate_compiled_rules(compiled)
        assert result["valid"] is False
        assert "id" in result["error"]

    def test_validate_status_references_valid(self):
        """Valid status references pass validation"""
        from server.services.rules_compiler import validate_status_references
        
        compiled = {
            "rules": [
                {
                    "id": "S1",
                    "when": {"status_is": ["חדש"]},
                    "action": "collect_details"
                }
            ]
        }
        catalog = [
            {"id": 1, "label": "חדש"},
            {"id": 2, "label": "נסגרה הובלה"}
        ]
        
        result = validate_status_references(compiled, catalog)
        assert result is None  # No error

    def test_validate_status_references_invalid(self):
        """Non-existent status reference fails validation"""
        from server.services.rules_compiler import validate_status_references
        
        compiled = {
            "rules": [
                {
                    "id": "S1",
                    "when": {"status_is": ["סטטוס לא קיים"]},
                    "action": "collect_details"
                }
            ]
        }
        catalog = [
            {"id": 1, "label": "חדש"},
            {"id": 2, "label": "נסגרה הובלה"}
        ]
        
        result = validate_status_references(compiled, catalog)
        assert result is not None
        assert "סטטוס לא קיים" in result
        assert "חדש" in result  # Should list available statuses

    @patch("openai.OpenAI")
    def test_compile_success_with_mock(self, mock_openai_cls):
        """Successful compilation with mocked LLM"""
        from server.services.rules_compiler import compile_business_rules
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "rules": [
                {
                    "id": "R1",
                    "priority": 100,
                    "when": {"condition": "מעל 2 חדרים"},
                    "action": "schedule_meeting"
                }
            ],
            "constraints": {"one_question_at_a_time": True},
            "entities_schema": {"fields": [{"name": "חדרים", "type": "number"}]}
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client
        
        result = compile_business_rules("מעל 2 חדרים → לתאם פגישה")
        assert result["success"] is True
        assert len(result["compiled"]["rules"]) == 1
        assert result["compiled"]["rules"][0]["action"] == "schedule_meeting"

    @patch("openai.OpenAI")
    def test_compile_error_from_llm(self, mock_openai_cls):
        """Compiler-reported error (e.g., unknown status) is handled"""
        from server.services.rules_compiler import compile_business_rules
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "error": "הסטטוס 'לא קיים' לא נמצא ברשימה"
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client
        
        result = compile_business_rules("אם הסטטוס 'לא קיים' → לאסוף", business_id=1)
        assert result["success"] is False
        assert "לא קיים" in result["error"]


# ─── Decision Engine Tests ─────────────────────────────────────────────


class TestDecisionEngine:
    """Test suite for the decision engine"""
    
    def test_validate_decision_valid(self):
        """Valid decision passes validation"""
        from server.services.decision_engine import validate_decision
        
        decision = {
            "action": "collect_details",
            "confidence": 0.85,
            "rule_hits": ["R1"],
            "extracted": {"facts": {"rooms": "3"}},
            "missing": ["date"],
            "next_question": "מתי תרצה?",
            "reply": "מעולה! מתי תרצה לקבוע?"
        }
        
        result = validate_decision(decision)
        assert result["valid"] is True

    def test_validate_decision_invalid_action(self):
        """Invalid action fails validation"""
        from server.services.decision_engine import validate_decision
        
        decision = {
            "action": "invalid_action",
            "confidence": 0.85
        }
        
        result = validate_decision(decision)
        assert result["valid"] is False

    def test_confidence_gate_blocks_high_impact(self):
        """Low confidence blocks schedule_meeting"""
        from server.services.decision_engine import apply_confidence_gates
        
        decision = {
            "action": "schedule_meeting",
            "confidence": 0.4,
            "next_question": None,
            "reply": "בוא נקבע פגישה"
        }
        
        result = apply_confidence_gates(decision)
        assert result["action"] == "ask_clarifying_question"

    def test_confidence_gate_allows_high_confidence(self):
        """High confidence allows schedule_meeting"""
        from server.services.decision_engine import apply_confidence_gates
        
        decision = {
            "action": "schedule_meeting",
            "confidence": 0.85,
            "next_question": None,
            "reply": "בוא נקבע פגישה"
        }
        
        result = apply_confidence_gates(decision)
        assert result["action"] == "schedule_meeting"

    def test_status_enforcement_blocks_action(self):
        """Status rules block disallowed actions"""
        from server.services.decision_engine import apply_status_enforcement
        
        compiled_logic = {
            "rules": [
                {
                    "id": "S1",
                    "when": {"status_is": ["נסגרה הובלה"]},
                    "effects": {
                        "allowed_actions": ["answer_questions", "handoff_human"],
                        "block_actions": ["collect_details", "schedule_meeting"]
                    }
                }
            ]
        }
        
        decision = {
            "action": "collect_details",
            "confidence": 0.9
        }
        
        result = apply_status_enforcement(decision, compiled_logic, "נסגרה הובלה")
        assert result["action"] != "collect_details"
        assert result["action"] in ["answer_questions", "handoff_human"]

    def test_status_enforcement_allows_permitted_action(self):
        """Status rules allow permitted actions to pass through"""
        from server.services.decision_engine import apply_status_enforcement
        
        compiled_logic = {
            "rules": [
                {
                    "id": "S1",
                    "when": {"status_is": ["חדש"]},
                    "effects": {
                        "allowed_actions": ["collect_details", "ask_clarifying_question"],
                        "block_actions": []
                    }
                }
            ]
        }
        
        decision = {
            "action": "collect_details",
            "confidence": 0.9
        }
        
        result = apply_status_enforcement(decision, compiled_logic, "חדש")
        assert result["action"] == "collect_details"

    def test_fallback_decision_structure(self):
        """Fallback decision has all required fields"""
        from server.services.decision_engine import FALLBACK_DECISION
        
        assert "action" in FALLBACK_DECISION
        assert "confidence" in FALLBACK_DECISION
        assert "rule_hits" in FALLBACK_DECISION
        assert "reply" in FALLBACK_DECISION
        assert FALLBACK_DECISION["action"] == "collect_details"

    def test_build_context_envelope_structure(self):
        """Context envelope has correct message structure"""
        from server.services.decision_engine import build_context_envelope
        
        messages = build_context_envelope(
            channel="whatsapp",
            user_message="שלום, צריך הובלה",
            compiled_logic={"rules": [], "constraints": {}},
            known_facts={"name": "יוסי"},
            lead_status={"id": 1, "label": "חדש"},
            status_catalog=[{"id": 1, "label": "חדש"}],
            history_summary="שיחה ראשונה"
        )
        
        # Should have at least: system prompt, context, user message
        assert len(messages) >= 3
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "שלום, צריך הובלה"

    def test_build_context_envelope_includes_status(self):
        """Context envelope includes lead status when provided"""
        from server.services.decision_engine import build_context_envelope
        
        messages = build_context_envelope(
            channel="whatsapp",
            user_message="שלום",
            compiled_logic=None,
            known_facts=None,
            lead_status={"id": 5, "label": "נסגרה הובלה"},
            status_catalog=None
        )
        
        # Find the context message
        context_content = " ".join(m["content"] for m in messages if m["role"] == "system")
        assert "נסגרה הובלה" in context_content


# ─── Status-Specific Tests ─────────────────────────────────────────────


class TestStatusLogic:
    """Test suite for status-based business logic"""
    
    def test_new_status_allows_collect(self):
        """Status 'חדש' should allow collect_details action"""
        from server.services.decision_engine import apply_status_enforcement
        
        compiled = {
            "rules": [
                {
                    "id": "S1",
                    "when": {"status_is": ["חדש"]},
                    "effects": {
                        "allowed_actions": ["collect_details", "ask_clarifying_question"],
                        "block_actions": []
                    }
                }
            ]
        }
        
        decision = {"action": "collect_details", "confidence": 0.8}
        result = apply_status_enforcement(decision, compiled, "חדש")
        assert result["action"] == "collect_details"

    def test_closed_status_blocks_collect(self):
        """Status 'נסגרה הובלה' should block collect_details"""
        from server.services.decision_engine import apply_status_enforcement
        
        compiled = {
            "rules": [
                {
                    "id": "S2",
                    "when": {"status_is": ["נסגרה הובלה"]},
                    "effects": {
                        "allowed_actions": ["answer_questions", "handoff_human"],
                        "block_actions": ["collect_details", "schedule_meeting"]
                    }
                }
            ]
        }
        
        decision = {"action": "collect_details", "confidence": 0.9}
        result = apply_status_enforcement(decision, compiled, "נסגרה הובלה")
        assert result["action"] != "collect_details"

    def test_offer_sent_allows_sell(self):
        """Status 'נשלחה הצעה' should allow sell_close action"""
        from server.services.decision_engine import apply_status_enforcement
        
        compiled = {
            "rules": [
                {
                    "id": "S3",
                    "when": {"status_is": ["נשלחה הצעה"]},
                    "effects": {
                        "allowed_actions": ["sell_close", "answer_questions", "handoff_human"],
                        "block_actions": []
                    }
                }
            ]
        }
        
        decision = {"action": "sell_close", "confidence": 0.75}
        result = apply_status_enforcement(decision, compiled, "נשלחה הצעה")
        assert result["action"] == "sell_close"

    def test_invalid_status_in_compile_returns_error(self):
        """Referencing non-existent status in compile should return error"""
        from server.services.rules_compiler import validate_status_references
        
        compiled = {
            "rules": [
                {
                    "id": "S4",
                    "when": {"status_is": ["סטטוס פיקטיבי"]},
                    "action": "collect_details"
                }
            ]
        }
        catalog = [
            {"id": 1, "label": "חדש"},
            {"id": 2, "label": "מחכה להצעת מחיר"},
            {"id": 3, "label": "נסגרה הובלה"}
        ]
        
        error = validate_status_references(compiled, catalog)
        assert error is not None
        assert "סטטוס פיקטיבי" in error

    def test_status_restriction_repair(self):
        """Schedule_meeting blocked by status should be repaired to allowed action"""
        from server.services.decision_engine import apply_status_enforcement
        
        compiled = {
            "rules": [
                {
                    "id": "S5",
                    "when": {"status_is": ["נסגרה הובלה"]},
                    "effects": {
                        "allowed_actions": ["answer_questions", "service_support"],
                        "block_actions": ["schedule_meeting", "collect_details", "sell_close"]
                    }
                }
            ]
        }
        
        decision = {"action": "schedule_meeting", "confidence": 0.9}
        result = apply_status_enforcement(decision, compiled, "נסגרה הובלה")
        assert result["action"] in ["answer_questions", "service_support"]
