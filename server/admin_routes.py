"""
Admin Routes for Business Management
רוטים של מנהל מערכת לניהול עסקים
"""

from flask import Blueprint, request, jsonify
from app import app, db
from models import Business, User, CallLog
from auth import admin_required
import logging

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
logger = logging.getLogger(__name__)

@admin_bp.route('/businesses', methods=['GET'])
@admin_required
def get_all_businesses():
    """קבלת כל העסקים במערכת"""
    try:
        businesses = Business.query.all()
        businesses_data = []
        
        for business in businesses:
            business_dict = {
                'id': business.id,
                'name': business.name,
                'type': business.business_type,
                'phone': business.twilio_phone_number,
                'whatsapp_phone': business.whatsapp_phone_number,
                'ai_prompt': business.ai_prompt,
                'services': {
                    'calls': business.calls_enabled,
                    'whatsapp': business.whatsapp_enabled,
                    'crm': business.crm_enabled
                },
                'created_at': business.created_at.isoformat() if business.created_at else None
            }
            businesses_data.append(business_dict)
        
        return jsonify(businesses_data)
    
    except Exception as e:
        logger.error(f"Error fetching businesses: {e}")
        return jsonify({'error': 'Failed to fetch businesses'}), 500

@admin_bp.route('/businesses', methods=['POST'])
@admin_required
def create_business():
    """יצירת עסק חדש"""
    try:
        data = request.get_json()
        
        # וידוא שדות חובה
        required_fields = ['name', 'phone', 'ai_prompt']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # יצירת עסק חדש
        new_business = Business(
            name=data['name'],
            business_type=data.get('type', ''),
            twilio_phone_number=data['phone'],
            whatsapp_phone_number=data.get('whatsapp_phone', ''),
            ai_prompt=data['ai_prompt'],
            calls_enabled=data.get('services', {}).get('calls', True),
            whatsapp_enabled=data.get('services', {}).get('whatsapp', False),
            crm_enabled=data.get('services', {}).get('crm', False)
        )
        
        db.session.add(new_business)
        db.session.commit()
        
        logger.info(f"✅ New business created: {new_business.name} (ID: {new_business.id})")
        
        return jsonify({
            'id': new_business.id,
            'message': 'Business created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating business: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create business'}), 500

@admin_bp.route('/businesses/<int:business_id>', methods=['PUT'])
@admin_required
def update_business(business_id):
    """עדכון עסק קיים"""
    try:
        business = Business.query.get_or_404(business_id)
        data = request.get_json()
        
        # עדכון נתונים
        business.name = data.get('name', business.name)
        business.business_type = data.get('type', business.business_type)
        business.twilio_phone_number = data.get('phone', business.twilio_phone_number)
        business.whatsapp_phone_number = data.get('whatsapp_phone', business.whatsapp_phone_number)
        business.ai_prompt = data.get('ai_prompt', business.ai_prompt)
        
        # עדכון שירותים
        services = data.get('services', {})
        business.calls_enabled = services.get('calls', business.calls_enabled)
        business.whatsapp_enabled = services.get('whatsapp', business.whatsapp_enabled)
        business.crm_enabled = services.get('crm', business.crm_enabled)
        
        db.session.commit()
        
        logger.info(f"✅ Business updated: {business.name} (ID: {business.id})")
        
        return jsonify({'message': 'Business updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating business: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update business'}), 500

@admin_bp.route('/businesses/<int:business_id>', methods=['DELETE'])
@admin_required
def delete_business(business_id):
    """מחיקת עסק"""
    try:
        business = Business.query.get_or_404(business_id)
        business_name = business.name
        
        # מחיקת כל הנתונים הקשורים לעסק (אם נדרש)
        # כרגע נשמור את הנתונים להיסטוריה
        
        db.session.delete(business)
        db.session.commit()
        
        logger.info(f"✅ Business deleted: {business_name} (ID: {business_id})")
        
        return jsonify({'message': 'Business deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting business: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete business'}), 500

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_admin_stats():
    """קבלת סטטיסטיקות כלליות למנהל"""
    try:
        total_businesses = Business.query.count()
        active_businesses = Business.query.filter(
            (Business.calls_enabled == True) | 
            (Business.whatsapp_enabled == True) | 
            (Business.crm_enabled == True)
        ).count()
        total_calls = CallLog.query.count()
        total_users = User.query.count()
        
        return jsonify({
            'totalBusinesses': total_businesses,
            'activeBusinesses': active_businesses,
            'totalCalls': total_calls,
            'totalUsers': total_users
        })
    
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

# רישום הBlueprint יתבצע בapp.py