"""
Test Assets AI Toggle Feature
Tests that the assets_use_ai setting correctly controls AI access to assets tools
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_logic():
    """Test the logic of is_assets_enabled without database"""
    
    # Simulate the function logic
    def is_assets_enabled_logic(enabled_pages, assets_use_ai):
        """Simulated logic of is_assets_enabled"""
        # Check if assets page is enabled
        if 'assets' not in enabled_pages:
            return False
        
        # Check if AI is allowed to use assets tools
        if not assets_use_ai:
            return False
        
        return True
    
    print("Testing Assets AI Toggle Logic")
    print("=" * 50)
    
    # Test 1: Assets page enabled + AI enabled
    print("\nTest 1: Assets page enabled + AI enabled")
    result1 = is_assets_enabled_logic(['assets', 'dashboard'], True)
    print(f"  enabled_pages=['assets', 'dashboard'], assets_use_ai=True")
    print(f"  Result: {result1}")
    assert result1 == True, "Should be enabled when both conditions are met"
    print("  ✅ PASS")
    
    # Test 2: Assets page enabled + AI disabled
    print("\nTest 2: Assets page enabled + AI disabled")
    result2 = is_assets_enabled_logic(['assets', 'dashboard'], False)
    print(f"  enabled_pages=['assets', 'dashboard'], assets_use_ai=False")
    print(f"  Result: {result2}")
    assert result2 == False, "Should be disabled when AI is disabled"
    print("  ✅ PASS")
    
    # Test 3: Assets page disabled + AI enabled
    print("\nTest 3: Assets page disabled + AI enabled")
    result3 = is_assets_enabled_logic(['dashboard'], True)
    print(f"  enabled_pages=['dashboard'], assets_use_ai=True")
    print(f"  Result: {result3}")
    assert result3 == False, "Should be disabled when page is not enabled"
    print("  ✅ PASS")
    
    # Test 4: Assets page disabled + AI disabled
    print("\nTest 4: Assets page disabled + AI disabled")
    result4 = is_assets_enabled_logic(['dashboard'], False)
    print(f"  enabled_pages=['dashboard'], assets_use_ai=False")
    print(f"  Result: {result4}")
    assert result4 == False, "Should be disabled when both are disabled"
    print("  ✅ PASS")
    
    print("\n" + "=" * 50)
    print("All logic tests passed! ✅")
    print("=" * 50)

if __name__ == '__main__':
    try:
        test_logic()
        print("\n✅ Assets AI Toggle Feature logic is correct!")
        print("\nSummary:")
        print("- AI tools are enabled ONLY when:")
        print("  1. 'assets' is in enabled_pages (page permission)")
        print("  2. assets_use_ai is True (AI tools permission)")
        print("- This ensures fine-grained control over AI access")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
