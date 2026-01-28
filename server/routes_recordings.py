"""
Recording Management API Routes
API for recording download jobs with progress tracking and cancellation
"""
from flask import Blueprint, jsonify, request, g, send_file, make_response, Response
from server.models_sql import db, RecordingRun, Business, CallLog
from server.auth_api import require_api_auth
from server.services.recording_service import check_local_recording_exists, _get_recordings_dir
from datetime import datetime
import logging
import os
import traceback

log = logging.getLogger(__name__)

recordings_bp = Blueprint('recordings', __name__, url_prefix='/api/recordings')


@recordings_bp.route('/runs/<int:run_id>/status', methods=['GET'])
@require_api_auth
def get_recording_run_status(run_id):
    """
    Get status of a recording run
    
    Returns:
        {
            "run_id": 123,
            "status": "running",
            "call_sid": "CA...",
            "job_type": "download",
            "can_cancel": true,
            "cancel_requested": false,
            "created_at": "...",
            "started_at": "...",
            "completed_at": "..."
        }
    """
    run = RecordingRun.query.get_or_404(run_id)
    
    # Check authorization
    if run.business_id != g.business_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    return jsonify({
        "run_id": run.id,
        "status": run.status,
        "call_sid": run.call_sid,
        "recording_sid": run.recording_sid,
        "job_type": run.job_type,
        "can_cancel": run.status in ['queued', 'running'],
        "cancel_requested": run.cancel_requested,
        "error_message": run.error_message,
        "retry_count": run.retry_count,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None
    })


@recordings_bp.route('/runs/<int:run_id>/cancel', methods=['POST'])
@require_api_auth
def cancel_recording_run(run_id):
    """
    Request cancellation of a recording run
    
    Sets cancel_requested=true. Worker checks this and stops processing.
    """
    run = RecordingRun.query.get_or_404(run_id)
    
    # Check authorization
    if run.business_id != g.business_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Check if already completed
    if run.status in ['completed', 'failed', 'cancelled']:
        return jsonify({"error": "Run already finished"}), 400
    
    # Set cancel flag
    run.cancel_requested = True
    db.session.commit()
    
    log.info(f"[RECORDING] Cancel requested for run {run_id} (call_sid={run.call_sid})")
    
    return jsonify({"ok": True})


@recordings_bp.route('/runs/active', methods=['GET'])
@require_api_auth
def get_active_recording_runs():
    """
    Get all active recording runs for current business
    
    Returns list of runs in 'queued' or 'running' status
    """
    runs = RecordingRun.query.filter(
        RecordingRun.business_id == g.business_id,
        RecordingRun.status.in_(['queued', 'running'])
    ).order_by(RecordingRun.created_at.desc()).limit(50).all()
    
    return jsonify({
        "runs": [
            {
                "run_id": run.id,
                "status": run.status,
                "call_sid": run.call_sid,
                "job_type": run.job_type,
                "cancel_requested": run.cancel_requested,
                "created_at": run.created_at.isoformat() if run.created_at else None
            }
            for run in runs
        ]
    })


