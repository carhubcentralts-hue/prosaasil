#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Production Main Server
"""

import sys
import os

# Import the production server
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

if __name__ == '__main__':
    print("🚀 AgentLocator CRM - Production System")
    print("📊 Hebrew Business Management Platform")
    print("🔐 Login: admin/admin, shai/shai123")
    print("🌐 Professional Interface Ready")
    
    from app_simple import app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)