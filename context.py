from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from config import Settings

if TYPE_CHECKING:
    from baidu import BaiduClient
    from laws import LawCorpus


@dataclass
class AppContext:
    settings: Settings
    baidu: "BaiduClient"
    corpus: "LawCorpus"
