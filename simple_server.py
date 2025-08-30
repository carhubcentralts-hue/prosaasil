#!/usr/bin/env python3
"""
Simple Flask server for testing React app
"""

from flask import Flask, send_from_directory, jsonify
import os

app = Flask(__name__)

# Static files from dist
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('./dist/assets', filename)

# Catch-all for SPA routing
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    # Skip API routes
    if path.startswith('api/'):
        return jsonify({'error': 'API not found'}), 404
    
    # Serve React app for all other routes
    return send_from_directory('./dist', 'index.html')

if __name__ == '__main__':
    print('🚀 Simple server starting on port 5000...')
    print('📁 Serving React app from ./dist/')
    app.run(host='0.0.0.0', port=5000, debug=True)