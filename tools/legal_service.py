from __future__ import annotations

import json
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from errors import ToolError, run_tool

CITY_WHITELIST = {"济南", "济南市"}
DISTRICT_WHITELIST = {
    "历下区",
    "市中区",
    "槐荫区",
    "天桥区",
    "历城区",
    "长清区",
    "章丘区",
    "济阳区",
    "莱芜区",
    "钢城区",
    "平阴县",
    "商河县",
}

QUERY_MAP = {
    "法院": "人民法院",
    "律师事务所": "律师事务所",
    "法律援助中心": "法律援助",
}


def _find(
    ctx: AppContext,
    keyword: str,
    city: str,
    district: str | None,
    limit: int,
) -> list[dict]:
    if city not in CITY_WHITELIST:
        raise ToolError(
            "CITY_NOT_FOUND",
            f"暂不支持城市“{city}”，v1 只覆盖济南及下属区县",
        )
    if district is not None and district not in DISTRICT_WHITELIST:
        raise ToolError(
            "CITY_NOT_FOUND",
            f"未找到区县“{district}”，请提供济南市下属区县名称",
        )

    query = QUERY_MAP[keyword]
    region = district or city
    rows = ctx.baidu.place_search(query, region, limit)
    if district:
        name_matches = [row for row in rows if district in (row.get("name") or "")]
        if name_matches:
            rows = name_matches
        else:
            address_matches = [
                row for row in rows if district in (row.get("address") or "")
            ]
            if address_matches:
                rows = address_matches
    if not rows:
        raise ToolError(
            "NO_RESULTS",
            f"在{region}未找到“{keyword}”相关机构，请换关键词或提供更具体的区县",
        )

    results = []
    for row in rows[:limit]:
        location = row.get("location") or {}
        results.append(
            {
                "name": row.get("name"),
                "address": row.get("address"),
                "telephone": row.get("telephone"),
                "lat": location.get("lat"),
                "lng": location.get("lng"),
            }
        )
    return results


def register_legal_service(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "在指定城市搜索法院、律师事务所或法律援助中心，返回机构名称、地址、"
            "电话和经纬度。用户问“去哪个法院立案”“附近有没有法律援助”“找律师”时使用。"
            "只返回机构信息，不判断管辖，也不评价律师水平。"
        ),
        structured_output=False,
    )
    def find_legal_service(
        keyword: Annotated[
            Literal["法院", "律师事务所", "法律援助中心"],
            Field(description="要查找的机构类型：法院、律师事务所或法律援助中心"),
        ],
        city: Annotated[
            str,
            Field(description="城市名称；v1 只支持济南及下属区县"),
        ] = "济南",
        district: Annotated[
            str | None,
            Field(description="济南下属区县，如“历下区”；不填则在全市范围搜索"),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=10, description="返回条数上限，1–10，默认 5"),
        ] = 5,
    ) -> str:
        return json.dumps(
            run_tool(lambda: _find(ctx, keyword, city, district, limit)),
            ensure_ascii=False,
        )
