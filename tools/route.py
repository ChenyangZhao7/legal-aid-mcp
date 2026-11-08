from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from errors import run_tool

_POINT_RE = re.compile(r"^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$")


def parse_point(value: str) -> tuple[float, float] | None:
    """Parse 'lat,lng'. Addresses that happen to contain a comma return None."""
    text = value.strip()
    if not _POINT_RE.match(text):
        return None
    lat_text, lng_text = text.split(",", 1)
    return float(lat_text.strip()), float(lng_text.strip())


def _to_point(ctx: AppContext, value: str) -> tuple[float, float]:
    point = parse_point(value)
    if point is not None:
        return point
    lng, lat = ctx.baidu.geocode(value)
    return lat, lng


def _plan(ctx: AppContext, origin: str, destination: str, mode: str) -> dict:
    origin_point = _to_point(ctx, origin)
    destination_point = _to_point(ctx, destination)
    return ctx.baidu.route(origin_point, destination_point, mode)


def register_route(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "规划从起点到终点的驾车或步行路线，返回距离、预计时间和主要路段。"
            "用户问“怎么去法院/律所/法律援助中心”时使用。起点和终点可以是地址或"
            "“纬度,经度”；如果只有机构名，先用 find_legal_service 查地址。"
        ),
        structured_output=False,
    )
    def plan_route(
        origin: Annotated[
            str,
            Field(description="起点地址，或“纬度,经度”坐标，如 36.67,117.0"),
        ],
        destination: Annotated[
            str,
            Field(description="终点地址，或“纬度,经度”坐标"),
        ],
        mode: Annotated[
            Literal["driving", "walking"],
            Field(description="出行方式：driving 驾车（默认）或 walking 步行"),
        ] = "driving",
    ) -> str:
        return json.dumps(
            run_tool(lambda: _plan(ctx, origin, destination, mode)),
            ensure_ascii=False,
        )
