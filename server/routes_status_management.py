"""
Lead Status Management API Routes
Allows businesses to create, read, update, delete custom lead statuses
"""
from flask import Blueprint, request, jsonify, session
from server.auth_api import require_api_auth, get_current_user
from server.models_sql import LeadStatus, Lead, Business
from server.db import db
from datetime import datetime
import logging

status_management_bp = Blueprint('status_management', __name__)

@status_management_bp.route('/api/statuses', methods=['GET'])
@require_api_auth(['owner', 'admin', 'agent', 'system_admin'])
def get_business_statuses():
    """Get all active statuses for the current business with auto-seeding"""
    try:
        auth_result = get_current_user()
        logging.info(f"[StatusAPI GET] auth_result type: {type(auth_result)}")
        if isinstance(auth_result, tuple):
            logging.warning(f"[StatusAPI GET] Auth returned tuple (error): {auth_result}")
            return auth_result  # Return error response
        user = auth_result
        logging.info(f"[StatusAPI GET] user: {user}")
        
        # ✅ Security fix: get business_id from current session context
        business_id = user.get('business_id') if user else None
        logging.info(f"[StatusAPI GET] Initial business_id from user: {business_id}")
        
        # For impersonation support - use impersonated tenant if available
        if session.get('impersonating') and session.get('impersonated_tenant_id'):
            business_id = session.get('impersonated_tenant_id')
            logging.info(f"[StatusAPI GET] Using impersonated business_id: {business_id}")
        
        # BUILD 138: ONLY system_admin can override business_id via query param
        is_system_admin = user.get('role') == 'system_admin'
        if not business_id and is_system_admin:
            # Try to get business_id from query parameter (system_admin only)
            business_id = request.args.get('business_id', type=int)
            
            # If still no business_id, use first available business
            if not business_id:
                first_business = Business.query.first()
                if first_business:
                    business_id = first_business.id
        
        if not business_id:
            return jsonify({'error': 'Business context required'}), 400
            
        statuses = LeadStatus.query.filter_by(
            business_id=business_id, 
            is_active=True
        ).order_by(LeadStatus.order_index).all()
        
        # ✅ Auto-seeding: If no statuses exist, create default ones (idempotent)
        if not statuses:
            # Default Hebrew real estate statuses
            default_statuses = [
                {'name': 'new', 'label': 'חדש', 'color': 'bg-blue-100 text-blue-800', 'is_default': True},
                {'name': 'attempting', 'label': 'בניסיון קשר', 'color': 'bg-yellow-100 text-yellow-800'},
                {'name': 'contacted', 'label': 'נוצר קשר', 'color': 'bg-purple-100 text-purple-800'},
                {'name': 'qualified', 'label': 'מוכשר', 'color': 'bg-green-100 text-green-800'},
                {'name': 'won', 'label': 'זכיה', 'color': 'bg-emerald-100 text-emerald-800', 'is_system': True},
                {'name': 'lost', 'label': 'אובדן', 'color': 'bg-red-100 text-red-800', 'is_system': True},
                {'name': 'unqualified', 'label': 'לא מוכשר', 'color': 'bg-gray-100 text-gray-800', 'is_system': True}
            ]
            
            for index, status_data in enumerate(default_statuses):
                status = LeadStatus()
                status.business_id = business_id
                status.name = status_data['name']
                status.label = status_data['label']
                status.color = status_data['color']
                status.order_index = index
                status.is_default = status_data.get('is_default', False)
                status.is_system = status_data.get('is_system', False)
                db.session.add(status)
            
            db.session.commit()
            
            # Re-query to get the created statuses
            statuses = LeadStatus.query.filter_by(
                business_id=business_id, 
                is_active=True
            ).order_by(LeadStatus.order_index).all()
        
        result = []
        for status in statuses:
            result.append({
                'id': status.id,
                'name': status.name,
                'label': status.label,
                'color': status.color,
                'description': status.description,
                'order_index': status.order_index,
                'is_default': status.is_default,
                'is_system': status.is_system,
                'created_at': status.created_at.isoformat()
            })
        
        logging.info(f"[StatusAPI] Returning {len(result)} statuses for business_id={business_id}: {[s['label'] for s in result]}")
        return jsonify({'items': result, 'total': len(result)})
        
    except Exception as e:
        logging.error(f"Error fetching business statuses: {e}")
        return jsonify({'error': str(e)}), 500

