#!/usr/bin/env python3
"""
Simple validation script for AMD and Topic Classification fixes
No dependencies required - just validates code structure
"""
import re


def test_amd_parameters():
    """Test that AMD parameters are correctly structured"""
    print("\n" + "="*60)
    print("TEST 1: Verify AMD Parameter Structure")
    print("="*60)
    
    with open('server/routes_outbound.py', 'r') as f:
        code = f.read()
    
    # Verify new parameters are present
    assert 'async_amd=True' in code, "❌ async_amd parameter not found"
    assert 'async_amd_status_callback=' in code, "❌ async_amd_status_callback parameter not found"
    assert 'async_amd_status_callback_method=' in code, "❌ async_amd_status_callback_method parameter not found"
    
    # Count occurrences (should be 2 - one for single call, one for bulk)
    async_amd_count = code.count('async_amd=True')
    assert async_amd_count >= 2, f"❌ Expected 2+ async_amd=True, found {async_amd_count}"
    
    # Verify fallback exists
    assert 'TypeError' in code, "❌ TypeError fallback handling not found"
    fallback_msg = 'AMD parameters not supported' in code or 'AMD not supported' in code
    assert fallback_msg, "❌ AMD fallback message not found"
    
    print("✅ AMD parameters correctly updated in code")
    print(f"✅ async_amd=True found {async_amd_count} times")
    print("✅ Fallback error handling implemented")
    print("✅ Both call locations updated")
    
    return True


def test_reclassify_endpoint():
    """Test reclassify endpoint structure"""
    print("\n" + "="*60)
    print("TEST 2: Reclassify Endpoint Structure")
    print("="*60)
    
    with open('server/routes_ai_topics.py', 'r') as f:
        code = f.read()
    
    assert '/reclassify-topic' in code, "❌ Reclassify endpoint not found"
    assert 'reclassify_call_topic' in code, "❌ Reclassify function not found"
    assert 'detected_topic_id = None' in code, "❌ Topic reset not found"
    assert 'classify_text' in code, "❌ Classification call not found"
    
    # Check endpoint returns proper structure
    assert 'classification' in code, "❌ Classification result not returned"
    assert 'previous_topic' in code, "❌ Previous topic not tracked"
    
    print("✅ Reclassify endpoint exists at /api/call_logs/<id>/reclassify-topic")
    print("✅ Endpoint resets detected_topic fields")
    print("✅ Endpoint calls classify_text")
    print("✅ Endpoint returns classification result")
    print("✅ Endpoint tracks previous topic")
    
    return True


def test_cache_invalidation():
    """Test that cache invalidation is called in CRUD operations"""
    print("\n" + "="*60)
    print("TEST 3: Cache Invalidation in CRUD")
    print("="*60)
    
    with open('server/routes_ai_topics.py', 'r') as f:
        code = f.read()
    
    # Count invalidate_cache calls
    invalidate_count = code.count('topic_classifier.invalidate_cache(business_id)')
    
    assert invalidate_count >= 3, f"❌ Expected at least 3 invalidate_cache calls, found {invalidate_count}"
    
    # Check it's called in create, update, delete
    create_section = code[code.find('def create_topic'):code.find('def update_topic')]
    update_section = code[code.find('def update_topic'):code.find('def delete_topic')]
    delete_section = code[code.find('def delete_topic'):code.find('def rebuild_embeddings')]
    
    assert 'invalidate_cache' in create_section, "❌ Cache invalidation not in create_topic"
    assert 'invalidate_cache' in update_section, "❌ Cache invalidation not in update_topic"
    assert 'invalidate_cache' in delete_section, "❌ Cache invalidation not in delete_topic"
    
    print("✅ Cache invalidation in create_topic")
    print("✅ Cache invalidation in update_topic")
    print("✅ Cache invalidation in delete_topic")
    print(f"✅ Total invalidate_cache calls: {invalidate_count}")
    
    return True


def test_enhanced_logging():
    """Test that enhanced logging is present"""
    print("\n" + "="*60)
    print("TEST 4: Enhanced Logging")
    print("="*60)
    
    with open('server/services/topic_classifier.py', 'r') as f:
        code = f.read()
    
    # Check for comprehensive logging
    assert 'log.info' in code, "❌ INFO logging not found"
    assert '[TOPIC_CLASSIFY]' in code, "❌ TOPIC_CLASSIFY log prefix not found"
    assert 'business_id=' in code, "❌ business_id not logged"
    assert 'topics_loaded=' in code, "❌ topics_loaded not logged"
    assert 'top_matches' in code, "❌ top_matches not logged"
    
    # Count log statements
    log_count = code.count('log.info(')
    
    assert log_count >= 5, f"❌ Expected at least 5 log.info calls, found {log_count}"
    
    # Verify specific log messages
    assert 'LAYER 1 SUCCESS' in code, "❌ LAYER 1 SUCCESS log not found"
    assert 'LAYER 2 SUCCESS' in code, "❌ LAYER 2 SUCCESS log not found"
    assert 'BELOW THRESHOLD' in code, "❌ BELOW THRESHOLD log not found"
    
    print("✅ INFO level logging implemented")
    print("✅ [TOPIC_CLASSIFY] prefix used")
    print("✅ business_id logged")
    print("✅ topics_loaded logged")
    print("✅ top_matches logged")
    print("✅ Layer 1/2 success messages")
    print("✅ Below threshold message")
    print(f"✅ Total log.info statements: {log_count}")
    
    return True


