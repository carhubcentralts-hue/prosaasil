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
            "embedding_threshold": ai_settings.embedding_threshold,
            "embedding_top_k": ai_settings.embedding_top_k,
            "auto_tag_leads": ai_settings.auto_tag_leads,
            "auto_tag_calls": ai_settings.auto_tag_calls,
            "auto_tag_whatsapp": ai_settings.auto_tag_whatsapp,
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
        
        if 'embedding_threshold' in data:
            threshold = float(data['embedding_threshold'])
            if not (0.5 <= threshold <= 0.95):  # Match UI range
                return jsonify({"error": "Threshold must be between 0.5 and 0.95"}), 400
            ai_settings.embedding_threshold = threshold
        
        if 'embedding_top_k' in data:
            top_k = int(data['embedding_top_k'])
            if top_k < 1 or top_k > 10:
                return jsonify({"error": "top_k must be between 1 and 10"}), 400
            ai_settings.embedding_top_k = top_k
        
        if 'auto_tag_leads' in data:
            ai_settings.auto_tag_leads = bool(data['auto_tag_leads'])
        
        if 'auto_tag_calls' in data:
            ai_settings.auto_tag_calls = bool(data['auto_tag_calls'])
        
        if 'auto_tag_whatsapp' in data:
            ai_settings.auto_tag_whatsapp = bool(data['auto_tag_whatsapp'])
        
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


@ai_topics_bp.route('/api/call_logs/<int:call_log_id>/reclassify-topic', methods=['POST'])
@require_api_auth(['owner', 'admin'])
@csrf.exempt
def reclassify_call_topic(call_log_id):
    """
    Re-classify topic for a specific call log.
    
    This endpoint:
    1. Resets the detected_topic fields (id, confidence, source)
    2. Re-runs topic classification
    3. Returns the new classification result
    
    Useful after:
    - Updating topic definitions
    - Adding/modifying synonyms
    - Adjusting classification threshold
    """
    try:
        from flask import g
        from server.models_sql import CallLog, BusinessAISettings, Lead
        business_id = g.business_id
        
        # Get call log
        call_log = CallLog.query.filter_by(
            id=call_log_id,
            business_id=business_id
        ).first()
        
        if not call_log:
            return jsonify({"error": "Call log not found"}), 404
        
        # Get AI settings
        ai_settings = BusinessAISettings.query.filter_by(business_id=business_id).first()
        
        if not ai_settings or not ai_settings.embedding_enabled:
            return jsonify({
                "error": "Topic classification is not enabled for this business"
            }), 400
        
        # Get transcript to classify
        text_to_classify = None
        if call_log.final_transcript and len(call_log.final_transcript.strip()) > 50:
            text_to_classify = call_log.final_transcript
        elif call_log.transcription and len(call_log.transcription.strip()) > 50:
            text_to_classify = call_log.transcription
        
        if not text_to_classify:
            return jsonify({
                "error": "No transcript available for classification (transcript too short or missing)"
            }), 400
        
        logger.info(f"[RECLASSIFY] Starting re-classification for call {call_log_id} ({len(text_to_classify)} chars)")
        
        # Reset existing classification
        old_topic_id = call_log.detected_topic_id
        old_topic_name = None
        if old_topic_id:
            old_topic = BusinessTopic.query.get(old_topic_id)
            old_topic_name = old_topic.name if old_topic else None
        
        call_log.detected_topic_id = None
        call_log.detected_topic_confidence = None
        call_log.detected_topic_source = None
        
        # Also reset lead topic if exists and was set by this call
        if call_log.lead_id:
            lead = Lead.query.get(call_log.lead_id)
            if lead and lead.detected_topic_id == old_topic_id:
                lead.detected_topic_id = None
                lead.detected_topic_confidence = None
                lead.detected_topic_source = None
        
        db.session.commit()
        
        logger.info(f"[RECLASSIFY] Reset classification for call {call_log_id} (was: {old_topic_name})")
        
        # Run classification
        classification_result = topic_classifier.classify_text(business_id, text_to_classify)
        
        if classification_result:
            topic_id = classification_result['topic_id']
            confidence = classification_result['score']
            method = classification_result.get('method', 'embedding')
            topic_name = classification_result['topic_name']
            
            logger.info(f"[RECLASSIFY] ✅ New topic: '{topic_name}' (confidence={confidence:.3f}, method={method})")
            
            # Update call log if auto_tag_calls is enabled
            if ai_settings.auto_tag_calls:
                call_log.detected_topic_id = topic_id
                call_log.detected_topic_confidence = confidence
                call_log.detected_topic_source = method
            
            # Update lead if auto_tag_leads is enabled and lead exists
            if ai_settings.auto_tag_leads and call_log.lead_id:
                lead = Lead.query.get(call_log.lead_id)
                if lead:
                    lead.detected_topic_id = topic_id
                    lead.detected_topic_confidence = confidence
                    lead.detected_topic_source = method
            
            db.session.commit()
            
            return jsonify({
                "success": True,
                "classification": {
                    "topic_id": topic_id,
                    "topic_name": topic_name,
                    "confidence": confidence,
                    "method": method,
                    "top_matches": classification_result.get('top_matches', [])
                },
                "previous_topic": old_topic_name,
                "message": f"Successfully re-classified call to topic '{topic_name}' (method: {method})"
            })
        else:
            logger.info(f"[RECLASSIFY] No topic matched threshold for call {call_log_id}")
            db.session.commit()
            
            return jsonify({
                "success": True,
                "classification": None,
                "previous_topic": old_topic_name,
                "message": "No topic matched the classification threshold"
            })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error re-classifying call {call_log_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

