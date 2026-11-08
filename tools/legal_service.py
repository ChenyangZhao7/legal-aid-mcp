from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from divisions import DivisionIndex
from errors import ToolError, run_tool
from legal_aid import LegalAidClient
from maps.base import GeoPoint, Place
from maps.crosscheck import match_places, place_confidence, place_discrepancies
from maps.service import MapService

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


def _maps(ctx: AppContext) -> MapService:
    return ctx.maps or MapService(ctx.settings)


def _divisions(ctx: AppContext) -> DivisionIndex | None:
    if ctx.divisions is not None:
        return ctx.divisions
    path = ctx.settings.law_data_dir.parent / "divisions" / "jinan.json"
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / "data" / "divisions" / "jinan.json"
    if path.exists():
        return DivisionIndex.load(path)
    return None


def _legal_aid(ctx: AppContext, divisions: DivisionIndex | None) -> LegalAidClient | None:
    if ctx.legal_aid is not None:
        return ctx.legal_aid
    if divisions is None:
        return None
    return LegalAidClient(ctx.settings, divisions)


def _source(place: Place) -> dict:
    return {
        "provider": place.provider,
        "name": place.name,
        "address": place.address,
        "telephone": place.telephone,
        "lat": place.native.lat,
        "lng": place.native.lng,
        "coord_system": place.native.system,
    }


def _official_places(result) -> list[Place]:
    places = []
    for center in result.centers:
        point = GeoPoint(center.lat or 0.0, center.lng or 0.0, "wgs84")
        place = Place(
            provider="12348",
            name=center.name,
            address=center.address,
            telephone=center.telephone,
            point=point,
            native=point,
            adcode=center.adcode,
            data_source="12348" if result.source == "12348" else "snapshot",
        )
        place.sources = [_source(place)]
        place.confidence = "official"
        places.append(place)
    return places


def _merge_official(official: list[Place], mapped: list[Place]) -> list[Place]:
    merged = list(official)
    for place in mapped:
        for existing in merged:
            if existing.provider != "12348":
                continue
            if match_places(existing, place):
                existing.sources.append(_source(place))
                existing.confidence = place_confidence(existing.sources)
                existing.discrepancies = place_discrepancies(existing.sources)
                break
        else:
            merged.append(place)
    return merged


def _to_dict(place: Place) -> dict:
    has_location = bool(place.point.lat or place.point.lng)
    sources = place.sources or [_source(place)]
    return {
        "name": place.name,
        "address": place.address,
        "telephone": place.telephone,
        "lat": place.point.lat if has_location else None,
        "lng": place.point.lng if has_location else None,
        "coord_system": "wgs84",
        "adcode": place.adcode,
        "source": place.data_source or ("12348" if place.provider == "12348" else "map"),
        "confidence": place.confidence,
        "sources": sources,
        "discrepancies": place.discrepancies,
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

    divisions = _divisions(ctx)
    if district is not None:
        if divisions is not None and divisions.find(district) is None:
            raise ToolError(
                "CITY_NOT_FOUND",
                f"未找到区县“{district}”，请提供济南市下属区县名称",
            )
        if divisions is None and district not in DISTRICT_WHITELIST:
            raise ToolError(
                "CITY_NOT_FOUND",
                f"未找到区县“{district}”，请提供济南市下属区县名称",
            )

    query = QUERY_MAP[keyword]
    region = district or city
    maps = _maps(ctx)
    mapped: list[Place] = []
    map_error: ToolError | None = None
    try:
        mapped = maps.place_search(query, region, limit)
    except ToolError as exc:
        map_error = exc

    official: list[Place] = []
    if keyword == "法律援助中心":
        client = _legal_aid(ctx, divisions)
        if client is not None:
            try:
                result = client.search(district=district, limit=limit)
                official = _official_places(result)
            except ToolError:
                official = []

    merged = _merge_official(official, mapped)
    if district:
        name_matches = [place for place in merged if district in (place.name or "")]
        if name_matches:
            merged = name_matches
        else:
            address_matches = [
                place for place in merged if district in (place.address or "")
            ]
            if address_matches:
                merged = address_matches
    if not merged:
        if map_error is not None:
            raise map_error
        raise ToolError(
            "NO_RESULTS",
            f"在{region}未找到“{keyword}”相关机构，请换关键词或提供更具体的区县",
        )
    return [_to_dict(place) for place in merged[:limit]]


def register_legal_service(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "在指定城市搜索法院、律师事务所或法律援助中心，返回机构名称、地址、"
            "电话和经纬度。用户问“去哪个法院立案”“附近有没有法律援助”“找律师”时使用。"
            "只返回机构信息，不判断管辖，也不评价律师水平。"
            "法律援助中心优先使用 12348 官方目录；地图结果会标注来源和置信度。"
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
