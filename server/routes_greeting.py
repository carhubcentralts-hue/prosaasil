# -*- coding: utf-8 -*-
"""
⚡ BUILD 117 - Greeting Cache Management API
Endpoints for managing and invalidating greeting cache
"""
from flask import Blueprint, request, jsonify
from server.auth_utils import require_api_auth
from server.services.greeting_builder import invalidate_greeting_for_business, get_cache_stats

greeting_bp = Blueprint("greeting", __name__)


@greeting_bp.route("/api/greeting/invalidate", methods=["POST"])
@require_api_auth(['admin', 'manager', 'business'])
def invalidate_greeting():
    """
    Invalidate (clear) cached greeting for a business.
    
    Call this when business greeting settings change.
    
    Request body:
        {
            "business_id": "123"  // Business ID to invalidate
        }
    
    Returns:
        {
            "ok": true,
            "removed": 2  // Number of cache entries removed
        }
    """
    try:
        data = request.get_json()
        
        # Guard against missing or invalid JSON (must be a dict)
        if not isinstance(data, dict):
            return jsonify({
                "ok": False,
                "error": "request body must be a JSON object"
            }), 400
        
        business_id = data.get("business_id")
        
        if not business_id:
            return jsonify({
                "ok": False,
                "error": "missing business_id"
            }), 400
        
        # Invalidate cache for this business
        removed_count = invalidate_greeting_for_business(str(business_id))
        
        return jsonify({
            "ok": True,
            "removed": removed_count,
            "message": f"Invalidated {removed_count} cached greeting(s) for business {business_id}"
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@greeting_bp.route("/api/greeting/cache/stats", methods=["GET"])
@require_api_auth(['admin', 'manager'])
def get_cache_statistics():
    """
    Get greeting cache statistics.
    
    Returns:
        {
            "total_entries": 15,
            "max_entries": 256,
            "utilization_pct": 5.86
        }
    """
    try:
        stats = get_cache_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
