from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from baidu import CacheStore
from config import Settings
from divisions import Division, DivisionIndex
from errors import ToolError

LIST_URL = "https://www.12348.gov.cn/legalList/getlegalList"
SNAPSHOT = Path(__file__).resolve().parent / "data" / "legal_aid" / "jinan.json"


def sign_payload(
    page_num: int,
    page_size: int,
    xzqh: str,
    mc: str,
    v_key: str | None = None,
    guid: str | None = None,
    crawler_cookie: str | None = None,
) -> dict:
    v_key = v_key or str(uuid.uuid4())
    guid = guid or str(uuid.uuid4())
    crawler_cookie = crawler_cookie or str(uuid.uuid4())
    raw = f"{v_key}{guid}{page_num}.{page_size}"
    md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()
    number = sum(ord(md5[index]) for index in (5, 3, 1, 6, 8, 10))
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "xzqh": xzqh,
        "mc": mc,
        "v_key": v_key,
        "guid": guid,
        "number": number,
        "crawlerCookie": crawler_cookie,
    }


@dataclass
class LegalAidCenter:
    name: str
    address: str | None
    telephone: str | None
    lat: float | None
    lng: float | None
    adcode: str | None = None
    id: str | None = None
    source: str = "12348"

    @classmethod
    def from_row(cls, row: dict) -> "LegalAidCenter":
        try:
            lat = float(row.get("wd")) if row.get("wd") else None
            lng = float(row.get("jd")) if row.get("jd") else None
        except (TypeError, ValueError):
            lat = lng = None
        return cls(
            name=row.get("mc") or "",
            address=row.get("dz"),
            telephone=row.get("dh"),
            lat=lat,
            lng=lng,
            adcode=str(row.get("xzqh") or "") or None,
            id=row.get("id"),
        )


@dataclass
class LegalAidResult:
    centers: list[LegalAidCenter]
    coverage: dict = field(default_factory=dict)
    warnings: list[dict] = field(default_factory=list)
    source: str = "none"


def fetch_centers(
    xzqh: str,
    transport: httpx.BaseTransport | None = None,
) -> list[LegalAidCenter]:
    payload = sign_payload(1, 50, xzqh, "")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.12348.gov.cn/",
        "Origin": "https://www.12348.gov.cn",
        "Cookie": f"crawlerCookie={payload['crawlerCookie']}",
    }
    try:
        with httpx.Client(transport=transport, timeout=30) as client:
            response = client.post(LIST_URL, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException:
        raise ToolError("UPSTREAM_TIMEOUT", "12348 查询超时，请稍后重试")
    except httpx.HTTPError:
        raise ToolError("UPSTREAM_ERROR", "12348 查询失败，请稍后重试")

    try:
        data = response.json()
    except ValueError:
        raise ToolError("UPSTREAM_ERROR", "12348 返回了非 JSON 响应")
    if not isinstance(data, dict):
        raise ToolError("UPSTREAM_ERROR", "12348 返回格式异常")
    if data.get("success") is False:
        message = data.get("errormsg") or ""
        raise ToolError("UPSTREAM_ERROR", f"12348 查询失败：{message}")
    return [LegalAidCenter.from_row(row) for row in data.get("list") or []]


class LegalAidClient:
    def __init__(
        self,
        settings: Settings,
        divisions: DivisionIndex,
        transport: httpx.BaseTransport | None = None,
        now=None,
        snapshot_path: Path | None = None,
        request_interval: float = 0.15,
    ) -> None:
        self.settings = settings
        self.divisions = divisions
        self.transport = transport
        self.request_interval = request_interval
        self._failed: set[str] = set()
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.cache = CacheStore(
            settings.cache_dir, settings.legal_aid_cache_hours, self.now
        )
        self.live = settings.use_live and settings.legal_aid_live
        self.snapshot_path = Path(snapshot_path) if snapshot_path else SNAPSHOT
        self.snapshot = self._load_snapshot()

    def _load_snapshot(self) -> dict:
        if not self.snapshot_path.exists():
            return {"districts": {}}
        try:
            return json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"districts": {}}

    def _districts(self, district: str | None) -> list[Division]:
        if district is None:
            return self.divisions.districts()
        node = self.divisions.find(district)
        if node is None:
            raise ToolError("DIVISION_NOT_FOUND", f"民政部区划中没有“{district}”")
        return [node]

    def _snapshot_centers(self, code6: str) -> tuple[list[LegalAidCenter], bool]:
        entry = (self.snapshot.get("districts") or {}).get(code6)
        if not entry or entry.get("status") not in {"ok", "empty"}:
            return [], False
        centers = [LegalAidCenter(**row) for row in entry.get("centers") or []]
        for center in centers:
            center.source = "snapshot"
        return centers, True

    def _fetch_district(self, node: Division) -> list[LegalAidCenter]:
        code6 = node.code[:6]
        cache_key = f"legal_aid_{code6}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [LegalAidCenter(**row) for row in cached.get("centers") or []]
        centers = fetch_centers(code6, transport=self.transport)
        for center in centers:
            center.source = "12348"
        self.cache.set(
            cache_key, {"centers": [asdict(center) for center in centers]}
        )
        return centers

    def search(
        self,
        district: str | None = None,
        keyword: str | None = None,
        limit: int = 5,
    ) -> LegalAidResult:
        nodes = self._districts(district)
        centers: list[LegalAidCenter] = []
        warnings: list[dict] = []
        coverage = {
            "districts_total": len(nodes),
            "districts_live": 0,
            "districts_snapshot": 0,
            "districts_map": 0,
            "districts_failed": 0,
        }

        for index, node in enumerate(nodes):
            code6 = node.code[:6]
            live_centers = None
            if self.live and code6 not in self._failed:
                try:
                    live_centers = self._fetch_district(node)
                    coverage["districts_live"] += 1
                except ToolError:
                    self._failed.add(code6)
                    live_centers = None
                if index < len(nodes) - 1:
                    time.sleep(self.request_interval)

            if live_centers is not None:
                centers.extend(live_centers)
                continue

            snapshot_centers, found = self._snapshot_centers(code6)
            if found:
                centers.extend(snapshot_centers)
                coverage["districts_snapshot"] += 1
                warnings.append(
                    {
                        "code": "LEGAL_AID_PARTIAL",
                        "district": node.name,
                        "message": "12348 实时查询不可用，已使用本地快照",
                    }
                )
            else:
                coverage["districts_failed"] += 1
                warnings.append(
                    {
                        "code": "LEGAL_AID_PARTIAL",
                        "district": node.name,
                        "message": "12348 与快照均不可用",
                    }
                )

        if keyword:
            centers = [center for center in centers if keyword in center.name]
        centers = centers[:limit]

        if not centers and coverage["districts_failed"] == coverage["districts_total"]:
            raise ToolError(
                "LEGAL_AID_UNAVAILABLE",
                "12348 与本地快照都不可用，无法确认法律援助中心；请稍后重试或改用地图搜索",
            )

        if coverage["districts_live"]:
            source = "12348"
        elif coverage["districts_snapshot"]:
            source = "snapshot"
        else:
            source = "none"
        return LegalAidResult(
            centers=centers,
            coverage=coverage,
            warnings=warnings,
            source=source,
        )
