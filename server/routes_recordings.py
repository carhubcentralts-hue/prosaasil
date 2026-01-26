"""
Recording Management API Routes
API for recording download jobs with progress tracking and cancellation
"""
from flask import Blueprint, jsonify, request, g, send_file, make_response, Response
from server.models_sql import db, RecordingRun, Business, CallLog
from server.auth_api import require_api_auth
from server.routes_crm import get_business_id
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


@recordings_bp.route('/file/<call_sid>', methods=['GET'])
@require_api_auth
def serve_recording_file(call_sid):
    """
    🔥 NEW: Serve recording file directly from disk
    
    This endpoint serves the MP3 file from the local recordings directory.
    Use this for direct file serving without blob URL complexity.
    
    Returns:
    - 200 + audio/mpeg file if recording exists on disk
    - 404 + JSON if file not found
    - 403 if call doesn't belong to user's tenant
    """
    try:
        business_id = get_business_id()
        if not business_id:
            log.warning(f"Serve recording file: No business_id for call_sid={call_sid}")
            return jsonify({"error": "Business ID required"}), 400
        
        # Check if call exists and belongs to this business (tenant validation)
        call = CallLog.query.filter(
            CallLog.call_sid == call_sid,
            CallLog.business_id == business_id
        ).first()
        
        if not call:
            log.warning(f"Serve recording file: Call not found call_sid={call_sid}, business_id={business_id}")
            return jsonify({"error": "Recording not found"}), 404
        
        # Check if file exists locally
        if not check_local_recording_exists(call_sid):
            log.warning(f"Serve recording file: File not found on disk for call_sid={call_sid}")
            return jsonify({
                "error": "Recording file not available",
                "message": "Recording has not been downloaded yet. Please use the stream endpoint to trigger download."
            }), 404
        
        # File exists - serve it
        recordings_dir = _get_recordings_dir()
        file_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
        
        # Get file size for headers
        file_size = os.path.getsize(file_path)
        
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
        
        return response
            
    except Exception as e:
        log.error(f"Error serving recording file for {call_sid}: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500
