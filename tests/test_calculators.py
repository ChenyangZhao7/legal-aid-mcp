from datetime import date
from pathlib import Path

from calculators import deadline, litigation_fee, preservation_fee
from holidays import HolidayCalendar

ROOT = Path(__file__).resolve().parents[1]


def test_property_fee_100k():
    result = litigation_fee(100000, "财产案件")
    assert result["fee"] == 2300.0


def test_labor_fee():
    assert litigation_fee(None, "劳动争议")["fee"] == 10.0


def test_preservation_cap():
    assert preservation_fee(10_000_000)["fee"] == 5000.0


def test_preservation_small():
    assert preservation_fee(500)["fee"] == 30.0


def test_deadline_skips_start_day():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    result = deadline(date(2026, 11, 6), 15, "natural", cal)
    assert result["original_end_date"] == "2026-11-21"
    assert result["end_date"] == "2026-11-23"
    assert result["adjusted"] is True


def test_deadline_working_days():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    result = deadline(date(2026, 9, 30), 1, "working", cal)
    assert result["end_date"] == "2026-10-08"


def test_deadline_cross_year_january_first():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    result = deadline(date(2026, 12, 17), 15, "natural", cal)
    assert result["original_end_date"] == "2027-01-01"
    assert result["end_date"] == "2027-01-04"
    assert result["adjusted"] is True
