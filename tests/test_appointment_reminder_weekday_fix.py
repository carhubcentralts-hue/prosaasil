"""
Test for appointment reminder weekday/date fix

This test verifies that the weekday shown in appointment reminders
matches the actual date, especially when considering timezone conversions.

Bug: Messages showed "יום רביעי, 5 בפברואר 2026" (Wednesday) when
05/02/2026 is actually Thursday (יום חמישי) in Israel timezone.
"""
import sys
import os
from datetime import datetime
import pytz

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_format_hebrew_date_correct_weekday():
    """
    Test that format_hebrew_date shows correct weekday for the date.
    
    Key test case: 2026-02-05 is Thursday (יום חמישי), not Wednesday.
    """
    # Import Hebrew datetime utilities directly
    from server.services.hebrew_datetime import hebrew_weekday_name, _HE_MONTHS
    
    # Test the utilities directly
    # 2026-02-05 is Thursday
    test_date = datetime(2026, 2, 5).date()
    day_name = hebrew_weekday_name(test_date)
    
    # weekday() for 2026-02-05 returns 3 (Thursday)
    assert test_date.weekday() == 3, f"2026-02-05 should be Thursday (weekday=3), got {test_date.weekday()}"
    
    # hebrew_weekday_name should return 'חמישי' (Thursday)
    assert day_name == 'חמישי', f"Expected 'חמישי' (Thursday), got: {day_name}"
    
    # Build the full format like the job does
    month_name = _HE_MONTHS.get(test_date.month, str(test_date.month))
    result = f"יום {day_name}, {test_date.day} {month_name} {test_date.year}"
    
    expected = "יום חמישי, 5 פברואר 2026"
    assert result == expected, f"Expected: {expected}, Got: {result}"
    
    print(f"✅ Test passed! Format: {result}")


def test_weekday_mapping_all_days():
    """
    Test that weekday mapping is consistent with Python's weekday() function for all days.
    
    Python weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    Hebrew days should map correctly.
    """
    from server.services.hebrew_datetime import hebrew_weekday_name
    
    # Test each day of the week (Feb 3-9, 2026)
    # Verified with Python calendar: calendar.day_name[datetime(2026, 2, X).weekday()]
    test_cases = [
        (datetime(2026, 2, 3).date(), 1, 'שלישי'),   # Tuesday (weekday=1)
        (datetime(2026, 2, 4).date(), 2, 'רביעי'),   # Wednesday (weekday=2)
        (datetime(2026, 2, 5).date(), 3, 'חמישי'),   # Thursday (weekday=3)
        (datetime(2026, 2, 6).date(), 4, 'שישי'),    # Friday (weekday=4)
        (datetime(2026, 2, 7).date(), 5, 'שבת'),     # Saturday (weekday=5)
        (datetime(2026, 2, 8).date(), 6, 'ראשון'),   # Sunday (weekday=6)
        (datetime(2026, 2, 9).date(), 0, 'שני'),     # Monday (weekday=0)
    ]
    
    for test_date, expected_weekday, expected_hebrew in test_cases:
        actual_weekday = test_date.weekday()
        assert actual_weekday == expected_weekday, \
            f"Date {test_date} should have weekday={expected_weekday}, got {actual_weekday}"
        
        actual_hebrew = hebrew_weekday_name(test_date)
        assert actual_hebrew == expected_hebrew, \
            f"Date {test_date} (weekday={actual_weekday}) should be '{expected_hebrew}', got '{actual_hebrew}'"
        
        print(f"✅ {test_date} -> weekday={actual_weekday} -> {expected_hebrew}")


def test_timezone_conversion():
    """
    Test that UTC datetimes are correctly converted to Israel time before formatting.
    """
    from server.services.hebrew_datetime import hebrew_weekday_name
    
    # 2026-02-04 23:00 UTC = 2026-02-05 01:00 Israel (next day!)
    utc_time = pytz.utc.localize(datetime(2026, 2, 4, 23, 0))
    israel_tz = pytz.timezone('Asia/Jerusalem')
    israel_time = utc_time.astimezone(israel_tz)
    
    # UTC date is Feb 4 (Wednesday), but Israel date is Feb 5 (Thursday)
    utc_date = utc_time.date()
    israel_date = israel_time.date()
    
    assert utc_date.day == 4, f"UTC date should be Feb 4, got {utc_date}"
    assert israel_date.day == 5, f"Israel date should be Feb 5, got {israel_date}"
    
    # Hebrew weekday should be based on Israel date (Thursday)
    day_name = hebrew_weekday_name(israel_date)
    assert day_name == 'חמישי', f"Israel date Feb 5 should be Thursday (חמישי), got: {day_name}"
    
    # UTC date would give Wednesday (wrong!)
    utc_day_name = hebrew_weekday_name(utc_date)
    assert utc_day_name == 'רביעי', f"UTC date Feb 4 should be Wednesday (רביעי), got: {utc_day_name}"
    
    print(f"✅ Timezone test passed!")
    print(f"   UTC: {utc_date} = {utc_day_name}")
    print(f"   Israel: {israel_date} = {day_name}")


if __name__ == '__main__':
    print("Testing Hebrew weekday mapping fix...\n")
    
    try:
        test_format_hebrew_date_correct_weekday()
        print()
        test_weekday_mapping_all_days()
        print()
        test_timezone_conversion()
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

