"""
Rules Compiler Service - Compiles Hebrew business logic to structured JSON
═════════════════════════════════════════════════════════════════════════════

Converts free-text Hebrew business rules (written by business owners)
into structured JSON rules that the Decision Engine can execute.

Compilation happens ONCE on save (not per message) for performance.
"""
import json
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Schema for compiled rules
COMPILED_RULES_SCHEMA = {
    "rules": [],           # List of {id, priority, when, action, effects}
    "constraints": {},     # Global constraints (one_question, tone, etc.)
    "entities_schema": {}  # Which fields to extract (generic, not hardcoded)
}

COMPILER_SYSTEM_PROMPT = """אתה מהדר (compiler) שממיר חוקים עסקיים בעברית למבנה JSON מוגדר.

קלט: טקסט חופשי בעברית שמתאר חוקים עסקיים.
פלט: JSON בלבד (ללא טקסט נוסף).

מבנה הפלט:
{
  "rules": [
    {
      "id": "R1",
      "priority": 100,
      "when": {
        "condition": "תיאור התנאי",
        "status_is": [],
        "status_is_not": [],
        "field_exists": [],
        "field_missing": []
      },
      "action": "collect_details|schedule_meeting|ask_clarifying_question|handoff_human|answer_questions|sell_close|service_support|none",
      "effects": {
        "response_mode": "collect|answer_only|sell|service|handoff",
        "allowed_actions": [],
        "block_actions": [],
        "set_status_to": null,
        "next_question": null
      }
    }
  ],
  "constraints": {
    "one_question_at_a_time": true,
    "tone": "professional",
    "language": "hebrew"
  },
  "entities_schema": {
    "fields": [
      {"name": "שם שדה", "type": "string|number|date|boolean", "required": false}
    ]
  }
}

כללים:
1. כל כלל חייב id ייחודי (R1, R2, S1, S2...)
2. כללי סטטוס מתחילים ב-S (S1, S2...)
3. priority: מספר גבוה = עדיפות גבוהה (100 = רגיל, 200 = גבוה)
4. action חייב להיות מהרשימה הקבועה
5. אם יש התייחסות לסטטוס, השתמש ב-status_is / status_is_not
6. חלץ entities_schema מתוך הכללים (אילו שדות העסק מעוניין לאסוף)
7. החזר JSON בלבד, ללא טקסט נוסף!

STATUS_CATALOG_PLACEHOLDER"""

COMPILER_VALIDATION_PROMPT = """בדוק את ה-JSON הבא ותקן שגיאות. החזר JSON תקין בלבד.
אם הכל תקין, החזר את ה-JSON כמו שהוא.
אם יש שגיאות, תקן והחזר JSON תקין."""


