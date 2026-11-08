from pathlib import Path

import pytest

from config import load_settings
from errors import ToolError
from maps.base import GeoPoint, Place, Route
from maps.service import MapService

ROOT = Path(__file__).resolve().parents[1]


def settings(tmp_path, **env):
    base = {
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
        "LAW_DATA_DIR": str(ROOT / "data" / "laws"),
    }
    base.update(env)
    return load_settings(env=base, base_dir=tmp_path)


def place(provider, name, lng=117.0, lat=36.67, address="经二路1号"):
    return Place(
        provider=provider,
        name=name,
        address=address,
        telephone="12368",
        point=GeoPoint(lat, lng, "wgs84"),
        native=GeoPoint(lat, lng, "wgs84"),
    )


class FailingProvider:
    name = "failing"
    enabled = True

    def place_search(self, query, region, limit):
        raise ToolError("UPSTREAM_TIMEOUT", "timeout")

    def geocode(self, address):
        raise ToolError("GEOCODE_FAILED", "geocode failed")

    def route(self, origin, destination, mode):
        raise ToolError("NO_ROUTE", "route failed")


class FakeProvider:
    enabled = True

    def __init__(self, name, places, distance=1000, duration=600):
        self.name = name
        self.places = places
        self.distance = distance
        self.duration = duration

    def place_search(self, query, region, limit):
        return self.places[:limit]

    def geocode(self, address):
        return GeoPoint(36.67, 117.0, "wgs84")

    def route(self, origin, destination, mode):
        return Route(self.name, self.distance, self.duration, steps=[])


def test_failover_uses_second_provider(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FailingProvider(), FakeProvider("tencent", [place("tencent", "A")])],
        cross_check=False,
    )
    places = service.place_search("法院", "济南", 5)
    assert places[0].provider == "tencent"


def test_union_keeps_secondary_only_poi(tmp_path):
    baidu = FakeProvider("baidu", [place("baidu", "济南市中级人民法院")])
    tencent = FakeProvider(
        "tencent",
        [
            place("tencent", "济南市中级人民法院", lng=117.0005, lat=36.6705),
            place("tencent", "济南市历下区人民法院", lng=117.04, lat=36.67),
        ],
    )
    service = MapService(settings(tmp_path), providers=[baidu, tencent], cross_check=True)
    places = service.place_search("法院", "济南", 5)
    assert {p.name for p in places} == {"济南市中级人民法院", "济南市历下区人民法院"}
    assert places[0].confidence in {"high", "medium"}


def test_conflict_surfaces(tmp_path):
    baidu = FakeProvider("baidu", [place("baidu", "济南市中级人民法院")])
    tencent = FakeProvider(
        "tencent",
        [place("tencent", "济南市中级人民法院", lng=117.02, lat=36.68)],
    )
    service = MapService(settings(tmp_path), providers=[baidu, tencent], cross_check=True)
    places = service.place_search("法院", "济南", 5)
    assert len(places) == 1
    assert places[0].confidence == "conflict"
    assert places[0].discrepancies


def test_all_failed_raises(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FailingProvider()],
        cross_check=False,
        failure_mode="error",
    )
    with pytest.raises(ToolError) as exc:
        service.place_search("法院", "济南", 5)
    assert exc.value.code == "ALL_SOURCES_FAILED"


def test_fixtures_fallback(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FailingProvider()],
        cross_check=False,
        failure_mode="fixtures",
    )
    places = service.place_search("人民法院", "济南", 5)
    assert any("济南市中级人民法院" in p.name for p in places)


def test_route_cross_check(tmp_path):
    baidu = FakeProvider("baidu", [], distance=1000, duration=600)
    tencent = FakeProvider("tencent", [], distance=1050, duration=620)
    service = MapService(settings(tmp_path), providers=[baidu, tencent], cross_check=True)
    route = service.route(
        GeoPoint(36.67, 117.0), GeoPoint(36.68, 117.1), "driving"
    )
    assert route.distance_m == 1000
    assert route.confidence == "high"
    assert len(route.sources) == 2


def test_geocode_failover(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FailingProvider(), FakeProvider("tencent", [])],
        cross_check=False,
    )
    result = service.geocode("济南市中级人民法院")
    assert result.point.system == "wgs84"
    assert result.sources[0]["provider"] == "tencent"


def test_crosscheck_uses_wgs84_not_native(tmp_path):
    baidu_place = place("baidu", "济南市中级人民法院")
    baidu_place.native = GeoPoint(36.671, 117.012, "bd09")
    tencent_place = place("tencent", "济南市中级人民法院")
    tencent_place.native = GeoPoint(36.67, 117.0, "gcj02")
    service = MapService(
        settings(tmp_path),
        providers=[
            FakeProvider("baidu", [baidu_place]),
            FakeProvider("tencent", [tencent_place]),
        ],
        cross_check=True,
    )
    places = service.place_search("法院", "济南", 5)
    assert places[0].confidence == "high"
    assert not any("距离" in item for item in places[0].discrepancies)


def test_secondary_failure_is_surfaced(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FakeProvider("baidu", [place("baidu", "A")]), FailingProvider()],
        cross_check=True,
    )
    places = service.place_search("法院", "济南", 5)
    assert places[0].name == "A"
    assert places[0].warnings


def test_non_tool_error_does_not_wipe_primary(tmp_path):
    class BrokenProvider:
        name = "tencent"
        enabled = True

        def place_search(self, query, region, limit):
            raise ValueError("bad json")

        def geocode(self, address):
            raise ValueError("bad")

        def route(self, origin, destination, mode):
            raise ValueError("bad")

    service = MapService(
        settings(tmp_path),
        providers=[FakeProvider("baidu", [place("baidu", "A")]), BrokenProvider()],
        cross_check=True,
    )
    places = service.place_search("法院", "济南", 5)
    assert places[0].name == "A"


def test_all_empty_is_no_results(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FakeProvider("baidu", []), FakeProvider("tencent", [])],
        cross_check=True,
    )
    with pytest.raises(ToolError) as exc:
        service.place_search("法院", "济南", 5)
    assert exc.value.code == "NO_RESULTS"


def test_fixtures_fallback_is_marked(tmp_path):
    service = MapService(
        settings(tmp_path),
        providers=[FailingProvider()],
        cross_check=False,
        failure_mode="fixtures",
    )
    places = service.place_search("人民法院", "济南", 5)
    assert places[0].mock is True
    assert places[0].data_source == "fixtures"


def test_cache_mode_returns_cached_result(tmp_path):
    state = {"fail": False}

    class FlakyProvider:
        name = "baidu"
        enabled = True

        def place_search(self, query, region, limit):
            if state["fail"]:
                raise ToolError("UPSTREAM_TIMEOUT", "timeout")
            return [place("baidu", "济南市中级人民法院")]

        def geocode(self, address):
            return GeoPoint(36.67, 117.0, "wgs84")

        def route(self, origin, destination, mode):
            return Route("baidu", 1000, 600)

    service = MapService(
        settings(tmp_path),
        providers=[FlakyProvider()],
        cross_check=False,
        failure_mode="cache",
    )
    first = service.place_search("法院", "济南", 5)
    assert first[0].cached is False
    state["fail"] = True
    second = service.place_search("法院", "济南", 5)
    assert second[0].cached is True
    assert second[0].name == "济南市中级人民法院"
