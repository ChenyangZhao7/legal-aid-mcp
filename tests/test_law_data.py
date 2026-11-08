import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    return json.loads((ROOT / "data" / "laws" / name).read_text(encoding="utf-8"))

def test_contract_book_count_and_boundaries():
    arts = load("civil_code_contract.json")
    assert len(arts) == 526
    assert arts[0]["article_number"] == 463
    assert arts[-1]["article_number"] == 988
    assert len({a["article_number"] for a in arts}) == 526

def test_contract_book_spot_checks():
    arts = {a["article_number"]: a for a in load("civil_code_contract.json")}
    assert "违约金" in arts[585]["text"]
    assert "解除" in arts[563]["text"]
    assert arts[585]["source_url"].startswith("https://flk.npc.gov.cn/detail")
    assert arts[585]["status"] == "有效"

def test_interpretation_count_and_boundaries():
    arts = load("contract_interpretation_2023.json")
    assert len(arts) == 69
    assert arts[0]["article_number"] == 1
    assert arts[-1]["article_number"] == 69
    assert "合同条款" in arts[0]["text"]

def test_source_url_has_no_highlight_markup():
    arts = load("civil_code_contract.json")
    assert all("<em" not in a["source_url"] and "%3Cem" not in a["source_url"] for a in arts)


def test_civil_procedure_law_count_and_boundaries():
    arts = load("civil_procedure_law.json")
    assert len(arts) == 306
    assert arts[0]["article_number"] == 1
    assert arts[-1]["article_number"] == 306
    by_number = {a["article_number"]: a for a in arts}
    assert "期间" in by_number[85]["text"]
    assert "十五日" in by_number[171]["text"]


def test_civil_procedure_interpretation_count():
    arts = load("civil_procedure_interpretation.json")
    assert len(arts) == 550
    assert arts[0]["article_number"] == 1
    assert arts[-1]["article_number"] == 550


def test_civil_evidence_rules_count():
    arts = load("civil_evidence_rules.json")
    assert len(arts) == 100
    assert arts[0]["article_number"] == 1
    assert arts[-1]["article_number"] == 100


def test_litigation_fee_rules_count():
    arts = load("litigation_fee_rules.json")
    assert len(arts) == 56
    by_number = {a["article_number"]: a for a in arts}
    assert "案件受理费" in by_number[13]["text"]
    assert "申请费" in by_number[14]["text"]


def test_legal_aid_law_count():
    arts = load("legal_aid_law.json")
    assert len(arts) == 71
    assert arts[0]["article_number"] == 1
    assert arts[-1]["article_number"] == 71

