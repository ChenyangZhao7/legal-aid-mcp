from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from baidu import BaiduClient
from config import Settings, load_settings
from context import AppContext
from divisions import DivisionIndex
from holidays import HolidayCalendar
from laws import LawCorpus
from legal_aid import LegalAidClient
from maps.service import MapService
from tools.calculator import register_calculator
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
    data_root: Path = settings.law_data_dir.parent
    divisions_path = data_root / "divisions" / "jinan.json"
    divisions = DivisionIndex.load(divisions_path) if divisions_path.exists() else None
    holidays = HolidayCalendar.load(
        data_root / "holidays",
        datetime.now().year,
        live=settings.use_live and settings.holiday_live,
        transport=transport,
    )
    ctx = AppContext(
        settings=settings,
        baidu=BaiduClient(settings, transport=transport),
        corpus=LawCorpus.load(settings.law_data_dir),
        maps=MapService(settings, transport=transport),
        divisions=divisions,
        legal_aid=LegalAidClient(settings, divisions) if divisions else None,
        holidays=holidays,
    )
    register_legal_service(server, ctx)
    register_route(server, ctx)
    register_law_search(server, ctx)
    register_citation(server, ctx)
    register_calculator(server, ctx)
    return server


if __name__ == "__main__":
    create_server().run("stdio")
