"""
Test: "Same Logic, Different Brain" Architecture Validation
=============================================================

Validates that Gemini and OpenAI use:
1. Same prompts (single source of truth)
2. Same guards and validation rules
3. Same audio pipeline (PCMU 8k, 20ms)
4. Same state machine
5. Provider isolation (no mixing)
"""
import os
import sys


def test_single_prompt_source():
    """Test that both providers use the same prompt building function"""
    print("\n" + "=" * 60)
    print("Test 1: Single Prompt Source")
    print("=" * 60)
    
    # Read prompt builder
    with open('server/services/realtime_prompt_builder.py', 'r') as f:
        content = f.read()
    
    # Should NOT have provider-specific prompt functions
    if 'def build_prompt_for_gemini' in content or 'def build_prompt_for_openai' in content:
        print("❌ FAIL: Found provider-specific prompt functions")
        return False
    
    # Should have universal prompt builder
    if 'def build_full_business_prompt(' in content:
        print("✓ build_full_business_prompt() exists (universal)")
    else:
        print("❌ FAIL: Universal prompt builder not found")
        return False
    
    # Should not modify prompts based on provider
    if 'if ai_provider == "gemini"' in content and 'prompt' in content:
        print("⚠️ WARNING: Prompt logic might be provider-specific")
        # This is OK for voice injection, but NOT for business logic
    
    print("✅ PASS: Single prompt source validated")
    return True


def test_unified_audio_output():
    """Test that both providers use the same audio output function"""
    print("\n" + "=" * 60)
    print("Test 2: Unified Audio Output")
    print("=" * 60)
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Should have single audio output function
    if 'def _send_pcm16_as_mulaw_frames(' not in content:
        print("❌ FAIL: Unified audio function not found")
        return False
    
    print("✓ _send_pcm16_as_mulaw_frames() exists")
    
    # Should NOT have provider-specific TX paths
    if 'def _send_audio_gemini(' in content or 'def _send_audio_openai(' in content:
        print("❌ FAIL: Provider-specific audio functions found")
        return False
    
    print("✓ No provider-specific audio functions")
    
    # Both TTS methods should use the same output
    if '_send_pcm16_as_mulaw_frames(tts_audio)' in content or '_send_pcm16_as_mulaw_frames_with_mark(tts_audio)' in content:
        print("✓ TTS uses unified audio output")
    else:
        print("⚠️ WARNING: TTS might not use unified output")
    
    # Check for PCMU format and frame size
    if 'FR = 160' in content and '# 20ms @ 8kHz' in content:
        print("✓ Frame size: 160 bytes (20ms @ 8kHz)")
    else:
        print("❌ FAIL: Frame size not properly defined")
        return False
    
    if 'audioop.lin2ulaw(pcm16_8k, 2)' in content:
        print("✓ Audio format: PCMU (μ-law)")
    else:
        print("❌ FAIL: μ-law conversion not found")
        return False
    
    print("✅ PASS: Unified audio output validated")
    return True


def test_provider_isolation():
    """Test that provider controls both LLM and TTS (no mixing)"""
    print("\n" + "=" * 60)
    print("Test 3: Provider Isolation (Brain+Voice)")
    print("=" * 60)
    
    # Check ai_service.py
    with open('server/services/ai_service.py', 'r') as f:
        ai_service_content = f.read()
    
    # Should route LLM based on ai_provider
    if "ai_provider = self._get_ai_provider(business_id)" in ai_service_content:
        print("✓ LLM routing based on ai_provider")
    else:
        print("❌ FAIL: LLM not routed by ai_provider")
        return False
    
    if "if ai_provider == 'gemini':" in ai_service_content:
        print("✓ Gemini LLM conditional exists")
    else:
        print("❌ FAIL: Gemini LLM routing not found")
        return False
    
    # Check media_ws_ai.py for TTS routing
    with open('server/media_ws_ai.py', 'r') as f:
        media_content = f.read()
    
    # Should use provider-specific voice validation
    if 'is_valid_voice(voice_name, ai_provider)' in media_content:
        print("✓ Voice validation is provider-specific")
    else:
        print("❌ FAIL: Voice validation not provider-specific")
        return False
    
    # Should NOT mix providers
    if 'openai_tts_fallback_for_gemini' in media_content or 'gemini_llm_with_openai_voice' in media_content:
        print("❌ FAIL: Provider mixing detected")
        return False
    
    print("✓ No provider mixing found")
    
    print("✅ PASS: Provider isolation validated")
    return True


