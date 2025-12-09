"""
Calls API Routes - מסלולי API לשיחות
Includes call listing, details, transcript, and secure recording download
"""
from flask import Blueprint, request, jsonify, send_file, current_app, session, g
from server.auth_api import require_api_auth
from server.routes_crm import get_business_id
from server.extensions import csrf
from server.models_sql import CallLog as Call, db
from server.tasks_recording import save_call_status
from sqlalchemy import or_
import os
import tempfile
import requests
from datetime import datetime, timedelta
import logging
import urllib.parse

log = logging.getLogger(__name__)

calls_bp = Blueprint("calls", __name__)

@calls_bp.route("/api/calls", methods=["GET"])
@require_api_auth()
def list_calls():
    """רשימת שיחות עם מסננים וחיפוש"""
    try:
        # Get filters from query params
        search = request.args.get('search', '').strip()
        status = request.args.get('status', 'all')
        direction = request.args.get('direction', 'all')
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
        offset = int(request.args.get('offset', 0))
        
        # BUILD 135: SECURITY FIX - Always use get_business_id() (tenant-isolated)
        # No longer accepting business_id from query param to prevent cross-tenant access
        business_id = get_business_id()
        
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Build query
        query = Call.query.filter(Call.business_id == business_id)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    Call.from_number.ilike(f'%{search}%'),
                    Call.transcription.ilike(f'%{search}%')
                )
            )
        
        if status != 'all':
            query = query.filter(Call.status == status)
            
        # Direction filter commented out as field doesn't exist in current CallLog model
        # if direction != 'all':
        #     query = query.filter(Call.direction == direction)
        
        # Order by creation time desc
        query = query.order_by(Call.created_at.desc())
        
        # Paginate
        total = query.count()
        calls = query.offset(offset).limit(limit).all()
        
        # Format response
        calls_data = []
        for call in calls:
            # Calculate expiry date (7 days from creation)
            expiry_date = None
            if call.recording_url and call.created_at:
                expiry_date = (call.created_at + timedelta(days=7)).isoformat()
            
            calls_data.append({
                "sid": call.call_sid,
                "lead_id": getattr(call, 'lead_id', None),
                "lead_name": getattr(call, 'lead_name', None),
                "from_e164": call.from_number,
                "to_e164": getattr(call, 'to_number', None),
                "duration": getattr(call, 'duration', 0),
                "status": call.status,
                "direction": getattr(call, 'direction', 'inbound'),
                "at": call.created_at.isoformat() if call.created_at else None,
                "created_at": call.created_at.isoformat() if call.created_at else None,
                "recording_url": call.recording_url,
                "transcription": call.transcription,
                "summary": call.summary if hasattr(call, 'summary') else None,
                "hasRecording": bool(call.recording_url),
                "hasTranscript": bool(call.transcription),
                "expiresAt": expiry_date
            })
        
        return jsonify({
            "success": True,
            "calls": calls_data,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": (offset + limit) < total
            }
        })
        
    except Exception as e:
        log.error(f"Error listing calls: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/<call_sid>/details", methods=["GET"])
@require_api_auth()
def get_call_details(call_sid):
    """פרטי שיחה מפורטים עם תמליל מלא"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            return jsonify({"success": False, "error": "Call not found"}), 404
        
        # Enhanced call details
        details = {
            "call": {
                "sid": call.call_sid,
                "lead_id": getattr(call, 'lead_id', None),
                "lead_name": getattr(call, 'lead_name', None),
                "from_e164": call.from_number,
                "to_e164": getattr(call, 'to_number', None),
                "duration": getattr(call, 'duration', 0),
                "status": call.status,
                "direction": getattr(call, 'direction', 'inbound'),
                "at": call.created_at.isoformat() if call.created_at else None,
                "recording_url": call.recording_url,
                "hasRecording": bool(call.recording_url),
                "hasTranscript": bool(call.transcription)
            },
            "transcript": call.transcription or "אין תמליל זמין",
            "summary": call.summary if call.summary else None,
            "sentiment": getattr(call, 'sentiment', None)
        }
        
        return jsonify({
            "success": True,
            **details
        })
        
    except Exception as e:
        log.error(f"Error getting call details: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/<call_sid>/download", methods=["GET"])
@require_api_auth()
def download_recording(call_sid):
    """הורדה מאובטחת של הקלטה דרך השרת - using unified recording service"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            return jsonify({"success": False, "error": "Call not found"}), 404
        
        # Check if recording is expired (7 days)
        if call.created_at and (datetime.utcnow() - call.created_at).days > 7:
            return jsonify({"success": False, "error": "Recording expired and deleted"}), 410
        
        # ✅ Use unified recording service - same source as worker
        from server.services.recording_service import get_recording_file_for_call
        
        audio_path = get_recording_file_for_call(call)
        if not audio_path:
            return jsonify({"success": False, "error": "Recording not available"}), 404
        
        # Serve the file directly
        return send_file(
            audio_path,
            mimetype="audio/mpeg",
            as_attachment=False,
        )
        
    except Exception as e:
        log.error(f"Error downloading recording: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/cleanup", methods=["POST"])
