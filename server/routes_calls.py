"""
Calls API Routes - מסלולי API לשיחות
Includes call listing, details, transcript, and secure recording download
"""
from flask import Blueprint, request, jsonify, send_file, current_app, session, g, Response, make_response
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
    """
    רשימת שיחות עם מסננים וחיפוש
    
    NEW: Filters out parent calls by default to prevent duplicates
    Shows only child legs or standalone calls
    """
    try:
        # Get filters from query params
        search = request.args.get('search', '').strip()
        status = request.args.get('status', 'all')
        direction = request.args.get('direction', 'all')
        lead_id = request.args.get('lead_id', '').strip()
        show_all = request.args.get('show_all', 'false').lower() == 'true'  # 🔥 NEW: Show parent calls
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
        offset = int(request.args.get('offset', 0))
        
        # BUILD 135: SECURITY FIX - Always use get_business_id() (tenant-isolated)
        # No longer accepting business_id from query param to prevent cross-tenant access
        business_id = get_business_id()
        
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Build query
        query = Call.query.filter(Call.business_id == business_id)
        
        # 🔥 NEW: Filter out parent calls by default (prevent duplicates)
        # Parent calls are typically short (1 second) and get replaced by child leg
        # Only show calls that either:
        # 1. Don't have a parent_call_sid (standalone/child calls)
        # 2. Have duration > 1 and status = completed (actual calls)
        # 3. show_all=true (admin debugging)
        if not show_all:
            # Smart filter: prefer child legs over parent calls
            # Hide parent calls that have corresponding child legs
            # Also hide very short cancelled/failed calls (< 2 seconds)
            from sqlalchemy import and_, not_, exists
            
            # Subquery to find call_sids that are parent_call_sid in other records
            parent_exists = exists().where(
                and_(
                    Call.parent_call_sid == Call.call_sid,
                    Call.business_id == business_id
                )
            )
            
            # Filter logic:
            # Include calls where:
            # 1. No parent_call_sid exists (standalone calls) OR
            # 2. Has parent_call_sid (is a child leg) OR
            # 3. Duration > 1 (actual conversation happened)
            # Exclude parent calls with duration <= 1 that have child legs
            query = query.filter(
                or_(
                    Call.parent_call_sid.isnot(None),  # Is a child leg
                    and_(
                        Call.parent_call_sid.is_(None),  # Has no parent
                        or_(
                            not_(parent_exists),  # And is not itself a parent of another call
                            Call.duration > 1  # Or has significant duration
                        )
                    )
                )
            )
        
        # Apply filters
        if lead_id:
            # Filter by lead_id if provided
            query = query.filter(Call.lead_id == int(lead_id))
        
        if search:
            # ✅ Search in both final_transcript (offline) and transcription (realtime)
            search_conditions = [
                Call.from_number.ilike(f'%{search}%'),
                Call.transcription.ilike(f'%{search}%')
            ]
            # Add final_transcript to search if column exists
            if hasattr(Call, 'final_transcript'):
                search_conditions.append(Call.final_transcript.ilike(f'%{search}%'))
            
            query = query.filter(or_(*search_conditions))
        
        if status != 'all':
            query = query.filter(Call.status == status)
            
        # ✅ Direction filter - CallLog model has direction field
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
            
            # ✅ Prefer offline transcript (final_transcript) over realtime (transcription)
            best_transcript = getattr(call, 'final_transcript', None) or call.transcription
            
            calls_data.append({
                "sid": call.call_sid,
                "call_sid": call.call_sid,  # 🔥 NEW: Add explicit call_sid field
                "lead_id": getattr(call, 'lead_id', None),
                "lead_name": getattr(call, 'lead_name', None),
                "from_e164": call.from_number,
                "to_e164": getattr(call, 'to_number', None),
                "duration": getattr(call, 'duration', 0),
                "status": call.status,
                "direction": getattr(call, 'direction', 'inbound'),
                "twilio_direction": getattr(call, 'twilio_direction', None),  # 🔥 NEW: Original Twilio direction
                "parent_call_sid": getattr(call, 'parent_call_sid', None),  # 🔥 NEW: Parent call SID
                "at": call.created_at.isoformat() if call.created_at else None,
                "created_at": call.created_at.isoformat() if call.created_at else None,
                "recording_url": call.recording_url,
                "transcription": best_transcript,
                "transcript": best_transcript,  # Alias for compatibility
                "final_transcript": getattr(call, 'final_transcript', None),  # 🔥 FIX: Add explicit final_transcript field
                "summary": call.summary if hasattr(call, 'summary') else None,
                "hasRecording": bool(call.recording_url),
                "hasTranscript": bool(best_transcript),
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
        # ✅ Prefer offline transcript (final_transcript) over realtime (transcription)
        best_transcript = getattr(call, 'final_transcript', None) or call.transcription or "אין תמליל זמין"
        
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
                "hasTranscript": bool(getattr(call, 'final_transcript', None) or call.transcription)
            },
            "transcript": best_transcript,
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
    """הורדה מאובטחת של הקלטה דרך השרת - with Range support for iOS"""
    try:
        business_id = get_business_id()
        if not business_id:
            log.warning(f"Download recording: No business_id for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            log.warning(f"Download recording: Call not found call_sid={call_sid}, business_id={business_id}")
            return jsonify({"success": False, "error": "Call not found"}), 404
        
        # Check if recording is expired (7 days)
        if call.created_at and (datetime.utcnow() - call.created_at).days > 7:
            log.info(f"Download recording: Recording expired for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Recording expired and deleted"}), 410
        
        # 🔥 FIX 502: Check if recording_url exists before attempting download
        if not call.recording_url:
            log.warning(f"Download recording: No recording_url for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Recording URL not available"}), 404
        
        # ✅ Use unified recording service - same source as worker
        from server.services.recording_service import get_recording_file_for_call
        
        # 🔥 FIX 502: Wrap in try-except to prevent crashes from Twilio failures
        try:
            audio_path = get_recording_file_for_call(call)
        except Exception as fetch_error:
            log.error(f"Download recording: Failed to fetch recording for call_sid={call_sid}: {fetch_error}")
            return jsonify({"success": False, "error": "Failed to fetch recording from Twilio"}), 500
        
        if not audio_path:
            log.warning(f"Download recording: No audio_path returned for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Recording not available"}), 404
        
        # 🔥 FIX 502: Verify file exists and is readable before attempting to serve
        if not os.path.exists(audio_path):
            log.error(f"Download recording: File does not exist at path={audio_path}")
            return jsonify({"success": False, "error": "Recording file not found"}), 404
        
        # 🎯 iOS FIX: Support Range requests for audio streaming
        # Get file size for Content-Length and Range calculations
        file_size = os.path.getsize(audio_path)
        
        # Check if Range header is present (iOS requires this)
        range_header = request.headers.get('Range', None)
        
        if range_header:
            # Parse Range header (format: "bytes=start-end")
            # Supports: bytes=0-999, bytes=0-, bytes=-500 (last 500 bytes)
            byte_range = range_header.replace('bytes=', '').split('-')
            
            # Handle suffix-byte-range-spec: bytes=-500 (last N bytes)
            if not byte_range[0] and byte_range[1]:
                # Request for last N bytes
                suffix_length = int(byte_range[1])
                start = max(0, file_size - suffix_length)
                end = file_size - 1
            else:
                # Normal range or open-ended range
                start = int(byte_range[0]) if byte_range[0] else 0
                end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
            
            # Ensure valid range
            if start >= file_size:
                return Response(status=416)  # Range Not Satisfiable
            
            end = min(end, file_size - 1)
            length = end - start + 1
            
            # Read partial content
            with open(audio_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)
            
            # Return 206 Partial Content with proper headers
            rv = Response(
                data,
                206,
                mimetype='audio/mpeg',
                direct_passthrough=True
            )
            rv.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            rv.headers.add('Accept-Ranges', 'bytes')
            rv.headers.add('Content-Length', str(length))
            # 🎯 FIX: Content-Disposition inline for browser playback (required for iOS/Chrome)
            rv.headers.add('Content-Disposition', 'inline')
            # 🎯 FIX: CORS headers for cross-origin requests (if frontend on different domain)
            # Security: Use specific origin from request header, NOT wildcard with credentials
            origin = request.headers.get('Origin')
            if origin:
                rv.headers.add('Access-Control-Allow-Origin', origin)
                rv.headers.add('Access-Control-Allow-Credentials', 'true')
                # 🎯 FIX: Vary header for proper caching with multiple origins
                rv.headers.add('Vary', 'Origin')
                # 🎯 FIX: Expose headers so UI can read them during Range requests
                rv.headers.add('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length, Content-Type')
            return rv
        else:
            # No Range header - serve entire file with Accept-Ranges header
            response = make_response(send_file(
                audio_path,
                mimetype="audio/mpeg",
                as_attachment=False,
                conditional=True,  # Enable conditional requests
                max_age=3600  # Cache for 1 hour
            ))
            # 🎯 FIX: Add required headers for audio streaming (iOS/Android compatibility)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Disposition'] = 'inline'
            response.headers['Content-Length'] = str(file_size)
            # 🎯 FIX: CORS headers for cross-origin requests
            # Security: Use specific origin from request header, NOT wildcard with credentials
            origin = request.headers.get('Origin')
            if origin:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                # 🎯 FIX: Vary header for proper caching with multiple origins
                response.headers['Vary'] = 'Origin'
                # 🎯 FIX: Expose headers so UI can read them during Range requests
                response.headers['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length, Content-Type'
            return response
        
    except Exception as e:
        log.error(f"Error downloading recording: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/recordings/<call_sid>/stream", methods=["GET"])
@require_api_auth()
def stream_recording(call_sid):
    """
    🔥 FIX 502: Asynchronous recording streaming endpoint
    
    Returns:
    - 200 + audio file if recording is cached locally
    - 202 Accepted if recording needs to be downloaded (job enqueued)
    - 403 Forbidden if call doesn't belong to user's tenant
    - 404 Not Found if call doesn't exist or no recording available
    - 410 Gone if recording is expired (>7 days)
    """
    try:
        business_id = get_business_id()
        if not business_id:
            log.warning(f"Stream recording: No business_id for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Check if call exists and belongs to this business (tenant validation)
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            log.warning(f"Stream recording: Call not found or access denied call_sid={call_sid}, business_id={business_id}")
            return jsonify({"success": False, "error": "Recording not found"}), 404
        
        # Check if recording is expired (7 days)
        if call.created_at and (datetime.utcnow() - call.created_at).days > 7:
            log.info(f"Stream recording: Recording expired for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Recording expired"}), 410
        
        # Check if recording_url exists
        if not call.recording_url:
            log.warning(f"Stream recording: No recording_url for call_sid={call_sid}")
            return jsonify({"success": False, "error": "No recording available"}), 404
        
        # Check if file exists locally
        from server.services.recording_service import check_local_recording_exists, _get_recordings_dir
        
        if check_local_recording_exists(call_sid):
            # File exists - serve it immediately
            recordings_dir = _get_recordings_dir()
            local_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
            
            # Get file size for Content-Length and Range calculations
            file_size = os.path.getsize(local_path)
            
            # Check if Range header is present (iOS requires this)
            range_header = request.headers.get('Range', None)
            
            if range_header:
                # Parse Range header (format: "bytes=start-end")
                byte_range = range_header.replace('bytes=', '').split('-')
                
                # Handle suffix-byte-range-spec: bytes=-500 (last N bytes)
                if not byte_range[0] and byte_range[1]:
                    suffix_length = int(byte_range[1])
                    start = max(0, file_size - suffix_length)
                    end = file_size - 1
                else:
                    start = int(byte_range[0]) if byte_range[0] else 0
                    end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
                
                # Ensure valid range
                if start >= file_size:
                    return Response(status=416)  # Range Not Satisfiable
                
                end = min(end, file_size - 1)
                length = end - start + 1
                
                # Read partial content
                with open(local_path, 'rb') as f:
                    f.seek(start)
                    data = f.read(length)
                
                # Return 206 Partial Content with proper headers
                rv = Response(
                    data,
                    206,
                    mimetype='audio/mpeg',
                    direct_passthrough=True
                )
                rv.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
                rv.headers.add('Accept-Ranges', 'bytes')
                rv.headers.add('Content-Length', str(length))
                rv.headers.add('Content-Disposition', 'inline')
                
                # CORS headers
                origin = request.headers.get('Origin')
                if origin:
                    rv.headers.add('Access-Control-Allow-Origin', origin)
                    rv.headers.add('Access-Control-Allow-Credentials', 'true')
                    rv.headers.add('Vary', 'Origin')
                    rv.headers.add('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length, Content-Type')
                return rv
            else:
                # No Range header - serve entire file
                response = make_response(send_file(
                    local_path,
                    mimetype="audio/mpeg",
                    as_attachment=False,
                    conditional=True,
                    max_age=3600
                ))
                response.headers['Accept-Ranges'] = 'bytes'
                response.headers['Content-Disposition'] = 'inline'
                response.headers['Content-Length'] = str(file_size)
                
                # CORS headers
                origin = request.headers.get('Origin')
                if origin:
                    response.headers['Access-Control-Allow-Origin'] = origin
                    response.headers['Access-Control-Allow-Credentials'] = 'true'
                    response.headers['Vary'] = 'Origin'
                    response.headers['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length, Content-Type'
                return response
        else:
            # File doesn't exist locally - enqueue download job and return 202
            log.info(f"Stream recording: File not cached for call_sid={call_sid}, enqueuing download job")
            
            # Enqueue job to download recording in background
            from server.tasks_recording import enqueue_recording_job
            enqueue_recording_job(
                call_sid=call_sid,
                recording_url=call.recording_url,
                business_id=business_id,
                from_number=call.from_number or "",
                to_number=call.to_number or "",
                retry_count=0
            )
            
            # Return 202 Accepted to indicate processing
            return jsonify({
                "success": True,
                "status": "processing",
                "message": "Recording is being prepared, please retry in a few seconds"
            }), 202
        
    except Exception as e:
        log.error(f"Error streaming recording for {call_sid}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

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