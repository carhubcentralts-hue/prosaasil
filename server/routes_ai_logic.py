"""
Logic-by-Prompt API Routes - Business Rules Management
═══════════════════════════════════════════════════════

Endpoints for:
- Saving/loading business logic rules (Hebrew text)
- Compiling rules to JSON
- Testing rules in sandbox mode
"""
from flask import Blueprint, request, jsonify, session
from server.models_sql import Business, db
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.utils.api_guard import api_handler
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

ai_logic_bp = Blueprint('ai_logic', __name__)


@ai_logic_bp.route('/api/business/current/ai-logic', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_ai_logic():
    """Get business logic rules text and compiled state"""
    try:
        from flask import g
        user_session = session.get('user') or {}
        tenant_id = (
            g.get('tenant')
            or session.get('impersonated_tenant_id')
            or (user_session.get('business_id') if isinstance(user_session, dict) else None)
        )
        if not tenant_id:
            user = session.get('al_user') or {}
            tenant_id = user.get('business_id') if isinstance(user, dict) else None
        
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
        
        business = Business.query.get(tenant_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        return jsonify({
            "ok": True,
            "ai_logic_text": business.ai_logic_text or "",
            "ai_logic_compiled": business.ai_logic_compiled,
            "ai_logic_compiled_at": business.ai_logic_compiled_at.isoformat() if business.ai_logic_compiled_at else None,
            "ai_logic_compile_version": business.ai_logic_compile_version or 0,
            "ai_logic_compile_error": business.ai_logic_compile_error
        })
    except Exception as e:
        logger.error(f"Error getting AI logic: {e}")
        return jsonify({"error": "שגיאה בטעינת החוקים"}), 500


@ai_logic_bp.route('/api/business/current/ai-logic', methods=['PUT'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def save_and_compile_ai_logic():
    """Save business logic text and compile it to JSON rules"""
    try:
        from flask import g
        user_session = session.get('user') or {}
        tenant_id = (
            g.get('tenant')
            or session.get('impersonated_tenant_id')
            or (user_session.get('business_id') if isinstance(user_session, dict) else None)
        )
        if not tenant_id:
            user = session.get('al_user') or {}
            tenant_id = user.get('business_id') if isinstance(user, dict) else None
        
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "חסרים נתונים"}), 400
        
        logic_text = data.get("ai_logic_text", "").strip()
        
        if not logic_text:
            return jsonify({"error": "לא הוזן טקסט חוקים"}), 400
        
        if len(logic_text) > 10000:
            return jsonify({"error": "טקסט החוקים ארוך מדי (מקסימום 10,000 תווים)"}), 400
        
        business = Business.query.get(tenant_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # Save text
        business.ai_logic_text = logic_text
        
        # Compile rules
        from server.services.rules_compiler import compile_business_rules, get_status_catalog_for_business
        status_catalog = get_status_catalog_for_business(tenant_id)
        
        result = compile_business_rules(
            logic_text=logic_text,
            status_catalog=status_catalog,
            business_id=tenant_id
        )
        
        if result["success"]:
            business.ai_logic_compiled = result["compiled"]
            business.ai_logic_compiled_at = datetime.utcnow()
            business.ai_logic_compile_version = (business.ai_logic_compile_version or 0) + 1
            business.ai_logic_compile_error = None
            
            db.session.commit()
            
            logger.info(f"[AI_LOGIC] ✅ Compiled rules for business {tenant_id} v{business.ai_logic_compile_version}")
            
            return jsonify({
                "ok": True,
                "compiled": result["compiled"],
                "compile_version": business.ai_logic_compile_version,
                "compile_time_ms": result["compile_time_ms"],
                "message": "החוקים נשמרו והודרו בהצלחה"
            })
        else:
            # Save text but mark compile error
            business.ai_logic_compile_error = result["error"]
            db.session.commit()
            
            logger.warning(f"[AI_LOGIC] ⚠️ Compile error for business {tenant_id}: {result['error']}")
            
            return jsonify({
                "ok": False,
                "error": result["error"],
                "compile_time_ms": result["compile_time_ms"],
                "message": "הטקסט נשמר אך ההידור נכשל"
            }), 422
        
    except Exception as e:
        logger.error(f"Error saving AI logic: {e}", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"error": "שגיאה בשמירת החוקים"}), 500


@ai_logic_bp.route('/api/business/current/ai-logic/test', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def test_ai_logic():
    """Test business rules against a sample message (sandbox)"""
    try:
        from flask import g
        user_session = session.get('user') or {}
        tenant_id = (
            g.get('tenant')
            or session.get('impersonated_tenant_id')
            or (user_session.get('business_id') if isinstance(user_session, dict) else None)
        )
        if not tenant_id:
            user = session.get('al_user') or {}
            tenant_id = user.get('business_id') if isinstance(user, dict) else None
        
        if not tenant_id:
            return jsonify({"error": "לא נמצא מזהה עסק"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "חסרים נתונים"}), 400
        
        test_message = data.get("message", "").strip()
        if not test_message:
            return jsonify({"error": "לא הוזנה הודעת בדיקה"}), 400
        
        lead_status_label = data.get("status_label")
        
        from server.services.decision_engine import test_rules_sandbox
        
        result = test_rules_sandbox(
            business_id=tenant_id,
            test_message=test_message,
            lead_status_label=lead_status_label
        )
        
        return jsonify({
            "ok": True,
            **result
        })
        
    except Exception as e:
        logger.error(f"Error testing AI logic: {e}", exc_info=True)
        return jsonify({"error": "שגיאה בבדיקת החוקים"}), 500
