"""
Minimal WSGI entry point for local development/preview.
No eventlet dependencies to avoid libstdc++ issues.
"""
import os
import sys

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from app_factory import create_app

# Create app with development config
app = create_app()

# Safety valve healthz endpoint (direct to app)
@app.route('/healthz')
def healthz():
    return {
        "status": "healthy",
        "app": "hebrew-ai-crm",
        "version": "1.0.0",
        "mode": "minimal"
    }, 200, {
        'X-App-Signature': 'minimal-wsgi',
        'Content-Type': 'application/json'
    }

if __name__ == '__main__':
    # Run Flask dev server for local testing
    app.run(host='0.0.0.0', port=5000, debug=False)