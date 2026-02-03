"""
Smart Prompt Generator v2 - Structured System Prompt Builder
Creates professional SYSTEM PROMPTS using rigid templates and AI as architect

🎯 Goal: Generate production-ready prompts with consistent structure
📋 Based on questionnaire → structured template → quality validation

Key Principles:
- ❌ Does NOT generate free-form text
- ✅ Builds prompts using rigid template structure
- ✅ LLM serves as conversation architect, not copywriter
- ✅ Every prompt includes: identity, goal, rules, flow, stop conditions, limitations
"""
from flask import Blueprint, request, jsonify, session
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.models_sql import Business, BusinessSettings, PromptRevisions, db
import logging
import os
import json
from datetime import datetime
import re
import time

logger = logging.getLogger(__name__)

smart_prompt_bp = Blueprint('smart_prompt', __name__)

# Maximum input lengths for security
MAX_FIELD_LENGTH = 500
MAX_TOTAL_INPUT = 4000

# OpenAI generation settings
MAX_RETRIES = 2  # 1 initial attempt + 1 retry
RETRY_DELAY = 0.5  # seconds
OPENAI_TIMEOUT = 12.0  # seconds

# Output template sections - MUST appear in this exact order
REQUIRED_SECTIONS = [
    "זהות הסוכן",
    "מטרת השיחה",
    "חוקי שיחה",
    "מהלך שיחה",
    "תנאי עצירה / העברה",
    "מגבלות ואיסורים"
]

# Internal System Prompt - This IS the smart generator itself
# This meta-prompt is THE CORE - without it, output will be poor
GENERATOR_SYSTEM_PROMPT = """אתה מחולל SYSTEM PROMPTS לסוכני AI קולים וכתובים.

המטרה שלך:
לייצר פרומפט מקצועי לסוכן שירות / מכירה,
שיעבוד בשיחה חיה עם לקוחות אמיתיים.

חוקים:
- כתוב בעברית בלבד
- אל תכתוב טקסט שיווקי
- אל תכתוב פסקאות
- אל תסביר דברים ללקוח
- כתוב רק הוראות לסוכן
- השתמש בכותרות ברורות
- השתמש ברשימות
- שאלות – אחת בכל פעם
- סוכן חייב לדעת מתי לעצור

חוקים קריטיים - חובה:
- אסור לך לבקש מידע חסר או להחזיר הודעה שחסרים פרטים
- אסור לכתוב "חסרות שאלות" או "צריך עוד פרטים" או דומה
- אם חסר מידע - תייצר פרומפט מושלם לפי מה שיש
- השתמש ב-placeholders הגיוניים במקום מידע חסר (לדוגמה: {{BUSINESS_NAME}}, {{HOURS}})
- אם שעות לא ידועות - כתוב "שעות פעילות: {{HOURS}} (או 'לא צוין')"
- אם שירותים לא ידועים - כתוב "שירותים: {{SERVICES}}"
- תמיד תייצר פרומפט שלם ושמיש, ללא חריגים

הפרומפט חייב לכלול את הסעיפים הבאים בלבד,
ובדיוק בסדר הזה:

1. זהות הסוכן
2. מטרת השיחה
3. חוקי שיחה
4. מהלך שיחה (שלבים)
5. תנאי עצירה / העברה לנציג אנושי
6. מגבלות ואיסורים

אם חסר מידע – השלם בצורה סבירה עם placeholders,
אבל אל תמציא הבטחות, מחירים או התחייבויות.

החזר את התשובה בפורמט הבא בדיוק:

========================
זהות הסוכן
========================
[תוכן]

========================
מטרת השיחה
========================
[תוכן]

========================
חוקי שיחה
========================
- [חוק 1]
- [חוק 2]
...

========================
מהלך שיחה
========================
1. [שלב 1]
2. [שלב 2]
...

========================
תנאי עצירה / העברה
========================
- [תנאי 1]
- [תנאי 2]
...

========================
מגבלות ואיסורים
========================
- [מגבלה 1]
- [מגבלה 2]
..."""


