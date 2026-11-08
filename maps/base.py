from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float
    system: str = "wgs84"


@dataclass
class Place:
    provider: str
    name: str
    address: str | None
    telephone: str | None
    point: GeoPoint
    native: GeoPoint
    adcode: str | None = None
    sources: list[dict] = field(default_factory=list)
    confidence: str = "low"
    discrepancies: list[str] = field(default_factory=list)
    data_source: str | None = None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class Route:
    provider: str
    distance_m: int
    duration_s: int
    steps: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    confidence: str = "low"
    discrepancies: list[str] = field(default_factory=list)


@dataclass
class GeocodeResult:
    point: GeoPoint
    sources: list[dict] = field(default_factory=list)
    confidence: str = "low"
    discrepancies: list[str] = field(default_factory=list)


class MapProvider(Protocol):
    name: str
    enabled: bool

    def place_search(self, query: str, region: str, limit: int) -> list[Place]: ...

    def geocode(self, address: str) -> GeoPoint: ...

    def route(
        self, origin: GeoPoint, destination: GeoPoint, mode: str
    ) -> Route: ...
