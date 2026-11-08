from __future__ import annotations

from dataclasses import replace

import httpx

from config import Settings
from coord import haversine_m
from errors import ToolError
from maps.baidu_provider import BaiduProvider
from maps.base import GeocodeResult, GeoPoint, Place, Route
from maps.crosscheck import (
    match_places,
    place_confidence,
    place_discrepancies,
    route_confidence,
    route_discrepancies,
)
from maps.tencent_provider import TencentProvider
from maps.tianditu_provider import TiandituProvider


def _source(place: Place) -> dict:
    return {
        "provider": place.provider,
        "name": place.name,
        "address": place.address,
        "telephone": place.telephone,
        "lat": place.native.lat,
        "lng": place.native.lng,
        "coord_system": place.native.system,
    }


class MapService:
    def __init__(
        self,
        settings: Settings,
        providers=None,
        transport: httpx.BaseTransport | None = None,
        now=None,
        cross_check: bool | None = None,
        failure_mode: str | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.now = now
        self.cross_check = (
            settings.map_cross_check if cross_check is None else cross_check
        )
        self.failure_mode = failure_mode or settings.map_live_failure_mode
        self.providers = (
            providers
            if providers is not None
            else self._default_providers(settings, transport, now)
        )

    @staticmethod
    def _default_providers(settings: Settings, transport, now):
        if not settings.use_live:
            return [BaiduProvider(settings, transport=transport, now=now)]
        providers = []
        for name in settings.map_providers:
            if name == "baidu":
                providers.append(BaiduProvider(settings, transport=transport, now=now))
            elif name == "tencent" and settings.tencent_map_key:
                providers.append(
                    TencentProvider(settings, transport=transport, now=now)
                )
            elif name == "tianditu" and settings.tianditu_key:
                providers.append(
                    TiandituProvider(settings, transport=transport, now=now)
                )
        return providers

    def _mock_baidu(self) -> BaiduProvider:
        mock_settings = replace(
            self.settings, use_live=False, use_mock=True
        )
        return BaiduProvider(mock_settings, now=self.now)

    def _all_failed(self, errors: dict[str, str]) -> ToolError:
        detail = "；".join(f"{name}: {code}" for name, code in errors.items())
        return ToolError(
            "ALL_SOURCES_FAILED",
            f"所有地图源都不可用（{detail or '无可用 provider'}），请检查 key/配额或改用缓存",
        )

    def _merge_places(self, groups: list[Place]) -> list[Place]:
        merged: list[Place] = []
        for place in groups:
            for existing in merged:
                if match_places(existing, place):
                    existing.sources.append(_source(place))
                    existing.confidence = place_confidence(existing.sources)
                    existing.discrepancies = place_discrepancies(existing.sources)
                    break
            else:
                place.sources = [_source(place)]
                place.confidence = "low"
                place.discrepancies = []
                place.data_source = "map"
                merged.append(place)
        return merged

    def place_search(self, query: str, region: str, limit: int) -> list[Place]:
        errors: dict[str, str] = {}
        successes: list[Place] = []
        for provider in self.providers:
            if not getattr(provider, "enabled", True):
                continue
            try:
                places = provider.place_search(query, region, limit)
            except ToolError as exc:
                errors[provider.name] = exc.code
                continue
            if places:
                successes.extend(places)
            else:
                errors[provider.name] = "NO_RESULTS"
            if not self.cross_check and successes:
                break

        if successes:
            return self._merge_places(successes)[:limit]

        if self.failure_mode == "fixtures":
            return self._mock_baidu().place_search(query, region, limit)[:limit]
        if not self.settings.use_live and self.failure_mode == "cache":
            raise ToolError("NO_RESULTS", "未找到匹配机构，请换关键词或区县")
        raise self._all_failed(errors)

    def geocode(self, address: str) -> GeocodeResult:
        errors: dict[str, str] = {}
        collected: list[tuple[str, GeoPoint]] = []
        for provider in self.providers:
            if not getattr(provider, "enabled", True):
                continue
            try:
                point = provider.geocode(address)
            except ToolError as exc:
                errors[provider.name] = exc.code
                continue
            collected.append((provider.name, point))
            if not self.cross_check:
                break

        if not collected:
            if self.failure_mode == "fixtures":
                point = self._mock_baidu().geocode(address)
                return GeocodeResult(
                    point=point,
                    sources=[
                        {
                            "provider": "baidu",
                            "lat": point.lat,
                            "lng": point.lng,
                            "coord_system": point.system,
                        }
                    ],
                    confidence="low",
                    discrepancies=["fixtures"],
                )
            if not self.settings.use_live and self.failure_mode == "cache":
                raise ToolError("GEOCODE_FAILED", f"无法解析地址：{address}")
            raise self._all_failed(errors)

        primary = collected[0][1]
        sources = [
            {
                "provider": name,
                "lat": point.lat,
                "lng": point.lng,
                "coord_system": point.system,
            }
            for name, point in collected
        ]
        distances = [
            haversine_m((primary.lng, primary.lat), (point.lng, point.lat))
            for _, point in collected[1:]
        ]
        max_distance = max(distances, default=0.0)
        if len(sources) < 2:
            confidence = "low"
        elif max_distance <= 500:
            confidence = "high"
        elif max_distance <= 1000:
            confidence = "medium"
        else:
            confidence = "conflict"
        discrepancies = [
            f"{collected[i + 1][0]} 与 {collected[0][0]} 坐标距离约 {round(distance)} 米"
            for i, distance in enumerate(distances)
            if distance > 500
        ]
        return GeocodeResult(
            point=primary,
            sources=sources,
            confidence=confidence,
            discrepancies=discrepancies,
        )

    def route(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> Route:
        errors: dict[str, str] = {}
        routes: list[Route] = []
        for provider in self.providers:
            if not getattr(provider, "enabled", True):
                continue
            try:
                route = provider.route(origin, destination, mode)
            except ToolError as exc:
                errors[provider.name] = exc.code
                continue
            routes.append(route)
            if not self.cross_check:
                break

        if not routes:
            if self.failure_mode == "fixtures":
                return self._mock_baidu().route(origin, destination, mode)
            if not self.settings.use_live and self.failure_mode == "cache":
                raise ToolError("NO_ROUTE", "未找到可用路线，请检查起点和终点")
            raise self._all_failed(errors)

        primary = routes[0]
        primary.sources = [
            {
                "provider": item.provider,
                "distance_m": item.distance_m,
                "duration_s": item.duration_s,
            }
            for item in routes
        ]
        primary.confidence = route_confidence(primary.sources)
        primary.discrepancies = route_discrepancies(primary.sources)
        return primary
