"""
User Management API Routes
Admin and Business Owner endpoints for managing users
"""
from flask import Blueprint, request, jsonify, session, g
from werkzeug.security import generate_password_hash
from server.models_sql import User, Business, db
from server.auth_api import require_api_auth
from server.authz import roles_required
from datetime import datetime

user_mgmt_api = Blueprint('user_mgmt_api', __name__, url_prefix='/api/admin/businesses')

@user_mgmt_api.route('/<int:business_id>/users', methods=['GET'])
@require_api_auth()
def get_business_users(business_id):
    """
    GET /api/admin/businesses/<id>/users
    Returns all users for a specific business
    
    Permissions:
    - system_admin: can view users for ANY business
    - owner/admin: can view users for THEIR business only
    """
    try:
        current_user = session.get('user')
        current_role = current_user.get('role')
        
        # Permission check
        if current_role == 'system_admin':
            # System admin can view any business
            pass
        elif current_role in ['owner', 'admin']:
            # Owner/admin can only view their own business
            if current_user.get('business_id') != business_id:
                return jsonify({'error': 'Forbidden: Can only manage users in your own business'}), 403
        else:
            return jsonify({'error': 'Forbidden: Insufficient permissions'}), 403
        
        # Get business
        business = Business.query.get_or_404(business_id)
        
        # Get all users for this business
        users = User.query.filter_by(business_id=business_id).order_by(User.created_at.desc()).all()
        
        users_data = [{
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'name': user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            'role': user.role,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        } for user in users]
        
        return jsonify({
            'business_id': business_id,
            'business_name': business.name,
            'users': users_data,
            'total': len(users_data)
        })
        
    except Exception as e:
        print(f"❌ Error fetching business users: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@user_mgmt_api.route('/<int:business_id>/users', methods=['POST'])
@require_api_auth()
def create_business_user(business_id):
    """
    POST /api/admin/businesses/<id>/users
    Create a new user for a business
    
    Body:
    {
        "email": "user@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe",
        "role": "admin"  // owner, admin, agent
    }
    
    Permissions:
    - system_admin: can create users for ANY business
    - owner: can create users for THEIR business only
    """
    try:
        current_user = session.get('user')
        current_role = current_user.get('role')
        
        # Permission check
        if current_role == 'system_admin':
            pass
        elif current_role == 'owner':
            if current_user.get('business_id') != business_id:
                return jsonify({'error': 'Forbidden: Can only create users in your own business'}), 403
        else:
            return jsonify({'error': 'Forbidden: Only owners and system admins can create users'}), 403
        
        # Get business
        business = Business.query.get_or_404(business_id)
        
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request data'}), 400
        
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        role = data.get('role', 'agent')
        
        # Validation
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if role not in ['owner', 'admin', 'agent']:
            return jsonify({'error': 'Invalid role. Must be: owner, admin, or agent'}), 400
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create user
        user = User(
            business_id=business_id,
            email=email,
            password_hash=generate_password_hash(password, method='scrypt'),
            first_name=first_name,
            last_name=last_name,
            name=f"{first_name} {last_name}".strip() or email,
            role=role,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        print(f"✅ Created user: {email} (role={role}) for business {business.name}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'name': user.name,
                'role': user.role,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@user_mgmt_api.route('/<int:business_id>/users/<int:user_id>', methods=['PUT'])
@require_api_auth()
def update_business_user(business_id, user_id):
    """
    PUT /api/admin/businesses/<id>/users/<user_id>
    Update user details (email, role, name, password)
    
    Body:
    {
        "email": "newemail@example.com",  // optional
        "role": "admin",                   // optional
        "first_name": "Jane",              // optional
        "last_name": "Smith",              // optional
        "password": "newpass123",          // optional
        "is_active": true                  // optional
    }
    """
    try:
        current_user = session.get('user')
        current_role = current_user.get('role')
        
        # Permission check
        if current_role == 'system_admin':
            pass
        elif current_role == 'owner':
            if current_user.get('business_id') != business_id:
                return jsonify({'error': 'Forbidden: Can only update users in your own business'}), 403
        else:
            return jsonify({'error': 'Forbidden: Only owners and system admins can update users'}), 403
        
        # Get user
        user = User.query.filter_by(id=user_id, business_id=business_id).first_or_404()
        
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request data'}), 400
        
        # Update fields
        if 'email' in data and data['email'] != user.email:
            # Check email uniqueness
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        
        if 'last_name' in data:
            user.last_name = data['last_name']
        
        if 'role' in data:
            if data['role'] not in ['owner', 'admin', 'agent']:
                return jsonify({'error': 'Invalid role'}), 400
            user.role = data['role']
        
        if 'password' in data and data['password']:
            user.password_hash = generate_password_hash(data['password'], method='scrypt')
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        # Update name from first_name + last_name
        user.name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        
        db.session.commit()
        
        print(f"✅ Updated user: {user.email} (role={user.role})")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'name': user.name,
                'role': user.role,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@user_mgmt_api.route('/<int:business_id>/users/<int:user_id>', methods=['DELETE'])
@require_api_auth()
def delete_business_user(business_id, user_id):
    """
    DELETE /api/admin/businesses/<id>/users/<user_id>
    Delete a user (except if they're the only owner)
    """
    try:
        current_user = session.get('user')
        current_role = current_user.get('role')
        
        # Permission check
        if current_role == 'system_admin':
            pass
        elif current_role == 'owner':
            if current_user.get('business_id') != business_id:
                return jsonify({'error': 'Forbidden: Can only delete users in your own business'}), 403
        else:
            return jsonify({'error': 'Forbidden: Only owners and system admins can delete users'}), 403
        
        # Get user
        user = User.query.filter_by(id=user_id, business_id=business_id).first_or_404()
        
        # Prevent deleting the only owner
        if user.role == 'owner':
            owner_count = User.query.filter_by(business_id=business_id, role='owner').count()
            if owner_count <= 1:
                return jsonify({'error': 'Cannot delete the only owner. Promote another user to owner first.'}), 400
        
        # Prevent deleting yourself
        if user.id == current_user.get('id'):
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        db.session.delete(user)
        db.session.commit()
        
        print(f"✅ Deleted user: {user.email}")
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@user_mgmt_api.route('/<int:business_id>/owner', methods=['POST'])
@require_api_auth()
def set_business_owner(business_id):
    """
    POST /api/admin/businesses/<id>/owner
    Set a user as owner (promotes user to owner role)
    
    Body:
    {
        "user_id": 123
    }
    """
    try:
        current_user = session.get('user')
        current_role = current_user.get('role')
        
        # Only system_admin and current owner can set new owner
        if current_role == 'system_admin':
            pass
        elif current_role == 'owner':
            if current_user.get('business_id') != business_id:
                return jsonify({'error': 'Forbidden: Can only set owner in your own business'}), 403
        else:
            return jsonify({'error': 'Forbidden: Only owners and system admins can set owners'}), 403
        
        # Parse request
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id is required'}), 400
        
        user_id = data['user_id']
        
        # Get user
        user = User.query.filter_by(id=user_id, business_id=business_id).first_or_404()
        
        # Set as owner
        user.role = 'owner'
        db.session.commit()
        
        print(f"✅ Set user as owner: {user.email}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'role': user.role
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error setting owner: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
