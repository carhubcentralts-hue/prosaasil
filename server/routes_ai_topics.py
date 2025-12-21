"""
AI Settings and Topics Management API

Endpoints for managing AI settings and business topics for classification
"""
from flask import Blueprint, request, jsonify
from server.models_sql import Business, BusinessAISettings, BusinessTopic, db
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.services.topic_classifier import topic_classifier
import logging

logger = logging.getLogger(__name__)

ai_topics_bp = Blueprint('ai_topics', __name__)


@ai_topics_bp.route('/api/business/ai-settings', methods=['GET'])
@require_api_auth(['owner', 'admin'])
def get_ai_settings():
    """Get AI settings for current business"""
    try:
        from flask import g
        business_id = g.business_id
        
        # Get or create AI settings
        ai_settings = BusinessAISettings.query.filter_by(business_id=business_id).first()
        
        if not ai_settings:
            # Create default settings
            ai_settings = BusinessAISettings(
                business_id=business_id,
                embedding_enabled=False,
                embedding_model="text-embedding-3-small",
                embedding_threshold=0.78,
                embedding_top_k=3,
                auto_tag_leads=True,
                auto_tag_calls=True
            )
            db.session.add(ai_settings)
            db.session.commit()
        
        return jsonify({
            "embedding_enabled": ai_settings.embedding_enabled,
            "embedding_model": ai_settings.embedding_model,
            "embedding_threshold": ai_settings.embedding_threshold,
            "embedding_top_k": ai_settings.embedding_top_k,
            "auto_tag_leads": ai_settings.auto_tag_leads,
            "auto_tag_calls": ai_settings.auto_tag_calls,
            "created_at": ai_settings.created_at.isoformat() if ai_settings.created_at else None,
            "updated_at": ai_settings.updated_at.isoformat() if ai_settings.updated_at else None
        })
    
    except Exception as e:
        logger.error(f"Error getting AI settings: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@ai_topics_bp.route('/api/business/ai-settings', methods=['PUT'])
@require_api_auth(['owner', 'admin'])
@csrf.exempt
def update_ai_settings():
    """Update AI settings for current business"""
    try:
        from flask import g
        business_id = g.business_id
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Get or create AI settings
        ai_settings = BusinessAISettings.query.filter_by(business_id=business_id).first()
        
        if not ai_settings:
            ai_settings = BusinessAISettings(business_id=business_id)
            db.session.add(ai_settings)
        
        # Update fields
        if 'embedding_enabled' in data:
            ai_settings.embedding_enabled = bool(data['embedding_enabled'])
        
        if 'embedding_model' in data:
            ai_settings.embedding_model = data['embedding_model']
        
        if 'embedding_threshold' in data:
            threshold = float(data['embedding_threshold'])
            if not (0.0 <= threshold <= 1.0):
                return jsonify({"error": "Threshold must be between 0.0 and 1.0"}), 400
            ai_settings.embedding_threshold = threshold
        
        if 'embedding_top_k' in data:
            top_k = int(data['embedding_top_k'])
            if top_k < 1:
                return jsonify({"error": "top_k must be at least 1"}), 400
            ai_settings.embedding_top_k = top_k
        
        if 'auto_tag_leads' in data:
            ai_settings.auto_tag_leads = bool(data['auto_tag_leads'])
        
        if 'auto_tag_calls' in data:
            ai_settings.auto_tag_calls = bool(data['auto_tag_calls'])
        
        db.session.commit()
        
        logger.info(f"✅ AI settings updated for business {business_id}")
        
        return jsonify({
            "success": True,
            "message": "AI settings updated successfully"
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating AI settings: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@ai_topics_bp.route('/api/business/topics', methods=['GET'])
@require_api_auth(['owner', 'admin'])
def list_topics():
    """List all topics for current business"""
    try:
        from flask import g
        business_id = g.business_id
        
        # Get query parameters
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        # Build query
        query = BusinessTopic.query.filter_by(business_id=business_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        
        topics = query.order_by(BusinessTopic.name).all()
        
        return jsonify({
            "topics": [
                {
                    "id": topic.id,
                    "name": topic.name,
                    "synonyms": topic.synonyms or [],
                    "is_active": topic.is_active,
                    "created_at": topic.created_at.isoformat() if topic.created_at else None,
                    "updated_at": topic.updated_at.isoformat() if topic.updated_at else None
                }
                for topic in topics
            ],
            "total": len(topics)
        })
    
    except Exception as e:
        logger.error(f"Error listing topics: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@ai_topics_bp.route('/api/business/topics', methods=['POST'])
@require_api_auth(['owner', 'admin'])
@csrf.exempt
def create_topic():
    """Create a new topic"""
    try:
        from flask import g
        business_id = g.business_id
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({"error": "Topic name is required"}), 400
        
        name = data['name'].strip()
        if not name:
            return jsonify({"error": "Topic name cannot be empty"}), 400
        
        # Check if topic with same name already exists
        existing = BusinessTopic.query.filter_by(
            business_id=business_id,
            name=name
        ).first()
        
        if existing:
            return jsonify({"error": f"Topic '{name}' already exists"}), 400
        
        # Create new topic
        topic = BusinessTopic(
            business_id=business_id,
            name=name,
            synonyms=data.get('synonyms', []),
            is_active=True
        )
        
        db.session.add(topic)
        db.session.commit()
        
        # Invalidate cache to trigger embedding generation
        topic_classifier.invalidate_cache(business_id)
        
        logger.info(f"✅ Topic created: {name} for business {business_id}")
        
        return jsonify({
            "success": True,
            "topic": {
                "id": topic.id,
                "name": topic.name,
                "synonyms": topic.synonyms or [],
                "is_active": topic.is_active,
                "created_at": topic.created_at.isoformat() if topic.created_at else None
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating topic: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@ai_topics_bp.route('/api/business/topics/<int:topic_id>', methods=['PUT'])
@require_api_auth(['owner', 'admin'])
@csrf.exempt
def update_topic(topic_id):
    """Update a topic"""
    try:
        from flask import g
        business_id = g.business_id
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Get topic
        topic = BusinessTopic.query.filter_by(
            id=topic_id,
            business_id=business_id
        ).first()
        
        if not topic:
            return jsonify({"error": "Topic not found"}), 404
        
        # Update fields
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({"error": "Topic name cannot be empty"}), 400
            
            # Check for duplicates
            existing = BusinessTopic.query.filter(
                BusinessTopic.business_id == business_id,
                BusinessTopic.name == name,
                BusinessTopic.id != topic_id
            ).first()
            
            if existing:
                return jsonify({"error": f"Topic '{name}' already exists"}), 400
            
            topic.name = name
        
        if 'synonyms' in data:
            topic.synonyms = data['synonyms'] if data['synonyms'] else []
        
        if 'is_active' in data:
            topic.is_active = bool(data['is_active'])
        
        # Clear embedding to force regeneration
        topic.embedding = None
        
        db.session.commit()
        
        # Invalidate cache
        topic_classifier.invalidate_cache(business_id)
        
        logger.info(f"✅ Topic updated: {topic.name} for business {business_id}")
        
        return jsonify({
            "success": True,
            "topic": {
                "id": topic.id,
                "name": topic.name,
                "synonyms": topic.synonyms or [],
                "is_active": topic.is_active,
                "updated_at": topic.updated_at.isoformat() if topic.updated_at else None
            }
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating topic: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@ai_topics_bp.route('/api/business/topics/<int:topic_id>', methods=['DELETE'])
@require_api_auth(['owner', 'admin'])
@csrf.exempt
def delete_topic(topic_id):
    """Soft delete a topic (set is_active=false)"""
    try:
        from flask import g
        business_id = g.business_id
        
        # Get topic
        topic = BusinessTopic.query.filter_by(
            id=topic_id,
            business_id=business_id
        ).first()
        
        if not topic:
            return jsonify({"error": "Topic not found"}), 404
        
        # Soft delete
        topic.is_active = False
        db.session.commit()
        
        # Invalidate cache
        topic_classifier.invalidate_cache(business_id)
        
        logger.info(f"✅ Topic soft deleted: {topic.name} for business {business_id}")
        
        return jsonify({
            "success": True,
            "message": f"Topic '{topic.name}' has been deactivated"
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting topic: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@ai_topics_bp.route('/api/business/topics/rebuild-embeddings', methods=['POST'])
@require_api_auth(['owner', 'admin'])
@csrf.exempt
def rebuild_embeddings():
    """Rebuild embeddings for all topics"""
    try:
        from flask import g
        business_id = g.business_id
        
        result = topic_classifier.rebuild_all_embeddings(business_id)
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500
    
    except Exception as e:
        logger.error(f"Error rebuilding embeddings: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
