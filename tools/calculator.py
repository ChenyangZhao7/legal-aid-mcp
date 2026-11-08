from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from calculators import DEADLINE_DAYS, deadline, litigation_fee, preservation_fee
from context import AppContext
from errors import ToolError, run_tool
from holidays import HolidayCalendar


def _basis(ctx: AppContext, law: str, number: int) -> dict | None:
    article = ctx.corpus.get(law, number)
    return article.to_tool_dict() if article else None


def _holiday_calendar(ctx: AppContext, year: int) -> HolidayCalendar:
    if ctx.holidays is not None and ctx.holidays.year == year:
        return ctx.holidays
    data_root = ctx.settings.law_data_dir.parent
    return HolidayCalendar.load(data_root / "holidays", year, live=False)


def _calculate(
    ctx: AppContext,
    action: str,
    amount: float | None,
    case_type: str,
    start_date: str | None,
    days: int | None,
    deadline_type: str,
    day_type: str,
) -> dict:
    try:
        if action == "litigation_fee":
            result = litigation_fee(amount, case_type)
            result["action"] = action
            result["legal_basis"] = _basis(ctx, "诉讼费用交纳办法", 13)
            return result

        if action == "preservation_fee":
            result = preservation_fee(amount)
            result["action"] = action
            result["legal_basis"] = _basis(ctx, "诉讼费用交纳办法", 14)
            return result

        if action == "deadline":
            if not start_date:
                raise ValueError("deadline 需要 start_date（送达日/收到日/事件发生日）")
            if deadline_type != "custom":
                if day_type != "natural":
                    raise ValueError("上诉期/答辩期按自然日计算，day_type 只能是 natural")
                days = DEADLINE_DAYS[deadline_type]
            if days is None:
                raise ValueError("deadline 需要 days 或 deadline_type")
            start = date.fromisoformat(start_date)
            holiday = _holiday_calendar(ctx, start.year)
            result = deadline(start, days, day_type, holiday)
            result["action"] = action
            result["deadline_type"] = deadline_type
            if deadline_type in {"appeal_judgment", "appeal_ruling"}:
                basis_article = 171
            elif deadline_type == "answer":
                basis_article = 128
            else:
                basis_article = 85
            result["legal_basis"] = _basis(ctx, "民事诉讼法", basis_article)
            notes = ["期间开始日不计算在内"]
            if result["adjusted"]:
                notes.append(
                    f"原届满日 {result['original_end_date']} 是休假日，顺延至 {result['end_date']}"
                )
            if holiday.source == "weekend-only":
                notes.append("未找到该年份节假日快照，仅按周末计算，请人工复核")
            result["notes"] = notes
            return result

        raise ValueError(f"不支持的 action：{action}")
    except (ValueError, KeyError) as exc:
        raise ToolError("CALCULATION_INVALID", str(exc))


def register_calculator(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "计算诉讼费、保全费或民事诉讼期间（上诉期/答辩期/自定义期间）。"
            "用户问“诉讼费多少”“保全费多少”“上诉期到哪天”“期间怎么算”时使用。"
            "所有结果附官方条文依据；期间计算的 start_date 是送达日/收到日/事件发生日，"
            "当天不计入，遇到法定休假日会顺延。"
        ),
        structured_output=False,
    )
    def legal_calculator(
        action: Annotated[
            Literal["litigation_fee", "preservation_fee", "deadline"],
            Field(description="计算类型：诉讼费、保全费或期间"),
        ],
        amount: Annotated[
            float | None,
            Field(ge=0, description="诉讼请求金额或保全财产数额；非财产案件可不填"),
        ] = None,
        case_type: Annotated[
            Literal[
                "财产案件",
                "离婚",
                "人格权",
                "知识产权",
                "劳动争议",
                "行政-商标专利海事",
                "行政-其他",
                "其他非财产",
            ],
            Field(description="案件类型，用于诉讼费标准"),
        ] = "财产案件",
        start_date: Annotated[
            str | None,
            Field(description="期间触发日，格式 YYYY-MM-DD，如判决书送达日"),
        ] = None,
        days: Annotated[
            int | None,
            Field(ge=1, description="自定义期间天数；appeal/answer 类型可自动取值"),
        ] = None,
        deadline_type: Annotated[
            Literal["appeal_judgment", "appeal_ruling", "answer", "custom"],
            Field(description="上诉期（判决15日/裁定10日）、答辩期15日或自定义期间"),
        ] = "custom",
        day_type: Annotated[
            Literal["natural", "working"],
            Field(description="自然日或工作日；默认自然日"),
        ] = "natural",
    ) -> str:
        return json.dumps(
            run_tool(
                lambda: _calculate(
                    ctx,
                    action,
                    amount,
                    case_type,
                    start_date,
                    days,
                    deadline_type,
                    day_type,
                )
            ),
            ensure_ascii=False,
        )
