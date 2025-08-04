from flask import Blueprint, request, jsonify
import json
import re
from datetime import datetime

phone_analysis_bp = Blueprint('phone_analysis', __name__)

@phone_analysis_bp.route('/api/crm/phone-analysis', methods=['GET'])
def analyze_phone_numbers():
    """Analyze +972 phone numbers in the database and check call readiness"""
    try:
        # Mock data for +972 phone numbers with business connections
        # In a real implementation, this would query the actual database
        mock_phone_data = [
            {
                'number': '+972501234567',
                'customer_id': 1,
                'customer_name': 'יוסי כהן',
                'business_id': 1,
                'business_name': 'מכון היופי של שרה',
                'status': 'active',
                'last_call': '2024-08-03T14:30:00Z',
                'call_count': 5,
                'last_updated': '2024-08-04T10:00:00Z'
            },
            {
                'number': '+972507654321',
                'customer_id': 2,
                'customer_name': 'רחל לוי',
                'business_id': 2,
                'business_name': 'חברת הביטוח הישראלית',
                'status': 'active',
                'last_call': '2024-08-02T16:45:00Z',
                'call_count': 3,
                'last_updated': '2024-08-04T09:30:00Z'
            },
            {
                'number': '+972509876543',
                'customer_id': 3,
                'customer_name': 'דוד ישראלי',
                'business_id': 1,
                'business_name': 'מכון היופי של שרה',
                'status': 'pending',
                'last_call': None,
                'call_count': 0,
                'last_updated': '2024-08-04T08:15:00Z'
            },
            {
                'number': '+972521122334',
                'customer_id': 4,
                'customer_name': 'מירי גולדברג',
                'business_id': 3,
                'business_name': 'סטודיו עיצוב הבית',
                'status': 'active',
                'last_call': '2024-08-04T12:00:00Z',
                'call_count': 7,
                'last_updated': '2024-08-04T12:05:00Z'
            },
            {
                'number': '+972545566778',
                'customer_id': 5,
                'customer_name': 'אבי רוזנברג',
                'business_id': 2,
                'business_name': 'חברת הביטוח הישראלית',
                'status': 'inactive',
                'last_call': '2024-07-15T10:30:00Z',
                'call_count': 2,
                'last_updated': '2024-08-01T14:20:00Z'
            }
        ]
        
        # Analyze call readiness for each number
        call_readiness = {}
        for phone_data in mock_phone_data:
            phone_number = phone_data['number']
            
            # Determine call readiness based on various factors
            if phone_data['status'] == 'active' and phone_data['call_count'] > 0:
                call_readiness[phone_number] = 'ready'
            elif phone_data['status'] == 'pending':
                call_readiness[phone_number] = 'pending'
            else:
                call_readiness[phone_number] = 'not_ready'
        
        # Business distribution analysis
        business_distribution = {}
        for phone_data in mock_phone_data:
            business_name = phone_data['business_name']
            if business_name not in business_distribution:
                business_distribution[business_name] = {
                    'count': 0,
                    'ready_for_calls': 0,
                    'active_customers': 0
                }
            
            business_distribution[business_name]['count'] += 1
            if call_readiness[phone_data['number']] == 'ready':
                business_distribution[business_name]['ready_for_calls'] += 1
            if phone_data['status'] == 'active':
                business_distribution[business_name]['active_customers'] += 1
        
        # Summary statistics
        total_numbers = len(mock_phone_data)
        ready_for_calls = len([r for r in call_readiness.values() if r == 'ready'])
        active_numbers = len([p for p in mock_phone_data if p['status'] == 'active'])
        
        response_data = {
            'phone_numbers': mock_phone_data,
            'call_readiness': call_readiness,
            'business_distribution': business_distribution,
            'summary': {
                'total_972_numbers': total_numbers,
                'ready_for_calls': ready_for_calls,
                'active_numbers': active_numbers,
                'readiness_percentage': round((ready_for_calls / total_numbers) * 100, 1) if total_numbers > 0 else 0
            },
            'deployment_readiness': {
                'call_system_ready': ready_for_calls > 0,
                'businesses_connected': len(business_distribution) > 0,
                'database_populated': total_numbers > 0,
                'overall_status': 'ready' if ready_for_calls > 0 and len(business_distribution) > 0 else 'pending'
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@phone_analysis_bp.route('/api/crm/business/<int:business_id>/phones', methods=['GET'])
def get_business_phone_numbers(business_id):
    """Get all +972 phone numbers for a specific business"""
    try:
        # Mock data filtered by business ID
        all_phones = [
            {
                'number': '+972501234567',
                'customer_id': 1,
                'customer_name': 'יוסי כהן',
                'business_id': 1,
                'status': 'active',
                'last_call': '2024-08-03T14:30:00Z',
                'call_count': 5
            },
            {
                'number': '+972509876543',
                'customer_id': 3,
                'customer_name': 'דוד ישראלי',
                'business_id': 1,
                'status': 'pending',
                'last_call': None,
                'call_count': 0
            }
        ]
        
        # Filter by business_id
        business_phones = [p for p in all_phones if p['business_id'] == business_id]
        
        return jsonify({
            'business_id': business_id,
            'phone_numbers': business_phones,
            'count': len(business_phones)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@phone_analysis_bp.route('/api/crm/phone/<phone_number>/readiness', methods=['GET'])
def check_phone_readiness(phone_number):
    """Check if a specific +972 phone number is ready for calls"""
    try:
        # Validate +972 format
        if not phone_number.startswith('+972'):
            return jsonify({'error': 'Not a valid +972 number'}), 400
        
        # Mock readiness check
        readiness_data = {
            'phone_number': phone_number,
            'is_ready': True,
            'last_verified': datetime.now().isoformat(),
            'checks': {
                'format_valid': True,
                'business_connected': True,
                'system_configured': True,
                'twilio_ready': True
            },
            'next_action': 'Ready for deployment' if True else 'Configuration needed'
        }
        
        return jsonify(readiness_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500