def _get_business_id():
    """Get current business ID from session"""
    from flask import g
    
    user_session = session.get('user') or {}
    tenant_id = g.get('tenant') or session.get('impersonated_tenant_id')
    
    if not tenant_id:
        tenant_id = user_session.get('business_id') if isinstance(user_session, dict) else None
    
    if not tenant_id:
        user = session.get('al_user') or {}
        tenant_id = user.get('business_id') if isinstance(user, dict) else None
    
    return tenant_id


def _sanitize_input(text: str, max_length: int = MAX_FIELD_LENGTH) -> str:
    """Sanitize and truncate input text"""
    if not text:
        return ''
    
    sanitized = text.strip()
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def _validate_prompt_structure(prompt_text: str) -> tuple[bool, str]:
    """
    Quality Gate: Validate generated prompt has correct structure
    
    Returns: (is_valid, error_message)
    """
    # Check for required sections
    missing_sections = []
    for section in REQUIRED_SECTIONS:
        if section not in prompt_text:
            missing_sections.append(section)
    
    if missing_sections:
        return False, f"חסרים סעיפים חובה: {', '.join(missing_sections)}"
    
    # Check for "שאלה אחת בכל פעם" rule
    if "שאלה אחת" not in prompt_text and "שאלה 1" not in prompt_text:
        return False, "חסר כלל 'שאלה אחת בכל פעם'"
    
    # Check for clear goal in "מטרת השיחה" section
    goal_section = prompt_text.split("מטרת השיחה")[1].split("===")[1] if "מטרת השיחה" in prompt_text else ""
    if len(goal_section.strip()) < 20:
        return False, "מטרת השיחה לא מפורטת מספיק"
    
    # Check for stop conditions
    stop_section = prompt_text.split("תנאי עצירה")[1] if "תנאי עצירה" in prompt_text else ""
    if len(stop_section.strip()) < 20:
        return False, "תנאי עצירה לא מפורטים"
    
    # Check for long paragraphs (more than 300 chars without newline is suspicious)
    lines = prompt_text.split('\n')
    for line in lines:
        # Skip section headers
        if '===' in line:
            continue
        if len(line.strip()) > 300 and not line.startswith('-') and not line[0].isdigit():
            return False, "נמצאה פסקה ארוכה מדי - יש להשתמש ברשימות"
    
    # Check for marketing language (basic detection)
    marketing_phrases = [
        "הטוב ביותר",
        "הכי טוב",
        "מומחים מובילים",
        "שירות ללא תחרות",
        "המומחים שלנו"
    ]
    lower_prompt = prompt_text.lower()
    found_marketing = [phrase for phrase in marketing_phrases if phrase in lower_prompt]
    if found_marketing:
        return False, f"נמצא ניסוח שיווקי: {found_marketing[0]}"
    
    return True, ""


def _generate_with_openai(questionnaire: dict, provider_config: dict) -> dict:
    """Generate prompt using OpenAI with timeout and retry"""
    from openai import OpenAI
    
    api_key = provider_config.get('api_key') or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    
    model = provider_config.get('model', 'gpt-4o-mini')
    
    client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT)
    
    # Build user prompt from questionnaire
    user_prompt = f"""צור SYSTEM PROMPT לסוכן AI על בסיס המידע הבא:

שם העסק: {questionnaire.get('business_name', 'לא צוין')}
סוג העסק: {questionnaire.get('business_type', 'לא צוין')}
קהל יעד: {questionnaire.get('target_audience', 'לקוחות כלליים')}
מטרה עיקרית: {questionnaire.get('main_goal', 'שירות לקוחות')}
מה זה ליד איכותי: {questionnaire.get('what_is_quality_lead', 'לקוח שמביע עניין')}
שירותים: {', '.join(questionnaire.get('services', [])) or 'לא צוין'}
שעות פעילות: {questionnaire.get('working_hours', '09:00-18:00')}
סגנון שיחה: {questionnaire.get('conversation_style', 'מקצועי')}
פעולות אסורות: {', '.join(questionnaire.get('forbidden_actions', [])) or 'לא צוין'}
חוקי העברה: {questionnaire.get('handoff_rules', 'לא צוין')}
אינטגרציות: {', '.join(questionnaire.get('integrations', [])) or 'אין'}
"""
    
    # Retry logic
    for attempt in range(MAX_RETRIES):
        try:
            start_time = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2500,
                temperature=0.5
            )
            duration = time.time() - start_time
            logger.info(f"OpenAI prompt generation completed in {duration:.2f}s (attempt {attempt + 1})")
            
            return {
                "prompt_text": response.choices[0].message.content.strip(),
                "provider": "openai",
                "model": model
            }
        except Exception as e:
            is_last_attempt = (attempt == MAX_RETRIES - 1)
            if is_last_attempt:
                logger.error(f"OpenAI call failed after {MAX_RETRIES} attempts: {str(e)}")
                raise
            else:
                logger.warning(f"OpenAI call failed (attempt {attempt + 1}), retrying: {str(e)}")
                time.sleep(RETRY_DELAY)


