"""
Test lead notes context integration

This test verifies that:
1. build_name_anchor_message includes lead notes in the context
2. Lead notes are properly formatted and truncated
"""

def test_build_name_anchor_message_with_notes():
    """Test that build_name_anchor_message includes lead notes"""
    from server.services.realtime_prompt_builder import build_name_anchor_message
    
    # Test 1: Basic name + notes
    result = build_name_anchor_message(
        customer_name="דני",
        use_name_policy=True,
        customer_gender="male",
        lead_notes="לקוח ביקש תיקון רכב. בעיית בלמים."
    )
    
    print(f"Test 1 - Basic name + notes:")
    print(f"  Result: {result}")
    assert "דני" in result, "Should include customer name"
    assert "בלמים" in result, "Should include notes content"
    assert "Previous notes:" in result, "Should have 'Previous notes:' prefix"
    print(f"  ✅ PASS\n")
    
    # Test 2: Long notes get truncated
    long_notes = "א" * 600  # 600 chars
    result = build_name_anchor_message(
        customer_name="רחל",
        use_name_policy=False,
        customer_gender="female",
        lead_notes=long_notes
    )
    
    print(f"Test 2 - Long notes truncation:")
    print(f"  Input length: {len(long_notes)} chars")
    print(f"  Result length: {len(result)} chars")
    assert len(result) < 700, "Result should be truncated"
    assert "..." in result, "Should have ellipsis for truncation"
    print(f"  ✅ PASS\n")
    
    # Test 3: No notes provided
    result = build_name_anchor_message(
        customer_name="משה",
        use_name_policy=True,
        customer_gender="male",
        lead_notes=None
    )
    
    print(f"Test 3 - No notes:")
    print(f"  Result: {result}")
    assert "משה" in result, "Should include customer name"
    assert "Previous notes:" not in result, "Should not mention notes if none provided"
    print(f"  ✅ PASS\n")
    
    # Test 4: Empty notes string
    result = build_name_anchor_message(
        customer_name="שרה",
        use_name_policy=True,
        customer_gender="female",
        lead_notes="   "
    )
    
    print(f"Test 4 - Empty notes string:")
    print(f"  Result: {result}")
    assert "שרה" in result, "Should include customer name"
    assert "Previous notes:" not in result, "Should not mention notes if empty"
    print(f"  ✅ PASS\n")
    
    # Test 5: Name without policy, with notes
    result = build_name_anchor_message(
        customer_name="יוסי",
        use_name_policy=False,
        customer_gender="male",
        lead_notes="לקוח קבוע. מעדיף שעות בוקר."
    )
    
    print(f"Test 5 - Name without policy, with notes:")
    print(f"  Result: {result}")
    assert "יוסי" in result, "Should include customer name"
    assert "קבוע" in result, "Should include notes"
    assert "Previous notes:" in result, "Should include notes even without name policy"
    print(f"  ✅ PASS\n")
    
    print("=" * 60)
    print("ALL TESTS PASSED! ✅")
    print("=" * 60)


if __name__ == "__main__":
    test_build_name_anchor_message_with_notes()
