"""
Tests for Live Call API endpoints
Tests the browser-based voice chat functionality
"""
import pytest
import json
import base64
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from server.app_factory import create_app
from server.db import db as _db


@pytest.fixture
def app():
    """Create test Flask application"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    """Database fixture"""
    return _db


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


def test_live_call_stt_missing_audio(client, auth_headers):
    """Test STT endpoint with missing audio data"""
    response = client.post(
        '/api/live_call/stt',
        json={},
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'audio' in data['error'].lower()


def test_live_call_stt_invalid_base64(client, auth_headers):
    """Test STT endpoint with invalid base64 encoding"""
    response = client.post(
        '/api/live_call/stt',
        json={
            'audio': 'not-valid-base64!!!',
            'format': 'webm'
        },
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('server.routes_live_call.OpenAI')
def test_live_call_stt_success(mock_openai, client, auth_headers):
    """Test successful STT conversion"""
    # Mock OpenAI Whisper response
    mock_client = MagicMock()
    mock_transcript = MagicMock()
    mock_transcript.text = "שלום, איך אפשר לעזור?"
    mock_client.audio.transcriptions.create.return_value = mock_transcript
    mock_openai.return_value = mock_client
    
    # Create valid base64 audio
    audio_bytes = b'\x00' * 100  # Dummy audio
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    response = client.post(
        '/api/live_call/stt',
        json={
            'audio': audio_base64,
            'format': 'webm'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'text' in data
    assert data['text'] == "שלום, איך אפשר לעזור?"
    assert data['language'] == 'he'


def test_live_call_chat_missing_text(client, auth_headers):
    """Test chat endpoint with missing text"""
    response = client.post(
        '/api/live_call/chat',
        json={},
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_live_call_chat_text_too_long(client, auth_headers):
    """Test chat endpoint with text exceeding limit"""
    long_text = 'א' * 3000  # Exceeds MAX_TEXT_LENGTH
    response = client.post(
        '/api/live_call/chat',
        json={
            'text': long_text
        },
        headers=auth_headers
    )
    assert response.status_code == 413
    data = json.loads(response.data)
    assert 'error' in data
    assert 'long' in data['error'].lower()


@patch('server.routes_live_call.OpenAI')
@patch('server.routes_live_call.AIService')
def test_live_call_chat_success(mock_ai_service, mock_openai, client, auth_headers, business):
    """Test successful chat processing"""
    # Mock AIService
    mock_service_instance = MagicMock()
    mock_service_instance.get_system_prompt.return_value = "אתה עוזר AI"
    mock_ai_service.return_value = mock_service_instance
    
    # Mock OpenAI Chat response
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "שלום! איך אוכל לעזור לך?"
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    response = client.post(
        '/api/live_call/chat',
        json={
            'text': 'מה המזג היום?',
            'conversation_history': []
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'response' in data
    assert data['response'] == "שלום! איך אוכל לעזור לך?"
    assert 'conversation_id' in data


def test_live_call_tts_missing_text(client, auth_headers):
    """Test TTS endpoint with missing text"""
    response = client.post(
        '/api/live_call/tts',
        json={},
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('server.routes_live_call.tts_provider')
def test_live_call_tts_success_openai(mock_tts, client, auth_headers, business_settings):
    """Test successful TTS with OpenAI"""
    # Mock TTS synthesis
    audio_bytes = b'\x00\x01\x02' * 100  # Dummy MP3 data
    mock_tts.synthesize.return_value = (audio_bytes, 'audio/mpeg')
    mock_tts.is_gemini_available.return_value = True
    
    # Set OpenAI as provider
    business_settings.tts_provider = 'openai'
    business_settings.voice_id = 'alloy'
    
    response = client.post(
        '/api/live_call/tts',
        json={
            'text': 'שלום עולם'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.mimetype == 'audio/mpeg'
    assert len(response.data) > 0


@patch('server.routes_live_call.tts_provider')
def test_live_call_tts_gemini_unavailable(mock_tts, client, auth_headers, business_settings):
    """Test TTS when Gemini requested but unavailable"""
    # Mock Gemini unavailable
    mock_tts.is_gemini_available.return_value = False
    
    # Set Gemini as provider
    business_settings.tts_provider = 'gemini'
    business_settings.voice_id = 'he-IL-Wavenet-A'
    
    response = client.post(
        '/api/live_call/tts',
        json={
            'text': 'שלום עולם'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 503
    data = json.loads(response.data)
    assert 'error' in data
    assert 'Gemini' in data['error']
    assert 'unavailable' in data['error']


@patch('server.routes_live_call.tts_provider')
def test_live_call_tts_synthesis_error(mock_tts, client, auth_headers, business_settings):
    """Test TTS when synthesis fails"""
    # Mock synthesis failure
    mock_tts.synthesize.return_value = (None, 'TTS synthesis failed')
    mock_tts.is_gemini_available.return_value = True
    
    response = client.post(
        '/api/live_call/tts',
        json={
            'text': 'שלום עולם'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data


def test_live_call_endpoints_require_auth(client):
    """Test that all endpoints require authentication"""
    # STT without auth
    response = client.post('/api/live_call/stt', json={'audio': 'test'})
    assert response.status_code in [401, 403]
    
    # Chat without auth
    response = client.post('/api/live_call/chat', json={'text': 'test'})
    assert response.status_code in [401, 403]
    
    # TTS without auth
    response = client.post('/api/live_call/tts', json={'text': 'test'})
    assert response.status_code in [401, 403]


@patch('server.routes_live_call.OpenAI')
def test_live_call_conversation_context(mock_openai, client, auth_headers):
    """Test that conversation context is maintained"""
    # Mock AIService and OpenAI
    with patch('server.routes_live_call.AIService') as mock_ai_service:
        mock_service_instance = MagicMock()
        mock_service_instance.get_system_prompt.return_value = "אתה עוזר AI"
        mock_ai_service.return_value = mock_service_instance
        
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "תשובה"
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Send message with history
        conversation_history = [
            {'role': 'user', 'content': 'מה שמך?'},
            {'role': 'assistant', 'content': 'אני עוזר AI'}
        ]
        
        response = client.post(
            '/api/live_call/chat',
            json={
                'text': 'תודה',
                'conversation_history': conversation_history
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify OpenAI was called with full context
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        
        # Should have system prompt + history + current message
        assert len(messages) >= 3
        assert any(msg['content'] == 'מה שמך?' for msg in messages)
        assert any(msg['content'] == 'אני עוזר AI' for msg in messages)
        assert any(msg['content'] == 'תודה' for msg in messages)


# Fixtures
@pytest.fixture
def business(app, db):
    """Create test business"""
    from server.models_sql import Business
    business = Business(
        id=1,
        name='Test Business',
        business_type='general',
        tts_provider='openai',
        tts_voice_id='alloy',
        tts_speed=1.0,
        tts_language='he-IL',
        voice_id='alloy'
    )
    db.session.add(business)
    db.session.commit()
    return business


@pytest.fixture
def business_settings(business):
    """Return business as business_settings for backward compatibility"""
    return business


@pytest.fixture
def auth_headers(app, client, business):
    """Create authenticated request headers with proper session"""
    # Use session_transaction to set session for test client
    with client.session_transaction() as sess:
        # Set session in the format expected by require_api_auth
        sess['user'] = {
            'id': 1,
            'business_id': business.id,
            'role': 'owner',
            'email': 'test@test.com'
        }
    return {}
