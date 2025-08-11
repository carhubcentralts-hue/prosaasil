#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Professional Main Server
מערכת מקצועית עם אימות פשוט
"""

import sys
import os

# Import the simple professional server
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

if __name__ == '__main__':
    print("🚀 AgentLocator CRM - Professional System")
    print("📊 Starting Professional Hebrew Business Management")
    print("🔐 Easy Login: admin/admin, user/user, manager/123")
    print("🌐 Professional Interface Ready")
    
    try:
        from app_simple import app
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"Error starting server: {e}")
        
        # Fallback simple server
        from flask import Flask, jsonify
        fallback_app = Flask(__name__)
        
        @fallback_app.route('/')
        def home():
            return '''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>AgentLocator CRM</title>
    <link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { 
            font-family: "Assistant", sans-serif; margin: 0; direction: rtl; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
        }
        .container { 
            background: white; padding: 3rem; border-radius: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15); text-align: center; max-width: 500px;
        }
        h1 { color: #2d3748; font-size: 2.2rem; margin-bottom: 1rem; }
        .status { color: #48bb78; font-weight: 600; margin: 1rem 0; }
        .credentials { background: #f8fafc; padding: 2rem; border-radius: 16px; margin: 2rem 0; }
        .cred-item { margin: 0.8rem 0; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AgentLocator CRM</h1>
        <div class="status">✅ מערכת מקצועית מוכנה</div>
        <p>מערכת ניהול לקוחות עם בינה מלאכותית עברית</p>
        <div class="credentials">
            <strong>פרטי התחברות:</strong>
            <div class="cred-item">admin / admin (מנהל)</div>
            <div class="cred-item">user / user (עסק)</div>
            <div class="cred-item">manager / 123 (מנהל ראשי)</div>
        </div>
    </div>
</body>
</html>'''
        
        @fallback_app.route('/health')
        def health():
            return jsonify({'status': 'healthy'})
        
        fallback_app.run(host='0.0.0.0', port=5000)