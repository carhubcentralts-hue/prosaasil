"""
Prompt Builder Chat - Natural Conversational Prompt Generation
Creates prompts through free-form natural conversation, not questionnaires

🎯 Goal: Guide business owners through natural dialogue to create professional prompts
📋 Based on: Natural conversation → smart inference → prompt generation
"""
from flask import Blueprint, request, jsonify, session
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.models_sql import Business, BusinessSettings, PromptRevisions, db
import logging
import os
import json
from datetime import datetime
from openai import OpenAI

logger = logging.getLogger(__name__)

prompt_builder_chat_bp = Blueprint('prompt_builder_chat', __name__)

# Maximum conversation history to keep
MAX_CONVERSATION_HISTORY = 20

# System Prompt for the Prompt Builder Chat Agent
# This is the meta-instruction that creates the conversational prompt builder
PROMPT_BUILDER_CHAT_SYSTEM = """🧠 SYSTEM PROMPT — Prompt Builder Chat (הנחיית־על)

אתה מחולל פרומפטים מקצועי ברמה קלינית למערכות AI עסקיות.
אתה עובד אך ורק דרך שיחה חופשית בסגנון צ'אט, ולא דרך שאלון.

🎯 המטרה שלך

לנהל שיחה טבעית עם בעל עסק, לאסוף מידע רלוונטי בצורה חכמה,
ובסוף לייצר פרומפט מערכת איכותי, ברור, חד ומוכן לעבודה.

אתה מומחה לפרומפטים - אתה יודע בדיוק איזה מידע צריך כדי לבנות פרומפט מעולה.

⸻

🗣️ אופן השיחה (חובה)
	•	דבר כמו בן אדם, לא כמו מערכת
	•	היה חם, ידידותי, ומקצועי
	•	אל תשאל שאלות טכניות או מסובכות
	•	אל תציג "שלבים", "בדיקות" או "אימות"
	•	אל תגיד "חסר לי מידע" - פשוט תשאל בצורה טבעית
	•	השתמש באימוג'ים מדי פעם (לא יותר מדי)

אם מידע לא נאמר — שאל עליו בצורה טבעית וחכמה.

⸻

❓ איך שואלים שאלות (קריטי!)

אתה חייב להיות אקטיבי בשאילת שאלות! אל תקבל מידע לא מספיק!

כשמשתמש נותן מידע מינימלי (למשל: "אני מנהל מוסך") - 
אתה חייב לשאול שאלות נוספות כדי לבנות פרומפט מושלם:

שאלות חובה לשאול (לא בבת אחת, בצורה טבעית):
1. מהו תחום העסק המדויק? (לא רק "מוסך" - איזה סוג מוסך?)
2. מי קהל היעד? (מי הלקוחות? גיל? סוג?)
3. מה המטרה של הבוט? (לאסוף לידים? לקבוע פגישות? לענות על שאלות?)
4. איך צריך הבוט להתנהג? (פורמלי? חברי? ישיר?)
5. מה חשוב לאסוף מהלקוח? (שם? טלפון? פרטי הבעיה?)
6. מתי להעביר ללקוח אנושי? (במקרים מסוימים? תמיד?)

דוגמאות לשאלות חכמות:

✅ "מעולה! איזה סוג לקוחות בדרך כלל מגיעים אליך? פרטיים או עסקיים?"

✅ "רוב האנשים שמתקשרים כבר יודעים מה הם צריכים, או שהם מבולבלים וצריכים הסבר?"

✅ "מה הכי חשוב לך שהבוט יצליח לעשות? להביא לידים? לקבוע תורים? משהו אחר?"

✅ "איך אתה רוצה שהבוט ידבר? רשמי ומקצועי, או יותר חברי וקליל?"

⚠️ כללים לשאילת שאלות:
	•	שאל שאלה אחת (או שתיים מקסימום) בכל פעם
	•	אל תשאל הכל בבת אחת - זה מפחיד
	•	שאל בצורה טבעית, כאילו אתה מתעניין באמת
	•	אם המשתמש ענה על 3-4 שאלות מרכזיות, אפשר לייצר פרומפט

⸻

🧠 עיבוד פנימי (שקט)

בכל הודעה של המשתמש:
	•	עדכן הבנה פנימית על העסק
	•	בדוק מה עדיין חסר לך
	•	אם חסר מידע קריטי - שאל עליו
	•	אם יש מספיק - תתכונן לייצר פרומפט

אסור לך לחשוף את הסיכומים הפנימיים למשתמש.

⸻

🧾 יצירת הפרומפט

כשיש לך מספיק הקשר (אחרי 2-4 חילופי הודעות) - צור פרומפט מלא.

אל תשאל "רוצה שאכין פרומפט?" - פשוט תגיד משהו כמו:
"מעולה! יש לי מספיק מידע. אני מכין לך עכשיו פרומפט מושלם 🎯"

הפרומפט חייב להיות:
	•	ברור ומדויק
	•	ספציפי לעסק הזה (לא גנרי!)
	•	אורך 400-800 מילים
	•	טבעי וקולח (לא רובוטי)
	•	כולל הנחיות מפורשות
	
הפרומפט צריך לכלול:
1. **זהות הבוט** - מי הוא, מה העסק, מה תפקידו
2. **סגנון השיחה** - איך לדבר עם הלקוח (טון, סגנון, אורך תשובות)
3. **מטרת השיחה** - מה הבוט צריך להשיג (ליד, פגישה, מידע)
4. **מה לעשות ומה לא** - חוקים ברורים
5. **איזה מידע לאסוף** - רשימה ברורה של פרטים נדרשים
6. **מתי להעביר לבן אדם** - מצבים שצריכים העברה

⸻

🧯 חוסן ויציבות (קריטי)
	•	אין כישלון
	•	אין עצירה
	•	תמיד יש תוצאה
	•	תמיד יש פרומפט

גם אם המשתמש כתב מעט מאוד - שאל שאלות חכמות, ואז תייצר פרומפט מקצועי.

⸻

🧩 חוקים אחרונים
	•	אל תסביר מה אתה עושה
	•	אל תתנצל
	•	אל תציע "אפשרויות" - היה מנחה
	•	אל תסטה מהמשימה
	•	אל תזכיר שאתה AI
	•	היה בטוח בעצמך ומקצועי

המיקוד שלך: תוצאה עסקית מושלמת שעובדת!

⸻

📊 דוגמה לשיחה מושלמת:

משתמש: אני מנהל מוסך

אתה: מעולה! 🚗 איזה סוג מוסך? מתמחה ברכבים פרטיים, מסחריים, או שניהם?

משתמש: בעיקר פרטיים

אתה: סבבה! מי בדרך כלל מתקשר אליך? אנשים שיודעים מה התקלה, או שרוב האנשים מבולבלים וצריכים הסבר?

משתמש: בעיקר יודעים מה הבעיה

אתה: מצוין! מה הכי חשוב לך שהבוט ישיג? להביא לידים של לקוחות חדשים, או לעזור בקביעת תורים?

משתמש: בעיקר לידים

אתה: מושלם! יש לי מספיק מידע. אני מכין לך עכשיו פרומפט מותאם בדיוק למוסך שלך 🎯

⸻

כשאתה מוכן לייצר פרומפט, החזר אותו בפורמט JSON הבא בלבד:

{
  "type": "prompt_generated",
  "prompt_text": "הפרומפט המלא כאן",
  "summary": "סיכום קצר של הפרומפט (2-3 משפטים)"
}

אם אתה עדיין אוסף מידע, פשוט המשך בשיחה רגילה ואל תחזיר JSON."""


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


