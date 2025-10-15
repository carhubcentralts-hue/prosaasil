"""
Admin API for managing business contact channels
Allows admins to map phone numbers and WhatsApp tenants to businesses
"""
from flask import Blueprint, request, jsonify
from server.db import db
from server.models_sql import BusinessContactChannel, Business
from server.services.business_resolver import add_business_channel, list_business_channels, delete_business_channel
from server.extensions import csrf
import logging

log = logging.getLogger(__name__)

admin_channels_bp = Blueprint('admin_channels', __name__, url_prefix='/api/admin/channels')

@admin_channels_bp.route('/', methods=['GET'])
def get_all_channels():
    """Get all business contact channels"""
    try:
        channels = BusinessContactChannel.query.all()
        return jsonify({
            "ok": True,
            "channels": [
                {
                    "id": c.id,
                    "business_id": c.business_id,
                    "channel_type": c.channel_type,
                    "identifier": c.identifier,
                    "is_primary": c.is_primary,
                    "created_at": c.created_at.isoformat() if c.created_at else None
                }
                for c in channels
            ]
        }), 200
    except Exception as e:
        log.error(f"Error fetching channels: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_channels_bp.route('/business/<int:business_id>', methods=['GET'])
def get_business_channels(business_id):
    """Get all channels for a specific business"""
    try:
        channels = list_business_channels(business_id)
        return jsonify({"ok": True, "channels": channels}), 200
    except Exception as e:
        log.error(f"Error fetching business channels: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_channels_bp.route('/', methods=['POST'])
@csrf.exempt  # Temporary - should require auth
def create_channel():
    """Create a new business contact channel mapping"""
    try:
        data = request.get_json()
        business_id = data.get('business_id')
        channel_type = data.get('channel_type')
        identifier = data.get('identifier')
        is_primary = data.get('is_primary', False)
        
        if not business_id or not channel_type or not identifier:
            return jsonify({
                "ok": False,
                "error": "Missing required fields: business_id, channel_type, identifier"
            }), 400
        
        # Validate channel_type
        valid_types = ['twilio_voice', 'twilio_sms', 'whatsapp']
        if channel_type not in valid_types:
            return jsonify({
                "ok": False,
                "error": f"Invalid channel_type. Must be one of: {', '.join(valid_types)}"
            }), 400
        
        # Validate business exists
        business = Business.query.get(business_id)
        if not business:
            return jsonify({
                "ok": False,
                "error": f"Business with ID {business_id} not found"
            }), 404
        
        # Create channel
        channel = add_business_channel(business_id, channel_type, identifier, is_primary)
        
        return jsonify({
            "ok": True,
            "channel": {
                "id": channel.id,
                "business_id": channel.business_id,
                "channel_type": channel.channel_type,
                "identifier": channel.identifier,
                "is_primary": channel.is_primary
            }
        }), 201
        
    except Exception as e:
        log.error(f"Error creating channel: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_channels_bp.route('/<int:channel_id>', methods=['DELETE'])
@csrf.exempt  # Temporary - should require auth
def remove_channel(channel_id):
    """Delete a business contact channel"""
    try:
        success = delete_business_channel(channel_id)
        if success:
            return jsonify({"ok": True, "message": "Channel deleted"}), 200
        else:
            return jsonify({"ok": False, "error": "Channel not found"}), 404
    except Exception as e:
        log.error(f"Error deleting channel: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_channels_bp.route('/businesses', methods=['GET'])
def get_businesses():
    """Get all businesses for the dropdown"""
    try:
        businesses = Business.query.all()
        return jsonify({
            "ok": True,
            "businesses": [
                {
                    "id": b.id,
                    "name": b.name,
                    "phone": b.phone_e164,
                    "is_active": b.is_active
                }
                for b in businesses
            ]
        }), 200
    except Exception as e:
        log.error(f"Error fetching businesses: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
