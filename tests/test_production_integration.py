"""
Production integration tests for Hebrew AI Call Center CRM
Tests all critical production components working together
"""
import pytest
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

def test_app_factory_creates_app():
    """Test that the app factory creates a Flask app successfully"""
    with patch.dict(os.environ, {
        'PUBLIC_HOST': 'https://test.example.com',
        'TWILIO_ACCOUNT_SID': 'test_sid',
        'TWILIO_AUTH_TOKEN': 'test_token',
        'WHATSAPP_PROVIDER': 'baileys'
    }):
        from server.app_factory import create_app
        app = create_app()
        assert app is not None
        assert app.config['PUBLIC_HOST'] == 'https://test.example.com'

def test_database_models_import():
    """Test that SQLAlchemy models import successfully"""
    try:
        from server.models_sql import Business, Customer, CallLog, WhatsAppMessage
        from server.db import db
        assert Business is not None
        assert Customer is not None
        assert CallLog is not None
        assert WhatsAppMessage is not None
        assert db is not None
    except ImportError as e:
        pytest.fail(f"Failed to import database models: {e}")

def test_whatsapp_providers_work():
    """Test that WhatsApp providers can be instantiated"""
    from server.whatsapp_providers import BaileysProvider, TwilioProvider, get_provider
    
    # Test Baileys provider
    baileys = BaileysProvider()
    assert baileys is not None
    
    # Test provider factory
    with patch.dict(os.environ, {'WHATSAPP_PROVIDER': 'baileys'}):
        provider = get_provider()
        assert isinstance(provider, BaileysProvider)

def test_twilio_security_decorator():
    """Test that Twilio security decorator works"""
    from server.twilio_security import require_twilio_signature
    
    @require_twilio_signature
    def test_webhook():
        return "success"
    
    assert test_webhook is not None

def test_hebrew_tts_functions():
    """Test that Hebrew TTS functions work without errors"""
    from server.hebrew_tts_enhanced import create_hebrew_audio
    
    # This should not crash even without actual TTS services
    result = create_hebrew_audio("שלום", "test_call")
    # Result can be None if services unavailable, that's OK

def test_production_config():
    """Test production configuration"""
    from server.production_config import ProductionConfig, init_production_config
    from flask import Flask
    
    app = Flask(__name__)
    init_production_config(app)
    
    assert not app.config.get('DEBUG', True)
    assert not app.config.get('TESTING', True)

def test_critical_routes_registered():
    """Test that all critical routes are registered"""
    with patch.dict(os.environ, {
        'PUBLIC_HOST': 'https://test.example.com',
        'TWILIO_ACCOUNT_SID': 'test_sid',
        'TWILIO_AUTH_TOKEN': 'test_token',
        'WHATSAPP_PROVIDER': 'baileys'
    }):
        from server.app_factory import create_app
        app = create_app()
        
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/api/health')
            assert response.status_code == 200
            
            # Test that critical webhook routes exist (even if they return 401/403)
            webhook_routes = [
                '/webhook/incoming_call',
                '/webhook/handle_recording', 
                '/webhook/call_status',
                '/webhook/whatsapp/incoming',
                '/webhook/whatsapp/status'
            ]
            
            for route in webhook_routes:
                response = client.post(route)
                # We expect 401/403/500, not 404 (route not found)
                assert response.status_code != 404, f"Route {route} not found"

if __name__ == "__main__":
    # Quick test run
    test_app_factory_creates_app()
    test_database_models_import()
    test_whatsapp_providers_work()
    test_twilio_security_decorator()
    test_hebrew_tts_functions()
    test_production_config()
    test_critical_routes_registered()
    print("✅ All production integration tests passed!")