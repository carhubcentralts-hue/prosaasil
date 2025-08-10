#!/usr/bin/env python3
"""
שרת Flask מתקדם - AgentLocator
מערכת CRM מתקדמת עם הרשאות מבדילות לעברית
"""

import sys
import os
sys.path.append('server')

from server.app import app, init_database

if __name__ == '__main__':
    print("🚀 מפעיל את AgentLocator - מערכת CRM מתקדמת")
    print("📍 Backend: Flask (Python)")
    print("📍 Frontend: React + Vite")
    print("📍 הרשאות: Admin (כל הנתונים) / Business (נתונים אישיים)")
    
    # אתחול מסד נתונים
    init_database()
    
    # הפעלת השרת
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)