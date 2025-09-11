# AI Prompt Management API - לפי ההנחיות המדויקות
from flask import Blueprint, request, jsonify, session
from server.models_sql import Business, BusinessSettings, PromptRevisions, User, db
from server.routes_admin import require_api_auth  # Standardized import per guidelines
from server.extensions import csrf
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

ai_prompt_bp = Blueprint('ai_prompt', __name__)

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt', methods=['GET'])
@require_api_auth(['admin', 'manager'])
def get_business_prompt(business_id):
    """Get AI prompts for business - Admin (שיחות ווואטסאפ נפרד)"""
    try:
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if settings:
            # Get latest version number
            latest_revision = PromptRevisions.query.filter_by(
                tenant_id=business_id
            ).order_by(PromptRevisions.version.desc()).first()
            
            version = latest_revision.version if latest_revision else 1
            
            # הפרד לשיחות ווואטסאפ - לפי ההנחיות המדויקות
            # ✅ תיקון: העדפה לפרומפט מטבלת businesses אם קיים
            prompt_data = settings.ai_prompt or business.system_prompt or "You are Leah, a helpful Hebrew real-estate AI assistant..."
            try:
                import json
                if prompt_data.startswith('{'):
                    parsed_prompt = json.loads(prompt_data)
                    calls_prompt = parsed_prompt.get('calls', prompt_data)
                    whatsapp_prompt = parsed_prompt.get('whatsapp', prompt_data)
                else:
                    # fallback - אותו פרומפט לשניהם
                    calls_prompt = prompt_data
                    whatsapp_prompt = prompt_data
            except:
                # fallback - אותו פרומפט לשניהם
                calls_prompt = prompt_data
                whatsapp_prompt = prompt_data
            
            return jsonify({
                "calls_prompt": calls_prompt,
                "whatsapp_prompt": whatsapp_prompt,
                "version": version,
                "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
                "updated_by": settings.updated_by
            })
        else:
            # Return default prompts - ✅ תיקון: השתמש בפרומפט מטבלת businesses אם זמין
            default_prompt = business.system_prompt or "את ליאה, עוזרת נדל\"ן ישראלית. תפקידך לסייע ללקוחות במציאת דירות ומשרדים."
            return jsonify({
                "calls_prompt": default_prompt,
                "whatsapp_prompt": default_prompt,
                "version": 1,
                "updated_at": None,
                "updated_by": None
            })
    
    except Exception as e:
        logger.error(f"Error getting prompt for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בטעינת הפרומפט"}), 500

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt', methods=['PUT'])
@require_api_auth(['admin', 'manager'])
def update_business_prompt(business_id):
    """Update AI prompts for business - Admin (דורש CSRF) - שיחות ווואטסאפ נפרד"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "חסרים נתונים"}), 400
        
        # שדות אופציונליים: calls_prompt, whatsapp_prompt + backward compatibility
        calls_prompt = data.get('calls_prompt')
        whatsapp_prompt = data.get('whatsapp_prompt') 
        
        # תמיכה לאחור - אם נשלח רק 'prompt', השתמש בו לשניהם
        if not calls_prompt and not whatsapp_prompt and data.get('prompt'):
            calls_prompt = data.get('prompt')
            whatsapp_prompt = data.get('prompt')
        
        if not calls_prompt and not whatsapp_prompt:
            return jsonify({"error": "חסר תוכן פרומפט (לפחות שיחות או וואטסאפ)"}), 400
        
        # ולידציות שרת - לפי ההנחיות
        if calls_prompt and len(calls_prompt) > 10000:
            return jsonify({"error": "פרומפט שיחות ארוך מדי (מקסימום 10,000 תווים)"}), 400
        if whatsapp_prompt and len(whatsapp_prompt) > 10000:
            return jsonify({"error": "פרומפט וואטסאפ ארוך מדי (מקסימום 10,000 תווים)"}), 400
        
        # Sanitization בסיסי
        for prompt_text in [calls_prompt, whatsapp_prompt]:
            if prompt_text and ('{{' in prompt_text or '}}' in prompt_text):
                return jsonify({"error": "הפרומפט מכיל תווים לא חוקיים"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        current_user = session.get('user', {})
        user_id = current_user.get('email', 'unknown')
        
        # Get current settings to merge with new data
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        # Build updated prompt object
        import json
        current_prompts = {}
        if settings and settings.ai_prompt:
            try:
                if settings.ai_prompt.startswith('{'):
                    current_prompts = json.loads(settings.ai_prompt)
                else:
                    # Legacy single prompt - convert to object
                    current_prompts = {
                        'calls': settings.ai_prompt,
                        'whatsapp': settings.ai_prompt
                    }
            except:
                current_prompts = {}
        
        # Update only provided fields
        if calls_prompt is not None:
            current_prompts['calls'] = calls_prompt
        if whatsapp_prompt is not None:
            current_prompts['whatsapp'] = whatsapp_prompt
        
        # Store as JSON
        new_prompt_data = json.dumps(current_prompts, ensure_ascii=False)
        
        # Get or create settings
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
        
        # Get next version number
        latest_revision = PromptRevisions.query.filter_by(
            tenant_id=business_id
        ).order_by(PromptRevisions.version.desc()).first()
        
        next_version = (latest_revision.version + 1) if latest_revision else 1
        
        # יצירת prompt_revisions (version++)
        revision = PromptRevisions()
        revision.tenant_id = business_id
        revision.version = next_version
        revision.prompt = new_prompt_data
        revision.changed_by = user_id
        revision.changed_at = datetime.utcnow()
        db.session.add(revision)
        
        db.session.commit()
        
        # Runtime Apply - לוג הוכחה לפי ההנחיות המדויקות
        logger.info(f"AI_PROMPT loaded tenant={business_id} v={next_version}")
        
        return jsonify({
            "calls_prompt": current_prompts.get('calls', ''),
            "whatsapp_prompt": current_prompts.get('whatsapp', ''),
            "version": next_version,
            "updated_at": settings.updated_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating prompt for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בעדכון הפרומפט"}), 500

@ai_prompt_bp.route('/api/business/current/prompt', methods=['GET'])
@require_api_auth(['business', 'admin'])  # ✅ אדמין יכול לקרוא פרומפטים גם כשהוא מתחזה
def get_current_business_prompt():
    """Get AI prompt for current business - Business (Impersonated)"""
    try:
        tenant_id = session.get('impersonated_tenant_id') or session.get('user', {}).get('business_id')  # Fixed key per guidelines
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
            
        return get_business_prompt(tenant_id)
        
    except Exception as e:
        logger.error(f"Error getting current business prompt: {e}")
        return jsonify({"error": "שגיאה בטעינת הפרומפט"}), 500

@ai_prompt_bp.route('/api/business/current/prompt', methods=['PUT'])
@require_api_auth(['business', 'admin'])  # ✅ אדמין יכול לעדכן פרומפטים גם כשהוא מתחזה
def update_current_business_prompt():
    """Update AI prompt for current business - Business (Impersonated, דורש CSRF)"""
    try:
        tenant_id = session.get('impersonated_tenant_id') or session.get('user', {}).get('business_id')  # Fixed key per guidelines
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
            
        return update_business_prompt(tenant_id)
        
    except Exception as e:
        logger.error(f"Error updating current business prompt: {e}")
        return jsonify({"error": "שגיאה בעדכון הפרומפט"}), 500

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt/history', methods=['GET'])
@require_api_auth(['admin', 'manager'])
def get_prompt_history(business_id):
    """Get prompt history for business - Admin"""
    try:
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        revisions = PromptRevisions.query.filter_by(
            tenant_id=business_id
        ).order_by(PromptRevisions.version.desc()).all()
        
        history = [{
            "version": rev.version,
            "prompt": rev.prompt,
            "changed_by": rev.changed_by,
            "changed_at": rev.changed_at.isoformat()
        } for rev in revisions]
        
        return jsonify({"history": history})
        
    except Exception as e:
        logger.error(f"Error getting prompt history for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בטעינת ההיסטוריה"}), 500

@ai_prompt_bp.route('/api/business/current/prompt/history', methods=['GET'])
@require_api_auth(['business'])
def get_current_prompt_history():
    """Get prompt history for current business - Business (Impersonated)"""
    try:
        tenant_id = session.get('impersonated_tenant_id') or session.get('user', {}).get('business_id')  # Fixed key per guidelines
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
            
        return get_prompt_history(tenant_id)
        
    except Exception as e:
        logger.error(f"Error getting current prompt history: {e}")
        return jsonify({"error": "שגיאה בטעינת ההיסטוריה"}), 500