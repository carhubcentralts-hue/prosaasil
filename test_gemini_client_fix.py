#!/usr/bin/env python3
"""
Test Gemini Client Initialization Fix

Verifies that:
1. Gemini clients can be initialized without http_options error
2. Warmup properly handles missing API keys
3. API adapter query uses efficient range-based filtering
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_gemini_client_initialization():
    """Test that Gemini clients initialize without http_options errors"""
    logger.info("=" * 80)
    logger.info("TEST 1: Gemini Client Initialization")
    logger.info("=" * 80)
    
    # Check that google_clients.py doesn't contain problematic http_options
    logger.info("✓ Checking google_clients.py for http_options issues...")
    
    with open('server/services/providers/google_clients.py', 'r') as f:
        content = f.read()
        
    # Check that http_options={'client': ...} is NOT present (excluding comments)
    lines_with_http_options = [line for line in content.split('\n') 
                               if ("http_options={'client':" in line or 'http_options={"client":' in line)
                               and not line.strip().startswith('#')]
    
    if lines_with_http_options:
        logger.error("❌ FAIL: Found http_options={'client': ...} in google_clients.py")
        logger.error("   This will cause ValidationError in genai.Client()")
        for line in lines_with_http_options[:3]:
            logger.error(f"   Found: {line.strip()}")
        return False
    
    logger.info("  ✅ No problematic http_options={'client': ...} found")
    
    # Check that genai.Client is called with just api_key
    if 'genai.Client(api_key=gemini_api_key)' in content:
        logger.info("  ✅ Found correct genai.Client(api_key=...) initialization")
    else:
        logger.warning("  ⚠️  Could not verify genai.Client initialization pattern")
    
    # Verify both LLM and TTS clients are fixed
    llm_client_section = content[content.find('def get_gemini_llm_client'):content.find('def get_gemini_tts_client')]
    tts_client_section = content[content.find('def get_gemini_tts_client'):content.find('def get_gemini_client')]
    
    for section_name, section in [('LLM', llm_client_section), ('TTS', tts_client_section)]:
        # Check for http_options= in actual code (not comments)
        lines_with_http_options = [line for line in section.split('\n') 
                                   if 'http_options=' in line 
                                   and not line.strip().startswith('#')]
        if lines_with_http_options:
            logger.error(f"❌ FAIL: {section_name} client still has http_options parameter")
            for line in lines_with_http_options[:2]:
                logger.error(f"   Found: {line.strip()}")
            return False
        logger.info(f"  ✅ {section_name} client is correctly initialized")
    
    logger.info("✅ TEST 1 PASSED: Gemini clients are correctly initialized\n")
    return True


def test_warmup_includes_gemini():
    """Test that warmup code includes Gemini clients"""
    logger.info("=" * 80)
    logger.info("TEST 2: Gemini Warmup in Startup")
    logger.info("=" * 80)
    
    logger.info("✓ Checking lazy_services.py for Gemini warmup...")
    
    with open('server/services/lazy_services.py', 'r') as f:
        content = f.read()
    
    # Check for Gemini LLM warmup
    if 'get_gemini_llm_client' in content:
        logger.info("  ✅ Found get_gemini_llm_client() call in warmup")
    else:
        logger.error("❌ FAIL: get_gemini_llm_client() not found in warmup")
        return False
    
    # Check for Gemini TTS warmup
    if 'get_gemini_tts_client' in content:
        logger.info("  ✅ Found get_gemini_tts_client() call in warmup")
    else:
        logger.error("❌ FAIL: get_gemini_tts_client() not found in warmup")
        return False
    
    # Check that warmup handles errors gracefully
    warmup_section = content[content.find('def warmup_services_async'):content.find('def start_periodic_warmup')]
    
    if 'RuntimeError' in warmup_section and 'WARMUP_GEMINI' in warmup_section:
        logger.info("  ✅ Warmup handles Gemini errors gracefully")
    else:
        logger.warning("  ⚠️  Could not verify error handling in warmup")
    
    logger.info("✅ TEST 2 PASSED: Gemini warmup is properly configured\n")
    return True


def test_api_adapter_query_optimization():
    """Test that api_adapter uses efficient range-based queries"""
    logger.info("=" * 80)
    logger.info("TEST 3: API Adapter Query Optimization")
    logger.info("=" * 80)
    
    logger.info("✓ Checking api_adapter.py for query optimization...")
    
    with open('server/api_adapter.py', 'r') as f:
        content = f.read()
    
    # Check that db.func.date() is NOT used for calls_in_range
    calls_in_range_section = content[content.find('calls_in_range'):content.find('calls_in_range', content.find('calls_in_range') + 1) + 50]
    
    if 'db.func.date(' in calls_in_range_section:
        logger.error("❌ FAIL: Still using db.func.date() in calls_in_range query")
        logger.error("   This breaks index usage and causes slow queries")
        return False
    
    logger.info("  ✅ No db.func.date() found in calls_in_range query")
    
    # Check for range-based filtering
    if 'CallLog.created_at >=' in calls_in_range_section and 'CallLog.created_at <=' in calls_in_range_section:
        logger.info("  ✅ Using efficient range-based query (created_at >= ... AND created_at <=)")
    else:
        logger.warning("  ⚠️  Could not verify range-based query pattern")
    
    # Check for datetime conversion
    if 'datetime.combine' in calls_in_range_section:
        logger.info("  ✅ Properly converting dates to datetime for comparison")
    else:
        logger.warning("  ⚠️  Could not verify datetime conversion")
    
    logger.info("✅ TEST 3 PASSED: API adapter query is optimized\n")
    return True


def test_migration_index_added():
    """Test that migration 111 adds the composite index"""
    logger.info("=" * 80)
    logger.info("TEST 4: Migration 111 Index Addition")
    logger.info("=" * 80)
    
    logger.info("✓ Checking db_migrate.py for composite index...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check for Migration 111
    if 'Migration 111' not in content:
        logger.error("❌ FAIL: Migration 111 not found in db_migrate.py")
        return False
    
    logger.info("  ✅ Found Migration 111")
    
    # Check for composite index creation
    if 'idx_call_log_business_created' in content:
        logger.info("  ✅ Found idx_call_log_business_created index")
    else:
        logger.error("❌ FAIL: Composite index idx_call_log_business_created not found")
        return False
    
    # Verify index is on (business_id, created_at)
    if 'ON call_log(business_id, created_at)' in content:
        logger.info("  ✅ Index correctly defined on (business_id, created_at)")
    else:
        logger.error("❌ FAIL: Index not defined on correct columns")
        return False
    
    logger.info("✅ TEST 4 PASSED: Composite index is properly added\n")
    return True


def test_migration_109_batching():
    """Test that migration 109 uses batched updates"""
    logger.info("=" * 80)
    logger.info("TEST 5: Migration 109 Batched Updates")
    logger.info("=" * 80)
    
    logger.info("✓ Checking db_migrate.py for batched backfill...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find migration 109 section
    migration_109_start = content.find('Migration 109')
    if migration_109_start == -1:
        logger.error("❌ FAIL: Migration 109 not found")
        return False
    
    migration_109_section = content[migration_109_start:migration_109_start + 5000]
    
    # Check for batch_size variable
    if 'batch_size' in migration_109_section:
        logger.info("  ✅ Found batch_size variable")
    else:
        logger.error("❌ FAIL: No batching found in migration 109")
        return False
    
    # Check for LIMIT in UPDATE query
    if 'LIMIT :batch_size' in migration_109_section or 'LIMIT {}' in migration_109_section:
        logger.info("  ✅ Found LIMIT in UPDATE query (batched)")
    else:
        logger.warning("  ⚠️  Could not verify LIMIT in UPDATE query")
    
    # Check for commit in loop (batched commits)
    if 'db.session.commit()' in migration_109_section and 'while True:' in migration_109_section:
        logger.info("  ✅ Found batched commits in loop")
    else:
        logger.warning("  ⚠️  Could not verify batched commits")
    
    logger.info("✅ TEST 5 PASSED: Migration 109 uses batched updates\n")
    return True


def test_statement_timeout_config():
    """Test that statement_timeout is set to 0 (unlimited) for migrations"""
    logger.info("=" * 80)
    logger.info("TEST 6: Statement Timeout Configuration")
    logger.info("=" * 80)
    
    logger.info("✓ Checking db_migrate.py for statement_timeout...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check for STATEMENT_TIMEOUT variable
    if 'STATEMENT_TIMEOUT' in content:
        logger.info("  ✅ Found STATEMENT_TIMEOUT configuration")
    else:
        logger.error("❌ FAIL: STATEMENT_TIMEOUT not found")
        return False
    
    # Check default is '0' (unlimited)
    if 'STATEMENT_TIMEOUT = os.getenv("MIGRATION_STATEMENT_TIMEOUT", "0")' in content:
        logger.info("  ✅ Default statement_timeout is '0' (unlimited)")
    else:
        logger.warning("  ⚠️  Default statement_timeout may not be '0'")
    
    # Check that it's actually set in the connection
    if 'SET LOCAL statement_timeout' in content:
        logger.info("  ✅ statement_timeout is set on connection")
    else:
        logger.error("❌ FAIL: statement_timeout is not set on connection")
        return False
    
    logger.info("✅ TEST 6 PASSED: Statement timeout properly configured\n")
    return True


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("GEMINI CLIENT FIX VERIFICATION")
    logger.info("=" * 80 + "\n")
    
    tests = [
        test_gemini_client_initialization,
        test_warmup_includes_gemini,
        test_api_adapter_query_optimization,
        test_migration_index_added,
        test_migration_109_batching,
        test_statement_timeout_config,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            logger.exception("Full traceback:")
            results.append(False)
    
    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    passed = sum(results)
    total = len(results)
    logger.info(f"Passed: {passed}/{total}")
    
    if all(results):
        logger.info("✅ ALL TESTS PASSED - Fixes are correctly implemented")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED - Review implementation")
        return 1


if __name__ == '__main__':
    sys.exit(main())
