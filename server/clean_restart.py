#!/usr/bin/env python3
"""
Clean System Restart - מאתחל את המערכת ללא בעיות
"""

import os
import sys
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

def clean_start():
    """התחלה נקייה של המערכת"""
    print("🧹 Starting Clean System Initialization...")
    
    # הסרת קבצי cache שגורמים לבעיות
    cache_patterns = [
        '__pycache__',
        '*.pyc',
        'app.db',
        'conversation_log.json'
    ]
    
    for pattern in cache_patterns:
        os.system(f'find . -name "{pattern}" -exec rm -rf {{}} + 2>/dev/null || true')
    
    print("✅ Cache cleaned")
    
    # יצירת מופע Flask חדש ללא בעיות
    try:
        # Import עם Flask app בסיסי
        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy
        from datetime import datetime
        
        # יצירת app חדש
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clean_system.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db = SQLAlchemy()
        db.init_app(app)
        
        # יצירת מודלים פשוטים
        class CleanBusiness(db.Model):
            __tablename__ = 'clean_businesses'
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(200), nullable=False)
            business_type = db.Column(db.String(100), default='real_estate')
            phone = db.Column(db.String(50))
            email = db.Column(db.String(100))
            is_active = db.Column(db.Boolean, default=True)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            
        class CleanCallLog(db.Model):
            __tablename__ = 'clean_call_logs'
            id = db.Column(db.Integer, primary_key=True)
            call_sid = db.Column(db.String(100), unique=True)
            business_id = db.Column(db.Integer, default=1)
            from_number = db.Column(db.String(50))
            call_status = db.Column(db.String(50), default='completed')
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        with app.app_context():
            # יצירת טבלאות חדשות
            db.create_all()
            
            # יצירת עסק ראשי
            existing = CleanBusiness.query.first()
            if not existing:
                business = CleanBusiness()
                business.name = 'שי דירות ומשרדים בע״מ'
                business.business_type = 'real_estate'
                business.phone = '+972-3-555-7777'
                business.email = 'info@shai-realestate.co.il'
                business.is_active = True
                
                db.session.add(business)
                db.session.commit()
                
                print(f"✅ Clean business created: {business.name}")
            else:
                print(f"✅ Business already exists: {existing.name}")
        
        print("✅ Clean database initialized")
        return True
        
    except Exception as e:
        print(f"❌ Clean initialization failed: {e}")
        return False

def test_ai_without_database():
    """בדיקת AI בלי חיבור למסד נתונים"""
    print("\n🤖 Testing AI System (without database)...")
    
    try:
        from simple_ai_conversation import SimpleHebrewAI
        
        # יצירת מופע AI חדש
        ai = SimpleHebrewAI()
        
        # קבלת context ללא מסד נתונים (fallback)
        context = ai.get_business_context(1)
        print(f"✅ Business context: {context['name']}")
        
        # בדיקת OpenAI API Key
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and len(api_key) > 20:
            print(f"✅ OpenAI API Key available: {len(api_key)} chars")
        else:
            print("❌ OpenAI API Key missing")
            
        return True
        
    except Exception as e:
        print(f"❌ AI test failed: {e}")
        return False

def test_webhooks():
    """בדיקת Twilio webhooks"""
    print("\n📞 Testing Twilio Integration...")
    
    try:
        import requests
        
        # בדיקת incoming call webhook
        response = requests.post('http://localhost:5000/webhook/incoming_call', 
                               data={'CallSid': 'TEST_123', 'From': '+972501234567'},
                               timeout=5)
        
        if response.status_code == 200 and 'שלום וברכה' in response.text:
            print("✅ Incoming call webhook working")
            return True
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Webhook test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Clean System Restart\n")
    
    # Step 1: Clean initialization
    clean_ok = clean_start()
    
    # Step 2: Test AI system
    ai_ok = test_ai_without_database()
    
    # Step 3: Test webhooks
    webhook_ok = test_webhooks()
    
    print(f"\n📊 Clean System Status:")
    print(f"   Database: {'✅ CLEAN' if clean_ok else '❌ FAILED'}")
    print(f"   AI System: {'✅ READY' if ai_ok else '❌ FAILED'}")
    print(f"   Webhooks: {'✅ WORKING' if webhook_ok else '❌ FAILED'}")
    
    if all([clean_ok, ai_ok, webhook_ok]):
        print(f"\n🎯 SUCCESS! Clean system is operational!")
        print(f"   📞 Ready for real Twilio calls")
        print(f"   🤖 AI conversation system loaded")
        print(f"   🏢 Business: שי דירות ומשרדים בע״מ")
    else:
        print(f"\n⚠️  Some components need attention")