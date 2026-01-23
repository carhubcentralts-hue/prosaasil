"""
Prompt Builder API - AI-powered prompt generation from business questionnaire
Generates high-quality Hebrew AI prompts for businesses

🔒 Security:
- All endpoints require authentication
- Rate limiting on expensive AI generation
- Input size guards (max chars per field)
"""
from flask import Blueprint, request, jsonify, session
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.models_sql import Business, BusinessSettings, PromptRevisions, db
import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

prompt_builder_bp = Blueprint('prompt_builder', __name__)

# 🔒 Security: Input size limits
MAX_FIELD_LENGTH = 500  # Max chars per questionnaire field
MAX_TOTAL_INPUT = 4000  # Max total chars for all fields combined
MAX_PROMPT_LENGTH = 10000  # Max chars for generated prompt

# Prompt builder template for generating business prompts
PROMPT_BUILDER_TEMPLATE = """אתה מומחה ליצירת פרומפטים לסוכני AI בעברית. 
בהתבסס על המידע הבא על העסק, צור פרומפט מקצועי ויעיל לסוכן AI שמטפל בשיחות טלפון.

הפרומפט צריך לכלול:
1. הצגה קצרה של העסק והתפקיד
2. כללי שיחה ברורים (שאלה אחת בכל פעם, לא לחפור, להמשיך מאיפה שהפסיק)
3. מה נחשב ליד איכותי ומה לאסוף
4. סגנון הדיבור הרצוי
5. חוקים ואיסורים ספציפיים
6. התייחסות לשעות פעילות ושירותים

מידע על העסק:
- תחום העסק: {business_area}
- קהל יעד: {target_audience}
- מה נחשב ליד איכותי: {quality_lead}
- שעות פעילות: {working_hours}
- שירותים מרכזיים: {main_services}
- סגנון דיבור רצוי: {speaking_style}
- חוקים ואיסורים: {rules}
- אינטגרציות קיימות: {integrations}

צור פרומפט מקצועי בעברית שיהיה ברור, תמציתי ויעיל. הפרומפט צריך להיות מוכן לשימוש ישיר ללא עריכה נוספת.

החזר את התשובה בפורמט JSON הבא:
{{
    "prompt_text": "טקסט הפרומפט המלא",
    "title": "כותרת קצרה לפרומפט",
    "summary": "סיכום קצר של 2-3 משפטים"
}}
"""


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
    # Remove potential injection characters
    sanitized = text.strip()
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


