import json, os, sys
from pathlib import Path
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import load_settings
from server import create_server

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.asyncio
async def test_stdio_lists_five_tools():
    env = {**os.environ, "USE_MOCK": "1", "USE_LIVE": "0", "LAW_DATA_DIR": str(ROOT / "data" / "laws")}
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "find_legal_service",
                "plan_route",
                "search_law",
                "verify_citation",
                "legal_calculator",
            }
            result = await session.call_tool("search_law", {"query": "违约金过高"})
            data = json.loads(result.content[0].text)
            assert data[0]["article"] == "第五百八十五条"

@pytest.mark.asyncio
async def test_every_tool_parameter_has_description(tmp_path):
    settings = load_settings(env={
        "USE_MOCK": "1",
        "USE_LIVE": "0",
        "CACHE_DIR": str(tmp_path / "cache"),
        "LAW_DATA_DIR": str(ROOT / "data" / "laws"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }, base_dir=tmp_path)
    tools = await create_server(settings).list_tools()
    missing = [
        (tool.name, name)
        for tool in tools
        for name, schema in tool.input_schema.get("properties", {}).items()
        if not schema.get("description")
    ]
    assert missing == []