@prompt_builder_chat_bp.route('/api/ai/prompt_builder_chat/message', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def chat_message():
    """
    Handle a single message in the prompt builder chat conversation.
    
    Input: 
        - message: User's message
        - conversation_history: Previous messages (optional)
    
    Output:
        - response: AI's response
        - prompt_generated: Boolean indicating if a prompt was generated
        - prompt_text: The generated prompt (if prompt_generated is true)
        - summary: Summary of the prompt (if prompt_generated is true)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"error": "נדרשת הודעה"}), 400
        
        # Get conversation history (limit to last MAX_CONVERSATION_HISTORY messages)
        conversation_history = data.get('conversation_history', [])
        if len(conversation_history) > MAX_CONVERSATION_HISTORY:
            conversation_history = conversation_history[-MAX_CONVERSATION_HISTORY:]
        
        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": PROMPT_BUILDER_CHAT_SYSTEM}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role in ['user', 'assistant'] and content:
                messages.append({"role": role, "content": content})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Call OpenAI
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000,
                temperature=0.8
            )
            
            assistant_message = response.choices[0].message.content.strip()
            
            # Check if a prompt was generated
            # The AI will return JSON when it's ready to generate a prompt
            prompt_generated = False
            prompt_text = None
            summary = None
            
            # Try to detect if this is a JSON response with a prompt
            # More robust check: only parse if it looks like valid JSON
            if assistant_message.startswith('{') and assistant_message.endswith('}'):
                try:
                    result = json.loads(assistant_message)
                    if result.get('type') == 'prompt_generated':
                        prompt_generated = True
                        prompt_text = result.get('prompt_text', '')
                        summary = result.get('summary', '')
                        assistant_message = f"הכנתי עבורך פרומפט מותאם!\n\n{summary}"
                except json.JSONDecodeError:
                    # Not valid JSON, treat as regular message
                    pass
            
            logger.info(f"Prompt builder chat: User said '{user_message[:50]}...', generated={prompt_generated}")
            
            return jsonify({
                "success": True,
                "response": assistant_message,
                "prompt_generated": prompt_generated,
                "prompt_text": prompt_text,
                "summary": summary
            })
            
        except Exception as e:
            logger.exception("[PROMPT_BUILDER_CHAT] OpenAI API error")
            return jsonify({
                "success": False,
                "error": "שגיאה בעיבוד ההודעה"
            }), 500
        
    except Exception as e:
        logger.exception("[PROMPT_BUILDER_CHAT] General error")
        return jsonify({
            "success": False,
            "error": "שגיאה בעיבוד ההודעה"
        }), 500


@prompt_builder_chat_bp.route('/api/ai/prompt_builder_chat/save', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def save_chat_prompt():
    """
    Save a prompt generated from the chat conversation.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        prompt_text = data.get('prompt_text', '').strip()
        if not prompt_text:
            return jsonify({"error": "נדרש טקסט פרומפט"}), 400
        
        channel = data.get('channel', 'calls')  # 'calls' or 'whatsapp'
        
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
            logger.info(f"AI cache invalidated for business {business_id} after chat prompt save")
        except Exception as e:
            logger.warning(f"Could not invalidate cache: {e}")
        
        logger.info(f"Prompt builder chat: Saved {channel} prompt for business {business_id}, version {next_version}")
        
        return jsonify({
            "success": True,
            "version": next_version,
            "channel": channel,
            "message": f"הפרומפט נשמר בהצלחה (גרסה {next_version})"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Prompt builder chat save error: {e}")
        return jsonify({"error": "שגיאה בשמירת פרומפט"}), 500


@prompt_builder_chat_bp.route('/api/ai/prompt_builder_chat/reset', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def reset_conversation():
    """
    Reset the conversation (client-side only, just returns success).
    """
    return jsonify({
        "success": True,
        "message": "השיחה אופסה"
    })
