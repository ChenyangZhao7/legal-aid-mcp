import pytest
from laws import cn_to_int, int_to_cn, parse_citations, split_articles, normalize_text

@pytest.mark.parametrize("cn,n", [
    ("十", 10), ("十一", 11), ("二十", 20), ("一百", 100),
    ("五百八十五", 585), ("九百八十八", 988), ("一千二百六十", 1260),
])
def test_cn_to_int(cn, n):
    assert cn_to_int(cn) == n

@pytest.mark.parametrize("n,cn", [(10, "十"), (11, "十一"), (585, "五百八十五"), (1260, "一千二百六十")])
def test_int_to_cn(n, cn):
    assert int_to_cn(n) == cn

def test_parse_citations_forms():
    text = "见《中华人民共和国民法典》第五百八十五条、第 563 条，以及第585条。"
    got = parse_citations(text)
    assert [c.number for c in got] == [585, 563, 585]
    assert all(c.law == "民法典" for c in got)

def test_parse_citations_out_of_scope_law():
    got = parse_citations("合同法第114条和民诉法第122条")
    assert [(c.law, c.number) for c in got] == [("合同法", 114), ("民事诉讼法", 122)]

def test_parse_citations_full_interpretation_title():
    text = "最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释第一条"
    got = parse_citations(text)
    assert got[0].law == "合同编通则司法解释"
    assert got[0].number == 1

def test_parse_citations_unknown_law_prefix():
    got = parse_citations("刑法第585条")
    assert got[0].law == "刑法"
    assert got[0].number == 585

def test_parse_citations_bracketed_unknown_law():
    got = parse_citations("《中华人民共和国刑法》第585条")
    assert got[0].law == "中华人民共和国刑法"
    assert got[0].number == 585

def test_parse_citations_partial_interpretation_title():
    got = parse_citations("《中华人民共和国民法典》合同编通则若干问题的解释第585条")
    assert got[0].law != "民法典"

def test_parse_citations_placeholder():
    got = parse_citations("民诉法第X条")
    assert got[0].law == "民事诉讼法"
    assert got[0].number == 0

def test_parse_citations_no_prefix_is_not_explicit():
    got = parse_citations("第585条")
    assert got[0].law == "民法典"
    assert got[0].explicit is False

def test_split_articles_tracks_sections():
    paras = [
        "第三编　合　　同",
        "第一章　一般规定",
        "第四百六十三条　本编调整因合同产生的民事关系。",
        "第四百六十四条　合同是民事主体之间设立、变更、终止民事法律关系的协议。",
        "第二章　合同的订立",
        "第四百六十五条　依法成立的合同，受法律保护。",
    ]
    arts = split_articles(paras)
    assert [a["number"] for a in arts] == [463, 464, 465]
    assert arts[0]["section"] == ["第三编　合　　同", "第一章　一般规定"]
    assert arts[2]["section"] == ["第三编　合　　同", "第二章　合同的订立"]

def test_normalize_text():
    assert normalize_text("第五百八十五条　当事人可以约定…") == normalize_text("第五百八十五条 当事人可以约定...")
