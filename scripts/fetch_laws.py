from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from laws import split_articles  # noqa: E402

BASE = "https://flk.npc.gov.cn"

TARGETS = [
    {
        "law": "中华人民共和国民法典",
        "short_name": "民法典",
        "search_title": "中华人民共和国民法典",
        "out_name": "civil_code_contract.json",
        "flxz": "法律",
        "min_article": 463,
        "max_article": 988,
        "full_range": [1, 1260],
        "in_scope": [463, 988],
    },
    {
        "law": "最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释",
        "short_name": "合同编通则司法解释",
        "search_title": "最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释",
        "out_name": "contract_interpretation_2023.json",
        "flxz": "司法解释",
        "min_article": 1,
        "max_article": 69,
        "full_range": [1, 69],
        "in_scope": [1, 69],
    },
]

SXX_LABELS = {1: "已废止", 2: "已修改", 3: "有效", 4: "尚未生效"}


def _request_json(path: str, params: dict | None = None, payload: dict | None = None) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {"User-Agent": "Mozilla/5.0"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "")


def search_law(title: str) -> dict:
    payload = {
        "searchContent": title,
        "searchType": 1,
        "searchRange": 1,
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "gbrqYear": [],
        "orderByParam": {"order": "-1", "sort": ""},
        "pageNum": 1,
        "pageSize": 10,
    }
    result = _request_json("/law-search/search/list", payload=payload)
    if result.get("code") != 200:
        raise RuntimeError(f"搜索失败: {result.get('msg')}")
    for row in result.get("rows") or []:
        if _strip_tags(row.get("title", "")) == title:
            return row
    raise RuntimeError(f"没有找到标题完全匹配的法律: {title}")


def download_file(bbbs: str, fmt: str) -> bytes:
    result = _request_json("/law-search/download/pc", {"bbbs": bbbs, "format": fmt})
    if result.get("code") != 200 or not result.get("data", {}).get("url"):
        raise RuntimeError(f"下载地址获取失败 ({fmt}): {result.get('msg')}")
    return _download_bytes(result["data"]["url"])


def docx_paragraphs(docx_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    paragraphs: list[str] = []
    for block in re.findall(r"<w:p(?:\s[^>]*)?>.*?</w:p>", xml, re.S):
        texts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", block, re.S)
        text = html.unescape("".join(texts)).strip()
        if text and not text.startswith("<w:"):
            paragraphs.append(text)
    return paragraphs


def source_url(bbbs: str, flxz: str, title: str) -> str:
    query = urllib.parse.urlencode({"id": bbbs, "type": flxz, "title": title})
    return f"{BASE}/detail?{query}"


def fetch_target(target: dict, out_dir: Path, raw_dir: Path) -> dict:
    short_name = target["short_name"]
    row = search_law(target["search_title"])
    bbbs = row["bbbs"]
    docx_bytes = download_file(bbbs, "docx")
    pdf_bytes = download_file(bbbs, "pdf")
    source_sha = _sha256(docx_bytes)
    pdf_sha = _sha256(pdf_bytes)

    (raw_dir / f"{short_name}.docx").write_bytes(docx_bytes)
    (raw_dir / f"{short_name}.pdf").write_bytes(pdf_bytes)

    all_articles = split_articles(docx_paragraphs(docx_bytes))
    articles = [
        article
        for article in all_articles
        if target["min_article"] <= article["number"] <= target["max_article"]
    ]
    if not articles:
        raise RuntimeError(f"{short_name} 没有解析出条文")

    status = SXX_LABELS.get(row.get("sxx"), "未知")
    url = source_url(bbbs, target["flxz"], _strip_tags(row["title"]))
    records = []
    for article in articles:
        records.append(
            {
                "law": target["law"],
                "short_name": short_name,
                "article": article["title"],
                "article_number": article["number"],
                "text": article["text"],
                "section": article["section"],
                "promulgation_date": row.get("gbrq"),
                "effective_date": row.get("sxrq"),
                "status": status,
                "sxx": row.get("sxx"),
                "source_url": url,
                "bbbs": bbbs,
                "source_sha256": source_sha,
                "pdf_sha256": pdf_sha,
            }
        )

    (out_dir / target["out_name"]).write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"{short_name}: {len(records)} 条  docx_sha={source_sha[:12]}  pdf_sha={pdf_sha[:12]}"
    )
    return {
        "file": target["out_name"],
        "full_article_range": target["full_range"],
        "in_scope": target["in_scope"],
        "count": len(records),
        "promulgation_date": row.get("gbrq"),
        "effective_date": row.get("sxrq"),
        "status": status,
        "sxx": row.get("sxx"),
        "source_url": url,
        "bbbs": bbbs,
        "source_sha256": source_sha,
        "pdf_sha256": pdf_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取国家法律法规数据库的官方文本")
    parser.add_argument("--out", default="data/laws", help="输出 JSON 目录")
    parser.add_argument("--raw-dir", default="data/raw", help="原始 docx/pdf 目录")
    args = parser.parse_args()

    out_dir = ROOT / args.out
    raw_dir = ROOT / args.raw_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "laws": {},
    }
    for target in TARGETS:
        manifest["laws"][target["short_name"]] = fetch_target(target, out_dir, raw_dir)

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"manifest: {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
