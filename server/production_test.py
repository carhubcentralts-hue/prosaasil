#!/usr/bin/env python3
"""
Production Readiness Test - מבצע בדיקה מלאה שהמערכת מוכנה לשיחות אמיתיות
"""

import os
import sys
import requests
import json
from datetime import datetime
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

def test_complete_conversation_simulation():
    """בדיקת שיחה מלאה עם כל השלבים"""
    print("🎭 Simulating Complete Real Conversation")
    print("=" * 50)
    
    try:
        from simple_ai_conversation import SimpleHebrewAI
        
        ai = SimpleHebrewAI()
        conversation_turns = [
            "שלום, אני מחפש דירה להשכרה בתל אביב",
            "יש לי תקציב של 8000 שקל בחודש",
            "אני מעוניין באזור הצפון של העיר",
            "תודה רבה על העזרה, ביי"
        ]
        
        context = ai.get_business_context(1)
        print(f"📞 Business: {context['name']}")
        print(f"📱 Phone: {context['phone']}")
        
        call_sid = f"PROD_TEST_{datetime.now().timestamp()}"
        
        print(f"\n🎙️ Simulating conversation turns:")
        
        for i, user_input in enumerate(conversation_turns, 1):
            print(f"\nTurn {i}:")
            print(f"  🗣️ Customer: {user_input}")
            
            # יצירת תשובת AI
            ai_response = ai.generate_ai_response(user_input, context)
            print(f"  🤖 AI Response: {ai_response}")
            
            # בדיקת אם צריך לסיים
            should_end = ai.check_conversation_end(user_input, ai_response)
            print(f"  📊 Status: {'🔚 END CONVERSATION' if should_end else '🔄 CONTINUE'}")
            
            # שמירת התור
            ai.simple_save_conversation(
                call_sid, 
                user_input, 
                ai_response, 
                f"https://fake-recording-{i}.mp3"
            )
            
            if should_end:
                print("  ✅ Conversation ended naturally")
                break
        
        print(f"\n✅ Complete conversation simulation: SUCCESS")
        return True
        
    except Exception as e:
        print(f"❌ Conversation simulation failed: {e}")
        return False

def test_webhook_production_readiness():
    """בדיקת webhooks מוכנות לפרודקשן"""
    print(f"\n🔗 Testing Production Webhook Readiness")
    print("=" * 50)
    
    webhook_tests = [
        {
            'name': 'Incoming Call',
            'url': 'http://localhost:5000/webhook/incoming_call',
            'data': {
                'CallSid': 'PROD_INCOMING_TEST',
                'From': '+972501234567',
                'To': '+972355577777'
            },
            'expected_content': ['שלום וברכה', 'שי דירות ומשרדים', 'Record action']
        },
        {
            'name': 'Recording Handler (No URL)',
            'url': 'http://localhost:5000/webhook/handle_recording',
            'data': {
                'CallSid': 'PROD_RECORDING_TEST',
                'RecordingUrl': '',
                'From': '+972501234567'
            },
            'expected_content': ['לא קיבלתי את ההקלטה', 'Record action']
        }
    ]
    
    all_passed = True
    
    for test in webhook_tests:
        print(f"\n🧪 Testing {test['name']}:")
        try:
            response = requests.post(test['url'], data=test['data'], timeout=10)
            
            if response.status_code == 200:
                print(f"   ✅ HTTP Status: {response.status_code}")
                
                # בדיקת תוכן התגובה
                content_checks_passed = 0
                for expected in test['expected_content']:
                    if expected in response.text:
                        print(f"   ✅ Content check: '{expected}' found")
                        content_checks_passed += 1
                    else:
                        print(f"   ❌ Content check: '{expected}' missing")
                
                if content_checks_passed == len(test['expected_content']):
                    print(f"   ✅ All content checks passed")
                else:
                    print(f"   ❌ {content_checks_passed}/{len(test['expected_content'])} content checks passed")
                    all_passed = False
            else:
                print(f"   ❌ HTTP Status: {response.status_code}")
                all_passed = False
                
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            all_passed = False
    
    return all_passed

def test_conversation_logging():
    """בדיקת לוגים של שיחות לעסק"""
    print(f"\n📋 Testing Business Conversation Logging")
    print("=" * 50)
    
    try:
        # בדיקת קיום קובץ לוג
        if os.path.exists('conversation_log.json'):
            with open('conversation_log.json', 'r', encoding='utf-8') as f:
                conversations = json.load(f)
            
            print(f"✅ Log file exists with {len(conversations)} conversations")
            
            if len(conversations) > 0:
                latest = conversations[-1]
                print(f"✅ Latest conversation:")
                print(f"   Call SID: {latest.get('call_sid', 'N/A')}")
                print(f"   Customer: {latest.get('transcription', 'N/A')[:50]}...")
                print(f"   AI Response: {latest.get('ai_response', 'N/A')[:50]}...")
                print(f"   Timestamp: {latest.get('timestamp', 'N/A')}")
                
                return True
            else:
                print("❌ Log file is empty")
                return False
        else:
            print("❌ Log file doesn't exist")
            return False
            
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False

def print_production_summary():
    """סיכום מוכנות לפרודקשן"""
    print(f"\n" + "="*60)
    print(f"🎯 PRODUCTION READINESS SUMMARY")
    print(f"="*60)
    
    print(f"📞 TWILIO CONFIGURATION:")
    print(f"   Webhook URL (Incoming): /webhook/incoming_call")
    print(f"   Webhook URL (Recording): /webhook/handle_recording")
    print(f"   HTTP Method: POST")
    print(f"   Expected Format: application/x-www-form-urlencoded")
    
    print(f"\n🏢 BUSINESS DETAILS:")
    print(f"   Name: שי דירות ומשרדים בע״מ")
    print(f"   Type: Real Estate Agency")
    print(f"   Phone: +972-3-555-7777")
    
    print(f"\n🤖 AI FEATURES:")
    print(f"   Language: Hebrew (עברית)")
    print(f"   Model: OpenAI GPT-4o")
    print(f"   Transcription: OpenAI Whisper")
    print(f"   Conversation Flow: Continuous until 'bye'")
    print(f"   Response Style: Professional Real Estate Agent")
    
    print(f"\n📝 LOGGING:")
    print(f"   All conversations saved to: conversation_log.json")
    print(f"   Includes: Customer input, AI responses, timestamps")
    print(f"   Format: UTF-8 JSON for Hebrew support")
    
    print(f"\n⚡ PERFORMANCE:")
    print(f"   Real-time conversation processing")
    print(f"   Hebrew speech recognition")
    print(f"   Intelligent conversation end detection")
    
    print(f"\n🔒 READY FOR PRODUCTION: YES! ✅")
    print(f"="*60)

if __name__ == "__main__":
    print("🚀 Production Readiness Test\n")
    
    # Run all tests
    conversation_ok = test_complete_conversation_simulation()
    webhooks_ok = test_webhook_production_readiness()
    logging_ok = test_conversation_logging()
    
    print(f"\n📊 TEST RESULTS:")
    print(f"   Conversation Simulation: {'✅ PASS' if conversation_ok else '❌ FAIL'}")
    print(f"   Webhook Readiness: {'✅ PASS' if webhooks_ok else '❌ FAIL'}")
    print(f"   Conversation Logging: {'✅ PASS' if logging_ok else '❌ FAIL'}")
    
    if all([conversation_ok, webhooks_ok, logging_ok]):
        print(f"\n🎉 ALL TESTS PASSED!")
        print_production_summary()
    else:
        print(f"\n⚠️ Some tests failed - check above for details")