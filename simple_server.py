#!/usr/bin/env python3
"""
Simple server just for React app - no heavy dependencies
"""

import os
from flask import Flask, send_from_directory, send_file, jsonify

app = Flask(__name__)

# Serve React build files
@app.route('/')
def serve_index():
    """Serve the main React app"""
    return send_file('client/dist/index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve React build assets"""
    return send_from_directory('client/dist/assets', filename)

@app.route('/login')
@app.route('/forgot') 
@app.route('/reset')
@app.route('/<path:path>')
def serve_spa(path=None):
    """Serve React SPA for all other routes"""
    return send_file('client/dist/index.html')

@app.route('/api/health')
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'message': 'React server running'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Simple React Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)