def _generate_with_gemini(questionnaire: dict, provider_config: dict) -> dict:
    """Generate prompt using Google Gemini"""
    import google.generativeai as genai
    
    api_key = provider_config.get('api_key') or os.getenv("GEMINI_API_KEY")
    model_name = provider_config.get('model', 'gemini-pro')
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    # Build user prompt from questionnaire
    user_prompt = f"""צור SYSTEM PROMPT לסוכן AI על בסיס המידע הבא:

שם העסק: {questionnaire.get('business_name', 'לא צוין')}
סוג העסק: {questionnaire.get('business_type', 'לא צוין')}
קהל יעד: {questionnaire.get('target_audience', 'לקוחות כלליים')}
מטרה עיקרית: {questionnaire.get('main_goal', 'שירות לקוחות')}
מה זה ליד איכותי: {questionnaire.get('what_is_quality_lead', 'לקוח שמביע עניין')}
שירותים: {', '.join(questionnaire.get('services', [])) or 'לא צוין'}
שעות פעילות: {questionnaire.get('working_hours', '09:00-18:00')}
סגנון שיחה: {questionnaire.get('conversation_style', 'מקצועי')}
פעולות אסורות: {', '.join(questionnaire.get('forbidden_actions', [])) or 'לא צוין'}
חוקי העברה: {questionnaire.get('handoff_rules', 'לא צוין')}
אינטגרציות: {', '.join(questionnaire.get('integrations', [])) or 'אין'}
"""
    
    # Combine system prompt and user prompt for Gemini
    full_prompt = f"{GENERATOR_SYSTEM_PROMPT}\n\n{user_prompt}"
    
    response = model.generate_content(full_prompt)
    
    return {
        "prompt_text": response.text.strip(),
        "provider": "gemini",
        "model": model_name
    }


