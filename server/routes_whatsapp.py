import os, requests
from flask import Blueprint, jsonify, request
from server.extensions import csrf

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/api/whatsapp')
BAILEYS_BASE = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
INT_SECRET   = os.getenv('INTERNAL_SECRET')

def tenant_id_from_ctx():
    return getattr(request, 'tenant_id', None) or request.headers.get('X-Tenant-Id') or '1'

def _headers():
    return {'X-Internal-Secret': INT_SECRET, 'Content-Type': 'application/json'}

@whatsapp_bp.route('/status', methods=['GET'])
def status():
    t = tenant_id_from_ctx()
    r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/status", headers=_headers(), timeout=5)
    return jsonify(r.json()), r.status_code

@whatsapp_bp.route('/qr', methods=['GET'])
def qr():
    t = tenant_id_from_ctx()
    r = requests.get(f"{BAILEYS_BASE}/whatsapp/{t}/qr", headers=_headers(), timeout=5)
    if r.status_code == 404:           # אין QR כרגע
        return jsonify({"dataUrl": None}), 200
    return jsonify(r.json()), r.status_code

@csrf.exempt  # Bypass CSRF for internal API
@whatsapp_bp.route('/start', methods=['POST'])
def start():
    t = tenant_id_from_ctx()
    r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/start", headers=_headers(), timeout=10)
    return jsonify(r.json()), r.status_code

@csrf.exempt  # Bypass CSRF for internal API  
@whatsapp_bp.route('/reset', methods=['POST'])
def reset():
    t = tenant_id_from_ctx()
    r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/reset", headers=_headers(), timeout=10)
    return jsonify(r.json()), r.status_code

@csrf.exempt  # Bypass CSRF for internal API  
@whatsapp_bp.route('/disconnect', methods=['POST'])
def disconnect():
    t = tenant_id_from_ctx()
    r = requests.post(f"{BAILEYS_BASE}/whatsapp/{t}/disconnect", headers=_headers(), timeout=10)
    return jsonify(r.json()), r.status_code