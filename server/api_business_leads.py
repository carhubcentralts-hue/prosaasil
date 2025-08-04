from flask import Blueprint, request, jsonify
import json
from datetime import datetime

business_leads_bp = Blueprint('business_leads', __name__)

@business_leads_bp.route('/api/business/leads', methods=['GET'])
def get_business_leads():
    """Get leads for a specific business"""
    try:
        business_id = request.args.get('business_id', 1)
        
        # Mock leads data for the business
        mock_leads = [
            {
                'id': 1,
                'name': 'יוסי כהן',
                'phone': '+972501234567',
                'email': 'yossi@example.com',
                'status': 'new',
                'priority': 'high',
                'source': 'WhatsApp',
                'created_at': '2024-08-04T10:00:00Z',
                'last_contact': None,
                'business_id': business_id
            },
            {
                'id': 2,
                'name': 'רחל לוי',
                'phone': '+972507654321',
                'email': 'rachel@example.com',
                'status': 'contacted',
                'priority': 'medium',
                'source': 'Website Form',
                'created_at': '2024-08-03T15:30:00Z',
                'last_contact': '2024-08-04T09:00:00Z',
                'business_id': business_id
            },
            {
                'id': 3,
                'name': 'דוד ישראלי',
                'phone': '+972509876543',
                'email': 'david@example.com',
                'status': 'qualified',
                'priority': 'high',
                'source': 'Phone Call',
                'created_at': '2024-08-02T12:00:00Z',
                'last_contact': '2024-08-04T08:30:00Z',
                'business_id': business_id
            }
        ]
        
        return jsonify({
            'leads': mock_leads,
            'total': len(mock_leads),
            'business_id': business_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@business_leads_bp.route('/api/business/leads', methods=['POST'])
def create_business_lead():
    """Create a new lead for a business"""
    try:
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        required_fields = ['name', 'phone', 'business_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create new lead
        new_lead = {
            'id': 99,  # Mock ID
            'name': data.get('name', ''),
            'phone': data.get('phone', ''),
            'email': data.get('email', ''),
            'status': data.get('status', 'new'),
            'priority': data.get('priority', 'medium'),
            'source': data.get('source', 'Manual'),
            'created_at': datetime.now().isoformat(),
            'last_contact': None,
            'business_id': data.get('business_id', 1)
        }
        
        return jsonify({
            'success': True,
            'lead': new_lead,
            'message': 'Lead created successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@business_leads_bp.route('/api/business/leads/<int:lead_id>', methods=['PUT'])
def update_business_lead(lead_id):
    """Update a business lead"""
    try:
        data = request.json or {}
        
        # Mock update logic
        updated_lead = {
            'id': lead_id,
            'name': data.get('name', 'Updated Lead'),
            'phone': data.get('phone', '+972501234567'),
            'email': data.get('email', ''),
            'status': data.get('status', 'updated'),
            'priority': data.get('priority', 'medium'),
            'source': data.get('source', 'Manual'),
            'created_at': '2024-08-04T10:00:00Z',
            'last_contact': datetime.now().isoformat(),
            'business_id': data.get('business_id', 1)
        }
        
        return jsonify({
            'success': True,
            'lead': updated_lead,
            'message': 'Lead updated successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@business_leads_bp.route('/api/business/leads/<int:lead_id>', methods=['DELETE'])
def delete_business_lead(lead_id):
    """Delete a business lead"""
    try:
        # Mock delete logic
        return jsonify({
            'success': True,
            'message': f'Lead {lead_id} deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500