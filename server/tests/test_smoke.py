# server/tests/test_smoke.py
import pytest
from server.app_factory import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert b'"status":"healthy"' in r.data

def test_twilio_incoming(client):
    r = client.post("/webhook/incoming_call")
    assert r.status_code == 200
    assert b"<Record" in r.data
    assert b'maxLength="30"' in r.data
    assert b'timeout="5"' in r.data
    assert b'finishOnKey="*"' in r.data

def test_auth_login(client):
    r = client.post("/api/auth/login", 
                   json={"email": "admin@shai.com", "password": "admin123"})
    assert r.status_code == 200
    assert b'"success":true' in r.data

def test_crm_requires_auth(client):
    r = client.get("/api/crm/customers")
    assert r.status_code == 401

def test_business_requires_auth(client):
    r = client.get("/api/businesses")
    assert r.status_code == 401