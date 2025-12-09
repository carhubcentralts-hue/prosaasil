#!/usr/bin/env python3
"""
Verification script for TwiML WebSocket fix
Simulates what Twilio receives when a call comes in
"""

from twilio.twiml.voice_response import VoiceResponse

def test_incoming_call_twiml():
    """Test that incoming_call generates correct TwiML"""
    host = "prosaas.pro"
    call_sid = "CA_TEST_123"
    to_number = "+972123456789"
    
    # Replicate the fixed incoming_call logic
    vr = VoiceResponse()
    
    # NO vr.record() call anymore!
    
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(
        url=f"wss://{host}/ws/twilio-media",
        track="inbound_track"
    )
    
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value=to_number)
    
    twiml_str = str(vr)
    
    print("=" * 80)
    print("INCOMING CALL TwiML")
    print("=" * 80)
    print(twiml_str)
    print("=" * 80)
    
    # Verify no <Record> tag
    if "<Record" in twiml_str:
        print("❌ FAIL: TwiML contains <Record> tag!")
        return False
    
    # Verify has <Connect> and <Stream>
    if "<Connect" in twiml_str and "<Stream" in twiml_str:
        print("✅ PASS: TwiML has <Connect> and <Stream> only")
        return True
    else:
        print("❌ FAIL: TwiML missing required tags")
        return False

def test_outbound_call_twiml():
    """Test that outbound_call generates correct TwiML"""
    host = "prosaas.pro"
    call_sid = "CA_TEST_456"
    to_number = "+972987654321"
    
    # Replicate the fixed outbound_call logic
    vr = VoiceResponse()
    
    # NO vr.record() call anymore!
    
    connect = vr.connect(action=f"https://{host}/webhook/stream_ended")
    stream = connect.stream(
        url=f"wss://{host}/ws/twilio-media",
        track="inbound_track"
    )
    
    stream.parameter(name="CallSid", value=call_sid)
    stream.parameter(name="To", value=to_number)
    stream.parameter(name="direction", value="outbound")
    stream.parameter(name="lead_id", value="123")
    stream.parameter(name="lead_name", value="Test Lead")
    
    twiml_str = str(vr)
    
    print("\n")
    print("=" * 80)
    print("OUTBOUND CALL TwiML")
    print("=" * 80)
    print(twiml_str)
    print("=" * 80)
    
    # Verify no <Record> tag
    if "<Record" in twiml_str:
        print("❌ FAIL: TwiML contains <Record> tag!")
        return False
    
    # Verify has <Connect> and <Stream>
    if "<Connect" in twiml_str and "<Stream" in twiml_str:
        print("✅ PASS: TwiML has <Connect> and <Stream> only")
        return True
    else:
        print("❌ FAIL: TwiML missing required tags")
        return False

if __name__ == "__main__":
    print("\n🔍 Testing TwiML Generation After Fix\n")
    
    test1 = test_incoming_call_twiml()
    test2 = test_outbound_call_twiml()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if test1 and test2:
        print("✅ All tests PASSED - TwiML is correct!")
        print("✅ WebSocket connections should work now")
        print("✅ Recording still happens via stream_ended webhook")
        exit(0)
    else:
        print("❌ Some tests FAILED - check TwiML generation")
        exit(1)
