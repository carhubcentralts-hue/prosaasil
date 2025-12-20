"""
Hebrew date/time normalization utilities (server-side).

Goal: make appointment tools robust to common Hebrew inputs like:
- "היום", "מחר"
- "ראשון/שני/..." (next occurrence)
- Times like "שלוש", "בשלוש וחצי", "15", "15:00"

These utilities are intentionally lightweight and deterministic (no LLM).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, Sequence, Tuple, List

import pytz


_HE_WEEKDAY_TO_PY = {
    "שני": 0,
    "שלישי": 1,
    "רביעי": 2,
    "חמישי": 3,
    "שישי": 4,
    "שבת": 5,
    "ראשון": 6,
}

_PY_WEEKDAY_TO_HE = {v: k for k, v in _HE_WEEKDAY_TO_PY.items()}

_HE_MONTHS = {
    1: "ינואר",
    2: "פברואר",
    3: "מרץ",
    4: "אפריל",
    5: "מאי",
    6: "יוני",
    7: "יולי",
    8: "אוגוסט",
    9: "ספטמבר",
    10: "אוקטובר",
    11: "נובמבר",
    12: "דצמבר",
}

_HE_NUMBER_WORDS = {
    "אחת": 1,
    "אחד": 1,
    "שתיים": 2,
    "שניים": 2,
    "שתים": 2,
    "שלוש": 3,
    "ארבע": 4,
    "חמש": 5,
    "חמישה": 5,
    "שש": 6,
    "שבע": 7,
    "שמונה": 8,
    "תשע": 9,
    "עשר": 10,
    "עשרה": 10,
    "אחת עשרה": 11,
    "אחד עשר": 11,
    "שתים עשרה": 12,
    "שנים עשר": 12,
}


def _clean(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def hebrew_weekday_name(d: date) -> str:
    # Python: Monday=0 ... Sunday=6
    return _PY_WEEKDAY_TO_HE.get(d.weekday(), "")


def hebrew_date_display(d: date) -> str:
    # "יום ראשון, 21 בינואר 2026"
    wd = hebrew_weekday_name(d)
    month = _HE_MONTHS.get(d.month, str(d.month))
    return f"יום {wd}, {d.day} {month} {d.year}"


@dataclass(frozen=True)
class DateResolution:
    date_iso: str  # YYYY-MM-DD
    weekday_he: str  # ראשון/שני/...
    date_display_he: str  # "יום X, DD חודש YYYY"


def resolve_hebrew_date(text: str, tz: pytz.BaseTzInfo, now: Optional[datetime] = None) -> Optional[DateResolution]:
    """
    Resolve a Hebrew date phrase into an ISO date.
    Accepts:
    - YYYY-MM-DD
    - היום / מחר / מחרתיים
    - (יום) ראשון/שני/... -> nearest upcoming occurrence (inclusive)
    """
    s = _clean(text)
    if not s:
        return None

    if now is None:
        now = datetime.now(tz)
    if now.tzinfo is None:
        now = tz.localize(now)

    # Remove common prefixes ONLY when they are standalone words.
    # IMPORTANT: Do NOT strip "יום" from "היום".
    s_norm = re.sub(r"^(ביום|יום)\s+", "", s)
    s_norm = _clean(s_norm)

    # ISO date
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s_norm):
        try:
            y, m, d = map(int, s_norm.split("-"))
            dd = date(y, m, d)
            return DateResolution(
                date_iso=dd.isoformat(),
                weekday_he=hebrew_weekday_name(dd),
                date_display_he=hebrew_date_display(dd),
            )
        except Exception:
            return None

    # Relative
    if s_norm in {"היום", "היום."}:
        dd = now.date()
        return DateResolution(dd.isoformat(), hebrew_weekday_name(dd), hebrew_date_display(dd))
    if s_norm in {"מחר", "מחר."}:
        dd = (now + timedelta(days=1)).date()
        return DateResolution(dd.isoformat(), hebrew_weekday_name(dd), hebrew_date_display(dd))
    if s_norm in {"מחרתיים", "מחרתים"}:
        dd = (now + timedelta(days=2)).date()
        return DateResolution(dd.isoformat(), hebrew_weekday_name(dd), hebrew_date_display(dd))

    # Weekday name
    if s_norm in _HE_WEEKDAY_TO_PY:
        target_py = _HE_WEEKDAY_TO_PY[s_norm]
        today_py = now.date().weekday()
        delta = (target_py - today_py) % 7  # inclusive (0 means today)
        dd = (now + timedelta(days=delta)).date()
        return DateResolution(dd.isoformat(), hebrew_weekday_name(dd), hebrew_date_display(dd))

    return None


@dataclass(frozen=True)
class TimeResolution:
    """
    Represents a possibly-ambiguous time.
    - candidates_hhmm: ordered list of candidate times ("HH:MM") to try.
    """
    candidates_hhmm: Tuple[str, ...]


def _hhmm(hour: int, minute: int) -> Optional[str]:
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def resolve_hebrew_time(text: str) -> Optional[TimeResolution]:
    """
    Resolve Hebrew time phrases into one or more HH:MM candidates.

    Supports:
    - "15:00"
    - "15" / "3" / "03"
    - "בשלוש", "שלוש וחצי", "שלוש ורבע"
    """
    s = _clean(text)
    if not s:
        return None

    # Strip common wrappers
    s = re.sub(r"^(בשעה|בש|ב)\s+", "", s)
    s = _clean(s)

    # HH:MM
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        hhmm = _hhmm(h, mi)
        return TimeResolution((hhmm,)) if hhmm else None

    # "15" or "3" or "3 וחצי"
    # Normalize "וחצי/ורבע"
    minute = 0
    if "חצי" in s:
        minute = 30
        s = s.replace("וחצי", "").replace("חצי", "").strip()
    elif "רבע" in s:
        minute = 15
        s = s.replace("ורבע", "").replace("רבע", "").strip()

    # Digits hour
    m = re.fullmatch(r"(\d{1,2})", s)
    if m:
        h = int(m.group(1))
        if not (0 <= h <= 23):
            return None
        # If hour is <= 12 and no explicit AM/PM, keep both candidates (PM-first).
        if 1 <= h <= 12:
            cand: List[str] = []
            # Prefer afternoon/evening interpretation first (common for "שלוש" => 15:00)
            if h != 12:
                pm = _hhmm(h + 12, minute)
                if pm:
                    cand.append(pm)
            am = _hhmm(h % 24, minute)
            if am and am not in cand:
                cand.append(am)
            return TimeResolution(tuple(cand))
        hhmm = _hhmm(h, minute)
        return TimeResolution((hhmm,)) if hhmm else None

    # Hebrew number words
    # Try longest matches first (e.g., "אחת עשרה" before "אחת")
    s2 = s
    # Remove "ב" prefix stuck to word (e.g., "בשלוש")
    s2 = re.sub(r"^ב", "", s2)
    s2 = _clean(s2)
    for word, num in sorted(_HE_NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
        if s2 == word:
            h = num
            cand: List[str] = []
            if 1 <= h <= 12:
                if h != 12:
                    pm = _hhmm(h + 12, minute)
                    if pm:
                        cand.append(pm)
                am = _hhmm(h, minute)
                if am and am not in cand:
                    cand.append(am)
                return TimeResolution(tuple(cand))
            hhmm = _hhmm(h, minute)
            return TimeResolution((hhmm,)) if hhmm else None

    return None


def pick_best_time_candidate(
    candidates: Sequence[str],
    *,
    preferred_daytime_hours: Tuple[int, int] = (7, 21),
) -> Optional[str]:
    """
    Deterministic heuristic to pick a "best" candidate when we can't query availability yet.
    """
    if not candidates:
        return None
    start_h, end_h = preferred_daytime_hours
    for c in candidates:
        try:
            h = int(c.split(":")[0])
            if start_h <= h <= end_h:
                return c
        except Exception:
            continue
    return candidates[0]

