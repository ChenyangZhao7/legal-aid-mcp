import json, os, sys
from pathlib import Path
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.asyncio
async def test_stdio_lists_four_tools():
    env = {**os.environ, "USE_MOCK": "1", "USE_LIVE": "0", "LAW_DATA_DIR": str(ROOT / "data" / "laws")}
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "find_legal_service", "plan_route", "search_law", "verify_citation"
            }
            result = await session.call_tool("search_law", {"query": "违约金过高"})
            data = json.loads(result.content[0].text)
            assert data[0]["article"] == "第五百八十五条"
