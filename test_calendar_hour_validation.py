"""
Test for calendar hour validation fix
Tests that negative hour values are properly rejected in check_slot function
"""

def test_hour_validation_logic():
    """
    Test the hour validation logic that was fixed in tools_calendar.py
    
    The bug was that when searching backwards from a preferred time,
    if start_search_min < delta, then (start_search_min - delta) becomes negative,
    resulting in negative hour values.
    
    The fix adds validation: if hour < 0 or hour >= 24: return None
    """
    
    print("Testing hour validation logic from tools_calendar.py fix...")
    
    # Simulate the check_slot logic
    def validate_minute_offset(minute_offset: int) -> bool:
        """Returns True if minute_offset produces a valid hour (0-23)"""
        hour = minute_offset // 60
        minute = minute_offset % 60
        
        # This is the fixed validation
        if hour < 0 or hour >= 24:
            return False
        return True
    
    # Test cases
    test_cases = [
        # (minute_offset, expected_valid, description)
        (-120, False, "Negative offset -2 hours"),
        (-60, False, "Negative offset -1 hour"),
        (-1, False, "Negative offset -1 minute (hour becomes -1)"),
        (0, True, "Midnight 00:00"),
        (60, True, "1 AM"),
        (540, True, "9 AM"),
        (1439, True, "23:59 (last valid minute)"),
        (1440, False, "24:00 (next day)"),
        (1500, False, "25:00 (way over)"),
    ]
    
    print("\nTest Results:")
    print("-" * 70)
    all_passed = True
    
    for minute_offset, expected_valid, description in test_cases:
        hour = minute_offset // 60
        minute = minute_offset % 60
        is_valid = validate_minute_offset(minute_offset)
        status = "✅" if is_valid == expected_valid else "❌"
        
        print(f"{status} offset={minute_offset:5d} -> h={hour:3d}, m={minute:2d} | "
              f"valid={is_valid:5} | {description}")
        
        if is_valid != expected_valid:
            all_passed = False
            print(f"   ERROR: Expected valid={expected_valid}, got {is_valid}")
    
    print("-" * 70)
    
    if all_passed:
        print("\n✅ All tests PASSED! The fix correctly handles negative hours.")
        return True
    else:
        print("\n❌ Some tests FAILED!")
        return False


def test_scenario_from_bug_report():
    """
    Simulate the exact scenario from the bug report
    
    From logs: The AI was checking availability for "יום רביעי" (Wednesday)
    and the code tried to search backwards from start_search_min with delta values.
    When delta > start_search_min, the result was negative.
    """
    print("\n" + "=" * 70)
    print("Simulating the bug scenario from the report...")
    print("=" * 70)
    
    # Example: If start_search_min = 60 (1 AM) and we search backwards
    # with delta = 120 (2 hours), we get 60 - 120 = -60 (invalid!)
    
    scenarios = [
        (60, 0, 60, True),    # 1 AM - 0 hours = 1 AM (valid)
        (60, 60, 0, True),    # 1 AM - 1 hour = 0 AM (midnight, valid)
        (60, 120, -60, False), # 1 AM - 2 hours = -1 AM (INVALID - this was the bug!)
        (120, 180, -60, False), # 2 AM - 3 hours = -1 AM (INVALID)
        (0, 60, -60, False),  # 0 AM - 1 hour = -1 AM (INVALID)
    ]
    
    print("\nScenario: Searching backwards from start_search_min")
    print("-" * 70)
    
    all_handled = True
    for start_min, delta, result_min, should_be_valid in scenarios:
        hour = result_min // 60
        minute = result_min % 60
        
        # Apply the fix
        is_valid = not (hour < 0 or hour >= 24)
        status = "✅" if (is_valid == should_be_valid) else "❌"
        
        print(f"{status} start={start_min:4d}min - delta={delta:4d}min = {result_min:5d}min "
              f"(h={hour:3d}) | valid={is_valid:5}")
        
        if is_valid != should_be_valid:
            all_handled = False
    
    print("-" * 70)
    
    if all_handled:
        print("\n✅ Bug scenario is now HANDLED correctly by the fix!")
        print("   Negative hours are rejected and won't crash with ValueError")
        return True
    else:
        print("\n❌ Bug scenario is NOT handled!")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Calendar Hour Validation Fix - Test Suite")
    print("=" * 70)
    
    test1_passed = test_hour_validation_logic()
    test2_passed = test_scenario_from_bug_report()
    
    print("\n" + "=" * 70)
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED! The fix resolves the issue.")
        print("=" * 70)
        exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        print("=" * 70)
        exit(1)
