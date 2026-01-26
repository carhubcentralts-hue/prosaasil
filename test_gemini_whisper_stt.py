#!/usr/bin/env python3
"""
Test to verify that Gemini provider uses Whisper STT instead of Google Cloud STT.

This test ensures that:
1. Gemini provider routes to Whisper STT
2. No Google Cloud STT client is used for Gemini
3. Code references Whisper API instead of Google Cloud Speech-to-Text
"""
import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gemini_uses_whisper():
    """Verify that Gemini provider documentation mentions Whisper STT"""
    logger.info("Checking Gemini provider uses Whisper STT...")
    
    result = subprocess.run(
        ["grep", "-A", "5", "🔷 Gemini Provider", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    if "Whisper" in result.stdout:
        logger.info("✅ PASS: Gemini provider documentation mentions Whisper")
        return True
    else:
        logger.error("❌ FAIL: Gemini provider documentation does not mention Whisper")
        logger.error(f"Found: {result.stdout}")
        return False

def test_no_google_stt_for_gemini():
    """Verify that _google_stt_batch is not called for Gemini"""
    logger.info("Checking that _google_stt_batch is not called for Gemini...")
    
    # Check that _hebrew_stt doesn't call _google_stt_batch
    result = subprocess.run(
        ["grep", "-A", "100", "def _hebrew_stt", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    # Look for the section and check it doesn't have _google_stt_batch
    if "_google_stt_batch" not in result.stdout:
        logger.info("✅ PASS: _hebrew_stt does not call _google_stt_batch")
        return True
    else:
        logger.error("❌ FAIL: _hebrew_stt still calls _google_stt_batch")
        return False

def test_whisper_stt_for_gemini_exists():
    """Verify that _whisper_stt_for_gemini method exists"""
    logger.info("Checking for _whisper_stt_for_gemini method...")
    
    result = subprocess.run(
        ["grep", "def _whisper_stt_for_gemini", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("✅ PASS: _whisper_stt_for_gemini method exists")
        return True
    else:
        logger.error("❌ FAIL: _whisper_stt_for_gemini method not found")
        return False

def test_hebrew_stt_calls_whisper():
    """Verify that _hebrew_stt calls _whisper_stt_for_gemini"""
    logger.info("Checking that _hebrew_stt calls _whisper_stt_for_gemini...")
    
    result = subprocess.run(
        ["grep", "-A", "100", "def _hebrew_stt", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    if "_whisper_stt_for_gemini" in result.stdout:
        logger.info("✅ PASS: _hebrew_stt calls _whisper_stt_for_gemini")
        return True
    else:
        logger.error("❌ FAIL: _hebrew_stt does not call _whisper_stt_for_gemini")
        return False

def test_openai_client_check():
    """Verify that OpenAI client is checked for Gemini STT"""
    logger.info("Checking for OpenAI client usage in Gemini STT...")
    
    result = subprocess.run(
        ["grep", "-A", "100", "def _hebrew_stt", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    if "get_openai_client" in result.stdout:
        logger.info("✅ PASS: OpenAI client is used for Gemini STT")
        return True
    else:
        logger.error("❌ FAIL: OpenAI client not found in Gemini STT path")
        return False

def test_no_gemini_key_for_stt():
    """Verify that GEMINI_API_KEY is not used for STT in _hebrew_stt"""
    logger.info("Checking that GEMINI_API_KEY is not used for STT...")
    
    result = subprocess.run(
        ["grep", "-A", "100", "def _hebrew_stt", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    # Should not use get_gemini_api_key for STT
    if "get_gemini_api_key" not in result.stdout:
        logger.info("✅ PASS: GEMINI_API_KEY is not used for STT")
        return True
    else:
        logger.error("❌ FAIL: GEMINI_API_KEY is still used for STT")
        return False

def test_whisper_api_used():
    """Verify that Whisper API is called in _whisper_stt_for_gemini"""
    logger.info("Checking that Whisper API is used...")
    
    result = subprocess.run(
        ["grep", "-A", "50", "def _whisper_stt_for_gemini", "server/media_ws_ai.py"],
        capture_output=True,
        text=True
    )
    
    if "audio.transcriptions.create" in result.stdout and "whisper-1" in result.stdout:
        logger.info("✅ PASS: Whisper API is properly called")
        return True
    else:
        logger.error("❌ FAIL: Whisper API call not found or incorrect")
        return False

def main():
    """Run all tests"""
    logger.info("=" * 80)
    logger.info("Gemini Whisper STT Integration - Verification Tests")
    logger.info("=" * 80)
    
    tests = [
        ("Gemini uses Whisper", test_gemini_uses_whisper),
        ("No Google STT for Gemini", test_no_google_stt_for_gemini),
        ("_whisper_stt_for_gemini exists", test_whisper_stt_for_gemini_exists),
        ("_hebrew_stt calls Whisper", test_hebrew_stt_calls_whisper),
        ("OpenAI client check", test_openai_client_check),
        ("No GEMINI_KEY for STT", test_no_gemini_key_for_stt),
        ("Whisper API used", test_whisper_api_used),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info("\n" + "-" * 80)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Summary:")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 80)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 80)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
