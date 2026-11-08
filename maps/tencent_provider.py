from __future__ import annotations

import httpx

from config import Settings
from coord import gcj02_to_wgs84, wgs84_to_gcj02
from errors import ToolError
from maps.base import GeoPoint, Place, Route
from maps.live import LiveJsonClient

_BASE = "https://apis.map.qq.com"


def _status_code(data: dict) -> int:
    try:
        return int(data.get("status", 0))
    except (TypeError, ValueError):
        return -1


def _raise_status(data: dict) -> None:
    status = _status_code(data)
    if status == 0:
        return
    message = data.get("message") or ""
    if status == 120:
        raise ToolError("QUOTA_EXCEEDED", f"腾讯地图配额已用尽（status={status}）：{message}")
    if status in {121, 122}:
        raise ToolError("UPSTREAM_ERROR", f"腾讯地图请求受限（status={status}）：{message}")
    if 123 <= status <= 134:
        raise ToolError("AK_INVALID", f"腾讯地图 key 不可用（status={status}）：{message}")
    raise ToolError("UPSTREAM_ERROR", f"腾讯地图返回错误（status={status}）：{message}")


class TencentProvider:
    name = "tencent"

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        now=None,
    ) -> None:
        self.settings = settings
        self.key = settings.tencent_map_key
        self.enabled = bool(self.key)
        self.client = LiveJsonClient(
            self.name,
            _BASE,
            settings,
            transport=transport,
            now=now,
            budget_limit=settings.tencent_budget,
        )

    def place_search(self, query: str, region: str, limit: int) -> list[Place]:
        if not self.enabled:
            return []
        data = self.client.get(
            "/ws/place/v1/search",
            {
                "keyword": query,
                "boundary": f"region({region},0)",
                "page_size": limit,
                "page_index": 1,
                "key": self.key,
                "output": "json",
            },
        )
        _raise_status(data)
        places = []
        for row in data.get("data") or []:
            location = row.get("location") or {}
            lat = float(location.get("lat") or 0.0)
            lng = float(location.get("lng") or 0.0)
            wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
            places.append(
                Place(
                    provider=self.name,
                    name=row.get("title") or "",
                    address=row.get("address"),
                    telephone=row.get("tel"),
                    point=GeoPoint(wgs_lat, wgs_lng, "wgs84"),
                    native=GeoPoint(lat, lng, "gcj02"),
                    adcode=str((row.get("ad_info") or {}).get("adcode") or "") or None,
                    raw=row,
                )
            )
        return places

    def geocode(self, address: str) -> GeoPoint:
        if not self.enabled:
            raise ToolError("GEOCODE_FAILED", "未配置腾讯地图 key")
        data = self.client.get(
            "/ws/geocoder/v1/",
            {"address": address, "key": self.key},
        )
        _raise_status(data)
        try:
            location = data["result"]["location"]
            lat = float(location["lat"])
            lng = float(location["lng"])
        except (KeyError, TypeError, ValueError):
            raise ToolError("GEOCODE_FAILED", f"腾讯地图无法解析地址：{address}")
        wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
        return GeoPoint(wgs_lat, wgs_lng, "wgs84")

    def route(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> Route:
        if not self.enabled:
            raise ToolError("NO_ROUTE", "未配置腾讯地图 key")
        origin_lng, origin_lat = wgs84_to_gcj02(origin.lng, origin.lat)
        dest_lng, dest_lat = wgs84_to_gcj02(destination.lng, destination.lat)
        data = self.client.get(
            f"/ws/direction/v1/{mode}/",
            {
                "from": f"{origin_lat},{origin_lng}",
                "to": f"{dest_lat},{dest_lng}",
                "key": self.key,
            },
        )
        _raise_status(data)
        try:
            route = data["result"]["routes"][0]
            steps = [
                {
                    "instruction": step.get("instruction")
                    or (f"沿{step['road_name']}" if step.get("road_name") else "继续行驶"),
                    "road_name": step.get("road_name") or "",
                    "distance_m": int(step.get("distance") or 0),
                    "duration_s": int(step.get("duration") or 0),
                }
                for step in route.get("steps") or []
            ]
            return Route(
                provider=self.name,
                distance_m=int(route["distance"]),
                duration_s=int(route["duration"]),
                steps=steps,
            )
        except (KeyError, IndexError, TypeError, ValueError):
            raise ToolError("NO_ROUTE", "腾讯地图未找到可用路线")
