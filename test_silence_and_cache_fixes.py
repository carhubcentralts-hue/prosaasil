#!/usr/bin/env python3
"""
Test script for verifying silence handler and prompt cache fixes

Tests:
1. Prompt cache correctly separates inbound/outbound by direction
2. Cache key includes direction in the format business_id:direction
3. Cache invalidate works with and without direction
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_prompt_cache_direction_separation():
    """Test that prompt cache properly separates by direction"""
    print("\n" + "="*80)
    print("🔵 TEST 1: PROMPT CACHE DIRECTION SEPARATION")
    print("="*80)
    
    from server.services.prompt_cache import get_prompt_cache
    
    cache = get_prompt_cache()
    cache.clear()  # Start fresh
    
    # Test 1a: Set inbound prompt
    print("\n📋 Test 1a: Setting INBOUND prompt for business 1...")
    cache.set(
        business_id=1,
        system_prompt="This is INBOUND prompt for business 1",
        greeting_text="Hello inbound",
        direction="inbound"
    )
    
    # Test 1b: Set outbound prompt for same business
    print("📋 Test 1b: Setting OUTBOUND prompt for business 1...")
    cache.set(
        business_id=1,
        system_prompt="This is OUTBOUND prompt for business 1",
        greeting_text="Hello outbound",
        direction="outbound"
    )
    
    # Test 1c: Retrieve inbound prompt
    print("\n📋 Test 1c: Retrieving INBOUND prompt...")
    inbound_cached = cache.get(business_id=1, direction="inbound")
    if inbound_cached:
        print(f"  ✅ Got inbound prompt: {inbound_cached.system_prompt[:40]}...")
        print(f"  ✅ Direction field: {inbound_cached.direction}")
        inbound_correct = (
            "INBOUND" in inbound_cached.system_prompt and
            inbound_cached.direction == "inbound"
        )
    else:
        print("  ❌ Failed to retrieve inbound prompt")
        inbound_correct = False
    
    # Test 1d: Retrieve outbound prompt
    print("\n📋 Test 1d: Retrieving OUTBOUND prompt...")
    outbound_cached = cache.get(business_id=1, direction="outbound")
    if outbound_cached:
        print(f"  ✅ Got outbound prompt: {outbound_cached.system_prompt[:40]}...")
        print(f"  ✅ Direction field: {outbound_cached.direction}")
        outbound_correct = (
            "OUTBOUND" in outbound_cached.system_prompt and
            outbound_cached.direction == "outbound"
        )
    else:
        print("  ❌ Failed to retrieve outbound prompt")
        outbound_correct = False
    
    # Test 1e: Verify they are different
    print("\n📋 Test 1e: Verifying prompts are separate...")
    if inbound_cached and outbound_cached:
        different = inbound_cached.system_prompt != outbound_cached.system_prompt
        if different:
            print("  ✅ Inbound and outbound prompts are DIFFERENT (correct!)")
        else:
            print("  ❌ Inbound and outbound prompts are the SAME (wrong!)")
    else:
        print("  ❌ Could not compare - one or both prompts missing")
        different = False
    
    all_passed = inbound_correct and outbound_correct and different
    
    print("\n" + "="*80)
    print(f"TEST 1 RESULT: {'✅ PASS' if all_passed else '❌ FAIL'}")
    print("="*80)
    
    return all_passed


def test_cache_invalidate():
    """Test cache invalidation with and without direction"""
    print("\n" + "="*80)
    print("🗑️  TEST 2: CACHE INVALIDATION")
    print("="*80)
    
    from server.services.prompt_cache import get_prompt_cache
    
    cache = get_prompt_cache()
    cache.clear()  # Start fresh
    
    # Setup: Add both inbound and outbound prompts
    print("\n📋 Setup: Adding both inbound and outbound prompts for business 2...")
    cache.set(
        business_id=2,
        system_prompt="Inbound prompt for business 2",
        greeting_text="Hello",
        direction="inbound"
    )
    cache.set(
        business_id=2,
        system_prompt="Outbound prompt for business 2",
        greeting_text="Hello",
        direction="outbound"
    )
    
    # Test 2a: Invalidate only inbound
    print("\n📋 Test 2a: Invalidating INBOUND only...")
    cache.invalidate(business_id=2, direction="inbound")
    
    inbound_after_invalidate = cache.get(business_id=2, direction="inbound")
    outbound_after_invalidate = cache.get(business_id=2, direction="outbound")
    
    inbound_gone = inbound_after_invalidate is None
    outbound_still_there = outbound_after_invalidate is not None
    
    if inbound_gone:
        print("  ✅ Inbound cache entry removed")
    else:
        print("  ❌ Inbound cache entry still present")
    
    if outbound_still_there:
        print("  ✅ Outbound cache entry still present (correct!)")
    else:
        print("  ❌ Outbound cache entry was also removed (wrong!)")
    
    # Test 2b: Re-add inbound, then invalidate both
    print("\n📋 Test 2b: Re-adding inbound, then invalidating BOTH...")
    cache.set(
        business_id=2,
        system_prompt="Inbound prompt for business 2",
        greeting_text="Hello",
        direction="inbound"
    )
    
    # Invalidate without direction should clear both
    cache.invalidate(business_id=2)
    
    inbound_after = cache.get(business_id=2, direction="inbound")
    outbound_after = cache.get(business_id=2, direction="outbound")
    
    both_gone = (inbound_after is None) and (outbound_after is None)
    
    if both_gone:
        print("  ✅ Both inbound and outbound removed (correct!)")
    else:
        print("  ❌ Some entries still present after invalidating both")
    
    all_passed = inbound_gone and outbound_still_there and both_gone
    
    print("\n" + "="*80)
    print(f"TEST 2 RESULT: {'✅ PASS' if all_passed else '❌ FAIL'}")
    print("="*80)
    
    return all_passed


def test_cache_key_format():
    """Test that cache keys are in the correct format"""
    print("\n" + "="*80)
    print("🔑 TEST 3: CACHE KEY FORMAT")
    print("="*80)
    
    from server.services.prompt_cache import PromptCache
    
    cache = PromptCache()
    
    # Test _make_cache_key method
    print("\n📋 Testing cache key format...")
    
    key1 = cache._make_cache_key(123, "inbound")
    key2 = cache._make_cache_key(123, "outbound")
    key3 = cache._make_cache_key(456, "inbound")
    
    expected_format = key1 == "123:inbound"
    different_directions = key1 != key2
    different_businesses = key1 != key3
    
    print(f"  Key for business 123, inbound: {key1}")
    print(f"  Key for business 123, outbound: {key2}")
    print(f"  Key for business 456, inbound: {key3}")
    
    if expected_format:
        print("  ✅ Key format is correct (business_id:direction)")
    else:
        print(f"  ❌ Key format is wrong, expected '123:inbound', got '{key1}'")
    
    if different_directions:
        print("  ✅ Different directions produce different keys")
    else:
        print("  ❌ Different directions produce the same key")
    
    if different_businesses:
        print("  ✅ Different businesses produce different keys")
    else:
        print("  ❌ Different businesses produce the same key")
    
    all_passed = expected_format and different_directions and different_businesses
    
    print("\n" + "="*80)
    print(f"TEST 3 RESULT: {'✅ PASS' if all_passed else '❌ FAIL'}")
    print("="*80)
    
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 SILENCE HANDLER AND CACHE FIX TEST SUITE")
    print("="*80)
    
    results = []
    
    # Test 1: Direction separation
    try:
        result = test_prompt_cache_direction_separation()
        results.append(("Prompt Cache Direction Separation", result))
    except Exception as e:
        print(f"\n❌ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Prompt Cache Direction Separation", False))
    
    # Test 2: Cache invalidation
    try:
        result = test_cache_invalidate()
        results.append(("Cache Invalidation", result))
    except Exception as e:
        print(f"\n❌ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Cache Invalidation", False))
    
    # Test 3: Cache key format
    try:
        result = test_cache_key_format()
        results.append(("Cache Key Format", result))
    except Exception as e:
        print(f"\n❌ Test 3 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Cache Key Format", False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
