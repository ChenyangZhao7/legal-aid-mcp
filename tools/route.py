from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from coord import bd09_to_wgs84, gcj02_to_wgs84
from errors import run_tool
from maps.base import GeoPoint
from maps.service import MapService

_POINT_RE = re.compile(r"^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$")


def parse_point(value: str) -> tuple[float, float] | None:
    """Parse 'lat,lng'. Addresses that happen to contain a comma return None."""
    text = value.strip()
    if not _POINT_RE.match(text):
        return None
    lat_text, lng_text = text.split(",", 1)
    return float(lat_text.strip()), float(lng_text.strip())


def parse_point_with_system(
    value: str, coord_system: str = "wgs84"
) -> GeoPoint | None:
    point = parse_point(value)
    if point is None:
        return None
    lat, lng = point
    if coord_system == "gcj02":
        lng, lat = gcj02_to_wgs84(lng, lat)
    elif coord_system == "bd09":
        lng, lat = bd09_to_wgs84(lng, lat)
    return GeoPoint(lat, lng, "wgs84")


def _maps(ctx: AppContext) -> MapService:
    return ctx.maps or MapService(ctx.settings)


def _to_point(ctx: AppContext, value: str, coord_system: str) -> GeoPoint:
    point = parse_point_with_system(value, coord_system)
    if point is not None:
        return point
    return _maps(ctx).geocode(value).point


def _plan(
    ctx: AppContext,
    origin: str,
    destination: str,
    mode: str,
    coord_system: str,
) -> dict:
    origin_point = _to_point(ctx, origin, coord_system)
    destination_point = _to_point(ctx, destination, coord_system)
    route = _maps(ctx).route(origin_point, destination_point, mode)
    return {
        "distance_m": route.distance_m,
        "duration_s": route.duration_s,
        "steps": route.steps,
        "confidence": route.confidence,
        "sources": route.sources,
        "discrepancies": route.discrepancies,
        "warnings": route.warnings,
        "cached": route.cached,
        "mock": route.mock,
        "source": route.data_source,
        "coord_system": "wgs84",
    }


def register_route(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "规划从起点到终点的驾车或步行路线，返回距离、预计时间和主要路段。"
            "用户问“怎么去法院/律所/法律援助中心”时使用。起点和终点可以是地址或"
            "“纬度,经度”；坐标默认按 WGS-84 解释，可用 coord_system 指定 gcj02/bd09。"
            "如果只有机构名，先用 find_legal_service 查地址。"
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
        coord_system: Annotated[
            Literal["wgs84", "gcj02", "bd09"],
            Field(description="坐标输入使用的坐标系；默认 wgs84"),
        ] = "wgs84",
    ) -> str:
        return json.dumps(
            run_tool(lambda: _plan(ctx, origin, destination, mode, coord_system)),
            ensure_ascii=False,
        )
