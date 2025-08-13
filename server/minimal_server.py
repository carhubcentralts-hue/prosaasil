#!/usr/bin/env python3
"""
Minimal server for deployment - Entry point for Procfile
This file is used by the Procfile for production deployment.
"""

import os
import sys

# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Change to the parent directory so relative imports work
os.chdir(parent_dir)

# Import and create the Flask app
from server.app_factory import create_app

app = create_app()

if __name__ == '__main__':
    # Production deployment configuration
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    print("🎯 Starting Professional Hebrew AI Call Center CRM")
    print("🔐 Secure Authentication System Active") 
    print("🏢 Business: שי דירות ומשרדים בע״מ")
    print("✅ שיחות רציפות עם זיכרון AI - CONTINUOUS CONVERSATIONS")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)