"""
Test for business_settings_cache.py
Verifies caching behavior, TTL expiration, invalidation, and LRU eviction.
"""
import time
from server.services.business_settings_cache import (
    BusinessSettingsCache, 
    get_business_settings_cache,
    CACHE_TTL_SECONDS,
    MAX_CACHE_SIZE
)


def test_cache_hit_and_miss():
    """Test basic cache hit and miss behavior"""
    cache = BusinessSettingsCache()
    
    # Test cache miss
    result = cache.get(business_id=1)
    assert result is None, "Cache should miss for non-existent entry"
    
    # Set cache entry
    business_data = {"id": 1, "name": "Test Business"}
    settings_data = {"tenant_id": 1, "ai_prompt": "Test prompt"}
    cache.set(1, business_data, settings_data)
    
    # Test cache hit
    result = cache.get(business_id=1)
    assert result is not None, "Cache should hit for existing entry"
    assert result[0] == business_data, "Business data should match"
    assert result[1] == settings_data, "Settings data should match"
    
    print("✅ Cache hit/miss test passed")


def test_cache_ttl_expiration():
    """Test that cache entries expire after TTL"""
    cache = BusinessSettingsCache()
    
    # Mock short TTL for testing
    import server.services.business_settings_cache as cache_module
    original_ttl = cache_module.CACHE_TTL_SECONDS
    cache_module.CACHE_TTL_SECONDS = 1  # 1 second TTL
    
    try:
        business_data = {"id": 1, "name": "Test Business"}
        cache.set(1, business_data, None)
        
        # Should hit immediately
        result = cache.get(business_id=1)
        assert result is not None, "Cache should hit immediately"
        
        # Wait for expiration
        time.sleep(1.2)
        
        # Should miss after expiration
        result = cache.get(business_id=1)
        assert result is None, "Cache should miss after TTL expiration"
        
        print("✅ TTL expiration test passed")
    finally:
        # Restore original TTL
        cache_module.CACHE_TTL_SECONDS = original_ttl


def test_cache_invalidation():
    """Test explicit cache invalidation"""
    cache = BusinessSettingsCache()
    
    business_data = {"id": 1, "name": "Test Business"}
    cache.set(1, business_data, None)
    
    # Verify cache hit
    result = cache.get(business_id=1)
    assert result is not None, "Cache should hit before invalidation"
    
    # Invalidate
    cache.invalidate(business_id=1)
    
    # Verify cache miss after invalidation
    result = cache.get(business_id=1)
    assert result is None, "Cache should miss after invalidation"
    
    print("✅ Cache invalidation test passed")


def test_cache_clear():
    """Test clearing entire cache"""
    cache = BusinessSettingsCache()
    
    # Add multiple entries
    for i in range(5):
        business_data = {"id": i, "name": f"Business {i}"}
        cache.set(i, business_data, None)
    
    # Verify all exist
    stats = cache.stats()
    assert stats['total_entries'] == 5, "Should have 5 entries"
    
    # Clear cache
    cache.clear()
    
    # Verify all cleared
    stats = cache.stats()
    assert stats['total_entries'] == 0, "Cache should be empty after clear"
    
    # Verify no hits
    for i in range(5):
        result = cache.get(business_id=i)
        assert result is None, f"Cache should miss for business_id={i}"
    
    print("✅ Cache clear test passed")


