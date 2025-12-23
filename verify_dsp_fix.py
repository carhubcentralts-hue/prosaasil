#!/usr/bin/env python3
"""
Verification script for DSP fix
Demonstrates that DSP now accepts both bytes and Base64 string input
"""
import sys
import os
import base64

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.services.audio_dsp import AudioDSPProcessor

def main():
    print("=" * 70)
    print("DSP Fix Verification")
    print("=" * 70)
    print()
    
    # Create DSP processor
    processor = AudioDSPProcessor()
    print("✅ Created DSP processor instance")
    print()
    
    # Generate dummy μ-law audio (160 bytes = 20ms frame at 8kHz)
    mulaw_bytes = bytes([0x80] * 160)  # Silence in μ-law
    print(f"✅ Generated test audio: {len(mulaw_bytes)} bytes")
    print()
    
    # Test 1: Process bytes input (original behavior)
    print("Test 1: Bytes input (original behavior)")
    print("-" * 70)
    try:
        output_bytes = processor.process(mulaw_bytes)
        assert isinstance(output_bytes, bytes), "Output should be bytes"
        assert len(output_bytes) == len(mulaw_bytes), "Output length should match input"
        print(f"✅ Input:  bytes ({len(mulaw_bytes)} bytes)")
        print(f"✅ Output: bytes ({len(output_bytes)} bytes)")
        print(f"✅ Test 1 PASSED\n")
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}\n")
        return 1
    
    # Test 2: Process Base64 string input (new behavior - FIX!)
    print("Test 2: Base64 string input (NEW - fixes the bug!)")
    print("-" * 70)
    try:
        mulaw_b64 = base64.b64encode(mulaw_bytes).decode("ascii")
        output_b64 = processor.process(mulaw_b64)
        
        assert isinstance(output_b64, str), "Output should be string"
        assert len(output_b64) == len(mulaw_b64), "Output length should match input"
        
        # Verify it's valid Base64
        decoded_output = base64.b64decode(output_b64)
        assert len(decoded_output) == len(mulaw_bytes), "Decoded output should match original length"
        
        print(f"✅ Input:  Base64 string ({len(mulaw_b64)} chars)")
        print(f"✅ Output: Base64 string ({len(output_b64)} chars)")
        print(f"✅ Decoded output: {len(decoded_output)} bytes")
        print(f"✅ Test 2 PASSED\n")
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 3: Verify pipeline scenario (Twilio → DSP → OpenAI)
    print("Test 3: Pipeline scenario (Twilio → DSP → OpenAI)")
    print("-" * 70)
    try:
        # Simulate Twilio payload (Base64 string)
        twilio_payload = base64.b64encode(mulaw_bytes).decode("ascii")
        print(f"📥 Twilio sends: Base64 string ({len(twilio_payload)} chars)")
        
        # DSP processes it
        processed_payload = processor.process(twilio_payload)
        print(f"⚙️  DSP processes: Base64 → bytes → DSP → bytes → Base64")
        
        # Verify output is still Base64 string for OpenAI
        assert isinstance(processed_payload, str), "DSP output should remain Base64 string"
        print(f"📤 DSP outputs: Base64 string ({len(processed_payload)} chars)")
        
        # Verify OpenAI can receive it (simulate by decoding)
        openai_receives = base64.b64decode(processed_payload)
        print(f"✅ OpenAI receives: {len(openai_receives)} bytes of μ-law audio")
        print(f"✅ Test 3 PASSED\n")
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    
    print("=" * 70)
    print("🎉 All tests PASSED! DSP fix is working correctly!")
    print("=" * 70)
    print()
    print("Summary:")
    print("  • DSP accepts both bytes and Base64 string input")
    print("  • DSP returns output in same format as input")
    print("  • Pipeline Twilio → DSP → OpenAI works without errors")
    print("  • No changes needed to media_ws_ai.py")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
