import json
from pathlib import Path

import pytest
from mcp.server.mcpserver import MCPServer

from baidu import BaiduClient
from config import load_settings
from context import AppContext
from laws import LawCorpus
from tools.calculator import register_calculator

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def server(tmp_path):
    s = load_settings(
        env={
            "USE_LIVE": "0",
            "USE_MOCK": "1",
            "CACHE_DIR": str(tmp_path / "cache"),
            "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
            "LAW_DATA_DIR": str(ROOT / "data" / "laws"),
        },
        base_dir=tmp_path,
    )
    ctx = AppContext(
        settings=s,
        baidu=BaiduClient(s),
        corpus=LawCorpus.load(ROOT / "data" / "laws"),
    )
    mcp = MCPServer("test")
    register_calculator(mcp, ctx)
    return mcp


async def call(mcp, name, args):
    result = await mcp.call_tool(name, args)
    return json.loads(result.content[0].text)


async def test_calculator_fee(server):
    data = await call(
        server,
        "legal_calculator",
        {"action": "litigation_fee", "amount": 100000, "case_type": "财产案件"},
    )
    assert data["fee"] == 2300.0
    assert data["legal_basis"]["article"] == "第十三条"


async def test_calculator_deadline(server):
    data = await call(
        server,
        "legal_calculator",
        {"action": "deadline", "start_date": "2026-11-06", "days": 15, "day_type": "natural"},
    )
    assert data["end_date"] == "2026-11-23"
    assert data["legal_basis"]["article"] == "第八十五条"


async def test_calculator_preservation(server):
    data = await call(
        server,
        "legal_calculator",
        {"action": "preservation_fee", "amount": 10_000_000},
    )
    assert data["fee"] == 5000.0
    assert data["legal_basis"]["article"] == "第十四条"


async def test_calculator_invalid(server):
    data = await call(server, "legal_calculator", {"action": "deadline"})
    assert data["error"]["code"] == "CALCULATION_INVALID"