@status_management_bp.route('/api/statuses', methods=['POST'])  
@require_api_auth(['owner', 'admin', 'system_admin'])
def create_status():
    """Create a new custom status for the business"""
    try:
        logging.info("[StatusAPI POST] Creating new status...")
        auth_result = get_current_user()
        if isinstance(auth_result, tuple):
            logging.warning(f"[StatusAPI POST] Auth error: {auth_result}")
            return auth_result  # Return error response
        user = auth_result
        logging.info(f"[StatusAPI POST] user: {user}")
        
        # ✅ Security fix: get business_id from current session context with impersonation support
        business_id = user.get('business_id') if user else None
        logging.info(f"[StatusAPI POST] Initial business_id: {business_id}")
        if session.get('impersonating') and session.get('impersonated_tenant_id'):
            business_id = session.get('impersonated_tenant_id')
            logging.info(f"[StatusAPI POST] Using impersonated business_id: {business_id}")
        
        # ✅ FIX: Admin can create statuses with business_id from request body
        is_admin = user.get('role') in ['admin', 'superadmin']
        if not business_id and is_admin:
            data = request.get_json()
            business_id = data.get('business_id') if data else None
            
            # If still no business_id, use first available business
            if not business_id:
                first_business = Business.query.first()
                if first_business:
                    business_id = first_business.id
        
        if not business_id:
            return jsonify({'error': 'Business context required'}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
            
        # Validation - only label is required now
        if not data.get('label'):
            return jsonify({'error': 'label is required'}), 400
        
        # Auto-generate internal name if not provided
        import re
        import time
        
        if data.get('name'):
            raw_name = data['name'].strip().lower()
            # Replace non-alphanumeric with underscore
            raw_name = re.sub(r'[^a-z0-9]+', '_', raw_name).strip('_')
            if not raw_name:
                raw_name = f"custom_{int(time.time())}"
        else:
            # Generate unique name from timestamp
            raw_name = f"custom_{int(time.time())}"
        
        normalized_name = raw_name
        
        # Check for duplicate name within business
        existing = LeadStatus.query.filter_by(
            business_id=business_id,
            name=normalized_name
        ).first()
        
        if existing:
            return jsonify({'error': f'Status name "{data["name"]}" already exists'}), 400
        
        # Get next order index
        max_order = db.session.query(db.func.max(LeadStatus.order_index)).filter_by(
            business_id=business_id
        ).scalar() or 0
        
        # Create status
        status = LeadStatus()
        status.business_id = business_id
        status.name = normalized_name  # Use already normalized name
        status.label = data['label'].strip()
        status.color = data.get('color', 'bg-gray-100 text-gray-800')
        status.description = data.get('description', '').strip()
        status.order_index = max_order + 1
        status.is_default = data.get('is_default', False)
        status.is_system = False  # Custom statuses are never system
        
        # ✅ Exactly one default enforcement: handle all scenarios in transaction
        # First check if this business has any default status
        current_default = LeadStatus.query.filter_by(
            business_id=business_id,
            is_default=True,
            is_active=True
        ).first()
        
        if status.is_default:
            # If setting as default, unset all other defaults
            if current_default:
                db.session.query(LeadStatus).filter_by(
                    business_id=business_id,
                    is_default=True
                ).update({'is_default': False})
        elif not current_default:
            # If no current default exists and this isn't set as default, make this the default
            status.is_default = True
        
        logging.info(f"[StatusAPI POST] Adding status to session: business_id={business_id}, label={status.label}, name={status.name}")
        db.session.add(status)
        db.session.commit()
        logging.info(f"[StatusAPI POST] SUCCESS! Created status ID={status.id}, label={status.label}")
        
        response_data = {
            'message': 'Status created successfully',
            'status': {
                'id': status.id,
                'name': status.name,
                'label': status.label,
                'color': status.color,
                'description': status.description,
                'order_index': status.order_index,
                'is_default': status.is_default,
                'is_system': status.is_system,
                'created_at': status.created_at.isoformat() if status.created_at else None
            }
        }
        logging.info(f"[StatusAPI POST] Response: {response_data}")
        return jsonify(response_data), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating status: {e}")
        return jsonify({'error': str(e)}), 500

@status_management_bp.route('/api/statuses/<int:status_id>', methods=['PUT'])
@require_api_auth(['owner', 'admin', 'system_admin'])
def update_status(status_id):
    """Update an existing status"""
    try:
        auth_result = get_current_user()
        if isinstance(auth_result, tuple):
            return auth_result  # Return error response
        user = auth_result
        
        # ✅ Security fix: get business_id from current session context with impersonation support
        business_id = user.get('business_id') if user else None
        if session.get('impersonating') and session.get('impersonated_tenant_id'):
            business_id = session.get('impersonated_tenant_id')
        
        # ✅ FIX: Admin can update statuses - skip business_id check for admin
        is_admin = user.get('role') in ['admin', 'superadmin']
        if not business_id and not is_admin:
            return jsonify({'error': 'Business context required'}), 400
            
        # ✅ IDOR Protection: Verify status belongs to current business (or admin bypass)
        if is_admin and not business_id:
            # Admin without business_id can update any status
            status = LeadStatus.query.filter_by(id=status_id).first()
        else:
            # Regular user or admin with business_id - check ownership
            status = LeadStatus.query.filter_by(
                id=status_id,
                business_id=business_id
            ).first()
        
        if not status:
            return jsonify({'error': 'Status not found'}), 404
        
        # Update business_id for later use if admin
        if not business_id:
            business_id = status.business_id
            
        # ✅ System status protection
        if status.is_system:
            return jsonify({'error': 'Cannot modify system status'}), 403
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        # ✅ Name immutability: reject any attempts to change name
        if 'name' in data:
            return jsonify({'error': 'Status name cannot be changed after creation'}), 400
        
        # Update allowed fields only
        if 'label' in data:
            status.label = data['label'].strip()
        if 'color' in data:
            status.color = data['color']
        if 'description' in data:
            status.description = data['description'].strip()
        
        # ✅ Exactly one default enforcement for PUT
        if 'is_default' in data and not status.is_system:
            new_is_default = data['is_default']
            
            # Get current default status
            current_default = LeadStatus.query.filter_by(
                business_id=business_id,
                is_default=True,
                is_active=True
            ).first()
            
            if new_is_default:
                # Setting this as default - unset all others first
                if current_default and current_default.id != status.id:
                    db.session.query(LeadStatus).filter_by(
                        business_id=business_id,
                        is_default=True
                    ).update({'is_default': False})
                status.is_default = True
            else:
                # Trying to unset default - only allow if there's another default
                if current_default and current_default.id == status.id:
                    other_default = LeadStatus.query.filter(
                        LeadStatus.business_id == business_id,
                        LeadStatus.id != status.id,
                        LeadStatus.is_active == True
                    ).first()
                    
                    if not other_default:
                        return jsonify({'error': 'Cannot unset default status - at least one default status must exist per business'}), 400
                    else:
                        # Make the first available status the new default
                        other_default.is_default = True
                        status.is_default = False
                else:
                    # Not currently default, just update
                    status.is_default = False
            
        status.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Status updated successfully',
            'status': {
                'id': status.id,
                'name': status.name,
                'label': status.label,
                'color': status.color,
                'description': status.description,
                'order_index': status.order_index,
                'is_default': status.is_default,
                'is_system': status.is_system
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating status: {e}")
        return jsonify({'error': str(e)}), 500

@status_management_bp.route('/api/statuses/<int:status_id>', methods=['DELETE'])
@require_api_auth(['owner', 'admin', 'system_admin'])
def delete_status(status_id):
    """Delete a status (mark as inactive if leads exist)"""
    try:
        auth_result = get_current_user()
        if isinstance(auth_result, tuple):
            return auth_result  # Return error response
        user = auth_result
        
        # ✅ Security fix: get business_id from current session context with impersonation support
        business_id = user.get('business_id') if user else None
        if session.get('impersonating') and session.get('impersonated_tenant_id'):
            business_id = session.get('impersonated_tenant_id')
        
        # ✅ FIX: Admin can delete statuses - skip business_id check for admin
        is_admin = user.get('role') in ['admin', 'superadmin']
        if not business_id and not is_admin:
            return jsonify({'error': 'Business context required'}), 400
            
        # ✅ IDOR Protection: Verify status belongs to current business (or admin bypass)
        if is_admin and not business_id:
            status = LeadStatus.query.filter_by(id=status_id).first()
        else:
            status = LeadStatus.query.filter_by(
                id=status_id,
                business_id=business_id
            ).first()
        
        if not status:
            return jsonify({'error': 'Status not found'}), 404
        
        # Update business_id for later use if admin
        if not business_id:
            business_id = status.business_id
            
        # ✅ Enhanced system status protection
        if status.is_system:
            return jsonify({'error': 'Cannot delete system status'}), 403
        
        # ✅ Default status protection - cannot delete if it's the only default or no other default exists
        if status.is_default:
            other_defaults = LeadStatus.query.filter(
                LeadStatus.business_id == business_id,
                LeadStatus.id != status.id,
                LeadStatus.is_default == True,
                LeadStatus.is_active == True
            ).count()
            
            if other_defaults == 0:
                return jsonify({
                    'error': 'Cannot delete the only default status. Please designate another status as default first.'
                }), 409
        
        # Check if any leads use this status
        lead_count = Lead.query.filter_by(
            tenant_id=business_id,
            status=status.name
        ).count()
        
        if lead_count > 0:
            # ✅ Return 409 Conflict instead of 200 OK when status is in use
            return jsonify({
                'error': f'Cannot delete status - it is currently used by {lead_count} leads',
                'lead_count': lead_count,
                'action': 'deletion_blocked'
            }), 409
        else:
            # Safe to delete
            db.session.delete(status)
            db.session.commit()
            
            return jsonify({
                'message': 'Status deleted successfully',
                'action': 'deleted'
            })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting status: {e}")
        return jsonify({'error': str(e)}), 500

@status_management_bp.route('/api/statuses/reorder', methods=['POST'])
@require_api_auth(['owner', 'admin', 'system_admin'])
def reorder_statuses():
    """Reorder statuses by updating order_index"""
    try:
        auth_result = get_current_user()
        if isinstance(auth_result, tuple):
            return auth_result  # Return error response
        user = auth_result
        
        # ✅ Security fix: get business_id from current session context with impersonation support
        business_id = user.get('business_id') if user else None
        if session.get('impersonating') and session.get('impersonated_tenant_id'):
            business_id = session.get('impersonated_tenant_id')
        
        if not business_id:
            return jsonify({'error': 'Business context required'}), 400
            
        data = request.get_json()
        if not data or 'status_ids' not in data:
            return jsonify({'error': 'status_ids array required'}), 400
        
        status_ids = data['status_ids']
        
        # ✅ IDOR Protection: Update order indexes only for statuses that belong to current business
        for index, status_id in enumerate(status_ids):
            # Verify each status belongs to current business before updating
            status = LeadStatus.query.filter_by(
                id=status_id,
                business_id=business_id
            ).first()
            
            if not status:
                return jsonify({'error': f'Status {status_id} not found or access denied'}), 403
                
            status.order_index = index
            status.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'message': 'Statuses reordered successfully'})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error reordering statuses: {e}")
        return jsonify({'error': str(e)}), 500