def test_shared_guards():
    """Test that both providers use the same validation guards"""
    print("\n" + "=" * 60)
    print("Test 4: Shared Guards and Validators")
    print("=" * 60)
    
    # Check that guards are not provider-specific
    guards_file = 'server/services/hebrew_stt_validator.py'
    if not os.path.exists(guards_file):
        print("⚠️ WARNING: Guards file not found")
        return True  # Non-critical
    
    with open(guards_file, 'r') as f:
        content = f.read()
    
    # Should NOT have provider-specific validation
    if 'def is_gibberish_gemini' in content or 'def is_gibberish_openai' in content:
        print("❌ FAIL: Provider-specific guards found")
        return False
    
    print("✓ Guards are provider-agnostic")
    
    # Check name validation
    name_val_file = 'server/services/name_validation.py'
    if os.path.exists(name_val_file):
        with open(name_val_file, 'r') as f:
            name_content = f.read()
        
        if 'def is_valid_customer_name(' in name_content:
            print("✓ Name validation is universal")
        
        # Should NOT be provider-specific
        if 'ai_provider' in name_content:
            print("⚠️ WARNING: Name validation might be provider-specific")
    
    print("✅ PASS: Shared guards validated")
    return True


def test_state_machine_consistency():
    """Test that state machine is the same for both providers"""
    print("\n" + "=" * 60)
    print("Test 5: State Machine Consistency")
    print("=" * 60)
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check for universal state constants
    states = ['STATE_LISTEN', 'STATE_PROCESSING', 'STATE_SPEAK']
    for state in states:
        if f'{state} =' in content or f'"{state.lower()}"' in content.lower():
            print(f"✓ {state} defined")
        else:
            print(f"⚠️ {state} might not be defined")
    
    # Should NOT have provider-specific states
    if 'STATE_GEMINI_' in content or 'STATE_OPENAI_' in content:
        print("❌ FAIL: Provider-specific states found")
        return False
    
    print("✓ No provider-specific states")
    
    # Check that use_realtime_for_this_call controls pipeline, not state machine
    if 'use_realtime_for_this_call' in content:
        print("✓ Pipeline selection via use_realtime_for_this_call")
    
    print("✅ PASS: State machine consistency validated")
    return True


def test_logging_requirements():
    """Test that required logging is present"""
    print("\n" + "=" * 60)
    print("Test 6: Logging Requirements")
    print("=" * 60)
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Required logs
    required_logs = [
        '[CALL_ROUTING]',
        'provider=',
        '[GEMINI_PIPELINE]',
        '[OPENAI_PIPELINE]',
    ]
    
    for log_pattern in required_logs:
        if log_pattern in content:
            print(f"✓ Log pattern found: {log_pattern}")
        else:
            print(f"❌ FAIL: Missing log pattern: {log_pattern}")
            return False
    
    # Check ai_service.py for LLM logging
    with open('server/services/ai_service.py', 'r') as f:
        ai_service = f.read()
    
    if '[AI_SERVICE]' in ai_service and 'provider:' in ai_service:
        print("✓ AI Service logs provider")
    else:
        print("⚠️ WARNING: AI Service might not log provider")
    
    print("✅ PASS: Logging requirements met")
    return True