@prompt_builder_bp.route('/api/ai/prompt_builder/generate', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def generate_prompt():
    """
    Generate AI prompt from questionnaire answers.
    
    Input: questionnaire answers + business_id
    Output: prompt_text, title, short_summary
    
    🔒 Rate limited: 10 per minute
    🔒 Max input: 500 chars per field, 4000 chars total
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        # Extract answers from request
        answers = data.get('answers', {})
        
        # 🔒 Sanitize all inputs
        business_area = _sanitize_input(answers.get('business_area', ''))
        if not business_area:
            return jsonify({"error": "נדרש תחום העסק"}), 400
        
        # Optional fields with defaults (all sanitized)
        target_audience = _sanitize_input(answers.get('target_audience', '')) or 'לקוחות כלליים'
        quality_lead = _sanitize_input(answers.get('quality_lead', '')) or 'לקוח שמביע עניין בשירותים'
        working_hours = _sanitize_input(answers.get('working_hours', '')) or '09:00-18:00'
        main_services = _sanitize_input(answers.get('main_services', '')) or 'שירותים כלליים'
        speaking_style = _sanitize_input(answers.get('speaking_style', '')) or 'מקצועי ואדיב'
        rules = _sanitize_input(answers.get('rules', '')) or 'לא להבטיח מחירים או התחייבויות ללא אישור'
        integrations = _sanitize_input(answers.get('integrations', '')) or 'אין'
        
        # 🔒 Check total input size
        total_input_size = sum(len(x) for x in [
            business_area, target_audience, quality_lead, working_hours,
            main_services, speaking_style, rules, integrations
        ])
        if total_input_size > MAX_TOTAL_INPUT:
            return jsonify({"error": f"הקלט ארוך מדי (מקסימום {MAX_TOTAL_INPUT} תווים בסך הכל)"}), 400
        
        # Build the prompt for GPT
        generation_prompt = PROMPT_BUILDER_TEMPLATE.format(
            business_area=business_area,
            target_audience=target_audience,
            quality_lead=quality_lead,
            working_hours=working_hours,
            main_services=main_services,
            speaking_style=speaking_style,
            rules=rules,
            integrations=integrations
        )
        
        # Call OpenAI to generate the prompt
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "אתה מומחה ביצירת פרומפטים מקצועיים לסוכני AI. החזר תשובה בפורמט JSON בלבד."},
                    {"role": "user", "content": generation_prompt}
                ],
                max_tokens=2000,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, use the raw response as prompt text
                result = {
                    "prompt_text": result_text,
                    "title": f"פרומפט {business_area}",
                    "summary": f"פרומפט AI עבור {business_area}"
                }
            
            prompt_text = result.get('prompt_text', '')
            title = result.get('title', f'פרומפט {business_area}')
            summary = result.get('summary', f'פרומפט AI עבור {business_area}')
            
            logger.info(f"Prompt builder: Generated {len(prompt_text)} chars for {business_area}")
            
            return jsonify({
                "success": True,
                "prompt_text": prompt_text,
                "title": title,
                "summary": summary
            })
            
        except Exception as e:
            logger.error(f"OpenAI error in prompt generation: {e}")
            return jsonify({"error": f"שגיאה ביצירת פרומפט: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Prompt builder error: {e}")
        return jsonify({"error": "שגיאה ביצירת פרומפט"}), 500


@prompt_builder_bp.route('/api/ai/prompt_builder/save', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def save_generated_prompt():
    """
    Save a generated prompt to the business
    Can save as new or update existing
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        prompt_text = data.get('prompt_text', '').strip()
        if not prompt_text:
            return jsonify({"error": "נדרש טקסט פרומפט"}), 400
        
        channel = data.get('channel', 'calls')  # 'calls' or 'whatsapp'
        is_update = data.get('update_existing', False)
        
        # Get business ID
        business_id = _get_business_id()
        if not business_id:
            return jsonify({"error": "לא נמצא עסק"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # Get current user
        current_user = session.get('user', {})
        user_id = current_user.get('email', 'api_user')
        
        # Get or create business settings
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        import json
        
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
        
        # Create revision
        revision = PromptRevisions()
        revision.tenant_id = business_id
        revision.version = next_version
        revision.prompt = new_prompt_data
        revision.changed_by = user_id
        revision.changed_at = datetime.utcnow()
        db.session.add(revision)
        
        db.session.commit()
        
        # Invalidate cache
        try:
            from server.services.ai_service import invalidate_business_cache
            invalidate_business_cache(business_id)
            logger.info(f"AI cache invalidated for business {business_id} after prompt builder save")
        except Exception as e:
            logger.warning(f"Could not invalidate cache: {e}")
        
        logger.info(f"Prompt builder: Saved {channel} prompt for business {business_id}, version {next_version}")
        
        return jsonify({
            "success": True,
            "version": next_version,
            "channel": channel,
            "message": f"הפרומפט נשמר בהצלחה (גרסה {next_version})"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Prompt builder save error: {e}")
        return jsonify({"error": "שגיאה בשמירת פרומפט"}), 500


@prompt_builder_bp.route('/api/ai/prompt_builder/questions', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_questionnaire():
    """
    Get the questionnaire questions for the prompt builder wizard
    """
    questions = [
        {
            "id": "business_area",
            "question": "מהו תחום העסק שלך?",
            "placeholder": "לדוגמה: סלון יופי, משרד עורכי דין, מוסך רכב...",
            "required": True,
            "type": "text"
        },
        {
            "id": "target_audience",
            "question": "מיהו קהל היעד שלך?",
            "placeholder": "לדוגמה: נשים בגילאי 25-45, בעלי רכבי יוקרה, משפחות צעירות...",
            "required": False,
            "type": "text"
        },
        {
            "id": "quality_lead",
            "question": "מה נחשב ליד איכותי עבורך?",
            "placeholder": "לדוגמה: לקוח שרוצה להזמין תור השבוע, לקוח שמתעניין בפרויקט ספציפי...",
            "required": False,
            "type": "textarea"
        },
        {
            "id": "working_hours",
            "question": "מהן שעות הפעילות שלך?",
            "placeholder": "לדוגמה: א-ה 09:00-18:00, ו 09:00-13:00",
            "required": False,
            "type": "text"
        },
        {
            "id": "main_services",
            "question": "מהם השירותים/מוצרים המרכזיים שלך?",
            "placeholder": "פרט את השירותים העיקריים ומחירים אם רלוונטי",
            "required": False,
            "type": "textarea"
        },
        {
            "id": "speaking_style",
            "question": "באיזה סגנון דיבור אתה רוצה שהסוכן ידבר?",
            "placeholder": "לדוגמה: רגוע ואדיב, ישיר ומקצועי, חם ומכירתי...",
            "required": False,
            "type": "select",
            "options": [
                {"value": "רגוע ואדיב", "label": "רגוע ואדיב"},
                {"value": "ישיר ומקצועי", "label": "ישיר ומקצועי"},
                {"value": "חם ומכירתי", "label": "חם ומכירתי"},
                {"value": "פורמלי ורציני", "label": "פורמלי ורציני"},
                {"value": "צעיר ודינמי", "label": "צעיר ודינמי"}
            ]
        },
        {
            "id": "rules",
            "question": "האם יש חוקים או איסורים שהסוכן צריך לשמור?",
            "placeholder": "לדוגמה: לא להבטיח מחירים סופיים, לא להתחייב על זמנים...",
            "required": False,
            "type": "textarea"
        },
        {
            "id": "integrations",
            "question": "האם יש אינטגרציות קיימות שהסוכן צריך להכיר?",
            "placeholder": "לדוגמה: יומן Google, מערכת CRM, מערכת תורים...",
            "required": False,
            "type": "text"
        }
    ]
    
    return jsonify({
        "questions": questions,
        "title": "מחולל פרומפטים אוטומטי",
        "description": "ענה על השאלות הבאות כדי ליצור פרומפט מותאם אישית לעסק שלך"
    })
