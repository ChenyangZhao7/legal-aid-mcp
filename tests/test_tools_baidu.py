import json
from pathlib import Path
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
from baidu import BaiduClient
from config import load_settings
from context import AppContext
from laws import LawCorpus
from tools.legal_service import register_legal_service
from tools.route import register_route, parse_point

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def server(tmp_path):
    s = load_settings(env={
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }, base_dir=tmp_path)
    ctx = AppContext(settings=s, baidu=BaiduClient(s), corpus=LawCorpus.load(ROOT / "data" / "laws"))
    mcp = MCPServer("test")
    register_legal_service(mcp, ctx)
    register_route(mcp, ctx)
    return mcp

async def call(mcp, name, args):
    result = await mcp.call_tool(name, args)
    return json.loads(result.content[0].text)

async def test_find_court(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "city": "济南"})
    assert any("济南市中级人民法院" in r["name"] for r in data)

async def test_find_law_firm(server):
    data = await call(server, "find_legal_service", {"keyword": "律师事务所", "limit": 5})
    assert len(data) >= 1

async def test_find_lixia_court(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "district": "历下区", "limit": 5})
    assert "历下区" in data[0]["name"]

async def test_city_not_found(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "city": "火星"})
    assert data["error"]["code"] == "CITY_NOT_FOUND"
    assert "v1" not in data["error"]["message"]


async def test_duplicate_address_is_cleared(server):
    data = await call(server, "find_legal_service", {"keyword": "律师事务所"})
    firm = next(row for row in data if "舜达" in row["name"])
    assert firm["address"] is None
    assert any(warning.get("code") == "ADDRESS_MISSING" for warning in firm["warnings"])


async def test_mock_results_are_marked(server):
    data = await call(server, "find_legal_service", {"keyword": "法院"})
    assert data[0]["mock"] is True
    assert data[0]["source"] == "mock"

async def test_limit_schema_rejects_11(server):
    with pytest.raises(MCPToolError):
        await server.call_tool("find_legal_service", {"keyword": "法院", "limit": 11})

def test_parse_point_accepts_coordinates():
    assert parse_point("36.67,117.0") == (36.67, 117.0)

def test_parse_point_rejects_address_with_comma():
    assert parse_point("济南市历下区,经十路") is None

async def test_no_results(server, monkeypatch):
    monkeypatch.setattr(BaiduClient, "place_search", lambda *a, **k: [])
    data = await call(server, "find_legal_service", {"keyword": "法院"})
    assert data["error"]["code"] == "NO_RESULTS"

async def test_plan_route_with_addresses(server):
    data = await call(server, "plan_route", {"origin": "济南西站", "destination": "济南市中级人民法院"})
    assert data["distance_m"] > 0

async def test_plan_route_steps_include_road_name(server):
    data = await call(server, "plan_route", {"origin": "济南西站", "destination": "济南市中级人民法院"})
    first = data["steps"][0]
    assert first["instruction"]
    assert first["road_name"]

async def test_find_limit_slices(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "limit": 2})
    assert len(data) == 2

async def test_find_returns_confidence_and_sources(server):
    data = await call(server, "find_legal_service", {"keyword": "法院"})
    assert "confidence" in data[0]
    assert data[0]["sources"]
    assert data[0]["coord_system"] == "wgs84"

async def test_find_legal_aid_uses_official_or_snapshot(server):
    data = await call(server, "find_legal_service", {"keyword": "法律援助中心", "district": "历下区"})
    assert "results" in data
    assert "coverage" in data
    assert any(r["source"] in {"12348", "snapshot"} for r in data["results"])
    assert any("历下区法律援助中心" in r["name"] for r in data["results"])

async def test_find_district_does_not_fall_through(server):
    data = await call(server, "find_legal_service", {"keyword": "律师事务所", "district": "章丘区"})
    assert data["error"]["code"] == "NO_RESULTS"

async def test_find_legal_aid_unavailable_is_not_no_results(server, monkeypatch):
    from errors import ToolError
    from tools import legal_service

    class BadClient:
        def search(self, district=None, limit=5):
            raise ToolError("LEGAL_AID_UNAVAILABLE", "12348 down")

    monkeypatch.setattr(legal_service, "_legal_aid", lambda ctx, divisions: BadClient())
    monkeypatch.setattr(legal_service.MapService, "place_search", lambda *a, **k: [])
    data = await call(server, "find_legal_service", {"keyword": "法律援助中心", "district": "历下区"})
    assert data["error"]["code"] == "LEGAL_AID_UNAVAILABLE"

async def test_plan_route_accepts_wgs84(server):
    data = await call(server, "plan_route", {"origin": "36.67,117.0", "destination": "36.68,117.1"})
    assert data["distance_m"] > 0
    assert data["coord_system"] == "wgs84"

async def test_plan_route_accepts_bd09(server):
    data = await call(server, "plan_route", {
        "origin": "36.67,117.0",
        "destination": "36.68,117.1",
        "coord_system": "bd09",
    })
    assert "distance_m" in data or data["error"]["code"] == "GEOCODE_FAILED"


async def test_plan_route_mock_is_marked(server):
    data = await call(server, "plan_route", {
        "origin": "济南西站",
        "destination": "济南市中级人民法院",
    })
    assert data["mock"] is True
    assert data["source"] == "mock"

async def test_plan_route_coordinates(server):
    data = await call(server, "plan_route", {"origin": "36.67,117.0", "destination": "36.68,117.1"})
    assert data["distance_m"] > 0

async def test_plan_route_address_with_comma_is_not_coordinates(server):
    data = await call(server, "plan_route", {"origin": "济南市历下区,经十路", "destination": "济南市中级人民法院"})
    assert data["error"]["code"] == "GEOCODE_FAILED"
