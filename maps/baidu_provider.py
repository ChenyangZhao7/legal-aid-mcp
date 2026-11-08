from __future__ import annotations

import httpx

from baidu import BaiduClient
from config import Settings
from coord import bd09_to_wgs84, wgs84_to_bd09
from maps.base import GeoPoint, Place, Route


class BaiduProvider:
    name = "baidu"
    enabled = True

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        now=None,
    ) -> None:
        self.settings = settings
        self.mock = not settings.use_live
        self.client = BaiduClient(settings, transport=transport, now=now)

    def place_search(self, query: str, region: str, limit: int) -> list[Place]:
        places: list[Place] = []
        for row in self.client.place_search(query, region, limit):
            location = row.get("location") or {}
            lat = float(location.get("lat") or 0.0)
            lng = float(location.get("lng") or 0.0)
            wgs_lng, wgs_lat = bd09_to_wgs84(lng, lat)
            places.append(
                Place(
                    provider=self.name,
                    name=row.get("name") or "",
                    address=row.get("address"),
                    telephone=row.get("telephone"),
                    point=GeoPoint(wgs_lat, wgs_lng, "wgs84"),
                    native=GeoPoint(lat, lng, "bd09"),
                    raw=row,
                    mock=self.mock,
                    data_source="mock" if self.mock else "map",
                )
            )
        return places

    def geocode(self, address: str) -> GeoPoint:
        lng, lat = self.client.geocode(address)
        wgs_lng, wgs_lat = bd09_to_wgs84(lng, lat)
        return GeoPoint(wgs_lat, wgs_lng, "wgs84")

    def route(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> Route:
        origin_lng, origin_lat = wgs84_to_bd09(origin.lng, origin.lat)
        dest_lng, dest_lat = wgs84_to_bd09(destination.lng, destination.lat)
        data = self.client.route(
            (origin_lat, origin_lng), (dest_lat, dest_lng), mode
        )
        return Route(
            provider=self.name,
            distance_m=data["distance_m"],
            duration_s=data["duration_s"],
            steps=data.get("steps") or [],
            mock=self.mock,
            data_source="mock" if self.mock else "map",
        )
