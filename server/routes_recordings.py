"""
Recording Management API Routes
API for recording download jobs with progress tracking and cancellation
"""
from flask import Blueprint, jsonify, request, g
from server.models_sql import db, RecordingRun, Business
from server.auth_api import require_api_auth
from datetime import datetime
import logging

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