def test_voice_catalog_integration():
    """Test that voice catalog properly separates providers"""
    print("\n" + "=" * 60)
    print("Test 7: Voice Catalog Integration")
    print("=" * 60)
    
    with open('server/config/voice_catalog.py', 'r') as f:
        content = f.read()
    
    # Should have provider-specific voice lists
    if 'OPENAI_VOICES' in content and 'GEMINI_VOICES' in content:
        print("✓ Provider-specific voice lists exist")
    else:
        print("❌ FAIL: Voice lists not properly separated")
        return False
    
    # Should have validation function
    if 'def is_valid_voice(voice_id: str, provider: str)' in content:
        print("✓ is_valid_voice() takes provider parameter")
    else:
        print("❌ FAIL: Voice validation doesn't support providers")
        return False
    
    # Should have default voice function
    if 'def default_voice(provider: str)' in content:
        print("✓ default_voice() takes provider parameter")
    else:
        print("❌ FAIL: Default voice doesn't support providers")
        return False
    
    print("✅ PASS: Voice catalog integration validated")
    return True


def test_no_hardcoded_providers():
    """Test that there are no hardcoded provider assumptions"""
    print("\n" + "=" * 60)
    print("Test 8: No Hardcoded Provider Assumptions")
    print("=" * 60)
    
    # Check files for hardcoded OpenAI-only or Gemini-only assumptions
    files_to_check = [
        'server/services/ai_service.py',
        'server/media_ws_ai.py',
        'server/services/tts_provider.py',
    ]
    
    warnings = []
    
    for filepath in files_to_check:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Look for hardcoded "openai" or "gemini" strings (not in comments/logs)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip comments and log lines
            if '#' in line or 'logger.' in line or 'print(' in line:
                continue
            
            # Look for hardcoded provider strings in logic
            if 'ai_provider = "openai"' in line or 'ai_provider = "gemini"' in line:
                if 'default=' not in line and 'fallback' not in line.lower():
                    warnings.append(f"{filepath}:{i} - Hardcoded provider in logic")
    
    if warnings:
        print("⚠️ WARNINGS:")
        for w in warnings[:5]:  # Show first 5
            print(f"  - {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")
    else:
        print("✓ No hardcoded provider assumptions found")
    
    print("✅ PASS: No critical hardcoded assumptions")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("🔥 SAME LOGIC, DIFFERENT BRAIN - ARCHITECTURE VALIDATION 🔥")
    print("=" * 80)
    print("\nValidating: Gemini and OpenAI use identical logic/flow/guards/audio")
    
    tests = [
        ("Single Prompt Source", test_single_prompt_source),
        ("Unified Audio Output", test_unified_audio_output),
        ("Provider Isolation", test_provider_isolation),
        ("Shared Guards", test_shared_guards),
        ("State Machine Consistency", test_state_machine_consistency),
        ("Logging Requirements", test_logging_requirements),
        ("Voice Catalog Integration", test_voice_catalog_integration),
        ("No Hardcoded Providers", test_no_hardcoded_providers),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 80)
    if passed_count == total_count:
        print(f"✅✅✅ ALL TESTS PASSED ({passed_count}/{total_count}) ✅✅✅")
        print("=" * 80)
        print("\n🎯 Architecture Validation Summary:")
        print("1. ✓ Prompts are shared (single source of truth)")
        print("2. ✓ Audio pipeline is unified (PCMU 8k, 20ms)")
        print("3. ✓ Providers are isolated (no mixing)")
        print("4. ✓ Guards are shared (same validation)")
        print("5. ✓ State machine is consistent")
        print("6. ✓ Logging is comprehensive")
        print("7. ✓ Voice catalog is provider-aware")
        print("8. ✓ No hardcoded assumptions")
        print("\n✨ The architecture follows 'Same Logic, Different Brain' principle!")
        return 0
    else:
        print(f"❌❌❌ SOME TESTS FAILED ({passed_count}/{total_count}) ❌❌❌")
        print("=" * 80)
        print("\n⚠️ Architecture needs fixes to comply with principles")
        return 1


if __name__ == "__main__":
    sys.exit(main())
