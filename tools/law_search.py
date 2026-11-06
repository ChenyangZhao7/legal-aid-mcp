from __future__ import annotations

import json
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from errors import ToolError, run_tool
from laws import parse_citations


def _search(ctx: AppContext, query: str, law: str | None, limit: int) -> list[dict]:
    citations = parse_citations(query)
    if citations:
        citation = citations[0]
        scope = ctx.corpus.scope_of(citation.law, citation.number)
        if scope != "in_corpus":
            raise ToolError(
                "OUT_OF_SCOPE",
                f"{citation.raw} 不在 v1 收录范围（仅民法典合同编 463–988 与合同编通则司法解释）",
            )
        article = ctx.corpus.get(citation.law, citation.number)
        if article is None:
            raise ToolError("NO_MATCH", f"未找到 {citation.raw}")
        return [article.to_tool_dict()]

    return [article.to_tool_dict() for article in ctx.corpus.search(query, law, limit)]


def register_law_search(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "在本地民法典合同编和合同编通则司法解释中检索条文，返回条文号、原文、"
            "生效日期和出处。用户问“法律怎么规定”“违约金能不能调”“合同解除条件”时使用。"
            "只返回检索到的原文，不编造；没有匹配时明确说未找到。"
        ),
        structured_output=False,
    )
    def search_law(
        query: str,
        law: Literal["民法典", "合同编通则司法解释"] | None = None,
        limit: Annotated[int, Field(ge=1, le=10)] = 5,
    ) -> str:
        return json.dumps(
            run_tool(lambda: _search(ctx, query, law, limit)),
            ensure_ascii=False,
        )
