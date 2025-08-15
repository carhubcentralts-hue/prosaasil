#!/usr/bin/env python3
"""
Test continuous Hebrew conversation flow
"""

def simulate_continuous_call():
    """Simulate a continuous conversation flow"""
    print("🎯 Testing Continuous Hebrew Conversation Flow")
    print("=" * 50)
    
    # Test AI responses for various customer inputs
    test_inputs = [
        "שלום אני מחפש דירה להשכרה בתל אביב",
        "כמה עולה דירת 3 חדרים",
        "באיזה אזורים יש לכם דירות זמינות",
        "אני רוצה לקבוע פגישה לצפייה",
        "תודה רבה נשמח לשמוע ממכם"
    ]
    
    try:
        from server.ai_conversation import generate_response
        from server.hebrew_tts_enhanced import create_hebrew_audio
        
        for i, customer_input in enumerate(test_inputs, 1):
            print(f"\n{i}. Customer: {customer_input}")
            
            # Generate AI response
            ai_response = generate_response(customer_input, f"test_continuous_{i}")
            print(f"   AI Response: {ai_response}")
            
            # Test TTS generation
            tts_file = create_hebrew_audio(ai_response, f"test_turn_{i}")
            if tts_file:
                print(f"   TTS File: {tts_file} ✅")
            else:
                print(f"   TTS File: Failed ❌")
            
            print("-" * 40)
        
        print("\n🎉 Continuous conversation flow ready!")
        print("📞 The system will now:")
        print("   1. Play Hebrew greeting")
        print("   2. Record customer (30s max)")
        print("   3. Transcribe with Whisper")
        print("   4. Generate AI response in Hebrew")
        print("   5. Play TTS response")
        print("   6. Record again → LOOP until customer hangs up")
        
    except Exception as e:
        print(f"❌ Error testing continuous flow: {e}")

if __name__ == "__main__":
    simulate_continuous_call()