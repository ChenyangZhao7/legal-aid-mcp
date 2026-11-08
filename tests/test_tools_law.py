import json
from dataclasses import replace
from pathlib import Path
import pytest
from mcp.server.mcpserver import MCPServer
from baidu import BaiduClient
from config import load_settings
from context import AppContext
from laws import LawCorpus
from tools.law_search import register_law_search
from tools.citation import register_citation

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def server(tmp_path):
    s = load_settings(env={
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }, base_dir=tmp_path)
    ctx = AppContext(settings=s, baidu=BaiduClient(s), corpus=LawCorpus.load(ROOT / "data" / "laws"))
    mcp = MCPServer("test")
    register_law_search(mcp, ctx)
    register_citation(mcp, ctx)
    return mcp

async def call(mcp, name, args):
    result = await mcp.call_tool(name, args)
    return json.loads(result.content[0].text)

async def test_search_penalty(server):
    data = await call(server, "search_law", {"query": "违约金过高"})
    assert data[0]["article"] == "第五百八十五条"
    assert "违约金" in data[0]["text"]

async def test_search_law_filter(server):
    data = await call(server, "search_law", {"query": "合同解除", "law": "民法典"})
    assert any(r["article"] == "第五百六十三条" for r in data)

async def test_search_no_match(server):
    data = await call(server, "search_law", {"query": "完全不存在的词"})
    assert data["error"]["code"] == "NO_MATCH"

async def test_search_out_of_scope(server):
    data = await call(server, "search_law", {"query": "民法典第100条"})
    assert data["error"]["code"] == "OUT_OF_SCOPE"

async def test_verify_exists(server):
    data = await call(server, "verify_citation", {"text": "依据《中华人民共和国民法典》第五百八十五条"})
    assert data[0]["status"] == "exists"
    assert "违约金" in data[0]["official_text"]

async def test_verify_not_found(server):
    data = await call(server, "verify_citation", {"text": "民法典第9999条"})
    assert data[0]["status"] == "not_found"

async def test_verify_out_of_scope(server):
    data = await call(server, "verify_citation", {"text": "民法典第100条和合同法第114条"})
    assert [r["status"] for r in data] == ["out_of_scope", "out_of_scope"]

async def test_verify_no_citation(server):
    data = await call(server, "verify_citation", {"text": "今天天气不错"})
    assert data["error"]["code"] == "NO_CITATION_FOUND"

async def test_verify_mismatch(server):
    data = await call(server, "verify_citation", {"text": "民法典第585条：“这是一段完全错误的引文”"})
    assert data[0]["mismatch"] is True

def test_citation_status_amended():
    from types import SimpleNamespace
    from tools.citation import citation_status
    assert citation_status(SimpleNamespace(status="已修改")) == "amended"
    assert citation_status(SimpleNamespace(status="有效")) == "exists"

async def test_verify_unknown_law_is_out_of_scope(server):
    data = await call(server, "verify_citation", {"text": "刑法第585条"})
    assert data[0]["status"] == "out_of_scope"

async def test_verify_literal_placeholder(server):
    data = await call(server, "verify_citation", {"text": "民诉法第X条"})
    assert data[0]["status"] == "out_of_scope"

async def test_verify_no_prefix_is_ambiguous(server):
    data = await call(server, "verify_citation", {"text": "第585条"})
    assert data[0]["status"] == "ambiguous"

async def test_verify_no_prefix_with_hint(server):
    data = await call(server, "verify_citation", {"text": "第585条", "law_hint": "民法典"})
    assert data[0]["status"] == "exists"
    assert "违约金" in data[0]["official_text"]

async def test_verify_explicit_law_ignores_hint(server):
    data = await call(server, "verify_citation", {"text": "民法典第585条", "law_hint": "合同编通则司法解释"})
    assert data[0]["status"] == "exists"

async def test_verify_mismatch_false(server):
    data = await call(server, "verify_citation", {
        "text": "民法典第585条：“当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金”"
    })
    assert data[0]["mismatch"] is False

async def test_verify_duplicate_citations(server):
    data = await call(server, "verify_citation", {"text": "民法典第585条，民法典第585条"})
    assert len(data) == 1

async def test_search_interpretation_filter(server):
    data = await call(server, "search_law", {"query": "格式条款", "law": "合同编通则司法解释"})
    assert data
    assert all(r["law"].startswith("最高人民法院") for r in data)

async def test_search_unknown_law_out_of_scope(server):
    data = await call(server, "search_law", {"query": "刑法第585条"})
    assert data["error"]["code"] == "OUT_OF_SCOPE"

async def test_search_fake_article_is_no_match(server):
    data = await call(server, "search_law", {"query": "民法典第9999条"})
    assert data["error"]["code"] == "NO_MATCH"

async def test_search_law_filter_conflict(server):
    data = await call(server, "search_law", {"query": "民法典第585条", "law": "合同编通则司法解释"})
    assert data["error"]["code"] == "NO_MATCH"

async def test_search_multiple_citations_returns_all(server):
    data = await call(server, "search_law", {"query": "民法典第585条和民法典第563条"})
    assert [r["article"] for r in data] == ["第五百八十五条", "第五百六十三条"]

async def test_search_multiple_citations_keeps_in_corpus(server):
    data = await call(server, "search_law", {"query": "合同法第114条和民法典第585条"})
    assert [r["article"] for r in data] == ["第五百八十五条"]

async def test_search_no_prefix_uses_law_param_as_hint(server):
    data = await call(server, "search_law", {"query": "第1条", "law": "合同编通则司法解释"})
    assert data[0]["article"] == "第一条"
    assert data[0]["law"].startswith("最高人民法院")

async def test_verify_mismatch_quote_before_citation(server):
    data = await call(server, "verify_citation", {"text": "“这是一段完全错误的引文”，见民法典第585条"})
    assert data[0]["mismatch"] is True

async def test_verify_mismatch_quote_after_long_prefix(server):
    filler = "这是很长的说明文字。" * 30
    data = await call(server, "verify_citation", {
        "text": f"民法典第585条：{filler}“这是一段完全错误的引文”"
    })
    assert data[0]["mismatch"] is True

@pytest.fixture
def amended_server(tmp_path):
    s = load_settings(env={
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }, base_dir=tmp_path)
    corpus = LawCorpus.load(ROOT / "data" / "laws")
    corpus._by_law_number[("民法典", 585)] = replace(
        corpus._by_law_number[("民法典", 585)], status="已修改"
    )
    ctx = AppContext(settings=s, baidu=BaiduClient(s), corpus=corpus)
    mcp = MCPServer("test")
    register_citation(mcp, ctx)
    return mcp

async def test_verify_amended_when_article_modified(amended_server):
    data = await call(amended_server, "verify_citation", {"text": "民法典第585条"})
    assert data[0]["status"] == "amended"
