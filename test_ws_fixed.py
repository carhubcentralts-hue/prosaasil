#!/usr/bin/env python3
import websocket
import json
import time

def test_websocket_fixed():
    print("🔗 מנסה להתחבר ל-WebSocket אחרי תיקון Flask-Sock...")
    
    try:
        ws = websocket.create_connection("wss://ai-crmd.replit.app/ws/twilio-media", timeout=10)
        print("✅ התחברות הצליחה!")
        
        # שליחת start message
        start_msg = {
            "event": "start", 
            "start": {
                "streamSid": "MZ_test_flask_sock_fix",
                "callSid": "CA_test_flask_sock_fix"
            }
        }
        
        print(f"📤 שולח start: {json.dumps(start_msg)}")
        ws.send(json.dumps(start_msg))
        
        # המתנה קצרה
        time.sleep(3)
        print("⏳ המתנה הסתיימה")
        
        ws.close()
        print("🔒 חיבור נסגר")
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False

if __name__ == "__main__":
    result = test_websocket_fixed()
    print(f"🎯 תוצאה: {'הצלחה' if result else 'כישלון'}")
