#!/usr/bin/env python3
"""
Test script to verify Google Cloud STT authentication fix.

This script verifies that:
1. STT services require GOOGLE_APPLICATION_CREDENTIALS
2. No usage of google.auth.default() or implicit credential discovery
3. Explicit service_account.Credentials usage
"""
import os
import sys
import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_no_google_auth_default_usage():
    """Verify that google.auth.default is not used in STT files"""
    logger.info("Checking for google.auth.default usage...")
    
    result = subprocess.run(
        ["grep", "-r", "google.auth.default", 
         "server/services/gcp_stt_stream.py",
         "server/services/gcp_stt_stream_optimized.py",
         "server/media_ws_ai.py"],
        cwd="/home/runner/work/prosaasil/prosaasil",
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:  # grep returns non-zero when no matches found
        logger.info("✅ PASS: No google.auth.default usage found")
        return True
    else:
        logger.error(f"❌ FAIL: Found google.auth.default usage:\n{result.stdout}")
        return False

def test_explicit_credentials_import():
    """Verify that service_account module is imported"""
    logger.info("Checking for google.oauth2.service_account import...")
    
    result = subprocess.run(
        ["grep", "-r", "from google.oauth2 import service_account", 
         "server/services/gcp_stt_stream.py",
         "server/services/gcp_stt_stream_optimized.py",
         "server/media_ws_ai.py"],
        cwd="/home/runner/work/prosaasil/prosaasil",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:  # grep returns 0 when matches found
        matches = result.stdout.strip().split('\n')
        if len(matches) >= 2:  # Should be in at least 2 files
            logger.info(f"✅ PASS: Found service_account import in {len(matches)} files")
            return True
        else:
            logger.error(f"❌ FAIL: service_account import found in only {len(matches)} file(s)")
            return False
    else:
        logger.error("❌ FAIL: No service_account import found")
        return False

def test_explicit_credentials_usage():
    """Verify that Credentials.from_service_account_file is used"""
    logger.info("Checking for explicit service account file loading...")
    
    result = subprocess.run(
        ["grep", "-r", "Credentials.from_service_account_file", 
         "server/services/gcp_stt_stream.py",
         "server/services/gcp_stt_stream_optimized.py",
         "server/media_ws_ai.py"],
        cwd="/home/runner/work/prosaasil/prosaasil",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:  # grep returns 0 when matches found
        matches = result.stdout.strip().split('\n')
        if len(matches) >= 3:  # Should be in all 3 key locations
            logger.info(f"✅ PASS: Found from_service_account_file usage in {len(matches)} locations")
            return True
        else:
            logger.error(f"❌ FAIL: from_service_account_file found in only {len(matches)} location(s)")
            return False
    else:
        logger.error("❌ FAIL: No from_service_account_file usage found")
        return False

def test_google_application_credentials_usage():
    """Verify that GOOGLE_APPLICATION_CREDENTIALS env var is checked"""
    logger.info("Checking for GOOGLE_APPLICATION_CREDENTIALS usage...")
    
    result = subprocess.run(
        ["grep", "-r", "GOOGLE_APPLICATION_CREDENTIALS", 
         "server/services/gcp_stt_stream.py",
         "server/services/gcp_stt_stream_optimized.py",
         "server/media_ws_ai.py"],
        cwd="/home/runner/work/prosaasil/prosaasil",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:  # grep returns 0 when matches found
        matches = result.stdout.strip().split('\n')
        if len(matches) >= 3:  # Should be in all 3 files
            logger.info(f"✅ PASS: Found GOOGLE_APPLICATION_CREDENTIALS checks in {len(matches)} locations")
            return True
        else:
            logger.error(f"❌ FAIL: GOOGLE_APPLICATION_CREDENTIALS found in only {len(matches)} location(s)")
            return False
    else:
        logger.error("❌ FAIL: No GOOGLE_APPLICATION_CREDENTIALS usage found")
        return False

def test_no_gemini_key_for_stt():
    """Verify that GEMINI_API_KEY is not used for STT authentication in media_ws_ai.py"""
    logger.info("Checking that GEMINI_API_KEY is not used for STT authentication...")
    
    # Check if the old pattern exists (setting GOOGLE_API_KEY from gemini_api_key)
    result = subprocess.run(
        ["grep", "-A", "5", "os.environ\\['GOOGLE_API_KEY'\\]", 
         "server/media_ws_ai.py"],
        cwd="/home/runner/work/prosaasil/prosaasil",
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:  # grep returns non-zero when no matches found
        logger.info("✅ PASS: GEMINI_API_KEY is not used for STT authentication")
        return True
    else:
        logger.error(f"❌ FAIL: Found GEMINI_API_KEY being used for STT:\n{result.stdout}")
        return False

def test_no_deprecated_env_vars():
    """Verify that deprecated env vars are not used"""
    logger.info("Checking for deprecated environment variables...")
    
    deprecated_vars = [
        "GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON",
        "GOOGLE_STT_KEY",
        "GCLOUD_CREDENTIALS"
    ]
    
    all_passed = True
    for var in deprecated_vars:
        result = subprocess.run(
            ["grep", "-r", var, 
             "server/services/gcp_stt_stream.py",
             "server/services/gcp_stt_stream_optimized.py",
             "server/media_ws_ai.py"],
            cwd="/home/runner/work/prosaasil/prosaasil",
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:  # Found the deprecated var
            logger.error(f"❌ FAIL: Found deprecated variable {var}:\n{result.stdout}")
            all_passed = False
    
    if all_passed:
        logger.info("✅ PASS: No deprecated environment variables found")
    
    return all_passed

def main():
    """Run all tests"""
    logger.info("=" * 80)
    logger.info("Google Cloud STT Credentials Fix - Verification Tests")
    logger.info("=" * 80)
    
    tests = [
        ("No google.auth.default usage", test_no_google_auth_default_usage),
        ("Explicit credentials import", test_explicit_credentials_import),
        ("Explicit credentials usage", test_explicit_credentials_usage),
        ("GOOGLE_APPLICATION_CREDENTIALS usage", test_google_application_credentials_usage),
        ("No GEMINI_API_KEY for STT", test_no_gemini_key_for_stt),
        ("No deprecated env vars", test_no_deprecated_env_vars),
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
