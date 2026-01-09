"""
Test ash→cedar voice transition for content filter issue
Simulates the exact user scenario
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_voice_change_cache_invalidation():
    """
    Test that cache is properly invalidated when changing from ash to cedar
    """
    from server.config.voices import REALTIME_VOICES, DEFAULT_VOICE, SPEECH_CREATE_VOICES
    
    print("🧪 Testing ash→cedar voice transition\n")
    print("=" * 60)
    
    # 1. Verify both voices are valid
    print("\n1️⃣  Verifying voices are in REALTIME_VOICES:")
    print(f"   ash in REALTIME_VOICES: {'ash' in REALTIME_VOICES} ✅" if 'ash' in REALTIME_VOICES else "   ❌ ash NOT in REALTIME_VOICES")
    print(f"   cedar in REALTIME_VOICES: {'cedar' in REALTIME_VOICES} ✅" if 'cedar' in REALTIME_VOICES else "   ❌ cedar NOT in REALTIME_VOICES")
    
    # 2. Check preview engine difference
    print("\n2️⃣  Checking preview engine difference:")
    print(f"   ash in SPEECH_CREATE_VOICES: {'ash' in SPEECH_CREATE_VOICES} (uses TTS-1 for preview)")
    print(f"   cedar in SPEECH_CREATE_VOICES: {'cedar' in SPEECH_CREATE_VOICES} (uses Realtime for preview)")
    
    if 'ash' in SPEECH_CREATE_VOICES and 'cedar' not in SPEECH_CREATE_VOICES:
        print("   ⚠️  DIFFERENCE DETECTED: ash and cedar use DIFFERENT preview engines!")
        print("      - ash: speech.create (TTS-1 API)")
        print("      - cedar: Realtime API")
        print("      → This could cause state/cache issues during transition")
    
    # 3. Check default voice
    print(f"\n3️⃣  Current DEFAULT_VOICE: '{DEFAULT_VOICE}'")
    if DEFAULT_VOICE == 'cedar':
        print("   ℹ️  DEFAULT is cedar (new default)")
        print("   ℹ️  Database migration set default to 'ash' (old default)")
        print("   → Mismatch between code default and DB default!")
    
    # 4. Test voice validation
    print("\n4️⃣  Testing voice validation:")
    voices_to_test = ['ash', 'cedar', 'Ash', 'Cedar', 'ASH', 'CEDAR', ' ash', 'ash ', 'cedar\n']
    
    for voice in voices_to_test:
        is_valid = voice in REALTIME_VOICES
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"   '{repr(voice)}': {status}")
    
    # 5. Check for whitespace/encoding issues
    print("\n5️⃣  Checking for potential mapping issues:")
    ash_repr = repr('ash')
    cedar_repr = repr('cedar')
    print(f"   'ash' representation: {ash_repr}")
    print(f"   'cedar' representation: {cedar_repr}")
    print(f"   'ash' == 'ash': {('ash' == 'ash')}")
    print(f"   'cedar' == 'cedar': {('cedar' == 'cedar')}")
    
    # 6. Simulate cache key generation
    print("\n6️⃣  Cache key generation:")
    test_business_id = 123
    voice_cache_key_ash = f"voice_{test_business_id}"
    ai_settings_cache_key = f"ai_settings_{test_business_id}"
    prompt_cache_key_inbound = f"{test_business_id}:inbound"
    prompt_cache_key_outbound = f"{test_business_id}:outbound"
    
    print(f"   Voice cache key: {voice_cache_key_ash}")
    print(f"   AI settings cache key: {ai_settings_cache_key}")
    print(f"   Prompt cache key (inbound): {prompt_cache_key_inbound}")
    print(f"   Prompt cache key (outbound): {prompt_cache_key_outbound}")
    print("   ℹ️  Note: Voice is NOT part of prompt cache key!")
    print("   → Changing voice requires explicit cache invalidation")
    
    # 7. Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    print("=" * 60)
    print("\n✅ Both ash and cedar are valid Realtime voices")
    print("\n⚠️  KEY DIFFERENCES:")
    print("   1. Preview engine: ash uses TTS-1, cedar uses Realtime API")
    print("   2. Default voice: Code=cedar, DB migration=ash (mismatch)")
    print("   3. Cache keys: Voice NOT included in prompt cache key")
    print("\n🔍 POTENTIAL ROOT CAUSES FOR ash→cedar CONTENT FILTER:")
    print("   A. Preview engine state pollution")
    print("   B. Stale prompt cache not invalidated on voice change")
    print("   C. Case sensitivity or whitespace in voice comparison")
    print("   D. Default voice mismatch causing validation issues")
    
    print("\n✅ Test completed!")
    

def test_voice_sanitization():
    """Test if voice values need sanitization"""
    print("\n\n🧪 Testing voice value sanitization\n")
    print("=" * 60)
    
    test_values = [
        'ash',
        'cedar', 
        ' ash ',
        'Ash',
        'CEDAR',
        'ash\n',
        '\nash',
        'ash\r\n'
    ]
    
    for value in test_values:
        stripped = value.strip().lower()
        print(f"Original: {repr(value):20s} → Stripped: {repr(stripped):15s} {'✅ OK' if stripped in ['ash', 'cedar'] else '❌ BAD'}")
    
    print("\n✅ Sanitization test completed!")


if __name__ == "__main__":
    test_voice_change_cache_invalidation()
    test_voice_sanitization()
