import json
from pathlib import Path
import httpx
import pytest
from baidu import BaiduClient
from config import load_settings
from errors import ToolError

ROOT = Path(__file__).resolve().parents[1]

def settings(tmp_path, **env):
    base = {
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }
    base.update(env)
    return load_settings(env=base, base_dir=tmp_path)

def test_mock_place_court(tmp_path):
    c = BaiduClient(settings(tmp_path))
    rows = c.place_search("人民法院", "济南", 10)
    assert any("济南市中级人民法院" in r["name"] for r in rows)

def test_mock_geocode(tmp_path):
    c = BaiduClient(settings(tmp_path))
    lng, lat = c.geocode("济南市中级人民法院")
    assert 116 < lng < 118 and 36 < lat < 38

def test_mock_route(tmp_path):
    c = BaiduClient(settings(tmp_path))
    r = c.route((36.67, 117.0), (36.68, 117.1), "driving")
    assert r["distance_m"] > 0 and r["duration_s"] > 0

def test_live_quota_maps(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"status": 220, "message": "quota"})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "QUOTA_EXCEEDED"
    assert "test-ak" not in exc.value.message

def test_live_ak_invalid_maps(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"status": 203, "message": "invalid ak"})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "AK_INVALID"

def test_live_timeout_maps(tmp_path):
    def handler(request):
        raise httpx.TimeoutException("timeout")
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "UPSTREAM_TIMEOUT"

def test_live_upstream_error_maps(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"status": 500, "message": "boom"})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "UPSTREAM_ERROR"

def test_live_budget_exhausted(tmp_path):
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"status": 0, "results": []})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak", LIVE_BUDGET="1")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    c.place_search("人民法院", "济南", 5)
    # Different page_size = cache miss, so the budget is checked.
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 6)
    assert exc.value.code == "BUDGET_EXHAUSTED"
    assert calls["n"] == 1

def test_live_cache_hit_does_not_spend(tmp_path):
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"status": 0, "results": [{"name": "x"}]})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak", LIVE_BUDGET="5")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    c.place_search("人民法院", "济南", 5)
    c.place_search("人民法院", "济南", 5)
    assert calls["n"] == 1
