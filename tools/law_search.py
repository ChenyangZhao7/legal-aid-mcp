from __future__ import annotations

import json
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from errors import ToolError, run_tool
from laws import parse_citations


def _search(ctx: AppContext, query: str, law: str | None, limit: int) -> list[dict]:
    law_filter = ctx.corpus.resolve_law_name(law) if law is not None else None
    if law is not None and law_filter is None:
        raise ToolError("NO_MATCH", f"不支持的法律：{law}")

    citations = parse_citations(query)
    if citations:
        results: list[dict] = []
        seen: set[tuple[str, int]] = set()
        out_of_scope: str | None = None
        not_found: str | None = None
        for citation in citations:
            if not citation.explicit and law_filter is not None:
                citation_law = law_filter
            elif citation.explicit and law_filter is not None and citation.law != law_filter:
                raise ToolError("NO_MATCH", f"{citation.raw} 不属于指定法律 {law}")
            else:
                citation_law = citation.law

            key = (citation_law, citation.number)
            if key in seen:
                continue
            seen.add(key)

            scope = ctx.corpus.scope_of(citation_law, citation.number)
            if scope == "in_corpus":
                article = ctx.corpus.get(citation_law, citation.number)
                if article is not None and len(results) < limit:
                    results.append(article.to_tool_dict())
            elif scope == "out_of_scope":
                out_of_scope = out_of_scope or citation.raw
            else:
                not_found = not_found or citation.raw

        if results:
            return results
        if out_of_scope is not None:
            raise ToolError(
                "OUT_OF_SCOPE",
                f"{out_of_scope} 不在 v1 收录范围（仅民法典合同编 463–988 与合同编通则司法解释）",
            )
        if not_found is not None:
            raise ToolError("NO_MATCH", f"{not_found}：该法律全文没有这个条号")
        raise ToolError("NO_MATCH", "未找到匹配条文，请换关键词或指定法律")

    return [article.to_tool_dict() for article in ctx.corpus.search(query, law, limit)]


def register_law_search(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "在本地民法典合同编和合同编通则司法解释中检索条文，返回条文号、原文、"
            "生效日期和出处。用户问“法律怎么规定”“违约金能不能调”“合同解除条件”时使用。"
            "query 可以同时包含多个法条引用，会返回所有在收录范围内的条文；"
            "没写法律名的“第 X 条”默认按民法典处理，也可用 law 参数指定。"
            "只返回检索到的原文，不编造；没有匹配时明确说未找到。"
        ),
        structured_output=False,
    )
    def search_law(
        query: Annotated[
            str,
            Field(
                description=(
                    "检索关键词或法条引用，如“违约金过高”或“民法典第585条”；"
                    "可以同时包含多个引用"
                )
            ),
        ],
        law: Annotated[
            Literal[
                "民法典",
                "合同编通则司法解释",
                "民事诉讼法",
                "民诉法解释",
                "证据规定",
                "诉讼费用交纳办法",
                "法律援助法",
            ]
            | None,
            Field(description="限定法律；不填则检索收录范围内的全部法律"),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=10, description="返回条数上限，1–10，默认 5"),
        ] = 5,
    ) -> str:
        return json.dumps(
            run_tool(lambda: _search(ctx, query, law, limit)),
            ensure_ascii=False,
        )