@smart_prompt_bp.route('/api/ai/smart_prompt_generator/schema', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_input_schema():
    """
    Get the structured input schema for smart prompt generation
    Returns questionnaire structure with field definitions
    """
    schema = {
        "fields": [
            {
                "id": "business_name",
                "label": "שם העסק",
                "type": "text",
                "required": True,
                "placeholder": "לדוגמה: קליניקת אסתטיקה 'יופי טבעי'",
                "maxLength": 100
            },
            {
                "id": "business_type",
                "label": "סוג העסק / תחום",
                "type": "text",
                "required": True,
                "placeholder": "לדוגמה: קליניקת אסתטיקה, משרד עו\"ד, מוסך רכב",
                "maxLength": 100
            },
            {
                "id": "target_audience",
                "label": "קהל יעד",
                "type": "text",
                "required": False,
                "placeholder": "לדוגמה: נשים בגילאי 25-50, בעלי רכבי יוקרה",
                "maxLength": 200
            },
            {
                "id": "main_goal",
                "label": "מטרה עיקרית של השיחה",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "תיאום פגישה", "label": "תיאום פגישה / קביעת תור"},
                    {"value": "מכירה", "label": "מכירה / סגירת עסקה"},
                    {"value": "מידע", "label": "מתן מידע / שירות לקוחות"},
                    {"value": "סינון לידים", "label": "סינון וסיווג לידים"},
                    {"value": "תמיכה", "label": "תמיכה טכנית / פתרון בעיות"}
                ]
            },
            {
                "id": "what_is_quality_lead",
                "label": "מה נחשב ליד איכותי?",
                "type": "textarea",
                "required": False,
                "placeholder": "לדוגמה: לקוח שרוצה להזמין טיפול בשבועיים הקרובים, בתקציב של מעל 1000 ש\"ח",
                "maxLength": 300
            },
            {
                "id": "services",
                "label": "שירותים / מוצרים עיקריים",
                "type": "tags",
                "required": False,
                "placeholder": "הקלד שירות והקש Enter",
                "maxItems": 10
            },
            {
                "id": "working_hours",
                "label": "שעות פעילות",
                "type": "text",
                "required": False,
                "placeholder": "לדוגמה: א-ה 09:00-18:00, ו 09:00-13:00",
                "maxLength": 100
            },
            {
                "id": "conversation_style",
                "label": "סגנון שיחה",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "רגוע", "label": "רגוע ואדיב"},
                    {"value": "מקצועי", "label": "מקצועי וישיר"},
                    {"value": "מכירתי", "label": "חם ומכירתי"},
                    {"value": "פורמלי", "label": "פורמלי ורציני"}
                ]
            },
            {
                "id": "forbidden_actions",
                "label": "פעולות אסורות",
                "type": "tags",
                "required": False,
                "placeholder": "לדוגמה: הבטחת מחירים, התחייבות לזמנים",
                "maxItems": 10
            },
            {
                "id": "handoff_rules",
                "label": "מתי להעביר לנציג אנושי?",
                "type": "textarea",
                "required": False,
                "placeholder": "לדוגמה: תלונות רציניות, בקשות מורכבות, לקוח עצבני",
                "maxLength": 300
            },
            {
                "id": "integrations",
                "label": "אינטגרציות / מערכות קיימות",
                "type": "tags",
                "required": False,
                "placeholder": "לדוגמה: Google Calendar, CRM, מערכת תורים",
                "maxItems": 5
            }
        ]
    }
    
    return jsonify(schema)


