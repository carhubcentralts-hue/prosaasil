#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 AgentLocator v42 - שרת פשוט לוודא שהכל עובד
"""
import os
import json
import psycopg2
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# API לאימות שהמערכת עובדת
@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        # בדיקת חיבור לדטאבייס
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cur = conn.cursor()
        
        # בדיקת עסק שי דירות ומשרדים
        cur.execute("SELECT name, business_type, is_active FROM business WHERE name LIKE '%שי%'")
        business = cur.fetchone()
        
        # בדיקת שיחות
        cur.execute("SELECT COUNT(*) FROM call_log")
        calls_count = cur.fetchone()[0]
        
        # בדיקת משתמשים
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "AgentLocator v42 פעיל",
            "database": "connected",
            "business": {
                "name": business[0] if business else None,
                "type": business[1] if business else None,
                "active": business[2] if business else None
            },
            "stats": {
                "calls": calls_count,
                "users": users_count
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"שגיאה: {str(e)}"
        }), 500

@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cur = conn.cursor()
        
        # סטטיסטיקות מתקדמות
        cur.execute("SELECT COUNT(*) FROM business WHERE is_active = true")
        active_businesses = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM call_log WHERE created_at >= NOW() - INTERVAL '30 days'")
        recent_calls = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "active_businesses": active_businesses,
            "recent_calls": recent_calls,
            "system": "AgentLocator v42",
            "status": "operational"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v42/verification', methods=['GET'])
def verify_v42_components():
    """בדיקה שכל רכיבי v42 קיימים"""
    components = {
        "DataTable": os.path.exists("../client/src/components/DataTable.tsx"),
        "Socket.IO": os.path.exists("../client/src/lib/socket.ts"),
        "ServiceWorker": os.path.exists("../client/public/service-worker.js"),
        "DesignTokens": os.path.exists("../client/src/styles/design-tokens.css"),
        "PWAManifest": os.path.exists("../client/public/manifest.json"),
        "CI_CD": os.path.exists("../.github/workflows/ci.yml"),
        "DebugCleanup": os.path.exists("debug_cleanup.py")
    }
    
    success_count = sum(1 for status in components.values() if status)
    
    return jsonify({
        "v42_status": "verified",
        "components": components,
        "success_rate": f"{success_count}/{len(components)}",
        "all_working": success_count == len(components)
    })

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "project": "AgentLocator v42 Hebrew AI CRM",
        "business": "שי דירות ומשרדים בע״מ", 
        "status": "✅ מערכת פעילה",
        "endpoints": [
            "/api/status",
            "/api/admin/stats", 
            "/api/v42/verification"
        ]
    })

if __name__ == '__main__':
    print("🚀 מפעיל שרת אימות AgentLocator v42...")
    print("📋 נקודות בדיקה:")
    print("   - /api/status")
    print("   - /api/admin/stats") 
    print("   - /api/v42/verification")
    
    app.run(host='0.0.0.0', port=5000, debug=False)