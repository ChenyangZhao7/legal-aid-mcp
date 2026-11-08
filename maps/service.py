from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from datetime import datetime, timezone

import httpx

from baidu import CacheStore
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
        "lat": place.point.lat,
        "lng": place.point.lng,
        "coord_system": "wgs84",
        "native_lat": place.native.lat,
        "native_lng": place.native.lng,
        "native_coord_system": place.native.system,
    }


def _place_payload(place: Place) -> dict:
    return {
        "provider": place.provider,
        "name": place.name,
        "address": place.address,
        "telephone": place.telephone,
        "point": [place.point.lat, place.point.lng, place.point.system],
        "native": [place.native.lat, place.native.lng, place.native.system],
        "adcode": place.adcode,
        "sources": place.sources,
        "confidence": place.confidence,
        "discrepancies": place.discrepancies,
        "warnings": place.warnings,
        "data_source": place.data_source,
    }


def _place_from_payload(payload: dict) -> Place:
    point = payload["point"]
    native = payload["native"]
    return Place(
        provider=payload["provider"],
        name=payload["name"],
        address=payload.get("address"),
        telephone=payload.get("telephone"),
        point=GeoPoint(point[0], point[1], point[2]),
        native=GeoPoint(native[0], native[1], native[2]),
        adcode=payload.get("adcode"),
        sources=payload.get("sources") or [],
        confidence=payload.get("confidence") or "low",
        discrepancies=payload.get("discrepancies") or [],
        warnings=payload.get("warnings") or [],
        data_source=payload.get("data_source"),
    )


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
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.result_cache = CacheStore(
            settings.cache_dir, settings.cache_ttl_hours, self.now
        )
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

    def _merge_places(self, groups: list[Place], errors: dict[str, str]) -> list[Place]:
        warnings = [
            {"provider": name, "code": code} for name, code in errors.items()
        ]
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
                place.data_source = "mock" if not self.settings.use_live else "map"
                place.warnings = list(warnings)
                merged.append(place)
        for place in merged:
            if not place.warnings:
                place.warnings = list(warnings)
        return merged

    def place_search(self, query: str, region: str, limit: int) -> list[Place]:
        errors: dict[str, str] = {}
        successes: list[Place] = []
        any_success = False
        cache_key = hashlib.sha256(
            f"map_place:{query}:{region}:{limit}".encode("utf-8")
        ).hexdigest()
        for provider in self.providers:
            if not getattr(provider, "enabled", True):
                continue
            try:
                places = provider.place_search(query, region, limit)
                any_success = True
            except Exception as exc:  # isolate malformed providers
                errors[provider.name] = getattr(exc, "code", "INTERNAL")
                continue
            successes.extend(places)
            if not self.cross_check and successes:
                break

        if successes:
            merged = self._merge_places(successes, errors)[:limit]
            self.result_cache.set(
                cache_key, {"places": [_place_payload(place) for place in merged]}
            )
            return merged

        if self.failure_mode == "fixtures":
            places = self._mock_baidu().place_search(query, region, limit)[:limit]
            for place in places:
                place.mock = True
                place.data_source = "fixtures"
                place.warnings = list(place.warnings) + [
                    {"code": "FIXTURE_FALLBACK", "message": "使用本地样本，不是实时地图结果"}
                ]
            return places

        if self.failure_mode == "cache":
            cached = self.result_cache.get(cache_key)
            if cached:
                places = [
                    _place_from_payload(payload)
                    for payload in cached.get("places") or []
                ]
                for place in places:
                    place.cached = True
                    place.data_source = "cache"
                    place.warnings = list(place.warnings) + [
                        {"code": "CACHED", "message": "所有地图源失败，返回最近缓存"}
                    ]
                return places[:limit]
            if not self.settings.use_live:
                raise ToolError("NO_RESULTS", "未找到匹配机构，请换关键词或区县")

        if any_success:
            raise ToolError("NO_RESULTS", "未找到匹配机构，请换关键词或区县")
        raise self._all_failed(errors)

    def geocode(self, address: str) -> GeocodeResult:
        errors: dict[str, str] = {}
        collected: list[tuple[str, GeoPoint]] = []
        cache_key = hashlib.sha256(
            f"map_geocode:{address}".encode("utf-8")
        ).hexdigest()
        for provider in self.providers:
            if not getattr(provider, "enabled", True):
                continue
            try:
                point = provider.geocode(address)
            except Exception as exc:  # isolate malformed providers
                errors[provider.name] = getattr(exc, "code", "INTERNAL")
                continue
            collected.append((provider.name, point))
            if not self.cross_check:
                break

        warnings = [{"provider": name, "code": code} for name, code in errors.items()]
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
                    warnings=[{"code": "FIXTURE_FALLBACK"}],
                    mock=True,
                )
            if self.failure_mode == "cache":
                cached = self.result_cache.get(cache_key)
                if cached:
                    point = cached["point"]
                    return GeocodeResult(
                        point=GeoPoint(point[0], point[1], point[2]),
                        sources=cached.get("sources") or [],
                        confidence=cached.get("confidence") or "low",
                        discrepancies=cached.get("discrepancies") or [],
                        warnings=warnings + [{"code": "CACHED"}],
                        cached=True,
                    )
                if not self.settings.use_live:
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
        result = GeocodeResult(
            point=primary,
            sources=sources,
            confidence=confidence,
            discrepancies=discrepancies,
            warnings=warnings,
            mock=not self.settings.use_live,
        )
        self.result_cache.set(
            cache_key,
            {
                "point": [primary.lat, primary.lng, primary.system],
                "sources": sources,
                "confidence": confidence,
                "discrepancies": discrepancies,
            },
        )
        return result

    def route(self, origin: GeoPoint, destination: GeoPoint, mode: str) -> Route:
        errors: dict[str, str] = {}
        routes: list[Route] = []
        cache_key = hashlib.sha256(
            f"map_route:{origin.lat},{origin.lng}:{destination.lat},{destination.lng}:{mode}".encode(
                "utf-8"
            )
        ).hexdigest()
        for provider in self.providers:
            if not getattr(provider, "enabled", True):
                continue
            try:
                route = provider.route(origin, destination, mode)
            except Exception as exc:  # isolate malformed providers
                errors[provider.name] = getattr(exc, "code", "INTERNAL")
                continue
            routes.append(route)
            if not self.cross_check:
                break

        warnings = [{"provider": name, "code": code} for name, code in errors.items()]
        if not routes:
            if self.failure_mode == "fixtures":
                route = self._mock_baidu().route(origin, destination, mode)
                route.mock = True
                route.data_source = "fixtures"
                route.warnings = [{"code": "FIXTURE_FALLBACK"}]
                return route
            if self.failure_mode == "cache":
                cached = self.result_cache.get(cache_key)
                if cached:
                    route = Route(**cached["route"])
                    route.cached = True
                    route.data_source = "cache"
                    route.warnings = route.warnings + [{"code": "CACHED"}]
                    return route
                if not self.settings.use_live:
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
        primary.warnings = list(primary.warnings) + warnings
        primary.data_source = "mock" if not self.settings.use_live else "map"
        self.result_cache.set(cache_key, {"route": asdict(primary)})
        return primary
