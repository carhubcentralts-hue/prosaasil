import pytz
from datetime import datetime


def test_auto_correct_iso_year_fixes_old_training_year():
    from server.services.hebrew_datetime import auto_correct_iso_year

    tz = pytz.timezone("Asia/Jerusalem")
    now = tz.localize(datetime(2025, 12, 21, 10, 0, 0))

    corrected, did, reason = auto_correct_iso_year("2023-12-23", tz, now)
    assert did is True
    assert corrected == "2025-12-23"
    assert "year_roll" in reason


def test_auto_correct_iso_year_rolls_to_next_year_when_date_passed_this_year():
    from server.services.hebrew_datetime import auto_correct_iso_year

    tz = pytz.timezone("Asia/Jerusalem")
    now = tz.localize(datetime(2025, 12, 30, 10, 0, 0))

    corrected, did, _reason = auto_correct_iso_year("2025-01-01", tz, now)
    assert did is True
    assert corrected == "2026-01-01"


def test_auto_correct_iso_year_does_not_roll_recent_past_like_yesterday():
    from server.services.hebrew_datetime import auto_correct_iso_year

    tz = pytz.timezone("Asia/Jerusalem")
    now = tz.localize(datetime(2025, 12, 21, 10, 0, 0))

    corrected, did, reason = auto_correct_iso_year("2025-12-20", tz, now)
    assert did is False
    assert corrected == "2025-12-20"
    assert "recent_past" in (reason or "")


def test_auto_correct_iso_year_ignores_non_iso():
    from server.services.hebrew_datetime import auto_correct_iso_year

    tz = pytz.timezone("Asia/Jerusalem")
    now = tz.localize(datetime(2025, 12, 21, 10, 0, 0))

    corrected, did, reason = auto_correct_iso_year("23 בדצמבר", tz, now)
    assert did is False
    assert corrected == "23 בדצמבר"
    assert reason == ""

