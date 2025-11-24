# AI Prompt Management API - לפי ההנחיות המדויקות
from flask import Blueprint, request, jsonify, session
from server.models_sql import Business, BusinessSettings, PromptRevisions, User, db
from server.routes_admin import require_api_auth  # Standardized import per guidelines
from server.extensions import csrf
from server.utils.api_guard import api_handler
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

ai_prompt_bp = Blueprint('ai_prompt', __name__)

# A2) עטוף routes פרומפטים לפי ההוראות המדויקות  
@ai_prompt_bp.route('/api/business/<tenant>/prompts', methods=['POST'])
@api_handler
def save_prompt(tenant):
    """שמירת פרומפט לפי ההוראות - תמיד JSON + commit/rollback"""
    data = request.get_json(force=True)
    
    # מיפוי למודל BusinessSettings
    business_id = 1  # business_1 → 1
    if tenant == 'business_1':
        business_id = 1
    
    # Get or create settings
    settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
    if not settings:
        settings = BusinessSettings()
        settings.tenant_id = business_id
        db.session.add(settings)
    
    # עדכון הפרומפט
    settings.ai_prompt = data.get('body', data.get('prompt', ''))
    settings.updated_by = 'api_user'
    
    db.session.commit()
    
    # ✅ CRITICAL: Invalidate cache after save for immediate effect
    try:
        from server.services.ai_service import invalidate_business_cache
        invalidate_business_cache(business_id)
        logger.info(f"AI cache invalidated for business {business_id} after prompt save")
    except Exception as e:
        logger.error(f"Failed to invalidate cache: {e}")
    
    return {"ok": True, "id": settings.tenant_id}

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
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
            prompt_data = settings.ai_prompt or business.system_prompt or f"אתה עוזר נדל\"ן דיגיטלי של {{{{business_name}}}}. תפקידך לעזור ללקוחות למצוא נכסים."  # ✅ בלי שם hardcoded!
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
                "greeting_message": business.greeting_message or "",
                "whatsapp_greeting": business.whatsapp_greeting or "",
                "version": version,
                "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
                "updated_by": settings.updated_by
            })
        else:
            # Return default prompts - ✅ תיקון: השתמש בפרומפט מטבלת businesses אם זמין
            default_prompt = business.system_prompt or "אתה עוזר נדל\"ן ישראלי. תפקידך לסייע ללקוחות במציאת דירות ומשרדים."  # ✅ בלי שם hardcoded
            return jsonify({
                "calls_prompt": default_prompt,
                "whatsapp_prompt": default_prompt,
                "greeting_message": business.greeting_message or "",
                "whatsapp_greeting": business.whatsapp_greeting or "",
                "version": 1,
                "updated_at": None,
                "updated_by": None
            })
    
    except Exception as e:
        logger.error(f"Error getting prompt for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בטעינת הפרומפט"}), 500

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt', methods=['PUT', 'OPTIONS'])
@require_api_auth(['admin', 'manager'])
def update_business_prompt(business_id):
    """Update AI prompts for business - Admin (דורש CSRF) - שיחות ווואטסאפ נפרד"""
    
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "חסרים נתונים"}), 400
        
        # שדות אופציונליים: calls_prompt, whatsapp_prompt, greeting_message, whatsapp_greeting
        calls_prompt = data.get('calls_prompt')
        whatsapp_prompt = data.get('whatsapp_prompt')
        greeting_message = data.get('greeting_message')
        whatsapp_greeting = data.get('whatsapp_greeting')
        
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
        
        # Sanitization בסיסי - ✅ מאפשר placeholders כמו {{business_name}}
        # (removed validation - placeholders are now allowed)
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # ✅ שמירת הודעות ברכה בטבלת Business
        if greeting_message is not None:
            business.greeting_message = greeting_message
        if whatsapp_greeting is not None:
            business.whatsapp_greeting = whatsapp_greeting
        
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
        
        # ✅ CRITICAL: Invalidate AI service cache after prompt update for real-time effect
        try:
            from server.services.ai_service import invalidate_business_cache
            invalidate_business_cache(business_id)
            logger.info(f"🔥 AI cache invalidated for business {business_id} - prompt changes will apply immediately")
            print(f"🔥 CACHE CLEARED for business {business_id} - next call will use new prompt!")
        except Exception as cache_error:
            logger.error(f"❌ Failed to invalidate AI cache: {cache_error}")
            print(f"❌ CACHE CLEAR FAILED: {cache_error}")
        
        # Runtime Apply - לוג הוכחה לפי ההנחיות המדויקות
        logger.info(f"AI_PROMPT loaded tenant={business_id} v={next_version}")
        
        return jsonify({
            "success": True,  # ✅ תיקון: הוספת success field שהfrontend מצפה לו
            "calls_prompt": current_prompts.get('calls', ''),
            "whatsapp_prompt": current_prompts.get('whatsapp', ''),
            "greeting_message": business.greeting_message or "",
            "whatsapp_greeting": business.whatsapp_greeting or "",
            "version": next_version,
            "updated_at": settings.updated_at.isoformat() if settings.updated_at else datetime.utcnow().isoformat(),
            "message": "הפרומפט נשמר בהצלחה"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating prompt for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בעדכון הפרומפט"}), 500

@ai_prompt_bp.route('/api/business/current/prompt', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
@require_api_auth(['system_admin', 'owner', 'admin'])  # BUILD 138: owner can access AI settings
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
@require_api_auth(['system_admin', 'owner', 'admin'])  # BUILD 138: owner can update AI settings
def update_current_business_prompt():
    """Update AI prompt for current business - Business (Impersonated, דורש CSRF)"""
    try:
        tenant_id = session.get('impersonated_tenant_id') or session.get('user', {}).get('business_id')  # Fixed key per guidelines
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
        
        # Call the internal handler directly - returns Flask Response
        return update_business_prompt(tenant_id)
        
    except Exception as e:
        logger.error(f"Error updating current business prompt: {e}")
        return jsonify({"error": "שגיאה בעדכון הפרומפט"}), 500

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt/history', methods=['GET'])
@csrf.exempt  # GET requests don't need CSRF
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
@csrf.exempt  # GET requests don't need CSRF
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