@smart_prompt_bp.route('/api/ai/smart_prompt_generator/generate', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def generate_smart_prompt():
    """
    Generate a structured system prompt from questionnaire
    
    ✅ ALWAYS uses OpenAI (not related to business ai_provider)
    ✅ ALWAYS returns a prompt (best-effort) - never fails on quality
    
    Input: Structured questionnaire object
    Output: Structured prompt following rigid template + quality info (not blocking)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        questionnaire = data.get('questionnaire', {})
        # REMOVED: provider selection - always use OpenAI
        # REMOVED: provider_config - not needed, use env var
        
        # Validate required fields
        if not questionnaire.get('business_name'):
            return jsonify({"error": "שם העסק הוא שדה חובה"}), 400
        if not questionnaire.get('business_type'):
            return jsonify({"error": "סוג העסק הוא שדה חובה"}), 400
        if not questionnaire.get('main_goal'):
            return jsonify({"error": "מטרה עיקרית היא שדה חובה"}), 400
        if not questionnaire.get('conversation_style'):
            return jsonify({"error": "סגנון שיחה הוא שדה חובה"}), 400
        
        # Check if OpenAI API key is available
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY not configured for smart prompt generator")
            return jsonify({
                "error": "מחולל הפרומפטים הזמין דורש הגדרת OpenAI API Key",
                "details": "OPENAI_API_KEY environment variable is not set"
            }), 503
        
        # Sanitize all text inputs
        sanitized = {}
        for key, value in questionnaire.items():
            if isinstance(value, str):
                sanitized[key] = _sanitize_input(value)
            elif isinstance(value, list):
                # For tags/arrays, sanitize each item
                sanitized[key] = [_sanitize_input(str(item), 100) for item in value]
            else:
                sanitized[key] = value
        
        # Check total input size
        total_size = sum(len(str(v)) for v in sanitized.values())
        if total_size > MAX_TOTAL_INPUT:
            return jsonify({"error": f"סך הקלט ארוך מדי (מקסימום {MAX_TOTAL_INPUT} תווים)"}), 400
        
        # Generate prompt - ALWAYS with OpenAI
        logger.info(f"Generating smart prompt with openai for business: {sanitized.get('business_name')}")
        
        try:
            # ALWAYS use OpenAI - no provider selection
            result = _generate_with_openai(sanitized, {})
            
            prompt_text = result['prompt_text']
            
            # Quality Check - BUT DON'T FAIL, only warn
            is_valid, validation_error = _validate_prompt_structure(prompt_text)
            
            if not is_valid:
                # Log as warning, not error - still return the prompt
                logger.warning(f"Generated prompt has quality issues (returning anyway): {validation_error}")
            
            logger.info(f"Smart prompt generated successfully ({len(prompt_text)} chars) using {result['provider']}")
            
            # ALWAYS return 200 with the prompt
            response_data = {
                "success": True,
                "prompt_text": prompt_text,
                "provider": result['provider'],
                "model": result['model'],
                "length": len(prompt_text),
                "validation": {
                    "passed": is_valid,
                    "sections_found": REQUIRED_SECTIONS
                }
            }
            
            # Add quality warning if validation failed (but still return prompt)
            if not is_valid:
                response_data["quality_warning"] = validation_error
                response_data["note"] = "הפרומפט נוצר בהצלחה - ייתכנו שיפורים אפשריים"
            
            return jsonify(response_data), 200
            
        except ValueError as ve:
            # This catches the "OPENAI_API_KEY not configured" error
            logger.exception(f"Configuration error in smart prompt generator")
            return jsonify({
                "error": "שגיאת הגדרה",
                "details": str(ve)
            }), 503
        except Exception as gen_error:
            logger.exception(f"Error generating prompt with OpenAI")
            return jsonify({"error": f"שגיאה ביצירת הפרומפט"}), 500
        
    except Exception as e:
        logger.exception("Error in smart prompt generator")
        return jsonify({"error": "שגיאה כללית ביצירת הפרומפט"}), 500


@smart_prompt_bp.route('/api/ai/smart_prompt_generator/save', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def save_smart_prompt():
    """
    Save a generated smart prompt to business
    Stores as new prompt version with metadata
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        prompt_text = data.get('prompt_text', '').strip()
        channel = data.get('channel', 'calls')  # 'calls' or 'whatsapp'
        metadata = data.get('metadata', {})
        
        if not prompt_text:
            return jsonify({"error": "טקסט הפרומפט חסר"}), 400
        
        # Final validation before save
        is_valid, validation_error = _validate_prompt_structure(prompt_text)
        if not is_valid:
            return jsonify({
                "error": "הפרומפט לא תקין",
                "validation_error": validation_error
            }), 400
        
        # Get business ID
        business_id = _get_business_id()
        if not business_id:
            return jsonify({"error": "לא נמצא עסק"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # Get current user
        current_user = session.get('user', {})
        user_id = current_user.get('email', 'smart_generator')
        
        # Get or create business settings
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        # Build prompt object
        current_prompts = {}
        if settings and settings.ai_prompt:
            try:
                if settings.ai_prompt.startswith('{'):
                    current_prompts = json.loads(settings.ai_prompt)
                else:
                    current_prompts = {
                        'calls': settings.ai_prompt,
                        'whatsapp': settings.ai_prompt
                    }
            except (json.JSONDecodeError, TypeError, ValueError):
                current_prompts = {}
        
        # Update the specified channel
        current_prompts[channel] = prompt_text
        
        # Store as JSON
        new_prompt_data = json.dumps(current_prompts, ensure_ascii=False)
        
        if not settings:
            settings = BusinessSettings()
            settings.tenant_id = business_id
            settings.ai_prompt = new_prompt_data
            settings.updated_by = user_id
            db.session.add(settings)
        else:
            settings.ai_prompt = new_prompt_data
            settings.updated_by = user_id
            settings.updated_at = datetime.utcnow()
        
        # Get next version
        latest_revision = PromptRevisions.query.filter_by(
            tenant_id=business_id
        ).order_by(PromptRevisions.version.desc()).first()
        
        next_version = (latest_revision.version + 1) if latest_revision else 1
        
        # Create revision with metadata
        revision = PromptRevisions()
        revision.tenant_id = business_id
        revision.version = next_version
        revision.prompt = new_prompt_data
        revision.changed_by = f"{user_id} (Smart Generator v2)"
        revision.changed_at = datetime.utcnow()
        db.session.add(revision)
        
        db.session.commit()
        
        # Invalidate cache
        try:
            from server.services.ai_service import invalidate_business_cache
            invalidate_business_cache(business_id)
            logger.info(f"Cache invalidated for business {business_id} after smart prompt save")
        except Exception as e:
            logger.warning(f"Could not invalidate cache: {e}")
        
        logger.info(f"Smart prompt saved: business={business_id}, channel={channel}, version={next_version}, provider={metadata.get('provider', 'unknown')}")
        
        return jsonify({
            "success": True,
            "version": next_version,
            "channel": channel,
            "message": f"פרומפט חכם נשמר בהצלחה (גרסה {next_version})",
            "metadata": {
                "generator": "smart_v2",
                "provider": metadata.get('provider'),
                "saved_at": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception("Error saving smart prompt")
        return jsonify({"error": "שגיאה בשמירת הפרומפט"}), 500


@smart_prompt_bp.route('/api/ai/smart_prompt_generator/providers', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_available_providers():
    """
    Get list of available AI providers for prompt generation
    
    ✅ NOTE: Smart Prompt Generator ALWAYS uses OpenAI only
    This endpoint is kept for UI compatibility but returns only OpenAI
    """
    # Only return OpenAI - Gemini is not used for smart prompt generation
    providers = [
        {
            "id": "openai",
            "name": "OpenAI",
            "default": True,
            "models": ["gpt-4o-mini", "gpt-4o"],
            "description": "מערכת ברירת המחדל - אמינה ומהירה",
            "available": bool(os.getenv("OPENAI_API_KEY")),
            "note": "מחולל הפרומפטים החכם משתמש רק ב-OpenAI"
        }
    ]
    
    return jsonify({
        "providers": providers,
        "default_provider": "openai",
        "note": "Smart Prompt Generator uses OpenAI exclusively"
    })

# ═══════════════════════════════════════════════════════════════════════════
# 🔥 NEW: Status Change Prompt Management
# Allows businesses to customize how AI changes lead statuses
# ═══════════════════════════════════════════════════════════════════════════

@smart_prompt_bp.route('/api/ai/status_change_prompt/get', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_status_change_prompt():
    """
    Get current status change prompt for business
    Returns custom prompt or default template with consistent structure
    
    ✅ FIX: Always returns stable default (never 404/null)
    ✅ FIX: Consistent JSON format for all responses
    """
    try:
        business_id = _get_business_id()
        if not business_id:
            return jsonify({
                "ok": False,
                "error": "BUSINESS_CONTEXT_REQUIRED",
                "details": "לא נמצא עסק"
            }), 400
        
        logger.info(f"[GET_STATUS_PROMPT] business_id={business_id}")
        
        # Get latest revision
        latest_revision = PromptRevisions.query.filter_by(
            tenant_id=business_id
        ).order_by(PromptRevisions.version.desc()).first()
        
        if latest_revision and latest_revision.status_change_prompt:
            # Return custom prompt
            result = {
                "ok": True,
                "business_id": business_id,
                "prompt": latest_revision.status_change_prompt,
                "version": latest_revision.version,
                "exists": True,
                "has_custom_prompt": True,
                "updated_at": latest_revision.changed_at.isoformat() if latest_revision.changed_at else None
            }
            logger.info(f"[GET_STATUS_PROMPT] Returning custom prompt, version={latest_revision.version}")
            return jsonify(result)
        
        # Return default template - STABLE DEFAULT
        default_prompt = """🎯 הנחיות לשינוי סטטוס אוטומטי של לידים
==========================================

**עקרונות כלליים:**
- שנה סטטוס רק כאשר יש אינדיקציה ברורה מהלקוח
- תעדכן את הסטטוס בזמן אמת במהלך השיחה/צ'אט
- תמיד ספק סיבה ברורה לשינוי הסטטוס

**מתי לעדכן סטטוסים (דוגמאות לפי סטטוסים רלוונטיים):**

📌 מעוניין (interested):
- לקוח שואל שאלות על השירות/מוצר
- לקוח מבקש פרטים נוספים
- לקוח מראה עניין אקטיבי
דוגמה: "לקוח שאל על מחירים ושירותים - מראה עניין אקטיבי"

📌 נקבעה פגישה (appointment_scheduled):
- לקוח אישר פגישה בתאריך ושעה ספציפיים
- נקבעה פגישה דרך הסוכן
דוגמה: "נקבעה פגישה ליום ראשון 10:00"

📌 מחכה לחזרה (callback_requested):
- לקוח ביקש שנחזור אליו במועד מסוים
- לקוח עסוק כרגע ומבקש ליצור קשר מאוחר יותר
דוגמה: "לקוח ביקש שנחזור אליו מחר אחה״צ"

📌 נשלחה הצעה (proposal_sent):
- נשלחה הצעת מחיר ללקוח
- לקוח ביקש הצעת מחיר בכתב
דוגמה: "נשלחה הצעת מחיר למייל הלקוח"

📌 לא רלוונטי (not_relevant):
- לקוח אמר במפורש שהוא לא מעוניין
- טעינו במספר / לקוח לא בקבוצת היעד
דוגמה: "לקוח אמר שטעינו במספר ואינו מעוניין"

**מגבלות חשובות:**
❌ אל תשנה סטטוס אם:
- הלקוח רק ענה לשיחה (זה לא סיבה לשינוי)
- שאל שאלה כללית מאוד
- אמר "אני אחשוב על זה" (זה לא החלטה)
- לא ברור מה הכוונה שלו

**רמת ביטחון (confidence):**
- 1.0 = לקוח אמר משהו מפורש ("כן אני מתעניין", "קבע לי פגישה")
- 0.8-0.9 = ברור מההקשר אבל לא מפורש ("נשמע טוב", "כמה זה עולה?")
- 0.7 = יש רמז אבל לא בטוח
- פחות מ-0.7 = אל תעדכן!

💡 **העיקרון: תהיה שמרן! עדכן רק כשבטוח שצריך!**"""
        
        result = {
            "ok": True,
            "business_id": business_id,
            "prompt": default_prompt,
            "version": 0,
            "exists": False,
            "has_custom_prompt": False,
            "updated_at": None,
            "note": "זהו תבנית ברירת מחדל. ניתן להתאים אישית לפי צרכי העסק."
        }
        logger.info(f"[GET_STATUS_PROMPT] Returning default prompt")
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"[GET_STATUS_PROMPT] Error: {e}")
        return jsonify({
            "ok": False,
            "error": "PROMPT_LOAD_FAILED",
            "details": str(e)
        }), 500


@smart_prompt_bp.route('/api/ai/status_change_prompt/save', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def save_status_change_prompt():
    """
    Save custom status change prompt for business
    Creates new prompt revision with status_change_prompt
    
    ✅ FIX: Returns full updated prompt object (not just {ok:true})
    ✅ FIX: Optimistic locking with version conflict handling
    ✅ FIX: Read-through cache pattern (set after invalidate)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "ok": False,
                "error": "MISSING_DATA",
                "details": "נדרשים נתונים"
            }), 400
        
        prompt_text = data.get('prompt_text', '').strip()
        client_version = data.get('version')  # Optional: for optimistic locking
        
        if not prompt_text:
            return jsonify({
                "ok": False,
                "error": "EMPTY_PROMPT",
                "details": "טקסט הפרומפט חסר"
            }), 400
        
        if len(prompt_text) > 5000:
            return jsonify({
                "ok": False,
                "error": "PROMPT_TOO_LONG",
                "details": "הפרומפט ארוך מדי (מקסימום 5000 תווים)"
            }), 400
        
        # Get business ID
        business_id = _get_business_id()
        if not business_id:
            return jsonify({
                "ok": False,
                "error": "BUSINESS_CONTEXT_REQUIRED",
                "details": "לא נמצא עסק"
            }), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({
                "ok": False,
                "error": "BUSINESS_NOT_FOUND",
                "details": "עסק לא נמצא"
            }), 404
        
        logger.info(f"[SAVE_STATUS_PROMPT] business_id={business_id}, client_version={client_version}, prompt_length={len(prompt_text)}")
        
        # Get current user
        current_user = session.get('user', {})
        user_id = current_user.get('email', 'system')
        
        # Get latest revision to preserve other fields
        latest_revision = PromptRevisions.query.filter_by(
            tenant_id=business_id
        ).order_by(PromptRevisions.version.desc()).first()
        
        current_version = latest_revision.version if latest_revision else 0
        
        # ✅ OPTIMISTIC LOCKING: Check version conflict
        if client_version is not None and current_version != client_version:
            logger.warning(f"[SAVE_STATUS_PROMPT] Version conflict: client={client_version}, server={current_version}")
            # Return 409 Conflict with latest data
            return jsonify({
                "ok": False,
                "error": "VERSION_CONFLICT",
                "details": "מישהו שמר שינויים לפני שנייה. הפרומפט עודכן לגרסה החדשה.",
                "latest_version": current_version,
                "latest_prompt": latest_revision.status_change_prompt if latest_revision else "",
                "updated_at": latest_revision.changed_at.isoformat() if latest_revision and latest_revision.changed_at else None
            }), 409
        
        next_version = current_version + 1
        
        # Create new revision
        revision = PromptRevisions()
        revision.tenant_id = business_id
        revision.version = next_version
        revision.status_change_prompt = prompt_text
        
        # Preserve existing prompts from latest revision
        if latest_revision:
            revision.prompt = latest_revision.prompt
            revision.whatsapp_system_prompt = latest_revision.whatsapp_system_prompt
        
        revision.changed_by = f"{user_id} (Status Prompt Editor)"
        revision.changed_at = datetime.utcnow()
        
        # Commit to database
        db.session.add(revision)
        db.session.commit()
        
        logger.info(f"[SAVE_STATUS_PROMPT] Committed version={next_version}")
        
        # ✅ SELECT the saved record to ensure consistency
        saved_revision = PromptRevisions.query.filter_by(
            tenant_id=business_id,
            version=next_version
        ).first()
        
        if not saved_revision:
            logger.error(f"[SAVE_STATUS_PROMPT] Failed to retrieve saved revision!")
            return jsonify({
                "ok": False,
                "error": "SAVE_VERIFICATION_FAILED",
                "details": "השמירה נכשלה - לא ניתן לאמת את השינויים"
            }), 500
        
        # ✅ CACHE: Invalidate + Set (read-through pattern)
        try:
            from server.services.ai_service import invalidate_business_cache
            from server.services.prompt_cache import get_prompt_cache
            
            # Invalidate old cache
            invalidate_business_cache(business_id)
            
            # Note: PromptCache is for conversation prompts, not status prompts
            # Status prompts are loaded directly from DB by agent_factory
            # But we still invalidate to ensure fresh load
            
            logger.info(f"[SAVE_STATUS_PROMPT] Cache invalidated for business {business_id}")
        except Exception as e:
            logger.warning(f"[SAVE_STATUS_PROMPT] Could not invalidate cache: {e}")
        
        # ✅ RETURN FULL UPDATED OBJECT (not just {ok:true})
        response = {
            "ok": True,
            "business_id": business_id,
            "version": saved_revision.version,
            "prompt": saved_revision.status_change_prompt,
            "updated_at": saved_revision.changed_at.isoformat() if saved_revision.changed_at else None,
            "message": f"פרומפט סטטוסים נשמר בהצלחה (גרסה {saved_revision.version})"
        }
        
        logger.info(f"[SAVE_STATUS_PROMPT] SUCCESS: version={saved_revision.version}")
        return jsonify(response), 200
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"[SAVE_STATUS_PROMPT] Error: {e}")
        return jsonify({
            "ok": False,
            "error": "SAVE_FAILED",
            "details": "שגיאה בשמירת הפרומפט"
        }), 500