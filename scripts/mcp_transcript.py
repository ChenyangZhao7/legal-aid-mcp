from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

CALLS = [
    ("find_legal_service", {"keyword": "法院", "city": "济南", "limit": 3}),
    ("plan_route", {"origin": "济南西站", "destination": "济南市中级人民法院"}),
    ("search_law", {"query": "违约金过高", "limit": 3}),
    ("verify_citation", {"text": "依据《中华人民共和国民法典》第五百八十五条"}),
    ("legal_calculator", {"action": "litigation_fee", "amount": 100000, "case_type": "财产案件"}),
]


async def main(out_path: Path) -> None:
    env = {
        **os.environ,
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "LAW_DATA_DIR": str(ROOT / "data" / "laws"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "server.py")],
        env=env,
        cwd=str(ROOT),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            calls = []
            for name, arguments in CALLS:
                result = await session.call_tool(name, arguments)
                calls.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "result": json.loads(result.content[0].text),
                    }
                )
            transcript = {
                "tools": [tool.name for tool in tools.tools],
                "calls": calls,
            }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 stdio JSON-RPC 对话记录")
    parser.add_argument("--out", default="docs/mcp-transcript.json")
    args = parser.parse_args()
    asyncio.run(main(ROOT / args.out))
