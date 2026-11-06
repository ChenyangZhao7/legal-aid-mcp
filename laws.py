from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_UNITS = {"十": 10, "百": 100, "千": 1000}
_CN_DIGITS = "零一二三四五六七八九"
_CN_NUM = "零〇一二三四五六七八九十百千"


@dataclass(frozen=True)
class Citation:
    raw: str
    law: str
    article: str
    number: int
    start: int
    end: int


@dataclass(frozen=True)
class Article:
    law: str
    short_name: str
    article: str
    article_number: int
    text: str
    section: tuple[str, ...]
    promulgation_date: str
    effective_date: str
    status: str
    sxx: int
    source_url: str
    bbbs: str
    source_sha256: str
    pdf_sha256: str

    def to_tool_dict(self) -> dict:
        return {
            "law": self.law,
            "article": self.article,
            "text": self.text,
            "effective_date": self.effective_date,
            "source_url": self.source_url,
            "status": self.status,
        }


def cn_to_int(text: str) -> int:
    text = text.strip()
    if text.isdigit():
        return int(text)
    total = 0
    section = 0
    num = 0
    for ch in text:
        if ch in _DIGITS:
            num = _DIGITS[ch]
        elif ch in _UNITS:
            unit = _UNITS[ch]
            if num == 0:
                num = 1
            section += num * unit
            num = 0
        else:
            raise ValueError(f"不是有效的中文数字: {text!r}")
    return total + section + num


def int_to_cn(n: int) -> str:
    if n < 0:
        raise ValueError("条号不能为负数")
    if n == 0:
        return "零"
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        return "十" + (_CN_DIGITS[n - 10] if n > 10 else "")
    if n < 100:
        tens, ones = divmod(n, 10)
        return _CN_DIGITS[tens] + "十" + (_CN_DIGITS[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = _CN_DIGITS[hundreds] + "百"
        if rest == 0:
            return head
        if rest < 10:
            return head + "零" + _CN_DIGITS[rest]
        return head + int_to_cn(rest)
    thousands, rest = divmod(n, 1000)
    head = _CN_DIGITS[thousands] + "千"
    if rest == 0:
        return head
    if rest < 10:
        return head + "零" + _CN_DIGITS[rest]
    if rest < 100:
        return head + "零" + int_to_cn(rest)
    return head + int_to_cn(rest)


_LAW_ALIASES: dict[str, tuple[str, ...]] = {
    "合同编通则司法解释": (
        "最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释",
        "合同编通则司法解释",
    ),
    "民法典": ("中华人民共和国民法典", "民法典"),
    "合同法": ("中华人民共和国合同法", "合同法"),
    "民事诉讼法": ("中华人民共和国民事诉讼法", "民事诉讼法", "民诉法"),
}

_ALIAS_TO_LAW: list[tuple[str, str]] = sorted(
    ((alias, law) for law, aliases in _LAW_ALIASES.items() for alias in aliases),
    key=lambda item: len(item[0]),
    reverse=True,
)
_ALIAS_PATTERN = "|".join(re.escape(alias) for alias, _ in _ALIAS_TO_LAW)
_CITATION_RE = re.compile(
    rf"(?P<law>{_ALIAS_PATTERN})?\s*[》]?\s*第\s*(?P<num>[{_CN_NUM}\d]+)\s*条"
)


def parse_citations(text: str) -> list[Citation]:
    found: list[Citation] = []
    for match in _CITATION_RE.finditer(text):
        raw_law = match.group("law")
        law = "民法典"
        if raw_law:
            law = next(canon for alias, canon in _ALIAS_TO_LAW if alias == raw_law)
        num_text = match.group("num")
        number = int(num_text) if num_text.isdigit() else cn_to_int(num_text)
        found.append(
            Citation(
                raw=match.group(0),
                law=law,
                article=f"第{num_text}条",
                number=number,
                start=match.start(),
                end=match.end(),
            )
        )
    return found


_ARTICLE_RE = re.compile(rf"^第([{_CN_NUM}]+)条")
_HEADING_RE = re.compile(rf"^(第[{_CN_NUM}]+)(分编|编|章|节)")
_NUMBERED_HEADING_RE = re.compile(r"^[一二三四五六七八九十]+、")
_LEVEL_BY_UNIT = {"编": 0, "分编": 1, "章": 2, "节": 3}


def _heading_level(text: str) -> int | None:
    match = _HEADING_RE.match(text)
    if match:
        return _LEVEL_BY_UNIT[match.group(2)]
    if _NUMBERED_HEADING_RE.match(text):
        return 0
    return None


def split_articles(paragraphs: list[str]) -> list[dict]:
    articles: list[dict] = []
    sections: list[tuple[int, str]] = []
    current: dict | None = None

    def push_heading(text: str) -> None:
        nonlocal sections
        level = _heading_level(text)
        if level is None:
            return
        sections = [(lvl, title) for lvl, title in sections if lvl < level]
        sections.append((level, text))

    for paragraph in paragraphs:
        text = paragraph.strip()
        if not text:
            continue
        match = _ARTICLE_RE.match(text)
        if match:
            if current is not None:
                articles.append(current)
            current = {
                "number": cn_to_int(match.group(1)),
                "title": f"第{match.group(1)}条",
                "parts": [text],
                "section": [title for _, title in sections],
            }
        elif _heading_level(text) is not None:
            push_heading(text)
        elif current is not None:
            current["parts"].append(text)

    if current is not None:
        articles.append(current)
    for article in articles:
        article["text"] = "\n".join(article.pop("parts")).strip()
    return articles


def normalize_text(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"')
    return "".join(
        ch
        for ch in text
        if not ch.isspace() and not unicodedata.category(ch).startswith("P")
    )
