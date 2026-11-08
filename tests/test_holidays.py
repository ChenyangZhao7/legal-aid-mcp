from datetime import date
from pathlib import Path

from holidays import HolidayCalendar

ROOT = Path(__file__).resolve().parents[1]


def test_2026_national_day_holiday():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    assert cal.is_holiday(date(2026, 10, 1))
    assert not cal.is_workday(date(2026, 10, 1))


def test_2026_makeup_workday():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    assert cal.is_workday(date(2026, 10, 10))


def test_weekend_fallback(tmp_path):
    cal = HolidayCalendar.load(tmp_path, 2030)
    assert cal.is_holiday(date(2030, 1, 5))  # Saturday
    assert cal.source == "weekend-only"


def test_add_workdays():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    # 2026-09-30 is Wednesday; next workday after National Day is 2026-10-08.
    assert cal.add_workdays(date(2026, 9, 30), 1) == date(2026, 10, 8)
