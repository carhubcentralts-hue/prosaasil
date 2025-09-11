#!/usr/bin/env python3
"""
Simple test server to debug connection issues
"""
import os
import sys
from flask import Flask, jsonify

# Basic Flask app
app = Flask(__name__)

@app.route('/healthz')
def health():
    return 'ok', 200

@app.route('/test')
def test():
    return jsonify({
        'status': 'working',
        'message': 'Simple test server is responding',
        'port': os.getenv('PORT', '5000')
    })

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'message': 'Test server is running',
        'endpoints': ['/healthz', '/test', '/']
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    print(f"🚀 Starting simple test server on 0.0.0.0:{port}")
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)