@status_management_bp.route('/api/admin/statuses/initialize/<int:business_id>', methods=['POST'])
@require_api_auth(['system_admin'])
def initialize_default_statuses(business_id):
    """Initialize default statuses for a business (admin only)"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return jsonify({'error': 'Business not found'}), 404
        
        # Check if statuses already exist
        existing_count = LeadStatus.query.filter_by(business_id=business_id).count()
        if existing_count > 0:
            return jsonify({'error': 'Business already has statuses configured'}), 400
        
        # Default Hebrew real estate statuses
        default_statuses = [
            {'name': 'new', 'label': 'חדש', 'color': 'bg-blue-100 text-blue-800', 'is_default': True},
            {'name': 'attempting', 'label': 'בניסיון קשר', 'color': 'bg-yellow-100 text-yellow-800'},
            {'name': 'contacted', 'label': 'נוצר קשר', 'color': 'bg-purple-100 text-purple-800'},
            {'name': 'qualified', 'label': 'מוכשר', 'color': 'bg-green-100 text-green-800'},
            {'name': 'won', 'label': 'זכיה', 'color': 'bg-emerald-100 text-emerald-800', 'is_system': True},
            {'name': 'lost', 'label': 'אובדן', 'color': 'bg-red-100 text-red-800', 'is_system': True},
            {'name': 'unqualified', 'label': 'לא מוכשר', 'color': 'bg-gray-100 text-gray-800', 'is_system': True}
        ]
        
        for index, status_data in enumerate(default_statuses):
            status = LeadStatus()
            status.business_id = business_id
            status.name = status_data['name']
            status.label = status_data['label']
            status.color = status_data['color']
            status.order_index = index
            status.is_default = status_data.get('is_default', False)
            status.is_system = status_data.get('is_system', False)
            db.session.add(status)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Initialized {len(default_statuses)} default statuses for business',
            'business_name': business.name
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error initializing default statuses: {e}")
        return jsonify({'error': str(e)}), 500