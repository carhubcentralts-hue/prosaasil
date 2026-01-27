"""
Calls API Routes - מסלולי API לשיחות
Includes call listing, details, transcript, and secure recording download
"""
from flask import Blueprint, request, jsonify, send_file, current_app, session, g, Response, make_response
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.routes_crm import get_business_id
from server.extensions import csrf
from server.models_sql import CallLog as Call, db
from server.tasks_recording import save_call_status
from sqlalchemy import or_
import os
import tempfile
import requests
from datetime import datetime, timedelta, timezone
import logging
import urllib.parse

log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)  # Alias for consistency with other modules

calls_bp = Blueprint("calls", __name__)

@calls_bp.route("/api/calls", methods=["GET"])
@require_api_auth()
@require_page_access('calls_inbound')
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
        
        # 🔥 FIX: DO NOT enqueue downloads here!
        # This endpoint should ONLY return metadata.
        # Downloads should ONLY be triggered when:
        # 1. User clicks "play" button (calls stream_recording endpoint)
        # 2. User opens call details page
        # 3. Background cleanup runs (limited prefetch)
        
        # Format response
        calls_data = []
        for call in calls:
            # Calculate expiry date (7 days from creation)
            expiry_date = None
            if call.recording_url and call.created_at:
                expiry_date = (call.created_at + timedelta(days=7)).isoformat()
            
            # ✅ Prefer offline transcript (final_transcript) over realtime (transcription)
            best_transcript = getattr(call, 'final_transcript', None) or call.transcription
            
            # 🔥 FIX: Calculate customer phone based on direction
            # For inbound: customer is from_number (who called us)
            # For outbound: customer is to_number (who we called)
            call_direction = getattr(call, 'direction', 'inbound')
            customer_phone = call.from_number if call_direction == 'inbound' else getattr(call, 'to_number', call.from_number)
            
            calls_data.append({
                "sid": call.call_sid,
                "call_sid": call.call_sid,  # 🔥 NEW: Add explicit call_sid field
                "lead_id": getattr(call, 'lead_id', None),
                "lead_name": getattr(call, 'lead_name', None),
                "from_e164": call.from_number,
                "to_e164": getattr(call, 'to_number', None),
                "customer_phone": customer_phone,  # 🔥 NEW: Always the customer's phone (direction-aware)
                "duration": getattr(call, 'duration', 0),
                "status": call.status,
                "direction": call_direction,
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
@require_page_access('calls_inbound')
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
        
        # 🔥 FIX: Calculate customer phone based on direction
        call_direction = getattr(call, 'direction', 'inbound')
        customer_phone = call.from_number if call_direction == 'inbound' else getattr(call, 'to_number', call.from_number)
        
        details = {
            "call": {
                "sid": call.call_sid,
                "lead_id": getattr(call, 'lead_id', None),
                "lead_name": getattr(call, 'lead_name', None),
                "from_e164": call.from_number,
                "to_e164": getattr(call, 'to_number', None),
                "customer_phone": customer_phone,  # 🔥 NEW: Always the customer's phone (direction-aware)
                "duration": getattr(call, 'duration', 0),
                "status": call.status,
                "direction": call_direction,
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
@require_page_access('calls_inbound')
def download_recording(call_sid):
    """
    🔥 FIX: Download recording - API should NOT download, only serve if cached or queue to worker
    
    This endpoint is similar to stream_recording but for download (as attachment).
    Uses the same semaphore system to queue downloads to worker.
    """
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
        
        # Check if recording_url exists
        if not call.recording_url:
            log.warning(f"Download recording: No recording_url for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Recording URL not available"}), 404
        
        # 🔥 FIX: Check if file exists locally - do NOT download in API!
        from server.services.recording_service import check_local_recording_exists, _get_recordings_dir
        
        if check_local_recording_exists(call_sid):
            # File exists - serve it immediately for download
            recordings_dir = _get_recordings_dir()
            audio_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
            
            # 🎯 Support Range requests for audio streaming
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
                rv.headers.add('Content-Disposition', 'attachment')  # Download as attachment
                
                # CORS headers
                origin = request.headers.get('Origin')
                if origin:
                    rv.headers.add('Access-Control-Allow-Origin', origin)
                    rv.headers.add('Access-Control-Allow-Credentials', 'true')
                    rv.headers.add('Vary', 'Origin')
                    rv.headers.add('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length, Content-Type')
                return rv
            else:
                # No Range header - serve entire file for download
                response = make_response(send_file(
                    audio_path,
                    mimetype="audio/mpeg",
                    as_attachment=True,  # Force download
                    download_name=f"recording_{call_sid}.mp3",
                    conditional=True,
                    max_age=3600
                ))
                response.headers['Accept-Ranges'] = 'bytes'
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
            # File doesn't exist locally - enqueue download job (NO SLOT ACQUISITION IN API)
            # 🔥 FIX: API never acquires slots, just enqueues. Worker acquires/releases slots.
            from server.services.recording_semaphore import check_status
            from server.tasks_recording import enqueue_recording_download_only
            
            # Check current status first (dedup + queue position)
            status, info = check_status(business_id, call_sid)
            
            if status == "processing":
                # Already being downloaded
                log.debug(f"Download recording: Download in progress for call_sid={call_sid}")
                return jsonify({
                    "success": True,
                    "status": "processing",
                    "message": "Recording is being prepared, please retry in a few seconds"
                }), 202
            elif status == "queued":
                # Already in queue
                position = info.get("position", "?")
                log.debug(f"Download recording: Call {call_sid} in queue position {position}")
                return jsonify({
                    "success": True,
                    "status": "queued",
                    "message": f"Recording queued (position {position}), please retry in a few seconds"
                }), 202
            elif status == "failed":
                # 🔥 NEW: Return failed status to stop frontend retries
                log.error(f"Download recording: Download failed for call_sid={call_sid}")
                return jsonify({
                    "success": False,
                    "status": "failed",
                    "error": info.get("error", "Download failed"),
                    "message": "Recording download failed"
                }), 500
            
            # 🔥 FIX: Always enqueue - let worker handle slot management
            # This prevents API from acquiring slots that get stuck if worker fails
            logger.info(f"📤 [API DOWNLOAD] Enqueuing download for {call_sid} (worker will acquire slot)")
            log.debug(f"Download recording: Enqueuing download for call_sid={call_sid}")
            
            # Enqueue download job - worker will acquire slot and release in finally
            # 🔥 CRITICAL FIX: Returns (success, reason) tuple to distinguish dedup from errors
            job_success, reason = enqueue_recording_download_only(
                call_sid=call_sid,
                recording_url=call.recording_url,
                recording_sid=call.recording_sid,
                business_id=business_id,
                from_number=call.from_number or "",
                to_number=call.to_number or ""
            )
            
            # 🔥 CRITICAL FIX: Distinguish between dedup/cached (OK) vs error (FAIL)
            if not job_success:
                if reason == "error":
                    # Enqueue failed - return error to prevent infinite retry loop
                    logger.error(f"❌ [API DOWNLOAD] Failed to enqueue job for {call_sid}")
                    return jsonify({
                        "success": False,
                        "status": "error",
                        "error_code": "RQ_ENQUEUE_FAILED",
                        "message": "Failed to enqueue recording download - backend issue",
                        "details": "The server could not queue the recording job. Check server logs."
                    }), 500
                elif reason == "cached":
                    # File is cached - verify it exists and return ready
                    logger.info(f"🔧 [API DOWNLOAD] File cached for {call_sid}")
                    return jsonify({
                        "success": True,
                        "status": "ready",
                        "message": "Recording is ready"
                    }), 200
                elif reason == "duplicate":
                    # Duplicate job - a download is already in progress
                    # Return "processing" status to indicate user should wait
                    logger.info(f"🔧 [API DOWNLOAD] Download already in progress for {call_sid}")
                    return jsonify({
                        "success": True,
                        "status": "processing",
                        "message": "Recording is being prepared, please retry in a few seconds"
                    }), 202
                else:
                    # Unknown reason - log and return processing status
                    logger.warning(f"⚠️ [API DOWNLOAD] Unknown reason '{reason}' for {call_sid}")
                    return jsonify({
                        "success": True,
                        "status": "processing",
                        "message": "Recording is being prepared, please retry in a few seconds"
                    }), 202
            
            return jsonify({
                "success": True,
                "status": "queued",
                "message": "Recording queued for download, please retry in a few seconds"
            }), 202
        
    except Exception as e:
        log.error(f"Error downloading recording: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@calls_bp.route("/api/recordings/<call_sid>/status", methods=["GET"])
@require_api_auth()
@require_page_access('calls_inbound')
def get_recording_status(call_sid):
    """
    🔥 NEW: Check recording status without triggering download
    
    This endpoint ONLY checks status - it never enqueues jobs.
    Use this for polling instead of /stream to prevent queue flooding.
    
    Returns:
    - 200 + {"status": "ready"} if recording is cached locally
    - 200 + {"status": "processing", "ttl": N} if download in progress
    - 200 + {"status": "queued", "position": N, "queue_length": M} if in queue
    - 200 + {"status": "unknown"} if not found in system (needs to be started)
    - 404 if call doesn't exist or no recording available
    - 410 Gone if recording is expired (>7 days)
    """
    try:
        business_id = get_business_id()
        if not business_id:
            log.warning(f"Get recording status: No business_id for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Business ID required"}), 400
        
        # Check if call exists and belongs to this business (tenant validation)
        call = Call.query.filter(
            Call.call_sid == call_sid,
            Call.business_id == business_id
        ).first()
        
        if not call:
            log.warning(f"Get recording status: Call not found call_sid={call_sid}, business_id={business_id}")
            return jsonify({"success": False, "error": "Recording not found"}), 404
        
        # Check if recording is expired (7 days)
        if call.created_at and (datetime.utcnow() - call.created_at).days > 7:
            log.info(f"Get recording status: Recording expired for call_sid={call_sid}")
            return jsonify({"success": False, "error": "Recording expired"}), 410
        
        # Check if recording_url exists
        if not call.recording_url:
            log.warning(f"Get recording status: No recording_url for call_sid={call_sid}")
            return jsonify({"success": False, "error": "No recording available"}), 404
        
        # Check if file exists locally
        from server.services.recording_service import check_local_recording_exists
        
        if check_local_recording_exists(call_sid):
            # File is ready!
            return jsonify({
                "success": True,
                "status": "ready",
                "message": "Recording is ready to stream"
            }), 200
        
        # Check status in semaphore system (Redis)
        from server.services.recording_semaphore import check_status
        status, info = check_status(business_id, call_sid)
        
        if status == "processing":
            # Download in progress
            return jsonify({
                "success": True,
                "status": "processing",
                "ttl": info.get("ttl"),
                "message": "Recording is being prepared"
            }), 200
        elif status == "queued":
            # In queue waiting
            return jsonify({
                "success": True,
                "status": "queued",
                "position": info.get("position"),
                "queue_length": info.get("queue_length"),
                "message": f"Recording queued (position {info.get('position', '?')})"
            }), 200
        elif status == "failed":
            # 🔥 NEW: Return failed status to stop frontend retries
            return jsonify({
                "success": False,
                "status": "failed",
                "error": info.get("error", "Download failed"),
                "message": "Recording download failed"
            }), 500
        else:
            # Not in system - needs to be started
            return jsonify({
                "success": True,
                "status": "unknown",
                "message": "Recording not started yet"
            }), 200
            
    except Exception as e:
        # 🔥 FIX: Include traceback for better diagnostics
        import traceback
        log.error(f"Error getting recording status for {call_sid}: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False, 
            "error": "Internal server error",
            "error_code": "STATUS_EXCEPTION",
            "error_type": type(e).__name__
        }), 500

@calls_bp.route("/api/recordings/<call_sid>/stream", methods=["GET"])
@require_api_auth()
@require_page_access('calls_inbound')
def stream_recording(call_sid):
    """
    🔥 FIX 502: Asynchronous recording streaming endpoint
    
    🔥 SECURITY: Requires explicit user action to prevent mass enqueue
    - Query param: explicit_user_action=true OR
    - Header: X-User-Action: play
    
    Returns:
    - 200 + audio file if recording is cached locally
    - 202 Accepted if recording needs to be downloaded (job enqueued)
    - 400 Bad Request if explicit_user_action not provided
    - 403 Forbidden if call doesn't belong to user's tenant
    - 404 Not Found if call doesn't exist or no recording available
    - 410 Gone if recording is expired (>7 days)
    """
    try:
        # 🔥 CRITICAL GUARD: Prevent accidental mass enqueue
        # Require explicit user action parameter or header
        explicit_action = request.args.get('explicit_user_action', '').lower() == 'true'
        user_action_header = request.headers.get('X-User-Action', '').lower() == 'play'
        
        if not (explicit_action or user_action_header):
            log.warning(f"Stream recording: Missing explicit_user_action for call_sid={call_sid}")
            return jsonify({
                "success": False, 
                "error": "Missing required parameter: explicit_user_action=true or header X-User-Action: play"
            }), 400
        
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
        if call.created_at and (datetime.now(timezone.utc).replace(tzinfo=None) - call.created_at).days > 7:
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
                    # Normal range or open-ended range
                    # Handle empty strings by defaulting to 0 for start, file_size-1 for end
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
            # File doesn't exist locally - check for existing job or enqueue download
            # 🔥 FIX: Check RecordingRun status first to prevent duplicate job creation
            from server.models_sql import RecordingRun
            from server.tasks_recording import enqueue_recording_download_only
            
            # 🔥 CRITICAL: Check for existing RecordingRun to prevent duplicate jobs
            existing_run = RecordingRun.query.filter_by(
                business_id=business_id,
                call_sid=call_sid
            ).order_by(RecordingRun.created_at.desc()).first()
            
            if existing_run:
                # Job already exists - return status based on RecordingRun
                if existing_run.status == 'running':
                    log.debug(f"Stream recording: Download in progress for call_sid={call_sid} (run_id={existing_run.id})")
                    return jsonify({
                        "success": True,
                        "status": "processing",
                        "message": "Recording is being prepared, please retry in a few seconds"
                    }), 202
                elif existing_run.status == 'queued':
                    log.debug(f"Stream recording: Call {call_sid} in queue (run_id={existing_run.id})")
                    return jsonify({
                        "success": True,
                        "status": "queued",
                        "message": "Recording queued, please retry in a few seconds"
                    }), 202
                elif existing_run.status == 'failed':
                    # 🔥 NEW: Return failed status to stop frontend retries
                    log.error(f"Stream recording: Download failed for call_sid={call_sid} (run_id={existing_run.id})")
                    return jsonify({
                        "success": False,
                        "status": "failed",
                        "error": existing_run.error_message or "Download failed",
                        "message": "Recording download failed"
                    }), 500
                elif existing_run.status == 'completed':
                    # Job completed but file not found - may have been deleted
                    log.warning(f"Stream recording: Job completed but file missing for call_sid={call_sid}")
                    # Fall through to create new job
            
            # 🔥 FIX: Always enqueue - let worker handle slot management
            # This prevents API from acquiring slots that get stuck if worker fails
            logger.info(f"📤 [API STREAM] Enqueuing stream for {call_sid} (worker will acquire slot)")
            log.debug(f"Stream recording: Enqueuing download for call_sid={call_sid}")
            
            # Enqueue download job - worker will acquire slot and release in finally
            # 🔥 CRITICAL FIX: Returns (success, reason) tuple to distinguish dedup from errors
            job_success, reason = enqueue_recording_download_only(
                call_sid=call_sid,
                recording_url=call.recording_url,
                recording_sid=call.recording_sid,
                business_id=business_id,
                from_number=call.from_number or "",
                to_number=call.to_number or ""
            )
            
            # 🔥 CRITICAL FIX: Distinguish between dedup/cached (OK) vs error (FAIL)
            if not job_success:
                if reason == "error":
                    # Enqueue failed - return error to prevent infinite retry loop
                    logger.error(f"❌ [API STREAM] Failed to enqueue job for {call_sid}")
                    return jsonify({
                        "success": False,
                        "status": "error",
                        "error_code": "RQ_ENQUEUE_FAILED",
                        "message": "Failed to enqueue recording stream - backend issue",
                        "details": "The server could not queue the recording job. Check server logs."
                    }), 500
                elif reason == "cached":
                    # File is cached - verify it exists and return ready
                    logger.info(f"🔧 [API STREAM] File cached for {call_sid}")
                    return jsonify({
                        "success": True,
                        "status": "ready",
                        "message": "Recording is ready"
                    }), 200
                elif reason == "duplicate":
                    # Duplicate job - a download is already in progress
                    # Return "processing" status to indicate user should wait
                    logger.info(f"🔧 [API STREAM] Download already in progress for {call_sid}")
                    return jsonify({
                        "success": True,
                        "status": "processing",
                        "message": "Recording is being prepared, please retry in a few seconds"
                    }), 202
                else:
                    # Unknown reason - log and return processing status
                    logger.warning(f"⚠️ [API STREAM] Unknown reason '{reason}' for {call_sid}")
                    return jsonify({
                        "success": True,
                        "status": "processing",
                        "message": "Recording is being prepared, please retry in a few seconds"
                    }), 202
            
            return jsonify({
                "success": True,
                "status": "processing",
                "message": "Recording is being prepared, please retry in a few seconds"
            }), 202
        
    except Exception as e:
        # 🔥 FIX: Include traceback for better diagnostics
        import traceback
        log.error(f"Error streaming recording for {call_sid}: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False, 
            "error": "Internal server error",
            "error_code": "STREAM_EXCEPTION",
            "error_type": type(e).__name__
        }), 500

@calls_bp.route("/api/calls/cleanup", methods=["POST"])
@calls_bp.route("/api/calls/cleanup-recordings", methods=["POST"])
@require_api_auth(["system_admin", "owner", "admin"])
@require_page_access('calls_inbound')
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
@require_page_access('calls_inbound')
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
@require_page_access('calls_inbound')
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
@require_page_access('calls_inbound')
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