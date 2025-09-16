# server/routes_whatsapp.py
from flask import Blueprint, request, jsonify
import requests, os

wa_bp = Blueprint('wa_api', __name__, url_prefix='/api/wa-proxy')

BAILEYS_URL = os.getenv('BAILEYS_URL', 'http://127.0.0.1:3001')

@wa_bp.route('/send', methods=['POST'])
def send_whatsapp():
    try:
        # כאן CSRF של SeaSurf כבר מגן, כי זה POST same-origin
        data = request.get_json() or {}
        r = requests.post(f'{BAILEYS_URL}/send', json={
            'to': data.get('to'),
            'text': data.get('text')
        }, timeout=10)
        return (r.text, r.status_code, {'Content-Type': 'application/json'})
    except requests.RequestException:
        return jsonify({'error': 'baileys_unavailable'}), 503

@wa_bp.route('/health')
def whatsapp_health():
    try:
        r = requests.get(f'{BAILEYS_URL}/health', timeout=5)
        return (r.text, r.status_code, {'Content-Type': 'application/json'})
    except requests.RequestException:
        return jsonify({'error': 'baileys_unavailable'}), 503

@wa_bp.route('/qr')
def whatsapp_qr():
    try:
        r = requests.get(f'{BAILEYS_URL}/qr', timeout=5)
        return (r.text, r.status_code, {'Content-Type': 'application/json'})
    except requests.RequestException:
        return jsonify({'error': 'baileys_unavailable'}), 503

@wa_bp.route('/selftest')
def selftest():
    """Quick diagnostic endpoint"""
    try:
        health_r = requests.get(f'{BAILEYS_URL}/health', timeout=2)
        qr_r = requests.get(f'{BAILEYS_URL}/qr', timeout=2)
        return jsonify({
            'baileys_url': BAILEYS_URL,
            'health_status': health_r.status_code,
            'health_response': health_r.json() if health_r.status_code == 200 else None,
            'qr_status': qr_r.status_code,
            'timestamp': int(__import__('time').time())
        })
    except Exception as e:
        return jsonify({'error': str(e), 'baileys_url': BAILEYS_URL}), 500