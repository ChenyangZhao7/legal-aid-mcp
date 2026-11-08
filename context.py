from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from config import Settings

if TYPE_CHECKING:
    from baidu import BaiduClient
    from divisions import DivisionIndex
    from holidays import HolidayCalendar
    from laws import LawCorpus
    from legal_aid import LegalAidClient
    from maps.service import MapService


@dataclass
class AppContext:
    settings: Settings
    baidu: "BaiduClient"
    corpus: "LawCorpus"
    maps: "MapService | None" = None
    divisions: "DivisionIndex | None" = None
    legal_aid: "LegalAidClient | None" = None
    holidays: "HolidayCalendar | None" = None
