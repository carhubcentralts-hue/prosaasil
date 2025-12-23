#!/usr/bin/env python3
"""
Verification script for DSP pipeline fix
Tests the complete Twilio → DSP → OpenAI pipeline with Base64 encoding/decoding
"""
import sys
import os
import base64

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.services.audio_dsp import AudioDSPProcessor

def main():
    print("=" * 70)
    print("DSP Pipeline Verification (Base64 → bytes → DSP → bytes → Base64)")
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
    
    # Test: Complete pipeline (mimics media_ws_ai.py behavior)
    print("Test: Complete Twilio → DSP → OpenAI Pipeline")
    print("-" * 70)
    try:
        # Step 1: Twilio sends Base64 string (simulated)
        twilio_payload = base64.b64encode(mulaw_bytes).decode("ascii")
        print(f"📥 Step 1: Twilio payload (Base64): {len(twilio_payload)} chars")
        
        # Step 2: Decode Base64 to bytes before DSP
        mulaw_decoded = base64.b64decode(twilio_payload)
        print(f"🔓 Step 2: Decoded to bytes: {len(mulaw_decoded)} bytes")
        
        # Step 3: Process with DSP (bytes → bytes)
        processed_bytes = processor.process(mulaw_decoded)
        print(f"⚙️  Step 3: DSP processed: {len(processed_bytes)} bytes")
        
        # Step 4: Encode back to Base64 for OpenAI
        openai_payload = base64.b64encode(processed_bytes).decode("ascii")
        print(f"🔐 Step 4: Encoded to Base64: {len(openai_payload)} chars")
        
        # Verify
        assert isinstance(processed_bytes, bytes), "DSP output should be bytes"
        assert len(processed_bytes) == len(mulaw_bytes), "DSP output length should match input"
        assert isinstance(openai_payload, str), "OpenAI payload should be Base64 string"
        assert len(openai_payload) == len(twilio_payload), "Payload length should be preserved"
        
        print(f"📤 Step 5: Ready to send to OpenAI")
        print(f"✅ Pipeline test PASSED\n")
        
        # Summary
        print("=" * 70)
        print("Pipeline Summary")
        print("=" * 70)
        print(f"  Input:  Base64 string ({len(twilio_payload)} chars)")
        print(f"  DSP:    bytes → bytes ({len(mulaw_decoded)} → {len(processed_bytes)} bytes)")
        print(f"  Output: Base64 string ({len(openai_payload)} chars)")
        print()
        print("✅ DSP is now pure (bytes-only)")
        print("✅ Base64 encoding/decoding handled at call site")
        print("✅ Pipeline works correctly")
        print()
        
        return 0
        
    except Exception as e:
        print(f"❌ Pipeline test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
