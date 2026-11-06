from __future__ import annotations

import httpx
from mcp.server.mcpserver import MCPServer

from baidu import BaiduClient
from config import Settings, load_settings
from context import AppContext
from laws import LawCorpus
from tools.citation import register_citation
from tools.law_search import register_law_search
from tools.legal_service import register_legal_service
from tools.route import register_route


def create_server(
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> MCPServer:
    settings = settings or load_settings()
    server = MCPServer("legal-aid-mcp")
    ctx = AppContext(
        settings=settings,
        baidu=BaiduClient(settings, transport=transport),
        corpus=LawCorpus.load(settings.law_data_dir),
    )
    register_legal_service(server, ctx)
    register_route(server, ctx)
    register_law_search(server, ctx)
    register_citation(server, ctx)
    return server


if __name__ == "__main__":
    create_server().run("stdio")
