from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "民法典": {
        "file": "civil_code_contract.json",
        "count": 526,
        "first": 463,
        "last": 988,
    },
    "合同编通则司法解释": {
        "file": "contract_interpretation_2023.json",
        "count": 69,
        "first": 1,
        "last": 69,
    },
    "民事诉讼法": {
        "file": "civil_procedure_law.json",
        "count": 306,
        "first": 1,
        "last": 306,
    },
    "民诉法解释": {
        "file": "civil_procedure_interpretation.json",
        "count": 550,
        "first": 1,
        "last": 550,
    },
    "证据规定": {
        "file": "civil_evidence_rules.json",
        "count": 100,
        "first": 1,
        "last": 100,
    },
    "诉讼费用交纳办法": {
        "file": "litigation_fee_rules.json",
        "count": 56,
        "first": 1,
        "last": 56,
    },
    "法律援助法": {
        "file": "legal_aid_law.json",
        "count": 71,
        "first": 1,
        "last": 71,
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验本地法条语料")
    parser.add_argument("--data-dir", default="data/laws")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--require-raw", action="store_true", help="原始 docx/pdf 不存在时直接失败")
    args = parser.parse_args()

    data_dir = ROOT / args.data_dir
    raw_dir = ROOT / args.raw_dir
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        _fail(f"缺少 {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for name, expected in EXPECTED.items():
        path = data_dir / expected["file"]
        if not path.exists():
            _fail(f"缺少 {path}")
        articles = json.loads(path.read_text(encoding="utf-8"))
        if len(articles) != expected["count"]:
            _fail(f"{name} 条数 {len(articles)} != {expected['count']}")
        numbers = [a["article_number"] for a in articles]
        if numbers[0] != expected["first"] or numbers[-1] != expected["last"]:
            _fail(f"{name} 首尾条号 {numbers[0]}..{numbers[-1]} 不符")
        if len(set(numbers)) != len(numbers):
            _fail(f"{name} 有重复条号")
        for article in articles:
            if len(article.get("text", "")) <= 10:
                _fail(f"{name} 第 {article['article_number']} 条正文过短")
            if not article.get("source_url", "").startswith("https://flk.npc.gov.cn/detail"):
                _fail(f"{name} 第 {article['article_number']} 条 source_url 非法")
            if "<em" in article.get("source_url", "") or "%3Cem" in article.get("source_url", ""):
                _fail(f"{name} 第 {article['article_number']} 条 source_url 含高亮标签")

        entry = manifest.get("laws", {}).get(name)
        if not entry:
            _fail(f"manifest 缺少 {name}")
        for key in ("source_sha256", "pdf_sha256"):
            if not entry.get(key):
                print(f"WARN: {name} 没有 {key}，跳过原始文件校验")
                continue
            raw_name = "docx" if key == "source_sha256" else "pdf"
            raw_file = raw_dir / f"{name}.{raw_name}"
            if raw_file.exists():
                if _sha256(raw_file) != entry[key]:
                    _fail(f"{name} 的 {raw_file.name} SHA256 不匹配")
            else:
                if args.require_raw:
                    _fail(f"{raw_file} 不存在；--require-raw 要求原始文件必须存在")
                print(f"WARN: {raw_file} 不存在（已 gitignore），跳过原始文件校验")

    def by_number(file_name: str) -> dict[int, dict]:
        rows = json.loads((data_dir / file_name).read_text(encoding="utf-8"))
        return {row["article_number"]: row for row in rows}

    civil = by_number("civil_code_contract.json")
    if "违约金" not in civil[585]["text"]:
        _fail("民法典第 585 条不含“违约金”")
    if "解除" not in civil[563]["text"]:
        _fail("民法典第 563 条不含“解除”")

    interp = json.loads(
        (data_dir / "contract_interpretation_2023.json").read_text(encoding="utf-8")
    )
    if "合同条款" not in interp[0]["text"]:
        _fail("司法解释第 1 条不含“合同条款”")

    cpc = by_number("civil_procedure_law.json")
    if "期间" not in cpc[85]["text"]:
        _fail("民事诉讼法第 85 条不含“期间”")
    if "十五日" not in cpc[171]["text"]:
        _fail("民事诉讼法第 171 条不含“十五日”")

    evidence = by_number("civil_evidence_rules.json")
    if "证据" not in evidence[1]["text"]:
        _fail("民事诉讼证据规定第 1 条不含“证据”")

    fees = by_number("litigation_fee_rules.json")
    if "案件受理费" not in fees[13]["text"]:
        _fail("诉讼费用交纳办法第 13 条不含“案件受理费”")
    if "申请费" not in fees[14]["text"]:
        _fail("诉讼费用交纳办法第 14 条不含“申请费”")

    legal_aid = by_number("legal_aid_law.json")
    if "法律援助" not in legal_aid[2]["text"]:
        _fail("法律援助法第 2 条不含“法律援助”")

    total = sum(item["count"] for item in EXPECTED.values())
    print(f"OK: {total} 条；民法典合同编 526 条；司法解释 69 条；民事诉讼核心包已校验")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
