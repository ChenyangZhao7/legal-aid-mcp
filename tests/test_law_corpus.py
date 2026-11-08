from pathlib import Path
import pytest
from errors import ToolError
from laws import LawCorpus

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def corpus():
    return LawCorpus.load(ROOT / "data" / "laws")

def test_search_penalty_clause(corpus):
    hits = corpus.search("违约金过高", limit=5)
    assert hits[0].article_number == 585
    assert "违约金" in hits[0].text

def test_search_with_law_filter(corpus):
    hits = corpus.search("合同解除", law="民法典", limit=5)
    assert any(a.article_number == 563 for a in hits)

def test_search_exact_article(corpus):
    hits = corpus.search("第585条", limit=1)
    assert hits[0].article_number == 585

def test_scope_of(corpus):
    assert corpus.scope_of("民法典", 585) == "in_corpus"
    assert corpus.scope_of("民法典", 100) == "out_of_scope"
    assert corpus.scope_of("民法典", 9999) == "not_found"
    assert corpus.scope_of("合同法", 114) == "out_of_scope"

def test_no_match_raises(corpus):
    with pytest.raises(ToolError) as exc:
        corpus.search("完全不存在的词", limit=5)
    assert exc.value.code == "NO_MATCH"

def test_corpus_not_loaded(tmp_path):
    corpus = LawCorpus.load(tmp_path / "missing")
    with pytest.raises(ToolError) as exc:
        corpus.search("违约金", limit=5)
    assert exc.value.code == "CORPUS_NOT_LOADED"

def test_corpus_load_oserror(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "manifest.json").mkdir()
    corpus = LawCorpus.load(data)
    with pytest.raises(ToolError) as exc:
        corpus.search("违约金", limit=5)
    assert exc.value.code == "CORPUS_NOT_LOADED"

def test_gram_score_caps_text_contribution():
    from laws import _gram_score
    grams = {f"a{i}" for i in range(15)}
    text = " ".join(grams)
    assert _gram_score(text, "", grams) == 20

def test_search_generic_prefers_civil_code(corpus):
    hits = corpus.search("合同", limit=5)
    assert hits[0].short_name == "民法典"

def test_search_liability_prefers_civil_code(corpus):
    hits = corpus.search("违约责任", limit=5)
    assert hits[0].short_name == "民法典"
