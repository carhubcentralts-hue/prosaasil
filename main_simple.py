#!/usr/bin/env python3
"""
Simple Flask server for production testing
"""
import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/healthz')
def healthz():
    return "ok", 200

@app.route('/readyz')
def readyz():
    return jsonify({"status": "ready"}), 200

@app.route('/webhook/incoming_call', methods=['POST'])
def incoming_call():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>שלום וברוכים הבאים לשי דירות ומשרדים</Say>
</Response>'''
    return xml, 200, {'Content-Type': 'text/xml'}

if __name__ == "__main__":
    print("🚀 Starting Hebrew AI Call Center CRM")
    app.run(host="0.0.0.0", port=5000, debug=False)