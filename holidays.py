from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import httpx


def parse_timor(payload: dict, year: int) -> dict[str, dict]:
    days: dict[str, dict] = {}
    for key, item in (payload.get("holiday") or {}).items():
        value = item.get("date") or f"{year}-{key}"
        days[value] = {
            "holiday": bool(item.get("holiday")),
            "name": item.get("name") or "",
        }
    return days


def fetch_timor(
    year: int,
    api_base: str = "https://timor.tech/api/holiday",
    transport: httpx.BaseTransport | None = None,
) -> dict[str, dict]:
    query = urllib.parse.urlencode({"type": "Y", "week": "Y"})
    url = f"{api_base}/year/{year}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != 0:
        raise RuntimeError(f"节假日 API 返回错误：{payload}")
    return parse_timor(payload, year)


class HolidayCalendar:
    def __init__(
        self,
        year: int,
        days: dict[str, dict] | None = None,
        source: str = "weekend-only",
    ) -> None:
        self.year = year
        self.days = {
            date.fromisoformat(key): bool(value.get("holiday"))
            for key, value in (days or {}).items()
        }
        self.names = {
            date.fromisoformat(key): value.get("name") or ""
            for key, value in (days or {}).items()
        }
        self.source = source

    @classmethod
    def load(
        cls,
        data_dir: Path,
        year: int,
        live: bool = False,
        transport: httpx.BaseTransport | None = None,
        api_base: str = "https://timor.tech/api/holiday",
    ) -> "HolidayCalendar":
        path = Path(data_dir) / f"{year}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cls(year, payload.get("days") or {}, payload.get("source") or "snapshot")
        if live:
            days = fetch_timor(year, api_base=api_base, transport=transport)
            return cls(year, days, "timor")
        return cls(year, {}, "weekend-only")

    def is_holiday(self, day: date) -> bool:
        if day in self.days:
            return self.days[day]
        return day.weekday() >= 5

    def is_workday(self, day: date) -> bool:
        return not self.is_holiday(day)

    def next_workday(self, day: date) -> date:
        current = day + timedelta(days=1)
        while not self.is_workday(current):
            current += timedelta(days=1)
        return current

    def add_workdays(self, start: date, count: int) -> date:
        current = start
        remaining = count
        while remaining > 0:
            current += timedelta(days=1)
            if self.is_workday(current):
                remaining -= 1
        return current

    def workdays_between(self, start: date, end: date) -> int:
        current = start
        total = 0
        while current <= end:
            if self.is_workday(current):
                total += 1
            current += timedelta(days=1)
        return total
