#!/usr/bin/env python3
import websocket
import json
import time

def test_websocket():
    print("🔗 מנסה להתחבר ל-WebSocket...")
    
    try:
        # חיבור פשוט
        ws = websocket.create_connection("wss://ai-crmd.replit.app/ws/twilio-media", timeout=10)
        print("✅ התחברות הצליחה!")
        
        # שליחת start message
        start_msg = {
            "event": "start",
            "start": {
                "streamSid": "MZ_test_simple",
                "callSid": "CA_test_simple"
            }
        }
        
        print(f"📤 שולח start: {start_msg}")
        ws.send(json.dumps(start_msg))
        
        # המתנה לתגובה
        print("⏳ מחכה לתגובה...")
        time.sleep(2)
        
        try:
            response = ws.recv()
            print(f"📨 התקבל: {response}")
        except websocket.WebSocketTimeoutError:
            print("⏱️ Timeout - אין תגובה")
        except Exception as e:
            print(f"❌ שגיאה בקבלה: {e}")
        
        ws.close()
        print("🔒 חיבור נסגר")
        
        return True
        
    except websocket.WebSocketConnectionClosedException as e:
        print(f"❌ חיבור נסגר: {e}")
        return False
    except websocket.WebSocketBadStatusException as e:
        print(f"❌ סטטוס רע: {e}")
        return False
    except Exception as e:
        print(f"❌ שגיאה כללית: {e}")
        return False

if __name__ == "__main__":
    success = test_websocket()
    print(f"🎯 תוצאה: {'הצלחה' if success else 'כישלון'}")
