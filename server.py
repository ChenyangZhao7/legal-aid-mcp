from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

from config import Settings, load_settings

if TYPE_CHECKING:
    import httpx


def create_server(
    settings: Settings | None = None,
    transport: "httpx.BaseTransport | None" = None,
) -> MCPServer:
    settings = settings or load_settings()
    server = MCPServer("legal-aid-mcp")
    # Tools are registered in Task 9, once BaiduClient and LawCorpus exist.
    return server


if __name__ == "__main__":
    create_server().run("stdio")
