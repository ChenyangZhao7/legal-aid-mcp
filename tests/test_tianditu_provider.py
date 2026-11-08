from pathlib import Path

import httpx
import pytest

from config import load_settings
from errors import ToolError
from maps.base import GeoPoint
from maps.tianditu_provider import TiandituProvider

ROOT = Path(__file__).resolve().parents[1]


def settings(tmp_path, **env):
    base = {
        "USE_LIVE": "1",
        "USE_MOCK": "1",
        "BAIDU_AK": "test-ak",
        "TIANDITU_KEY": "test-tk",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
        "LAW_DATA_DIR": str(ROOT / "data" / "laws"),
    }
    base.update(env)
    return load_settings(env=base, base_dir=tmp_path)


def handler(request):
    path = request.url.path
    if "search" in path:
        return httpx.Response(
            200,
            json={
                "resultType": 1,
                "count": 1,
                "pois": [
                    {
                        "name": "济南市中级人民法院",
                        "address": "经二路1号",
                        "phone": "12368",
                        "lonlat": "117.012747,36.671879",
                    }
                ],
            },
        )
    if "geocoder" in path:
        return httpx.Response(
            200,
            json={
                "status": "0",
                "location": {"lon": 117.012747, "lat": 36.671879},
            },
        )
    return httpx.Response(
        200,
        json={
            "status": "0",
            "result": {
                "routes": [
                    {
                        "distance": 14205,
                        "duration": 2462,
                        "steps": [
                            {
                                "instruction": "沿经二路",
                                "road_name": "经二路",
                                "distance": 100,
                                "duration": 20,
                            }
                        ],
                    }
                ]
            },
        },
    )


def test_place_search(tmp_path):
    provider = TiandituProvider(settings(tmp_path), transport=httpx.MockTransport(handler))
    places = provider.place_search("人民法院", "济南", 5)
    assert places[0].name == "济南市中级人民法院"
    assert places[0].point.system == "wgs84"
    assert places[0].native.system == "wgs84"


def test_geocode(tmp_path):
    provider = TiandituProvider(settings(tmp_path), transport=httpx.MockTransport(handler))
    point = provider.geocode("济南市中级人民法院")
    assert point.system == "wgs84"
    assert 36 < point.lat < 38


def test_route(tmp_path):
    provider = TiandituProvider(settings(tmp_path), transport=httpx.MockTransport(handler))
    route = provider.route(GeoPoint(36.67, 117.0), GeoPoint(36.68, 117.1), "driving")
    assert route.distance_m == 14205
    assert route.steps[0]["road_name"] == "经二路"


def test_no_key_disabled(tmp_path):
    provider = TiandituProvider(settings(tmp_path, TIANDITU_KEY=""))
    assert provider.enabled is False


def test_error_maps(tmp_path):
    def bad_handler(request):
        return httpx.Response(200, json={"status": "1", "message": "bad"})

    provider = TiandituProvider(
        settings(tmp_path), transport=httpx.MockTransport(bad_handler)
    )
    with pytest.raises(ToolError) as exc:
        provider.place_search("人民法院", "济南", 5)
    assert exc.value.code == "UPSTREAM_ERROR"


def test_status_dict_success(tmp_path):
    def dict_handler(request):
        return httpx.Response(
            200,
            json={
                "status": {"infocode": 1000, "cndesc": "服务正常"},
                "count": 1,
                "pois": [
                    {
                        "name": "济南市中级人民法院",
                        "address": "经二路1号",
                        "lonlat": "117.012747,36.671879",
                    }
                ],
            },
        )

    provider = TiandituProvider(
        settings(tmp_path), transport=httpx.MockTransport(dict_handler)
    )
    places = provider.place_search("人民法院", "济南", 5)
    assert places[0].name == "济南市中级人民法院"