def test_lru_eviction():
    """Test LRU eviction when cache reaches max size"""
    cache = BusinessSettingsCache()
    
    # Mock small cache size for testing
    import server.services.business_settings_cache as cache_module
    original_max = cache_module.MAX_CACHE_SIZE
    cache_module.MAX_CACHE_SIZE = 5  # Small cache for testing
    
    try:
        # Fill cache to max
        for i in range(5):
            business_data = {"id": i, "name": f"Business {i}"}
            cache.set(i, business_data, None)
            time.sleep(0.01)  # Small delay to ensure different access times
        
        stats = cache.stats()
        assert stats['total_entries'] == 5, "Cache should be at max size"
        
        # Access entry 0 to make it most recently used
        cache.get(business_id=0)
        time.sleep(0.01)
        
        # Access entry 1 to make it second most recently used
        cache.get(business_id=1)
        time.sleep(0.01)
        
        # Add new entry (should evict least recently used, which is entry 2)
        business_data = {"id": 10, "name": "Business 10"}
        cache.set(10, business_data, None)
        
        # Verify entry 10 exists
        result = cache.get(business_id=10)
        assert result is not None, "New entry should exist"
        
        # Verify one of the old entries was evicted
        stats = cache.stats()
        assert stats['total_entries'] == 5, "Cache should still be at max size"
        
        # Entry 0 and 1 should still exist (recently accessed)
        assert cache.get(business_id=0) is not None, "Recently accessed entry 0 should exist"
        assert cache.get(business_id=1) is not None, "Recently accessed entry 1 should exist"
        
        print("✅ LRU eviction test passed")
    finally:
        # Restore original max
        cache_module.MAX_CACHE_SIZE = original_max


def test_cache_with_settings_data():
    """Test caching with optional settings data"""
    cache = BusinessSettingsCache()
    
    # Test without settings
    business_data = {"id": 1, "name": "Business 1"}
    cache.set(1, business_data, None)
    
    result = cache.get(business_id=1)
    assert result is not None
    assert result[0] == business_data
    assert result[1] is None, "Settings should be None"
    
    # Test with settings
    settings_data = {"tenant_id": 2, "ai_prompt": "Prompt"}
    cache.set(2, business_data, settings_data)
    
    result = cache.get(business_id=2)
    assert result is not None
    assert result[1] == settings_data, "Settings should match"
    
    print("✅ Cache with settings data test passed")


def test_singleton_pattern():
    """Test that get_business_settings_cache returns singleton"""
    cache1 = get_business_settings_cache()
    cache2 = get_business_settings_cache()
    
    assert cache1 is cache2, "Should return same singleton instance"
    
    # Test that data persists across calls
    business_data = {"id": 1, "name": "Test"}
    cache1.set(1, business_data, None)
    
    result = cache2.get(business_id=1)
    assert result is not None, "Data should persist across singleton calls"
    
    print("✅ Singleton pattern test passed")


def test_multi_tenant_isolation():
    """Test that cache entries are isolated by business_id"""
    cache = BusinessSettingsCache()
    
    # Add entries for different businesses
    for i in range(3):
        business_data = {"id": i, "name": f"Business {i}"}
        settings_data = {"tenant_id": i, "ai_prompt": f"Prompt {i}"}
        cache.set(i, business_data, settings_data)
    
    # Verify each business has its own data
    for i in range(3):
        result = cache.get(business_id=i)
        assert result is not None
        assert result[0]["id"] == i
        assert result[1]["tenant_id"] == i
    
    # Invalidate one business
    cache.invalidate(business_id=1)
    
    # Verify only that business is invalidated
    assert cache.get(business_id=0) is not None
    assert cache.get(business_id=1) is None
    assert cache.get(business_id=2) is not None
    
    print("✅ Multi-tenant isolation test passed")


def test_cache_stats():
    """Test cache statistics reporting"""
    cache = BusinessSettingsCache()
    
    # Add entries
    for i in range(3):
        business_data = {"id": i, "name": f"Business {i}"}
        cache.set(i, business_data, None)
    
    stats = cache.stats()
    assert stats['total_entries'] == 3
    assert stats['valid_entries'] == 3
    assert stats['expired_entries'] == 0
    
    print("✅ Cache stats test passed")


if __name__ == "__main__":
    test_cache_hit_and_miss()
    test_cache_ttl_expiration()
    test_cache_invalidation()
    test_cache_clear()
    test_lru_eviction()
    test_cache_with_settings_data()
    test_singleton_pattern()
    test_multi_tenant_isolation()
    test_cache_stats()
    print("\n✅ All business settings cache tests passed!")