@calls_bp.route("/api/calls/cleanup-recordings", methods=["POST"])
@require_api_auth(["system_admin", "owner", "admin"])
def cleanup_old_recordings():
    """מחיקה ידנית של הקלטות ישנות (רק למנהלים) - מסנן לפי עסק"""
    try:
        # Get business_id for tenant filtering
        business_id = get_business_id()
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Delete recordings older than 7 days - FILTERED BY BUSINESS
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        old_calls = Call.query.filter(
            Call.business_id == business_id,
            Call.created_at < cutoff_date,
            Call.recording_url.isnot(None)
        ).all()
        
        deleted_count = 0
        for call in old_calls:
            # Clear recording URL to mark as deleted
            call.recording_url = None
            deleted_count += 1
        
        db.session.commit()
        
        log.info(f"Cleaned up {deleted_count} old recordings for business {business_id}")
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"נמחקו {deleted_count} הקלטות ישנות"
        })
        
    except Exception as e:
        log.error(f"Error cleaning up recordings: {e}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/stats", methods=["GET"])
@require_api_auth()
def get_calls_stats():
    """סטטיסטיקות שיחות"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Get stats
        total_calls = Call.query.filter(Call.business_id == business_id).count()
        
        with_recording = Call.query.filter(
            Call.business_id == business_id,
            Call.recording_url.isnot(None)
        ).count()
        
        with_transcript = Call.query.filter(
            Call.business_id == business_id,
            Call.transcription.isnot(None)
        ).count()
        
        # Expiring soon (next 2 days)
        expiry_cutoff = datetime.utcnow() + timedelta(days=2)
        old_cutoff = datetime.utcnow() - timedelta(days=5)  # Created 5+ days ago
        
        expiring_soon = Call.query.filter(
            Call.business_id == business_id,
            Call.recording_url.isnot(None),
            Call.created_at < expiry_cutoff,
            Call.created_at > old_cutoff
        ).count()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_calls": total_calls,
                "with_recording": with_recording,
                "with_transcript": with_transcript,
                "expiring_soon": expiring_soon
            }
        })
        
    except Exception as e:
        log.error(f"Error getting call stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/<call_sid>/transcript", methods=["PUT"])
@require_api_auth()
def update_transcript(call_sid):
    """עדכון תמליל שיחה - לפי call_sid או מספר טלפון"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        data = request.get_json() or {}
        new_transcript = data.get('transcript', '').strip()
        
        if not new_transcript:
            return jsonify({"success": False, "error": "Transcript text required"}), 400
        
        # Try to find call by call_sid first
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        # If not found, try by phone number (E.164 format)
        if not call:
            call = Call.query.filter(
                Call.business_id == business_id
            ).filter(
                or_(
                    Call.from_number == call_sid,
                    Call.to_number == call_sid
                )
            ).order_by(Call.created_at.desc()).first()
        
        if not call:
            return jsonify({"success": False, "error": "Call not found"}), 404
        
        # Update transcript
        call.transcription = new_transcript
        db.session.commit()
        
        log.info(f"Updated transcript for call {call.call_sid} (phone: {call.from_number})")
        
        return jsonify({
            "success": True,
            "message": "Transcript updated successfully",
            "transcript": new_transcript,
            "call_sid": call.call_sid
        })
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error updating transcript: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@calls_bp.route("/api/calls/<call_sid>", methods=["DELETE"])
@require_api_auth(["admin", "owner", "system_admin"])
def delete_call(call_sid):
    """מחיקת שיחה - רק למנהלים"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            return jsonify({"success": False, "error": "Call not found"}), 404
        
        db.session.delete(call)
        db.session.commit()
        
        log.info(f"Deleted call {call_sid} for business {business_id}")
        
        return jsonify({
            "success": True,
            "message": "שיחה נמחקה בהצלחה"
        })
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error deleting call: {e}")
        return jsonify({"success": False, "error": str(e)}), 500