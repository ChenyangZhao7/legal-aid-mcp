from maps.base import GeoPoint, Place
from maps.crosscheck import (
    match_places,
    name_similarity,
    normalize_name,
    place_confidence,
    place_discrepancies,
    route_confidence,
    route_discrepancies,
)


def place(provider, name, address, lng=117.0, lat=36.67, phone=None):
    return Place(
        provider=provider,
        name=name,
        address=address,
        telephone=phone,
        point=GeoPoint(lat, lng),
        native=GeoPoint(lat, lng, "wgs84"),
    )


def test_normalize_name():
    assert normalize_name("济南市历下区人民法院") == normalize_name(
        "山东省济南市历下区人民法院"
    )


def test_name_similarity():
    assert name_similarity("济南市中级人民法院", "济南市中级人民法院") == 1.0
    assert name_similarity("济南市中级人民法院", "济南市历下区人民法院") < 0.8


def test_match_same_place():
    a = place("baidu", "济南市中级人民法院", "经二路1号")
    b = place("tencent", "济南市中级人民法院", "经二路1号", lng=117.0005, lat=36.6705)
    assert match_places(a, b)


def test_far_apart_same_address_is_conflict():
    a = place("baidu", "济南市中级人民法院", "经二路1号")
    b = place("tianditu", "济南市中级人民法院", "经二路1号", lng=117.02, lat=36.68)
    assert match_places(a, b)
    assert place_confidence(
        [
            {"provider": "baidu", "name": a.name, "address": a.address, "lng": 117.0, "lat": 36.67},
            {"provider": "tianditu", "name": b.name, "address": b.address, "lng": 117.02, "lat": 36.68},
        ]
    ) == "conflict"


def test_confidence_high():
    assert place_confidence(
        [
            {
                "name": "济南市中级人民法院",
                "address": "经二路1号",
                "telephone": "12368",
                "lng": 117.0,
                "lat": 36.67,
            },
            {
                "name": "济南市中级人民法院",
                "address": "经二路1号",
                "telephone": "12368",
                "lng": 117.0005,
                "lat": 36.6705,
            },
        ]
    ) == "high"


def test_discrepancies_distance():
    got = place_discrepancies(
        [
            {
                "provider": "baidu",
                "name": "济南市中级人民法院",
                "address": "经二路1号",
                "lng": 117.0,
                "lat": 36.67,
            },
            {
                "provider": "tencent",
                "name": "济南市中级人民法院",
                "address": "经二路1号",
                "lng": 117.02,
                "lat": 36.68,
            },
        ]
    )
    assert any("距离" in item for item in got)


def test_route_confidence():
    assert route_confidence(
        [
            {"provider": "baidu", "distance_m": 1000, "duration_s": 600},
            {"provider": "tencent", "distance_m": 1050, "duration_s": 620},
        ]
    ) == "high"


def test_route_discrepancies():
    got = route_discrepancies(
        [
            {"provider": "baidu", "distance_m": 1000, "duration_s": 600},
            {"provider": "tencent", "distance_m": 2000, "duration_s": 1200},
        ]
    )
    assert got
