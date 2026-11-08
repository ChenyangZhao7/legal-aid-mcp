from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from context import AppContext
from errors import ToolError, run_tool
from laws import Citation, normalize_text, parse_citations

_QUOTE_RE = re.compile(r"[“\"](.{2,200}?)[”\"]")
_MISMATCH_WINDOW = 500


def citation_status(article) -> str:
    return "exists" if article.status == "有效" else "amended"


def _mismatch(text: str, citation: Citation, official_text: str) -> bool | None:
    tail = text[citation.end : citation.end + _MISMATCH_WINDOW]
    match = _QUOTE_RE.search(tail)
    if not match:
        head = text[max(0, citation.start - _MISMATCH_WINDOW) : citation.start]
        matches = list(_QUOTE_RE.finditer(head))
        if not matches:
            return None
        match = matches[-1]
    quote = match.group(1)
    return normalize_text(quote) not in normalize_text(official_text)


def _verify(ctx: AppContext, text: str, law_hint: str | None) -> list[dict]:
    hint = ctx.corpus.resolve_law_name(law_hint) if law_hint is not None else None
    if law_hint is not None and hint is None:
        raise ToolError("NO_MATCH", f"不支持的法律提示：{law_hint}")

    citations = parse_citations(text)
    if not citations:
        raise ToolError("NO_CITATION_FOUND", "未识别到法条引用，请提供“民法典第 X 条”这类文字")

    seen: set[tuple[str, int]] = set()
    results: list[dict] = []
    for citation in citations:
        if not citation.explicit:
            if hint is None:
                results.append(
                    {
                        "citation": citation.raw,
                        "status": "ambiguous",
                        "official_text": None,
                        "mismatch": None,
                        "candidates": list(ctx.corpus.manifest.get("laws", {}).keys()),
                    }
                )
                continue
            law = hint
        else:
            law = citation.law

        key = (law, citation.number)
        if key in seen:
            continue
        seen.add(key)

        scope = ctx.corpus.scope_of(law, citation.number)
        if scope == "in_corpus":
            article = ctx.corpus.get(law, citation.number)
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
            "amended（已修改/已废止）、out_of_scope（真实存在但不在 v1 收录范围，不代表不存在）、"
            "ambiguous（引用没写法律名，需要 law_hint 才能判断）。"
        ),
        structured_output=False,
    )
    def verify_citation(
        text: Annotated[
            str,
            Field(description="包含法条引用的文字，如答辩状、合同或 AI 回答"),
        ],
        law_hint: Annotated[
            Literal["民法典", "合同编通则司法解释"] | None,
            Field(description="引用没写法律名时用它指定法律；引用里已写法律名时忽略"),
        ] = None,
    ) -> str:
        return json.dumps(
            run_tool(lambda: _verify(ctx, text, law_hint)),
            ensure_ascii=False,
        )
