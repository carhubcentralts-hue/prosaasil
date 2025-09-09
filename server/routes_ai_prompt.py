# AI Prompt Management API - לפי ההנחיות המדויקות
from flask import Blueprint, request, jsonify, session
from server.models_sql import Business, BusinessSettings, PromptRevisions, User, db
from server.routes_admin import require_api_auth
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

ai_prompt_bp = Blueprint('ai_prompt', __name__)

@ai_prompt_bp.route('/api/admin/businesses/<int:business_id>/prompt', methods=['GET'])
@require_api_auth(['admin', 'manager'])
def get_business_prompt(business_id):
    """Get AI prompt for business - Admin"""
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
            
            return jsonify({
                "prompt": settings.ai_prompt or "You are Leah, a helpful Hebrew real-estate AI assistant...",
                "version": version,
                "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
                "updated_by": settings.updated_by
            })
        else:
            # Return default prompt
            return jsonify({
                "prompt": "You are Leah, a helpful Hebrew real-estate AI assistant...",
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
    """Update AI prompt for business - Admin (דורש CSRF)"""
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({"error": "חסר תוכן הפרומפט"}), 400
        
        prompt = data['prompt']
        
        # ולידציות שרת - לפי ההנחיות
        if len(prompt) > 10000:  # 10k תווים מקסימום
            return jsonify({"error": "הפרומפט ארוך מדי (מקסימום 10,000 תווים)"}), 400
        
        # Sanitization בסיסי
        if '{{' in prompt or '}}' in prompt:
            return jsonify({"error": "הפרומפט מכיל תווים לא חוקיים"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        current_user = session.get('user', {})
        user_id = current_user.get('email', 'unknown')
        
        # Get or create settings
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if not settings:
            settings = BusinessSettings(
                tenant_id=business_id,
                ai_prompt=prompt,
                updated_by=user_id
            )
            db.session.add(settings)
        else:
            settings.ai_prompt = prompt
            settings.updated_by = user_id
            settings.updated_at = datetime.utcnow()
        
        # Get next version number
        latest_revision = PromptRevisions.query.filter_by(
            tenant_id=business_id
        ).order_by(PromptRevisions.version.desc()).first()
        
        next_version = (latest_revision.version + 1) if latest_revision else 1
        
        # יצירת prompt_revisions (version++)
        revision = PromptRevisions(
            tenant_id=business_id,
            version=next_version,
            prompt=prompt,
            changed_by=user_id,
            changed_at=datetime.utcnow()
        )
        db.session.add(revision)
        
        db.session.commit()
        
        # Runtime Apply - פרסום אירוע (TODO: Redis PubSub)
        logger.info(f"Agent prompt reloaded for tenant {business_id}, version {next_version}")
        
        return jsonify({
            "ok": True,
            "version": next_version,
            "updated_at": settings.updated_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating prompt for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בעדכון הפרומפט"}), 500

@ai_prompt_bp.route('/api/business/current/prompt', methods=['GET'])
@require_api_auth(['business'])
def get_current_business_prompt():
    """Get AI prompt for current business - Business (Impersonated)"""
    try:
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
            
        return get_business_prompt(tenant_id)
        
    except Exception as e:
        logger.error(f"Error getting current business prompt: {e}")
        return jsonify({"error": "שגיאה בטעינת הפרומפט"}), 500

@ai_prompt_bp.route('/api/business/current/prompt', methods=['PUT'])
@require_api_auth(['business'])
def update_current_business_prompt():
    """Update AI prompt for current business - Business (Impersonated, דורש CSRF)"""
    try:
        tenant_id = session.get('tenant_id')
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
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
            
        return get_prompt_history(tenant_id)
        
    except Exception as e:
        logger.error(f"Error getting current prompt history: {e}")
        return jsonify({"error": "שגיאה בטעינת ההיסטוריה"}), 500