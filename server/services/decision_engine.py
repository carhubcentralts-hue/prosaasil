"""
Decision Engine Service - Unified AI decision maker for all channels
═══════════════════════════════════════════════════════════════════════

Implements the DECIDE → RESPOND pattern:
1. DECIDE: Send context to LLM, get structured JSON decision
2. VALIDATE: Enforce schema, confidence gates, status constraints
3. REPAIR: If invalid, attempt one repair call
4. FALLBACK: If still invalid, use safe default
5. RESPOND: Return validated decision with reply text

Same engine for WhatsApp + Phone Calls - no hardcoded business logic.
"""
import json
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Valid actions (protocol-level, not business-level)
VALID_ACTIONS = {
    "collect_details", "schedule_meeting", "ask_clarifying_question",
    "handoff_human", "answer_questions", "sell_close", "service_support", "none"
}

# Decision schema that LLM must return
DECISION_SCHEMA = {
    "action": "collect_details|schedule_meeting|ask_clarifying_question|handoff_human|answer_questions|sell_close|service_support|none",
    "confidence": 0.0,
    "rule_hits": [],
    "extracted": {"facts": {}},
    "missing": [],
    "next_question": None,
    "reply": "",
    "proposed_status": None
}

# Minimum confidence to allow high-impact actions
CONFIDENCE_THRESHOLD = 0.65
HIGH_IMPACT_ACTIONS = {"schedule_meeting", "sell_close", "handoff_human"}

# Fallback decision when everything fails
FALLBACK_DECISION = {
    "action": "collect_details",
    "confidence": 0.0,
    "rule_hits": [],
    "extracted": {"facts": {}},
    "missing": [],
    "next_question": None,
    "reply": "איך אוכל לעזור לך?",
    "proposed_status": None
}

DECISION_SYSTEM_PROMPT = """אתה מנוע החלטות (Decision Engine) לעסק.
תפקידך: לקבל הודעת לקוח ולהחזיר החלטה מובנית בפורמט JSON בלבד.

═══ פורמט חובה ═══
{
  "action": "collect_details|schedule_meeting|ask_clarifying_question|handoff_human|answer_questions|sell_close|service_support|none",
  "confidence": 0.0-1.0,
  "rule_hits": ["R1","S2"],
  "extracted": {"facts": {"key": "value"}},
  "missing": ["field1","field2"],
  "next_question": "שאלה אחת בלבד או null",
  "reply": "תשובה ללקוח בעברית",
  "proposed_status": {"label": "שם סטטוס", "confidence": 0.8} או null
}

═══ כללים ═══
1. החזר JSON בלבד! אסור טקסט מחוץ ל-JSON
2. action חייב להיות מהרשימה
3. confidence = מידת הביטחון שהפעולה נכונה (0.0-1.0)
4. rule_hits = אילו כללים הופעלו (לפי ID)
5. extracted.facts = עובדות שחולצו מההודעה
6. missing = שדות שעדיין חסרים
7. next_question = שאלה אחת בלבד (אם צריך)
8. reply = תשובה מקצועית בעברית ללקוח
9. proposed_status = הצעה לשינוי סטטוס (רק אם הכללים מגדירים)"""