@recordings_bp.route('/<call_sid>/prepare', methods=['POST'])
@require_api_auth
def prepare_recording(call_sid):
    """
    🔥 NEW: Prepare recording endpoint - ensures recording job is queued/processing
    
    This endpoint ensures there's a job to download/prepare the recording file.
    Returns the current status of the recording preparation.
    
    Returns:
    - 202 Accepted with {"status": "queued"|"processing"|"ready"}
    - 404 if call doesn't exist or doesn't belong to user
    """
    try:
        business_id = g.business_id
        if not business_id:
            return jsonify({"error": "Business ID required"}), 400
        
        # Check if call exists and belongs to this business
        call = CallLog.query.filter(
            CallLog.call_sid == call_sid,
            CallLog.business_id == business_id
        ).first()
        
        if not call:
            log.warning(f"Prepare recording: Call not found call_sid={call_sid}, business_id={business_id}")
            return jsonify({"error": "Recording not found"}), 404
        
        # Check if file already exists locally
        if check_local_recording_exists(call_sid):
            log.info(f"[PREPARE] Recording already ready for call_sid={call_sid}")
            return jsonify({
                "status": "ready",
                "message": "Recording is ready for playback",
                "message_he": "ההקלטה מוכנה לניגון"
            }), 200  # 🔥 FIX: Use 200 OK when file is ready, not 202
        
        # Check if recording URL exists
        if not call.recording_url:
            log.warning(f"[PREPARE] No recording_url for call_sid={call_sid}")
            return jsonify({"error": "No recording available for this call"}), 404
        
        # Check for existing job
        existing_run = RecordingRun.query.filter(
            RecordingRun.call_sid == call_sid,
            RecordingRun.job_type.in_(['download', 'full']),
            RecordingRun.status.in_(['queued', 'running'])
        ).first()
        
        if existing_run:
            # Job already exists
            log.info(f"[PREPARE] Job already exists for call_sid={call_sid}, status={existing_run.status}")
            status = "processing" if existing_run.status == "running" else "queued"
            return jsonify({
                "status": status,
                "run_id": existing_run.id,
                "message": f"Recording is being prepared ({status})",
                "message_he": f"ההקלטה בתהליך הכנה ({status})"
            }), 202
        
        # Create new download job
        try:
            from server.tasks_recording import enqueue_recording_download_only
            
            # 🔥 FIX: Properly unpack tuple return value (success, reason)
            job_success, reason = enqueue_recording_download_only(
                call_sid=call_sid,
                recording_url=call.recording_url,
                business_id=business_id,
                from_number=call.from_number or "",
                to_number=call.to_number or "",
                recording_sid=call.recording_sid
            )
            
            if job_success:
                log.info(f"[PREPARE] Created download job for call_sid={call_sid}, reason={reason}")
                return jsonify({
                    "status": "queued",
                    "message": "Recording download job created",
                    "message_he": "משימת הורדת הקלטה נוצרה"
                }), 202
            elif reason == "cached":
                # File already exists
                log.info(f"[PREPARE] Recording already cached for call_sid={call_sid}")
                return jsonify({
                    "status": "ready",
                    "message": "Recording is ready for playback",
                    "message_he": "ההקלטה מוכנה לניגון"
                }), 200
            elif reason == "duplicate":
                # Job already queued
                log.info(f"[PREPARE] Job already queued for call_sid={call_sid}")
                return jsonify({
                    "status": "queued",
                    "message": "Recording download already in progress",
                    "message_he": "הורדת הקלטה כבר בתהליך"
                }), 202
            else:
                # Error enqueueing
                log.error(f"[PREPARE] Failed to enqueue job for call_sid={call_sid}, reason={reason}")
                return jsonify({
                    "error": "Failed to create recording job",
                    "message": "Could not initiate recording download"
                }), 500
                
        except Exception as e:
            log.error(f"[PREPARE] Error creating job for call_sid={call_sid}: {e}")
            return jsonify({
                "error": "Internal server error",
                "message": str(e)
            }), 500
            
    except Exception as e:
        log.error(f"Error in prepare_recording for {call_sid}: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@recordings_bp.route('/file/<call_sid>', methods=['GET', 'HEAD', 'OPTIONS'])
@require_api_auth
def serve_recording_file(call_sid):
    """
    🔥 NEW: Serve recording file directly from disk
    
    This endpoint serves the MP3 file from the local recordings directory.
    Worker handles downloads, this just serves existing files.
    
    Returns:
    - 200 + audio/mpeg file if recording exists on disk (GET) or headers only (HEAD)
    - 202 Accepted + Retry-After header if file is being prepared
    - 404 + JSON if recording doesn't exist at all
    - 403 if call doesn't belong to user's tenant
    """
    try:
        # 🔥 FIX: Handle HEAD requests for file existence checks
        is_head_request = request.method == 'HEAD'
        
        # 🔥 FIX: Use g.business_id directly (set by require_api_auth decorator)
        business_id = g.business_id
        if not business_id:
            log.warning(f"Serve recording file: No business_id for call_sid={call_sid}")
            if is_head_request:
                return Response(status=400)
            return jsonify({"error": "Business ID required"}), 400
        
        # Check if call exists and belongs to this business (tenant validation)
        call = CallLog.query.filter(
            CallLog.call_sid == call_sid,
            CallLog.business_id == business_id
        ).first()
        
        if not call:
            log.warning(f"Serve recording file: Call not found call_sid={call_sid}, business_id={business_id}")
            if is_head_request:
                return Response(status=404)
            return jsonify({"error": "Recording not found"}), 404
        
        # Check if file exists locally
        if not check_local_recording_exists(call_sid):
            # 🔥 FIX: Trigger download if recording_url exists but file not on disk
            if call.recording_url:
                log.info(f"Serve recording file: File not on disk, checking job status for call_sid={call_sid}")
                
                # Try to trigger download job if not already in progress
                try:
                    from server.tasks_recording import enqueue_recording_download_only
                    from server.models_sql import RecordingRun
                    
                    # Check if there's already a download job in progress (any type)
                    # Check both 'download' and 'full' job types since full jobs also download the file
                    existing_run = RecordingRun.query.filter(
                        RecordingRun.call_sid == call_sid,
                        RecordingRun.job_type.in_(['download', 'full']),
                        RecordingRun.status.in_(['queued', 'running'])
                    ).first()
                    
                    if not existing_run:
                        log.info(f"[RECORDING] No existing job found, enqueueing download-only job for call_sid={call_sid}")
                        # 🔥 FIX: Properly unpack tuple return value
                        job_success, reason = enqueue_recording_download_only(
                            call_sid=call_sid,
                            recording_url=call.recording_url,
                            business_id=business_id,
                            from_number=call.from_number or "",
                            to_number=call.to_number or "",
                            recording_sid=call.recording_sid
                        )
                        
                        if job_success or reason == "duplicate":
                            # Return 202 - file is being prepared
                            log.info(f"[RECORDING] Returning 202 Accepted - job created for call_sid={call_sid}")
                            if is_head_request:
                                response = Response(status=202)
                                response.headers['Retry-After'] = '2'
                                return response
                            return jsonify({
                                "status": "processing",
                                "message": "Recording is being prepared. Please retry in a few seconds.",
                                "message_he": "ההקלטה בתהליך הכנה. אנא נסה שוב בעוד כמה שניות."
                            }), 202, {'Retry-After': '2'}
                        elif reason == "cached":
                            # File became available during enqueue - fall through to serve it
                            log.info(f"[RECORDING] File became available for call_sid={call_sid}")
                        else:
                            # Error enqueueing - return 500
                            log.error(f"[RECORDING] Failed to enqueue job for call_sid={call_sid}, reason={reason}")
                            if is_head_request:
                                return Response(status=500)
                            return jsonify({
                                "error": "Failed to prepare recording",
                                "message": "Could not initiate recording download"
                            }), 500
                    else:
                        # Job exists - return 202 with status
                        log.info(f"[RECORDING] Job in progress for call_sid={call_sid}, job_type={existing_run.job_type}, status={existing_run.status}, run_id={existing_run.id}")
                        if is_head_request:
                            response = Response(status=202)
                            response.headers['Retry-After'] = '2'
                            return response
                        return jsonify({
                            "status": "processing",
                            "message": f"Recording is being prepared ({existing_run.status}). Please retry in a few seconds.",
                            "message_he": f"ההקלטה בתהליך הכנה ({existing_run.status}). אנא נסה שוב בעוד כמה שניות."
                        }), 202, {'Retry-After': '2'}
                        
                except Exception as e:
                    log.error(f"[RECORDING] Failed to check/enqueue download job: {e}")
                    # Return 500 for real errors
                    if is_head_request:
                        return Response(status=500)
                    return jsonify({
                        "error": "Internal server error",
                        "message": "Failed to initiate recording download"
                    }), 500
            else:
                # No recording_url - truly doesn't exist
                log.warning(f"Serve recording file: No recording_url available for call_sid={call_sid}")
                if is_head_request:
                    return Response(status=404)
                return jsonify({
                    "error": "Recording not found",
                    "message": "No recording is available for this call.",
                    "message_he": "אין הקלטה זמינה לשיחה זו."
                }), 404
        
        # File exists - serve it
        recordings_dir = _get_recordings_dir()
        file_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
        
        # Get file size for headers
        file_size = os.path.getsize(file_path)
        
        # 🔥 FIX: For HEAD requests, return only headers without body
        if is_head_request:
            response = Response(status=200)
            response.headers['Content-Type'] = 'audio/mpeg'
            response.headers['Content-Length'] = str(file_size)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-store'
            
            # Add CORS headers for cross-origin requests
            origin = request.headers.get('Origin')
            if origin:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Vary'] = 'Origin'
                response.headers['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length, Content-Type'
            
            return response
        
        # Check if Range header is present (for partial content requests)
        range_header = request.headers.get('Range', None)
        
        if range_header:
            # Parse Range header (format: "bytes=start-end")
            try:
                byte_range = range_header.replace('bytes=', '').split('-')
                
                # Handle suffix-byte-range-spec: bytes=-500 (last N bytes)
                if not byte_range[0] and byte_range[1]:
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
                with open(file_path, 'rb') as f:
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
                rv.headers.add('Cache-Control', 'no-store')  # Prevent browser caching for security
                rv.headers.add('Content-Disposition', 'inline')
                
                # 🔥 FIX: Add CORS headers for cross-origin requests
                origin = request.headers.get('Origin')
                if origin:
                    rv.headers.add('Access-Control-Allow-Origin', origin)
                    rv.headers.add('Access-Control-Allow-Credentials', 'true')
                    rv.headers.add('Vary', 'Origin')
                    rv.headers.add('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length, Content-Type')
                
                return rv
            except (ValueError, IndexError) as e:
                # Malformed Range header - log and serve entire file instead
                log.warning(f"Malformed Range header '{range_header}' for call_sid={call_sid}: {e}")
                # Fall through to serve entire file
        
        # No Range header or malformed Range - serve entire file
        response = make_response(send_file(
            file_path,
            mimetype="audio/mpeg",
            as_attachment=False,
            conditional=True
        ))
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-store'  # Prevent browser caching for security
        response.headers['Content-Disposition'] = 'inline'
        response.headers['Content-Length'] = str(file_size)
        
        # 🔥 FIX: Add CORS headers for cross-origin requests
        origin = request.headers.get('Origin')
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Vary'] = 'Origin'
            response.headers['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length, Content-Type'
        
        return response
            
    except Exception as e:
        log.error(f"Error serving recording file for {call_sid}: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        if request.method == 'HEAD':
            return Response(status=500)
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500
