#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Professional Hebrew AI Call Center
Rebuilt with App Factory Pattern Following v39-42 Specifications
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_factory import create_app

if __name__ == "__main__":
    env = os.getenv('FLASK_ENV', 'development')
    
    print("🚀 Starting AgentLocator CRM (Professional)")
    print(f"📱 Environment: {env}")
    print("🎯 עסק: שי דירות ומשרדים בע״מ")
    print("✅ Hebrew AI Support Ready")
    print("🔧 App Factory Pattern Active")
    
    app = create_app(env)
    app.run(host="0.0.0.0", port=5000, debug=(env=='development'))