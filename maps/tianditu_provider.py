from __future__ import annotations

import json

import httpx

from config import Settings
from errors import ToolError
from maps.base import GeoPoint, Place, Route
from maps.live import LiveJsonClient

_BASE = "https://api.tianditu.gov.cn"


def _raise_status(data: dict) -> None:
    for key in ("status", "resultCode", "returncode"):
        if key not in data:
            continue
        value = data.get(key)
        if value in (0, "0", 100, "100", None, ""):
            return
        message = data.get("message") or data.get("msg") or ""
        raise ToolError("UPSTREAM_ERROR", f"天地图返回错误（{key}={value}）：{message}")


class TiandituProvider:
    name = "tianditu"

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        now=None,
    ) -> None:
        self.settings = settings
        self.key = settings.tianditu_key
        self.enabled = bool(self.key)
        self.client = LiveJsonClient(
            self.name,
            _BASE,
            settings,
            transport=transport,
            now=now,
            budget_limit=settings.tianditu_budget,
        )

    def place_search(self, query: str, region: str, limit: int) -> list[Place]:
        if not self.enabled:
            return []
        post = {
            "keyWord": query,
            "level": 12,
            "mapBound": "-180,-90,180,90",
            "queryType": 1,
            "start": 0,
            "count": limit,
            "queryTerm": region,
        }
        data = self.client.get(
            "/v2/search",
            {
                "postStr": json.dumps(post, ensure_ascii=False),
                "type": "query",
                "tk": self.key,
            },
        )
        _raise_status(data)
        places = []
        for row in data.get("pois") or []:
            lonlat = row.get("lonlat") or "0,0"
            try:
                lng_text, lat_text = lonlat.split(",", 1)
                lng, lat = float(lng_text), float(lat_text)
            except (ValueError, AttributeError):
                lng, lat = 0.0, 0.0
            places.append(
                Place(
                    provider=self.name,
                    name=row.get("name") or "",
                    address=row.get("address"),
                    telephone=row.get("phone"),
                    point=GeoPoint(lat, lng, "wgs84"),
                    native=GeoPoint(lat, lng, "wgs84"),
                    raw=row,
                )
            )
        return places

    def geocode(self, address: str) -> GeoPoint:
        if not self.enabled:
            raise ToolError("GEOCODE_FAILED", "未配置天地图 tk")
        data = self.client.get(
            "/geocoder",
            {
                "postStr": json.dumps({"addr": address, "level": 12}, ensure_ascii=False),
                "type": "geocode",
                "tk": self.key,
            },
        )
        _raise_status(data)
        try:
            location = data.get("location") or data["result"]["location"]
            lng = float(location["lon"])
            lat = float(location["lat"])
        except (KeyError, TypeError, ValueError):
            raise ToolError("GEOCODE_FAILED", f"天地图无法解析地址：{address}")
        return GeoPoint(lat, lng, "wgs84")

    def route(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> Route:
        if not self.enabled:
            raise ToolError("NO_ROUTE", "未配置天地图 tk")
        style = "3" if mode == "walking" else "0"
        data = self.client.get(
            "/drive",
            {
                "postStr": json.dumps(
                    {
                        "orig": f"{origin.lng},{origin.lat}",
                        "dest": f"{destination.lng},{destination.lat}",
                        "style": style,
                    },
                    ensure_ascii=False,
                ),
                "tk": self.key,
            },
        )
        _raise_status(data)
        try:
            route = (data.get("result") or data)["routes"][0]
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
            raise ToolError("NO_ROUTE", "天地图未找到可用路线")
