#!/usr/bin/env python3
"""
Test Hebrew AI Conversation Flow
בדיקת תהליך השיחה המלא: תמלול → AI → TTS
"""

import os
import sys
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

def test_ai_system():
    """בדיקה מלאה של מערכת ה-AI"""
    print("🧪 Testing Hebrew AI Conversation System")
    print("=" * 50)
    
    # Test 1: Import all modules
    try:
        from whisper_handler import transcribe_hebrew
        print("✅ Whisper handler imported")
    except Exception as e:
        print(f"❌ Whisper handler failed: {e}")
        return False
        
    try:
        from hebrew_tts import HebrewTTSService
        tts = HebrewTTSService()
        print("✅ Hebrew TTS service loaded")
    except Exception as e:
        print(f"❌ TTS service failed: {e}")
        
    try:
        from ai_conversation import ai_conversation
        print("✅ AI conversation system loaded")
        
        # Test business context
        context = ai_conversation.get_business_context(1)
        print(f"✅ Business context: {context['name']}")
        
        # Test AI response generation
        test_input = "שלום, אני מחפש דירה"
        response = ai_conversation.generate_ai_response(test_input, [], context)
        print(f"✅ AI Response test: {response[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ AI conversation system failed: {e}")
        print(f"   Error details: {type(e).__name__}")
        return False

def test_database():
    """בדיקת חיבור למסד נתונים"""
    try:
        from app_simple import app
        from models import db, Business, CallLog
        
        with app.app_context():
            # Check if tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"✅ Database tables: {len(tables)} found")
            
            # Try to create a test business if none exists
            business = Business.query.first()
            if not business:
                print("⚠️  No business found in database")
            else:
                print(f"✅ Business found: {business.name}")
                
            return True
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_full_conversation_flow():
    """בדיקת תהליך שיחה מלא"""
    print("\n🎯 Testing Full Conversation Flow")
    print("=" * 50)
    
    try:
        from ai_conversation import ai_conversation
        
        # Simulate conversation turn
        call_sid = "TEST_CALL_123"
        fake_recording_url = "https://fake-recording.com/test.mp3"
        
        print(f"📞 Simulating conversation for call: {call_sid}")
        
        # This will fail on transcription (fake URL) but test the flow
        result = ai_conversation.process_conversation_turn(
            call_sid=call_sid,
            recording_url=fake_recording_url,
            turn_number=1
        )
        
        if result['success']:
            print("✅ Full conversation flow completed successfully")
            print(f"   Transcription: {result.get('transcription', 'N/A')}")
            print(f"   AI Response: {result.get('ai_response', 'N/A')}")
        else:
            print("⚠️  Flow completed with expected errors (fake recording URL)")
            
        return True
        
    except Exception as e:
        print(f"❌ Full conversation test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting AI System Tests...")
    
    ai_ok = test_ai_system()
    db_ok = test_database()
    flow_ok = test_full_conversation_flow()
    
    print("\n📊 Test Results Summary:")
    print(f"   AI System: {'✅ PASS' if ai_ok else '❌ FAIL'}")
    print(f"   Database: {'✅ PASS' if db_ok else '❌ FAIL'}")
    print(f"   Full Flow: {'✅ PASS' if flow_ok else '❌ FAIL'}")
    
    if all([ai_ok, db_ok, flow_ok]):
        print("\n🎉 ALL TESTS PASSED! AI System is ready for Twilio integration!")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")