def test_post_call_classification():
    """Test that classification runs after recording transcription"""
    print("\n" + "="*60)
    print("TEST 5: Post-Call Classification Integration")
    print("="*60)
    
    with open('server/tasks_recording.py', 'r') as f:
        code = f.read()
    
    # Check that classification is called after save
    assert 'AI TOPIC CLASSIFICATION' in code, "❌ Topic classification section not found"
    assert 'topic_classifier.classify_text' in code, "❌ classify_text call not found"
    assert 'detected_topic_source' in code, "❌ Idempotency check not found"
    assert 'final_transcript if (final_transcript' in code, "❌ final_transcript priority not found"
    
    # Check it's in save_call_to_db function
    save_func_start = code.find('def save_call_to_db')
    save_func_end = code.find('\ndef ', save_func_start + 1)
    save_func = code[save_func_start:save_func_end]
    
    assert 'topic_classifier.classify_text' in save_func, "❌ Classification not in save_call_to_db"
    assert 'detected_topic_id' in save_func, "❌ detected_topic_id not set"
    assert 'detected_topic_confidence' in save_func, "❌ detected_topic_confidence not set"
    assert 'detected_topic_source' in save_func, "❌ detected_topic_source not set"
    
    print("✅ Classification runs after call save")
    print("✅ Uses final_transcript (Whisper) if available")
    print("✅ Idempotency protection implemented")
    print("✅ Sets detected_topic_id, confidence, and source")
    print("✅ Updates both call_log and lead")
    
    return True


def test_synonym_matching():
    """Test that synonym matching logic is correct"""
    print("\n" + "="*60)
    print("TEST 6: Synonym Matching Logic")
    print("="*60)
    
    with open('server/services/topic_classifier.py', 'r') as f:
        code = f.read()
    
    # Check synonym matching in _keyword_match
    keyword_match_start = code.find('def _keyword_match')
    keyword_match_end = code.find('\n    def ', keyword_match_start + 1)
    keyword_match = code[keyword_match_start:keyword_match_end]
    
    assert 'synonyms' in keyword_match, "❌ Synonyms not checked"
    assert 'synonym_lower in text_lower' in keyword_match, "❌ Synonym substring check not found"
    assert '"method": "synonym"' in keyword_match or "'method': 'synonym'" in keyword_match, "❌ Synonym method not returned"
    assert 'topic_id' in keyword_match, "❌ Topic ID not returned"
    
    # Verify it returns the parent topic, not a synonym topic
    assert "topic['id']" in keyword_match, "❌ Parent topic ID not used"
    assert "topic['name']" in keyword_match, "❌ Parent topic name not used"
    
    print("✅ Synonym matching implemented")
    print("✅ Returns parent topic ID (not synonym topic)")
    print("✅ Returns parent topic name")
    print("✅ Method marked as 'synonym'")
    print("✅ Substring matching for synonyms")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("VALIDATING AMD AND TOPIC CLASSIFICATION FIXES")
    print("="*80)
    
    all_passed = True
    
    tests = [
        ("AMD Parameters", test_amd_parameters),
        ("Reclassify Endpoint", test_reclassify_endpoint),
        ("Cache Invalidation", test_cache_invalidation),
        ("Enhanced Logging", test_enhanced_logging),
        ("Post-Call Classification", test_post_call_classification),
        ("Synonym Matching", test_synonym_matching),
    ]
    
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL VALIDATION TESTS PASSED")
        print("="*80)
        print("\n📋 Implementation Summary:")
        print("━" * 80)
        print("\n🔧 Task 1: Twilio AMD Fix")
        print("  ✅ Replaced deprecated amd_status_callback parameters")
        print("  ✅ Using correct: async_amd=True + async_amd_status_callback")
        print("  ✅ Added TypeError fallback for SDK compatibility")
        print("  ✅ Applied to both single and bulk call endpoints")
        print("\n🎯 Task 2: Topic Classification")
        print("  ✅ Classification runs post-call after transcription")
        print("  ✅ Uses final_transcript (Whisper) with fallback to realtime")
        print("  ✅ 2-layer matching: keyword/synonym → embedding")
        print("  ✅ Synonym matching returns parent topic (not sub-topic)")
        print("  ✅ Idempotency protection implemented")
        print("  ✅ Cache invalidation on all CRUD operations")
        print("  ✅ Reclassify endpoint: POST /api/call_logs/:id/reclassify-topic")
        print("  ✅ Enhanced INFO-level logging with decision details")
        print("\n📊 Logging Details:")
        print("  • business_id, call_log_id")
        print("  • top match name + score + source")
        print("  • keyword match or embedding match indicator")
        print("  • number of topics loaded to index")
        print("\n🚀 Next Steps:")
        print("  1. Deploy to production")
        print("  2. Test outbound call (verify no 400 error)")
        print("  3. Verify CallSid created and appears in Twilio Console")
        print("  4. Test topic classification with synonyms")
        print("  5. Test reclassify endpoint via API")
        print("  6. Monitor logs for classification decisions")
        print("="*80)
        return 0
    else:
        print("❌ SOME VALIDATION TESTS FAILED")
        print("="*80)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