def compile_business_rules(
    logic_text: str,
    status_catalog: Optional[List[Dict[str, Any]]] = None,
    business_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Compile Hebrew business logic text into structured JSON rules.
    
    Args:
        logic_text: Free-text Hebrew business rules
        status_catalog: List of business statuses [{id, label, order_index}]
        business_id: Business ID for logging
    
    Returns:
        Dict with keys: success, compiled, error, compile_time_ms
    """
    if not logic_text or not logic_text.strip():
        return {
            "success": False,
            "compiled": None,
            "error": "לא הוזן טקסט חוקים",
            "compile_time_ms": 0
        }
    
    start_time = time.time()
    
    try:
        # Build compiler prompt with status catalog
        system_prompt = COMPILER_SYSTEM_PROMPT
        if status_catalog:
            catalog_text = "\n\nקטלוג סטטוסים של העסק:\n"
            for s in status_catalog:
                catalog_text += f"- id={s.get('id')}, label=\"{s.get('label')}\"\n"
            catalog_text += "\nאם העסק מתייחס לסטטוס שלא קיים ברשימה, החזר שגיאה בפורמט:\n"
            catalog_text += '{"error": "הסטטוס \'X\' לא קיים. הסטטוסים האפשריים: ..."}'
            system_prompt = system_prompt.replace("STATUS_CATALOG_PLACEHOLDER", catalog_text)
        else:
            system_prompt = system_prompt.replace("STATUS_CATALOG_PLACEHOLDER", "")
        
        # Call LLM for compilation
        from openai import OpenAI
        import os
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"הידור החוקים הבאים:\n\n{logic_text}"}
            ],
            temperature=0.0,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        raw_output = response.choices[0].message.content.strip()
        compile_time_ms = int((time.time() - start_time) * 1000)
        
        # Parse JSON output
        try:
            compiled = json.loads(raw_output)
        except json.JSONDecodeError as e:
            logger.error(f"[RULES_COMPILER] JSON parse error: {e}")
            return {
                "success": False,
                "compiled": None,
                "error": f"שגיאה בפענוח תוצאת ההידור: {str(e)}",
                "compile_time_ms": compile_time_ms
            }
        
        # Check for compiler-reported errors
        if "error" in compiled and isinstance(compiled["error"], str):
            return {
                "success": False,
                "compiled": None,
                "error": compiled["error"],
                "compile_time_ms": compile_time_ms
            }
        
        # Validate compiled structure
        validation_result = validate_compiled_rules(compiled)
        if not validation_result["valid"]:
            return {
                "success": False,
                "compiled": compiled,
                "error": validation_result["error"],
                "compile_time_ms": compile_time_ms
            }
        
        # Validate status references against catalog
        if status_catalog:
            status_error = validate_status_references(compiled, status_catalog)
            if status_error:
                return {
                    "success": False,
                    "compiled": None,
                    "error": status_error,
                    "compile_time_ms": compile_time_ms
                }
        
        logger.info(f"[RULES_COMPILER] ✅ Compiled {len(compiled.get('rules', []))} rules for business {business_id} in {compile_time_ms}ms")
        
        return {
            "success": True,
            "compiled": compiled,
            "error": None,
            "compile_time_ms": compile_time_ms
        }
        
    except Exception as e:
        compile_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[RULES_COMPILER] ❌ Compilation failed for business {business_id}: {e}", exc_info=True)
        return {
            "success": False,
            "compiled": None,
            "error": f"שגיאה בהידור: {str(e)}",
            "compile_time_ms": compile_time_ms
        }


def validate_compiled_rules(compiled: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the structure of compiled rules"""
    if not isinstance(compiled, dict):
        return {"valid": False, "error": "תוצאת ההידור אינה מבנה תקין"}
    
    # Must have rules array
    rules = compiled.get("rules")
    if rules is None:
        return {"valid": False, "error": "חסר שדה 'rules' בתוצאת ההידור"}
    
    if not isinstance(rules, list):
        return {"valid": False, "error": "שדה 'rules' חייב להיות רשימה"}
    
    # Validate each rule
    valid_actions = {
        "collect_details", "schedule_meeting", "ask_clarifying_question",
        "handoff_human", "answer_questions", "sell_close", "service_support", "none"
    }
    
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            return {"valid": False, "error": f"כלל {i+1} אינו מבנה תקין"}
        
        if "id" not in rule:
            return {"valid": False, "error": f"כלל {i+1} חסר שדה 'id'"}
        
        action = rule.get("action")
        if action and action not in valid_actions:
            return {"valid": False, "error": f"כלל {rule.get('id')}: פעולה '{action}' לא מוכרת. פעולות אפשריות: {', '.join(valid_actions)}"}
    
    return {"valid": True, "error": None}


def validate_status_references(compiled: Dict[str, Any], status_catalog: List[Dict[str, Any]]) -> Optional[str]:
    """Validate that all status references in rules exist in the catalog"""
    catalog_labels = {s.get("label", "").strip() for s in status_catalog}
    
    for rule in compiled.get("rules", []):
        when = rule.get("when", {})
        if not isinstance(when, dict):
            continue
        
        for status_ref in when.get("status_is", []):
            if status_ref.strip() not in catalog_labels:
                available = ", ".join(sorted(catalog_labels))
                return f"הסטטוס '{status_ref}' לא קיים. הסטטוסים האפשריים: {available}"
        
        for status_ref in when.get("status_is_not", []):
            if status_ref.strip() not in catalog_labels:
                available = ", ".join(sorted(catalog_labels))
                return f"הסטטוס '{status_ref}' לא קיים. הסטטוסים האפשריים: {available}"
    
    return None


def get_status_catalog_for_business(business_id: int) -> List[Dict[str, Any]]:
    """Load status catalog for a business"""
    try:
        from server.models_sql import LeadStatus
        statuses = LeadStatus.query.filter_by(
            business_id=business_id,
            is_active=True
        ).order_by(LeadStatus.order_index).all()
        
        return [
            {"id": s.id, "label": s.label, "name": s.name, "order_index": s.order_index}
            for s in statuses
        ]
    except Exception as e:
        logger.error(f"[RULES_COMPILER] Error loading status catalog for business {business_id}: {e}")
        return []
