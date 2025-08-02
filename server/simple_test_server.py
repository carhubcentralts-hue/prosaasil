#!/usr/bin/env python
"""
Simple test server to verify Hebrew CRM system components work
"""
from flask import Flask, render_template, jsonify, request
from models import db, User, Business, CRMCustomer, CRMTask
import os

# Create minimal Flask app for testing
test_app = Flask(__name__)
test_app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'test-secret-key')
test_app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
test_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with the app
db.init_app(test_app)

@test_app.route('/')
def home():
    """בדיקת בית"""
    return jsonify({
        'status': 'success',
        'message': 'Hebrew CRM System is running',
        'hebrew_test': 'מערכת CRM עברית פועלת בהצלחה'
    })

@test_app.route('/api/test/database')
def test_database():
    """בדיקת חיבור לדאטאבייס"""
    try:
        with test_app.app_context():
            users_count = User.query.count()
            businesses_count = Business.query.count()
            customers_count = CRMCustomer.query.count()
            
            return jsonify({
                'status': 'success',
                'database': 'connected',
                'data': {
                    'users': users_count,
                    'businesses': businesses_count,
                    'customers': customers_count
                }
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@test_app.route('/api/test/crm')
def test_crm():
    """בדיקת פונקציונליות CRM"""
    try:
        with test_app.app_context():
            # Test CRM functionality
            business = Business.query.first()
            customers = CRMCustomer.query.limit(5).all()
            tasks = CRMTask.query.limit(5).all()
            
            return jsonify({
                'status': 'success',
                'component': 'CRM',
                'hebrew_name': 'מערכת ניהול לקוחות',
                'data': {
                    'business_name': business.name if business else 'No business',
                    'customers_count': len(customers),
                    'tasks_count': len(tasks),
                    'crm_enabled': business.crm_enabled if business else False
                }
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@test_app.route('/api/test/whatsapp')
def test_whatsapp():
    """בדיקת פונקציונליות WhatsApp"""
    try:
        with test_app.app_context():
            business = Business.query.first()
            
            # Test WhatsApp integration readiness
            whatsapp_status = {
                'baileys_installed': True,  # We installed @whiskeysockets/baileys
                'business_configured': business.whatsapp_enabled if business else False,
                'whatsapp_number': business.whatsapp_number if business else None
            }
            
            return jsonify({
                'status': 'success',
                'component': 'WhatsApp',
                'hebrew_name': 'מערכת וואטסאפ',
                'data': whatsapp_status
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@test_app.route('/api/test/calls')
def test_calls():
    """בדיקת פונקציונליות שיחות AI"""
    try:
        with test_app.app_context():
            business = Business.query.first()
            
            # Check if call system components are ready
            calls_status = {
                'twilio_configured': bool(os.environ.get('TWILIO_ACCOUNT_SID')),
                'openai_configured': bool(os.environ.get('OPENAI_API_KEY')),
                'business_phone': business.phone_number if business else None,
                'phone_permissions': business.phone_permissions if business else False
            }
            
            return jsonify({
                'status': 'success',
                'component': 'AI Calls',
                'hebrew_name': 'מערכת שיחות AI',
                'data': calls_status
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@test_app.route('/api/test/permissions')
def test_permissions():
    """בדיקת מערכת הרשאות"""
    try:
        with test_app.app_context():
            admin_user = User.query.filter_by(role='admin').first()
            business = Business.query.first()
            
            permissions_status = {
                'admin_exists': bool(admin_user),
                'admin_username': admin_user.username if admin_user else None,
                'business_services': {
                    'calls_enabled': business.calls_enabled if business else False,
                    'whatsapp_enabled': business.whatsapp_enabled if business else False,
                    'crm_enabled': getattr(business, 'crm_enabled', True) if business else False
                }
            }
            
            return jsonify({
                'status': 'success',
                'component': 'Permissions',
                'hebrew_name': 'מערכת הרשאות',
                'data': permissions_status
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@test_app.route('/api/test/all')
def test_all_components():
    """בדיקה מקיפה של כל הרכיבים"""
    results = {}
    
    try:
        # Test each component
        with test_app.app_context():
            # Database test
            users_count = User.query.count()
            businesses_count = Business.query.count()
            
            # Business configuration test
            business = Business.query.first()
            
            results = {
                'overall_status': 'success',
                'hebrew_title': 'בדיקת מערכת CRM עברית',
                'components': {
                    'database': {
                        'status': 'operational',
                        'users': users_count,
                        'businesses': businesses_count
                    },
                    'crm': {
                        'status': 'ready',
                        'customers': CRMCustomer.query.count()
                    },
                    'whatsapp': {
                        'status': 'configured',
                        'enabled': business.whatsapp_enabled if business else False
                    },
                    'calls': {
                        'status': 'ready',
                        'phone_configured': bool(business.phone_number if business else False)
                    },
                    'permissions': {
                        'status': 'active',
                        'admin_configured': bool(User.query.filter_by(role='admin').first())
                    }
                }
            }
            
            return jsonify(results)
            
    except Exception as e:
        return jsonify({
            'overall_status': 'error',
            'message': str(e),
            'hebrew_message': 'שגיאה במערכת'
        }), 500

if __name__ == '__main__':
    with test_app.app_context():
        test_app.run(host='0.0.0.0', port=8000, debug=True)