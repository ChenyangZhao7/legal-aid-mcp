from __future__ import annotations

import json
import re

from mcp.server.mcpserver import MCPServer

from context import AppContext
from errors import ToolError, run_tool
from laws import Citation, normalize_text, parse_citations

_QUOTE_RE = re.compile(r"[“\"](.{2,200}?)[”\"]")


def citation_status(article) -> str:
    return "exists" if article.status == "有效" else "amended"


def _mismatch(text: str, citation: Citation, official_text: str) -> bool | None:
    tail = text[citation.end : citation.end + 200]
    match = _QUOTE_RE.search(tail)
    if not match:
        return None
    quote = match.group(1)
    return normalize_text(quote) not in normalize_text(official_text)


def _verify(ctx: AppContext, text: str) -> list[dict]:
    citations = parse_citations(text)
    if not citations:
        raise ToolError("NO_CITATION_FOUND", "未识别到法条引用，请提供“民法典第 X 条”这类文字")

    seen: set[tuple[str, int]] = set()
    results: list[dict] = []
    for citation in citations:
        key = (citation.law, citation.number)
        if key in seen:
            continue
        seen.add(key)

        scope = ctx.corpus.scope_of(citation.law, citation.number)
        if scope == "in_corpus":
            article = ctx.corpus.get(citation.law, citation.number)
            if article is None:
                status = "not_found"
                official_text = None
                mismatch = None
            else:
                status = citation_status(article)
                official_text = article.text
                mismatch = _mismatch(text, citation, article.text)
        elif scope == "out_of_scope":
            status = "out_of_scope"
            official_text = None
            mismatch = None
        else:
            status = "not_found"
            official_text = None
            mismatch = None

        results.append(
            {
                "citation": citation.raw,
                "status": status,
                "official_text": official_text,
                "mismatch": mismatch,
            }
        )
    return results


def register_citation(server: MCPServer, ctx: AppContext) -> None:
    @server.tool(
        description=(
            "核对一段文字中引用的法条是否存在、是否现行有效、原文是否一致。"
            "用户提供答辩状、合同、AI 回答，要求“核对法条”“看看引用对不对”时使用。"
            "返回 status：exists（存在且有效）、not_found（该法律全文没有这个条号）、"
            "amended（已修改/已废止）、out_of_scope（真实存在但不在 v1 收录范围，不代表不存在）。"
        ),
        structured_output=False,
    )
    def verify_citation(text: str) -> str:
        return json.dumps(run_tool(lambda: _verify(ctx, text)), ensure_ascii=False)
