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

async def test_plan_route_address_with_comma_is_not_coordinates(server):
    data = await call(server, "plan_route", {"origin": "济南市历下区,经十路", "destination": "济南市中级人民法院"})
    assert data["error"]["code"] == "GEOCODE_FAILED"
