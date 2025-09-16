"""
Calls API Routes - מסלולי API לשיחות
Includes call listing, details, transcript, and secure recording download
"""
from flask import Blueprint, request, jsonify, send_file, current_app, session
from server.auth_api import require_api_auth
from server.extensions import csrf
from server.models_sql import Call, db
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
        business_id = request.args.get('business_id')
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
        offset = int(request.args.get('offset', 0))
        
        # Get business_id from session if not provided
        if not business_id:
            business_id = session.get('business_id')
        
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Build query
        query = Call.query.filter(Call.business_id == business_id)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    Call.lead_name.ilike(f'%{search}%'),
                    Call.from_e164.ilike(f'%{search}%'),
                    Call.transcription.ilike(f'%{search}%')
                )
            )
        
        if status != 'all':
            query = query.filter(Call.status == status)
            
        if direction != 'all':
            query = query.filter(Call.direction == direction)
        
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
                "sid": call.sid,
                "lead_id": call.lead_id,
                "lead_name": call.lead_name,
                "from_e164": call.from_e164,
                "to_e164": call.to_e164,
                "duration": call.duration or 0,
                "status": call.status,
                "direction": call.direction,
                "at": call.created_at.isoformat() if call.created_at else None,
                "recording_url": call.recording_url,
                "transcription": call.transcription,
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
        business_id = session.get('business_id')
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        call = Call.query.filter(
            Call.sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            return jsonify({"success": False, "error": "Call not found"}), 404
        
        # Enhanced call details
        details = {
            "call": {
                "sid": call.sid,
                "lead_id": call.lead_id,
                "lead_name": call.lead_name,
                "from_e164": call.from_e164,
                "to_e164": call.to_e164,
                "duration": call.duration or 0,
                "status": call.status,
                "direction": call.direction,
                "at": call.created_at.isoformat() if call.created_at else None,
                "recording_url": call.recording_url,
                "hasRecording": bool(call.recording_url),
                "hasTranscript": bool(call.transcription)
            },
            "transcript": call.transcription or "אין תמליל זמין",
            "summary": call.summary or "הובנה ע״י בינה מלאכותית - פגישה או עניין במוצר", 
            "sentiment": call.sentiment or "ניטרלי"
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
    """הורדה מאובטחת של הקלטה דרך השרת"""
    try:
        business_id = session.get('business_id')
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        call = Call.query.filter(
            Call.sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call or not call.recording_url:
            return jsonify({"success": False, "error": "Recording not found"}), 404
        
        # Check if recording is expired (7 days)
        if call.created_at and (datetime.utcnow() - call.created_at).days > 7:
            return jsonify({"success": False, "error": "Recording expired and deleted"}), 410
        
        # Security: Validate recording URL is from trusted Twilio domain
        parsed_url = urllib.parse.urlparse(call.recording_url)
        allowed_hosts = ['api.twilio.com']
        if parsed_url.hostname not in allowed_hosts:
            log.warning(f"Suspicious recording URL host: {parsed_url.hostname}")
            return jsonify({"success": False, "error": "Invalid recording source"}), 403
        
        # Download from Twilio with auth
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            return jsonify({"success": False, "error": "Twilio credentials not configured"}), 500
        
        # Download recording
        mp3_url = f"{call.recording_url}.mp3"
        auth = (account_sid, auth_token)
        
        try:
            response = requests.get(mp3_url, auth=auth, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            log.error(f"Failed to download from Twilio: {e}")
            return jsonify({"success": False, "error": "Failed to download recording"}), 502
        
        # Create temporary file and serve it
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        try:
            tmp_file.write(response.content)
            tmp_file.close()
            
            # Serve file with proper cleanup
            try:
                return send_file(
                    tmp_file.name,
                    as_attachment=True,
                    download_name=f"recording-{call_sid}.mp3",
                    mimetype="audio/mpeg"
                )
            finally:
                # Clean up temp file immediately after sending
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    log.warning(f"Failed to cleanup temp file: {tmp_file.name}")
        except Exception as e:
            # Cleanup on error
            try:
                os.unlink(tmp_file.name)
            except OSError:
                pass
            raise e
    except Exception as e:
        log.error(f"Error downloading recording: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/cleanup", methods=["POST"])
@require_api_auth(["admin"])
def cleanup_old_recordings():
    """מחיקה ידנית של הקלטות ישנות (רק למנהלים)"""
    try:
        # Delete recordings older than 7 days
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        old_calls = Call.query.filter(
            Call.created_at < cutoff_date,
            Call.recording_url.isnot(None)
        ).all()
        
        deleted_count = 0
        for call in old_calls:
            # Clear recording URL and transcript to free space
            call.recording_url = None
            # Keep transcription for now as it's text and small
            deleted_count += 1
        
        db.session.commit()
        
        log.info(f"Cleaned up {deleted_count} old recordings")
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"נמחקו {deleted_count} הקלטות ישנות"
        })
        
    except Exception as e:
        log.error(f"Error cleaning up recordings: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/calls/stats", methods=["GET"])
@require_api_auth()
def get_calls_stats():
    """סטטיסטיקות שיחות"""
    try:
        business_id = session.get('business_id')
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