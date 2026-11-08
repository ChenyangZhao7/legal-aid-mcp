from pathlib import Path

import httpx
import pytest

from config import load_settings
from errors import ToolError
from maps.baidu_provider import BaiduProvider
from maps.live import LiveJsonClient

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


def test_mock_place_is_wgs84(tmp_path):
    provider = BaiduProvider(settings(tmp_path))
    places = provider.place_search("人民法院", "济南", 5)
    assert places[0].name
    assert places[0].point.system == "wgs84"
    assert places[0].native.system == "bd09"
    assert places[0].mock is True


def test_mock_route_is_marked(tmp_path):
    provider = BaiduProvider(settings(tmp_path))
    route = provider.route(
        provider.geocode("济南西站"),
        provider.geocode("济南市中级人民法院"),
        "driving",
    )
    assert route.mock is True


def test_mock_geocode_is_wgs84(tmp_path):
    provider = BaiduProvider(settings(tmp_path))
    point = provider.geocode("济南市中级人民法院")
    assert point.system == "wgs84"
    assert 36 < point.lat < 38


def test_mock_route(tmp_path):
    provider = BaiduProvider(settings(tmp_path))
    route = provider.route(
        provider.geocode("济南西站"),
        provider.geocode("济南市中级人民法院"),
        "driving",
    )
    assert route.distance_m > 0


def test_live_provider_place_search(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "status": 0,
                "results": [
                    {
                        "name": "济南市中级人民法院",
                        "address": "经二路1号",
                        "telephone": "12368",
                        "location": {"lat": 36.671879, "lng": 117.012747},
                    }
                ],
            },
        )

    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    provider = BaiduProvider(s, transport=httpx.MockTransport(handler))
    places = provider.place_search("人民法院", "济南", 5)
    assert places[0].name == "济南市中级人民法院"
    assert places[0].point.system == "wgs84"


def test_live_non_json_maps_to_upstream_error(tmp_path):
    def handler(request):
        return httpx.Response(200, text="<html>bad gateway</html>")

    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    client = LiveJsonClient(
        "tencent",
        "https://apis.map.qq.com",
        s,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ToolError) as exc:
        client.get("/ws/place/v1/search", {"key": "test", "keyword": "法院"})
    assert exc.value.code == "UPSTREAM_ERROR"
    assert "test" not in exc.value.message


def test_live_json_list_maps_to_upstream_error(tmp_path):
    def handler(request):
        return httpx.Response(200, json=[1, 2, 3])

    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    client = LiveJsonClient(
        "tencent",
        "https://apis.map.qq.com",
        s,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ToolError) as exc:
        client.get("/ws/place/v1/search", {"key": "test"})
    assert exc.value.code == "UPSTREAM_ERROR"