def build_context_envelope(
    channel: str,
    user_message: str,
    compiled_logic: Optional[Dict[str, Any]],
    known_facts: Optional[Dict[str, Any]],
    lead_status: Optional[Dict[str, Any]],
    status_catalog: Optional[List[Dict[str, Any]]],
    history_summary: Optional[str] = None,
    business_prompt: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Build a unified Context Envelope for the Decision Engine.
    Same structure for WhatsApp and Phone Calls.
    """
    messages = []
    
    # 1. System prompt (fixed, protocol-level)
    messages.append({"role": "system", "content": DECISION_SYSTEM_PROMPT})
    
    # 2. Business prompt (from DB)
    if business_prompt:
        messages.append({
            "role": "system",
            "content": f"═══ הנחיות העסק ═══\n{business_prompt}"
        })
    
    # 3. Compiled logic rules
    if compiled_logic:
        rules_text = json.dumps(compiled_logic, ensure_ascii=False, indent=2)
        messages.append({
            "role": "system",
            "content": f"═══ חוקי העסק (compiled) ═══\n{rules_text}"
        })
    
    # 4. Context data
    context_parts = []
    context_parts.append(f"ערוץ: {channel}")
    
    if lead_status:
        context_parts.append(f"סטטוס ליד: {json.dumps(lead_status, ensure_ascii=False)}")
    
    if status_catalog:
        catalog_str = json.dumps(status_catalog, ensure_ascii=False)
        context_parts.append(f"קטלוג סטטוסים: {catalog_str}")
    
    if known_facts:
        facts_str = json.dumps(known_facts, ensure_ascii=False)
        context_parts.append(f"עובדות ידועות: {facts_str}")
    
    if history_summary:
        context_parts.append(f"סיכום שיחה: {history_summary}")
    
    if constraints:
        constraints_str = json.dumps(constraints, ensure_ascii=False)
        context_parts.append(f"אילוצים: {constraints_str}")
    
    if context_parts:
        messages.append({
            "role": "system",
            "content": "═══ הקשר ═══\n" + "\n".join(context_parts)
        })
    
    # 5. User message
    messages.append({"role": "user", "content": user_message})
    
    return messages


def validate_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a decision against the required schema.
    Returns: {"valid": bool, "errors": list, "decision": dict}
    """
    errors = []
    
    if not isinstance(decision, dict):
        return {"valid": False, "errors": ["Decision is not a dict"], "decision": None}
    
    # Validate action
    action = decision.get("action")
    if not action or action not in VALID_ACTIONS:
        errors.append(f"Invalid action: {action}")
    
    # Validate confidence
    confidence = decision.get("confidence")
    if confidence is None:
        decision["confidence"] = 0.5
    elif not isinstance(confidence, (int, float)):
        errors.append(f"Invalid confidence: {confidence}")
    
    # Ensure required fields exist with defaults
    decision.setdefault("rule_hits", [])
    decision.setdefault("extracted", {"facts": {}})
    decision.setdefault("missing", [])
    decision.setdefault("next_question", None)
    decision.setdefault("reply", "")
    decision.setdefault("proposed_status", None)
    
    return {"valid": len(errors) == 0, "errors": errors, "decision": decision}


def apply_confidence_gates(decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply confidence gates: if confidence < threshold, block high-impact actions.
    """
    confidence = decision.get("confidence", 0.0)
    action = decision.get("action", "")
    
    if confidence < CONFIDENCE_THRESHOLD and action in HIGH_IMPACT_ACTIONS:
        logger.info(
            f"[DECISION_ENGINE] ⚠️ Confidence gate: {action} blocked (confidence={confidence:.2f} < {CONFIDENCE_THRESHOLD})"
        )
        decision["action"] = "ask_clarifying_question"
        if not decision.get("next_question"):
            decision["next_question"] = "אשמח לוודא - אפשר לפרט קצת יותר?"
        # Update reply to reflect the clarifying question
        if decision.get("next_question"):
            decision["reply"] = decision["next_question"]
    
    return decision


def apply_status_enforcement(
    decision: Dict[str, Any],
    compiled_logic: Optional[Dict[str, Any]],
    lead_status_label: Optional[str]
) -> Dict[str, Any]:
    """
    Enforce status-based rules from compiled logic.
    If a rule blocks the chosen action for the current status, change it.
    """
    if not compiled_logic or not lead_status_label:
        return decision
    
    rules = compiled_logic.get("rules", [])
    action = decision.get("action", "")
    
    for rule in rules:
        when = rule.get("when", {})
        effects = rule.get("effects", {})
        
        # Check if rule applies to current status
        status_is = when.get("status_is", [])
        status_is_not = when.get("status_is_not", [])
        
        applies = False
        if status_is and lead_status_label in status_is:
            applies = True
        if status_is_not and lead_status_label not in status_is_not:
            applies = True
        
        if not applies:
            continue
        
        # Check if action is blocked
        block_actions = effects.get("block_actions", [])
        allowed_actions = effects.get("allowed_actions", [])
        
        if block_actions and action in block_actions:
            logger.info(f"[DECISION_ENGINE] 🚫 Action '{action}' blocked by rule {rule.get('id')} for status '{lead_status_label}'")
            # Fall back to first allowed action or answer_questions
            if allowed_actions:
                decision["action"] = allowed_actions[0]
            else:
                decision["action"] = "answer_questions"
        
        if allowed_actions and action not in allowed_actions:
            logger.info(f"[DECISION_ENGINE] 🚫 Action '{action}' not in allowed list for status '{lead_status_label}'")
            decision["action"] = allowed_actions[0]
    
    return decision


def decide(
    business_id: int,
    channel: str,
    user_message: str,
    compiled_logic: Optional[Dict[str, Any]] = None,
    known_facts: Optional[Dict[str, Any]] = None,
    lead_status: Optional[Dict[str, Any]] = None,
    status_catalog: Optional[List[Dict[str, Any]]] = None,
    history_summary: Optional[str] = None,
    business_prompt: Optional[str] = None,
    lead_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Main Decision Engine entry point.
    
    DECIDE → VALIDATE → REPAIR → FALLBACK → RESPOND
    
    Args:
        business_id: Business ID
        channel: "whatsapp" or "call"
        user_message: Customer message
        compiled_logic: Compiled business rules JSON
        known_facts: Known facts about the lead
        lead_status: Current lead status {id, label}
        status_catalog: All statuses for the business
        history_summary: Conversation history summary
        business_prompt: Business system prompt
        lead_id: Lead ID for logging
    
    Returns:
        Validated decision dict
    """
    start_time = time.time()
    lead_status_label = lead_status.get("label") if lead_status else None
    
    # Build context envelope
    constraints = None
    if compiled_logic:
        constraints = compiled_logic.get("constraints")
    
    messages = build_context_envelope(
        channel=channel,
        user_message=user_message,
        compiled_logic=compiled_logic,
        known_facts=known_facts,
        lead_status=lead_status,
        status_catalog=status_catalog,
        history_summary=history_summary,
        business_prompt=business_prompt,
        constraints=constraints
    )
    
    # DECIDE: Call LLM
    decision = None
    try:
        decision = _call_llm_for_decision(messages)
    except Exception as e:
        logger.error(f"[DECISION_ENGINE] ❌ LLM call failed: {e}")
    
    # VALIDATE
    if decision:
        validation = validate_decision(decision)
        if not validation["valid"]:
            logger.warning(f"[DECISION_ENGINE] ⚠️ Invalid decision, attempting repair: {validation['errors']}")
            # REPAIR: One retry
            decision = _repair_decision(messages, decision)
            if decision:
                validation = validate_decision(decision)
                if not validation["valid"]:
                    decision = None
    
    # FALLBACK
    if not decision:
        logger.warning(f"[DECISION_ENGINE] 🔄 Using fallback decision for business {business_id}")
        decision = dict(FALLBACK_DECISION)
    
    # Apply confidence gates
    decision = apply_confidence_gates(decision)
    
    # Apply status enforcement
    decision = apply_status_enforcement(decision, compiled_logic, lead_status_label)
    
    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)
    decision["_latency_ms"] = latency_ms
    
    # Log decision
    _log_decision(
        business_id=business_id,
        lead_id=lead_id,
        channel=channel,
        decision=decision,
        lead_status_label=lead_status_label,
        latency_ms=latency_ms
    )
    
    # Save extracted facts
    if lead_id and decision.get("extracted", {}).get("facts"):
        _save_extracted_facts(
            lead_id=lead_id,
            business_id=business_id,
            facts=decision["extracted"]["facts"],
            confidence=decision.get("confidence", 0.5)
        )
    
    logger.info(
        f"[DECISION_ENGINE] ✅ Decision: action={decision.get('action')}, "
        f"confidence={decision.get('confidence'):.2f}, "
        f"rules={decision.get('rule_hits')}, "
        f"latency={latency_ms}ms"
    )
    
    return decision


def _call_llm_for_decision(messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Call LLM and parse JSON decision"""
    try:
        from openai import OpenAI
        import os
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[DECISION_ENGINE] JSON parse error: {e}")
        return None
    except Exception as e:
        logger.error(f"[DECISION_ENGINE] LLM error: {e}")
        return None


def _repair_decision(original_messages: List[Dict[str, str]], broken_decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Attempt to repair an invalid decision with one retry"""
    try:
        repair_messages = original_messages + [
            {
                "role": "assistant",
                "content": json.dumps(broken_decision, ensure_ascii=False)
            },
            {
                "role": "user",
                "content": "ה-JSON לא תקין. החזר JSON תקין בלבד בפורמט הנדרש. action חייב להיות מהרשימה."
            }
        ]
        return _call_llm_for_decision(repair_messages)
    except Exception as e:
        logger.error(f"[DECISION_ENGINE] Repair failed: {e}")
        return None


def _log_decision(
    business_id: int,
    lead_id: Optional[int],
    channel: str,
    decision: Dict[str, Any],
    lead_status_label: Optional[str],
    latency_ms: int
):
    """Log decision to ai_decisions table"""
    try:
        from server.models_sql import AIDecision
        from server.db import db
        
        proposed = decision.get("proposed_status")
        proposed_label = None
        if isinstance(proposed, dict):
            proposed_label = proposed.get("label")
        
        log_entry = AIDecision(
            business_id=business_id,
            lead_id=lead_id,
            channel=channel,
            action=decision.get("action", "unknown"),
            confidence=decision.get("confidence"),
            rule_hits=decision.get("rule_hits"),
            missing_fields=decision.get("missing"),
            extracted_facts=decision.get("extracted", {}).get("facts"),
            reply=decision.get("reply"),
            latency_ms=latency_ms,
            lead_status_label=lead_status_label,
            proposed_status=proposed_label
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.error(f"[DECISION_ENGINE] Failed to log decision: {e}")
        try:
            from server.db import db
            db.session.rollback()
        except Exception:
            pass


def _save_extracted_facts(
    lead_id: int,
    business_id: int,
    facts: Dict[str, Any],
    confidence: float
):
    """Save extracted facts to lead_facts table"""
    try:
        from server.models_sql import LeadFact
        from server.db import db
        
        for key, value in facts.items():
            if not key or not value:
                continue
            
            # Upsert: update if exists, insert if not
            existing = LeadFact.query.filter_by(lead_id=lead_id, key=key).first()
            if existing:
                existing.value = str(value)
                existing.confidence = confidence
                existing.updated_at = datetime.utcnow()
            else:
                fact = LeadFact(
                    lead_id=lead_id,
                    business_id=business_id,
                    key=key,
                    value=str(value),
                    confidence=confidence,
                    source="ai"
                )
                db.session.add(fact)
        
        db.session.commit()
        logger.info(f"[DECISION_ENGINE] ✅ Saved {len(facts)} facts for lead {lead_id}")
    except Exception as e:
        logger.error(f"[DECISION_ENGINE] Failed to save facts: {e}")
        try:
            from server.db import db
            db.session.rollback()
        except Exception:
            pass


def get_known_facts_for_lead(lead_id: int) -> Dict[str, Any]:
    """Load known facts for a lead from the database"""
    try:
        from server.models_sql import LeadFact
        facts = LeadFact.query.filter_by(lead_id=lead_id).all()
        return {f.key: f.value for f in facts}
    except Exception as e:
        logger.error(f"[DECISION_ENGINE] Error loading facts for lead {lead_id}: {e}")
        return {}


def test_rules_sandbox(
    business_id: int,
    test_message: str,
    compiled_logic: Optional[Dict[str, Any]] = None,
    lead_status_label: Optional[str] = None
) -> Dict[str, Any]:
    """
    Test sandbox: simulate a decision without saving to DB.
    Used in the Studio for business owners to test their rules.
    """
    lead_status = None
    if lead_status_label:
        lead_status = {"id": 0, "label": lead_status_label}
    
    # Get status catalog
    from server.services.rules_compiler import get_status_catalog_for_business
    status_catalog = get_status_catalog_for_business(business_id)
    
    # If no compiled_logic provided, load from business
    if compiled_logic is None:
        try:
            from server.models_sql import Business
            business = Business.query.get(business_id)
            if business and business.ai_logic_compiled:
                compiled_logic = business.ai_logic_compiled
        except Exception:
            pass
    
    # Run decision without DB logging
    start_time = time.time()
    
    constraints = None
    if compiled_logic:
        constraints = compiled_logic.get("constraints")
    
    messages = build_context_envelope(
        channel="test",
        user_message=test_message,
        compiled_logic=compiled_logic,
        known_facts={},
        lead_status=lead_status,
        status_catalog=status_catalog,
        constraints=constraints
    )
    
    decision = _call_llm_for_decision(messages)
    
    if not decision:
        decision = dict(FALLBACK_DECISION)
    else:
        validation = validate_decision(decision)
        if not validation["valid"]:
            decision = dict(FALLBACK_DECISION)
        else:
            decision = apply_confidence_gates(decision)
            decision = apply_status_enforcement(decision, compiled_logic, lead_status_label)
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    return {
        "action": decision.get("action"),
        "confidence": decision.get("confidence"),
        "rule_hits": decision.get("rule_hits"),
        "reply": decision.get("reply"),
        "next_question": decision.get("next_question"),
        "missing": decision.get("missing"),
        "extracted": decision.get("extracted"),
        "proposed_status": decision.get("proposed_status"),
        "latency_ms": latency_ms
    }
