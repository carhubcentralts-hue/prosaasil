"""
API Routes for Call Analysis and Transcription Management
Created for Hebrew AI Call Center CRM
"""

from flask import Blueprint, jsonify, request
from models import CallLog, db
from auth import admin_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
call_analysis_bp = Blueprint('call_analysis', __name__)

@call_analysis_bp.route('/api/admin/calls', methods=['GET'])
@admin_required
def get_all_calls():
    """Get all calls for admin analysis"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Get calls with pagination
        calls_query = CallLog.query.order_by(CallLog.created_at.desc())
        calls = calls_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        calls_data = []
        for call in calls.items:
            call_data = {
                'id': call.id,
                'call_sid': call.call_sid,
                'from_number': call.from_number,
                'to_number': call.to_number,
                'call_status': call.call_status,
                'call_duration': call.call_duration,
                'transcription': call.transcription,
                'ai_response': call.ai_response,
                'recording_url': call.recording_url,
                'created_at': call.created_at.isoformat() if call.created_at else None,
                'updated_at': call.updated_at.isoformat() if call.updated_at else None,
                'business_id': call.business_id,
                'conversation_summary': call.conversation_summary
            }
            calls_data.append(call_data)
        
        result = {
            'calls': calls_data,
            'pagination': {
                'page': calls.page,
                'pages': calls.pages,
                'per_page': calls.per_page,
                'total': calls.total,
                'has_next': calls.has_next,
                'has_prev': calls.has_prev
            }
        }
        
        logger.info(f"📞 Retrieved {len(calls_data)} calls for admin analysis")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Error fetching calls: {str(e)}")
        return jsonify({'error': 'Failed to fetch calls'}), 500

@call_analysis_bp.route('/api/admin/calls/<int:call_id>', methods=['GET'])
@admin_required
def get_call_details(call_id):
    """Get detailed information for a specific call"""
    try:
        call = CallLog.query.get_or_404(call_id)
        
        call_data = {
            'id': call.id,
            'call_sid': call.call_sid,
            'from_number': call.from_number,
            'to_number': call.to_number,
            'call_status': call.call_status,
            'call_duration': call.call_duration,
            'transcription': call.transcription,
            'ai_response': call.ai_response,
            'recording_url': call.recording_url,
            'created_at': call.created_at.isoformat() if call.created_at else None,
            'updated_at': call.updated_at.isoformat() if call.updated_at else None,
            'ended_at': call.ended_at.isoformat() if call.ended_at else None,
            'business_id': call.business_id,
            'conversation_summary': call.conversation_summary
        }
        
        logger.info(f"📞 Retrieved call details for ID: {call_id}")
        return jsonify(call_data)
        
    except Exception as e:
        logger.error(f"❌ Error fetching call {call_id}: {str(e)}")
        return jsonify({'error': 'Call not found'}), 404

@call_analysis_bp.route('/api/admin/calls/stats', methods=['GET'])
@admin_required
def get_call_stats():
    """Get call statistics for dashboard"""
    try:
        total_calls = CallLog.query.count()
        completed_calls = CallLog.query.filter_by(call_status='completed').count()
        calls_with_transcription = CallLog.query.filter(CallLog.transcription.isnot(None)).filter(CallLog.transcription != '').count()
        calls_with_ai_response = CallLog.query.filter(CallLog.ai_response.isnot(None)).filter(CallLog.ai_response != '').count()
        
        # Get calls from last 24 hours
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_calls = CallLog.query.filter(CallLog.created_at >= yesterday).count()
        
        stats = {
            'total_calls': total_calls,
            'completed_calls': completed_calls,
            'calls_with_transcription': calls_with_transcription,
            'calls_with_ai_response': calls_with_ai_response,
            'recent_calls_24h': recent_calls,
            'success_rate': round((completed_calls / total_calls * 100), 2) if total_calls > 0 else 0,
            'transcription_rate': round((calls_with_transcription / total_calls * 100), 2) if total_calls > 0 else 0
        }
        
        logger.info(f"📊 Call statistics retrieved: {stats}")
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"❌ Error calculating call stats: {str(e)}")
        return jsonify({'error': 'Failed to calculate statistics'}), 500

@call_analysis_bp.route('/api/admin/calls/<int:call_id>/transcription', methods=['PUT'])
@admin_required
def update_call_transcription(call_id):
    """Update transcription for a specific call"""
    try:
        call = CallLog.query.get_or_404(call_id)
        data = request.get_json()
        
        if 'transcription' in data:
            call.transcription = data['transcription']
        
        if 'ai_response' in data:
            call.ai_response = data['ai_response']
        
        call.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"✅ Updated transcription for call ID: {call_id}")
        return jsonify({'message': 'Transcription updated successfully'})
        
    except Exception as e:
        logger.error(f"❌ Error updating call {call_id}: {str(e)}")
        return jsonify({'error': 'Failed to update transcription'}), 500

@call_analysis_bp.route('/api/admin/calls/search', methods=['GET'])
@admin_required
def search_calls():
    """Search calls by phone number or transcription content"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'calls': []})
        
        # Search in phone numbers and transcriptions
        calls = CallLog.query.filter(
            (CallLog.from_number.like(f'%{query}%')) |
            (CallLog.transcription.like(f'%{query}%')) |
            (CallLog.ai_response.like(f'%{query}%'))
        ).order_by(CallLog.created_at.desc()).limit(20).all()
        
        calls_data = []
        for call in calls:
            call_data = {
                'id': call.id,
                'call_sid': call.call_sid,
                'from_number': call.from_number,
                'to_number': call.to_number,
                'call_status': call.call_status,
                'transcription': call.transcription,
                'ai_response': call.ai_response,
                'created_at': call.created_at.isoformat() if call.created_at else None,
                'business_id': call.business_id
            }
            calls_data.append(call_data)
        
        logger.info(f"🔍 Search query '{query}' returned {len(calls_data)} results")
        return jsonify({'calls': calls_data})
        
    except Exception as e:
        logger.error(f"❌ Error searching calls: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500