# 法律援助一条龙 MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个面向济南的 stdio MCP Server，提供找机构、查路线、查法条、核引用 4 个工具，默认 mock，真实调用有预算上限。

**Architecture:** Python 3.14 + MCP SDK 2.x（`MCPServer`，即 2.x 中的 FastMCP）单进程 stdio server。Baidu 客户端负责 HTTP、mock/live、缓存、预算和错误映射；本地语料由官方 docx 解析成 JSON，`laws.py` 负责加载、检索、引用解析。工具层只做参数校验、调用和返回结构。

**Tech Stack:** Python 3.14.7、`mcp==2.3.0`、`httpx`、`python-dotenv`、`pytest`、`pytest-asyncio`；docx 解析用标准库 `zipfile` + XML。

**Spec:** `docs/superpowers/specs/2026-11-06-legal-aid-mcp-design.md`（与 `执行书.md` 一起读）

## Global Constraints

- 运行环境：Windows，Python 3.14.7；`mcp==2.3.0` 的入口是 `from mcp.server.mcpserver import MCPServer`。
- 传输：stdio；`server.run("stdio")`。
- AK 只从环境变量 `BAIDU_AK` 读取；代码、日志、错误信息、缓存元数据里都不能出现 AK。
- `USE_LIVE=1` 即真实调用，即使 `USE_MOCK=1` 也以 live 为准，并向 stderr 打一条警告。
- `LIVE_BUDGET=20` 是项目生命周期硬上限，不按日重置。
- 默认 `USE_LIVE=0`、`USE_MOCK=1`；所有自动化测试都不发真实网络请求。
- 法条只来自官方 docx：民法典合同编 463–988 共 526 条；合同编通则司法解释 1–69 共 69 条。
- `verify_citation` 的 `status` 必须区分 `exists` / `not_found` / `amended` / `out_of_scope`；不能把“v1 没收录”说成“不存在”。
- 高德仅作为百度整体不可用时的备选；当前提供的 key 返回 `INVALID_USER_KEY`，v1 不实现高德适配器。
- 所有面向用户的提示用中文；代码标识符用英文。
- 每个任务结束提交一次；提交前确认没有 `.env`、`data/raw/`、`cache/` 被加入。

## Review Focus

1. **引用识别**：`第 585 条`（带空格）、`《中华人民共和国民法典》第五百八十五条`、不带法律前缀的 `第585条` 都要能识别；带前缀时不能用错法律。
2. **范围外引用**：`民法典第100条`、`合同法第114条`、`民诉法第X条` 必须返回 `out_of_scope`，不能返回 `not_found`。
3. **百度错误区分**：空结果、AK 无效（203/210/211/302）、配额超限（220）、超时必须是不同错误码，不能混成一个“查不到”。
4. **live 配置**：`USE_LIVE=1` 且 `USE_MOCK=1` 时必须真的发请求，不能静默走 mock。
5. **地址 vs 坐标**：`"济南市历下区,经十路"` 必须当地址去地理编码，不能被误判成 `lat,lng`。

---

## Task 1: 项目骨架、配置、错误封装、server 工厂

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `pytest.ini`
- Create: `config.py`
- Create: `errors.py`
- Create: `context.py`
- Create: `server.py`
- Create: `tests/test_config.py`
- Create: `tests/test_errors.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `Settings`（字段见下）、`load_settings(env=None, base_dir=None) -> Settings`、`ConfigError`
- Produces: `ToolError(code, message)`、`.to_dict() -> dict`、`error_dict(code, message) -> dict`、`run_tool(fn) -> T | dict`
- Produces: `AppContext(settings, baidu, corpus)`
- Produces: `create_server(settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> MCPServer`

- [ ] **Step 1: 写失败测试**

`tests/test_config.py`：

```python
from pathlib import Path
import pytest
from config import load_settings, ConfigError

ROOT = Path(__file__).resolve().parents[1]

def test_defaults(tmp_path):
    s = load_settings(env={}, base_dir=tmp_path)
    assert s.use_mock is True
    assert s.use_live is False
    assert s.live_budget == 20
    assert s.cache_ttl_hours == 24
    assert s.law_data_dir == tmp_path / "data" / "laws"
    assert s.fixtures_dir == tmp_path / "fixtures" / "baidu"

def test_live_requires_ak(tmp_path):
    with pytest.raises(ConfigError):
        load_settings(env={"USE_LIVE": "1"}, base_dir=tmp_path)

def test_live_wins_over_mock(tmp_path, capsys):
    s = load_settings(env={"USE_LIVE": "1", "USE_MOCK": "1", "BAIDU_AK": "test-ak"}, base_dir=tmp_path)
    assert s.use_live is True
    assert "USE_LIVE=1" in capsys.readouterr().err

def test_create_server_factory():
    from server import create_server
    s = load_settings(env={}, base_dir=ROOT)
    assert create_server(s).name == "legal-aid-mcp"
```

`tests/test_errors.py`：

```python
from errors import ToolError, error_dict, run_tool

def test_tool_error_shape():
    assert ToolError("NO_RESULTS", "没找到").to_dict() == {
        "error": {"code": "NO_RESULTS", "message": "没找到"}
    }

def test_run_tool_catches_tool_error():
    def f():
        raise ToolError("NO_RESULTS", "没找到")
    assert run_tool(f)["error"]["code"] == "NO_RESULTS"

def test_run_tool_catches_unexpected():
    def f():
        raise RuntimeError("boom")
    assert run_tool(f)["error"]["code"] == "INTERNAL"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_config.py tests/test_errors.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: 实现**

`requirements.txt`：

```text
mcp==2.3.0
httpx>=0.28
python-dotenv>=1.0
pytest>=8
pytest-asyncio>=0.24
```

`.env.example`：

```text
BAIDU_AK=your-baidu-server-ak
USE_MOCK=1
USE_LIVE=0
LIVE_BUDGET=20
CACHE_DIR=cache
CACHE_TTL_HOURS=24
LAW_DATA_DIR=data/laws
FIXTURES_DIR=fixtures/baidu
# AMAP_KEY=  # 备选，仅当百度不可用；需高德“Web 服务”类型 key
```

`pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
testpaths = tests
```

`config.py`：实现 `ConfigError`、`Settings`（字段：`base_dir`、`baidu_ak: str | None`、`use_mock`、`use_live`、`live_budget`、`cache_dir`、`cache_ttl_hours`、`law_data_dir`、`fixtures_dir`、`request_timeout_s`）。`env` 为 `None` 时才调用 `load_dotenv(base_dir / ".env")`。支持 `FIXTURES_DIR` 覆盖 fixtures 路径（测试用）。`USE_LIVE=1` 且没有 `BAIDU_AK` 时抛 `ConfigError`；同时 `USE_MOCK=1` 时向 stderr 打警告。相对路径一律相对 `base_dir` 解析。

`errors.py`：

```python
def run_tool(fn):
    try:
        return fn()
    except ToolError as exc:
        return exc.to_dict()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return error_dict("INTERNAL", "工具内部错误，请稍后重试")
```

`context.py`：`AppContext` 用 `TYPE_CHECKING` 引用 `BaiduClient`/`LawCorpus`（这两个模块 Task 6/4 才创建），避免 Task 1 导入失败。

`server.py`：`create_server()` 创建 `MCPServer("legal-aid-mcp")` 并构造 `Settings`；**暂不构造 `AppContext`**（Task 9 再接入，避免引用尚未存在的 `baidu.py`/`laws.py`）；`if __name__ == "__main__": create_server().run("stdio")`。

`.gitignore` 补 `data/raw/`、`cache/`、`.venv/`、`__pycache__/`、`.pytest_cache/`；保留 `.env` 和 `!.env.example`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_config.py tests/test_errors.py -q`
Expected: `7 passed`

- [ ] **Step 5: 提交**

```bash
git init
git add requirements.txt .env.example .gitignore pytest.ini config.py errors.py context.py server.py tests/test_config.py tests/test_errors.py
git commit -m "feat: bootstrap config, errors, and server factory"
```

---

## Task 2: 中文数字、引用解析、条文切分

**Files:**
- Create: `laws.py`（只放纯函数与 `Citation`/`Article` 数据结构）
- Create: `tests/test_laws.py`

**Interfaces:**
- Produces: `cn_to_int(s: str) -> int`
- Produces: `int_to_cn(n: int) -> str`
- Produces: `Citation(raw, law, article, number, start, end)`（dataclass）
- Produces: `parse_citations(text: str) -> list[Citation]`
- Produces: `split_articles(paragraphs: list[str]) -> list[dict]`，每项 `{title, number, text, section}`
- Produces: `normalize_text(s: str) -> str`

- [ ] **Step 1: 写失败测试**

`tests/test_laws.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_laws.py -q`
Expected: FAIL，`ImportError` 或 `cannot import name 'laws'`

- [ ] **Step 3: 实现纯函数**

实现要点：
- `cn_to_int` 的数字映射必须显式写 `{"零":0,"〇":0,"一":1,...,"九":9}`，不能靠 `enumerate("零〇一二...")`。
- `int_to_cn` 覆盖 1–1260；按千/百/十/个位拼接，处理 `十` 的省略（10→十，11→十一）。
- `parse_citations` 用“最长别名优先”的正则；别名前后允许 `《》` 和空白（`《中华人民共和国民法典》第五百八十五条` 必须能匹配）；别名表：
  - `民法典`：`中华人民共和国民法典`、`民法典`
  - `合同编通则司法解释`：`最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释`、`合同编通则司法解释`
  - `合同法`：`中华人民共和国合同法`、`合同法`
  - `民事诉讼法`：`中华人民共和国民事诉讼法`、`民事诉讼法`、`民诉法`
  - 无前缀时默认 `民法典`。
- `split_articles`：按 `^第[零〇一二三四五六七八九十百千]+条` 切分；`编/分编/章/节` 标题维护层级栈（`分编` 要先于 `编` 匹配），并支持司法解释的 `^[一二三四五六七八九十]+、` 标题；第一条之前的目录标题忽略。
- `normalize_text`：去掉所有空白和全角空格，统一中英文引号，保留中文和数字。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_laws.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add laws.py tests/test_laws.py
git commit -m "feat: add chinese numerals, citation parsing, and article splitting"
```

---

## Task 3: 抓取官方语料并生成 JSON

**Files:**
- Create: `scripts/fetch_laws.py`
- Create: `scripts/verify_laws.py`
- Create: `tests/test_law_data.py`
- Create: `data/laws/civil_code_contract.json`（生成）
- Create: `data/laws/contract_interpretation_2023.json`（生成）
- Create: `data/laws/manifest.json`（生成）
- Create: `data/raw/*.docx`、`data/raw/*.pdf`（生成，gitignore）

**Interfaces:**
- Consumes: `laws.split_articles`、`laws.cn_to_int`
- Produces: 两个 JSON 列表 + `manifest.json`，字段见设计文档 8.2
- Produces: `python scripts/fetch_laws.py --out data/laws --raw-dir data/raw`
- Produces: `python scripts/verify_laws.py --data-dir data/laws`

- [ ] **Step 1: 写失败测试**

`tests/test_law_data.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_law_data.py -q`
Expected: FAIL，`FileNotFoundError`

- [ ] **Step 3: 实现抓取与校验脚本**

`scripts/fetch_laws.py` 用标准库 `urllib.request`、`zipfile`、`hashlib`、`json`；脚本顶部把项目根加入 `sys.path`（`Path(__file__).resolve().parents[1]`），否则 `import laws` 会失败。
1. `POST https://flk.npc.gov.cn/law-search/search/list`，body 固定为：
   ```json
   {"searchContent": "<标题>", "searchType": 1, "searchRange": 1,
    "flfgCodeId": [], "zdjgCodeId": [], "gbrqYear": [],
    "orderByParam": {"order": "-1", "sort": ""}, "pageNum": 1, "pageSize": 10}
   ```
2. 先把搜索结果 title 里的 `<em class='highlight'>...</em>` 标签去掉，再选完全匹配的结果，拿 `bbbs/title/gbrq/sxrq/sxx/flxz`。
3. `GET /law-search/download/pc?bbbs=<bbbs>&format=docx`，再从返回的 `data.url` 下载 docx；`format=pdf` 同理下载 PDF。
4. 解析 docx：`word/document.xml` → `<w:p>` → `<w:t>` 文本；跳过以 `<w:` 开头的脏段落；用 `laws.split_articles` 切分。
5. 民法典只保留 463–988；司法解释保留 1–69（`split_articles` 的 section 也支持 `一、一般规定` 这类标题）。
6. 每条补 `law/short_name/promulgation_date/effective_date/status/sxx/source_url/bbbs/source_sha256/pdf_sha256`。`sxx` 映射：1=已废止、2=已修改、3=有效、4=尚未生效。
7. `source_url = https://flk.npc.gov.cn/detail?id=<bbbs>&type=<flxz>&title=<title>`（URL 编码）。
8. 写 JSON（`ensure_ascii=False, indent=2`）和 `manifest.json`（含 `full_article_range`、`in_scope`、`count`、两个 SHA256）。
9. 原始 docx/PDF 写 `data/raw/`。

`scripts/verify_laws.py` 校验：526/69、首尾条号、无重复、`text` 长度 > 20、`source_url` 非空、抽样“违约金/解除/合同条款”、原始文件 SHA256 与 manifest 一致；失败退出码 1。

- [ ] **Step 4: 抓取并校验**

Run:
```powershell
python scripts/fetch_laws.py --out data/laws --raw-dir data/raw
python scripts/verify_laws.py --data-dir data/laws
```
Expected: `fetch` 输出两条法律的条数与 SHA256；`verify` 输出 `OK: 民法典合同编 526 条；司法解释 69 条`，退出码 0。

交叉核对（本项目要求）：用 pi 的 bash 独立抓一份 docx，比较 SHA256 与主控抓取是否一致；不一致就停止入库并排查。若 pi 不可用，记录原因并在测试报告标注。

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_law_data.py -q`
Expected: `3 passed`

- [ ] **Step 6: 提交**

```bash
git add scripts/fetch_laws.py scripts/verify_laws.py tests/test_law_data.py data/laws
git commit -m "feat: fetch and verify official contract-law corpus"
```

---

## Task 4: `LawCorpus` 加载、检索、范围判断

**Files:**
- Modify: `laws.py`（追加 `Article`、`LawCorpus`）
- Create: `tests/test_law_corpus.py`

**Interfaces:**
- Consumes: `data/laws/*.json`、`manifest.json`
- Produces: `LawCorpus.load(data_dir: Path) -> LawCorpus`
- Produces: `LawCorpus.search(query: str, law: str | None = None, limit: int = 5) -> list[Article]`
- Produces: `LawCorpus.get(law: str, number: int) -> Article | None`
- Produces: `LawCorpus.scope_of(law: str, number: int) -> str`，返回 `in_corpus` / `out_of_scope` / `not_found`
- Produces: `LawCorpus.resolve_law_name(name: str | None) -> str | None`
- Produces: `Article.to_tool_dict() -> dict`，只含 `law/article/text/effective_date/source_url/status`

- [ ] **Step 1: 写失败测试**

`tests/test_law_corpus.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_law_corpus.py -q`
Expected: FAIL，`cannot import name 'LawCorpus'`

- [ ] **Step 3: 实现 `LawCorpus`**

检索打分（可解释、稳定）：
- 查询命中条号（`parse_citations` 或 `第X条`）→ 该条 +1000。
- 完整查询串出现在正文 → +20。
- 中文 2-gram 命中正文 → 每个不同 2-gram 出现一次 +2，上限 20。
- 命中 `section` 标题 → 每个 +3。
- v1 relevance prior：查询含“违约金” → 民法典 585 +100；含“合同解除/解除合同” → 民法典 563 +100。这是执行书两个核心问题的检索先验，避免程序性司法解释条文压过一般规则。
- 最低分 7：低于 7 视为无匹配，避免“完全不存在的词”这类 2-gram 噪声命中。
- 同分按 `article_number` 升序。
- `law` 过滤先做，非法法律名抛 `ToolError("NO_MATCH", ...)`。
- 无正分结果抛 `ToolError("NO_MATCH", "未找到匹配条文，请换关键词或指定法律")`。
- `LawCorpus.load` 捕获 `FileNotFoundError`/`JSONDecodeError`，设置 `load_error`；`search/get/scope_of` 在 `load_error` 存在时抛 `ToolError("CORPUS_NOT_LOADED", ...)`。

`scope_of` 用 `manifest["laws"][短名]["full_article_range"]` 和 `in_scope`：
- 在语料里 → `in_corpus`
- 不在语料但在全文范围 → `out_of_scope`
- 超出全文范围 → `not_found`
- 法律名不在 manifest → `out_of_scope`

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_law_corpus.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add laws.py tests/test_law_corpus.py
git commit -m "feat: add law corpus search and scope resolution"
```

---

## Task 5: 录制百度样本 fixtures

**Files:**
- Create: `scripts/record_fixtures.py`
- Create: `fixtures/baidu/place_court.json`
- Create: `fixtures/baidu/place_court_lixia.json`
- Create: `fixtures/baidu/place_law_firm.json`
- Create: `fixtures/baidu/place_legal_aid.json`
- Create: `fixtures/baidu/geocode_court.json`
- Create: `fixtures/baidu/geocode_west_station.json`
- Create: `fixtures/baidu/route_west_station.json`
- Create: `tests/test_fixtures.py`

**Interfaces:**
- Produces: 7 个原始百度响应 JSON，全部 `status == 0`
- Produces: `python scripts/record_fixtures.py --out fixtures/baidu`

- [ ] **Step 1: 写失败测试**

`tests/test_fixtures.py`：

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "baidu"

def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

def test_all_fixtures_ok():
    for path in FIXTURES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["status"] == 0, path.name

def test_court_fixture_has_jinan_intermediate():
    names = [r["name"] for r in load("place_court.json")["results"]]
    assert any("济南市中级人民法院" in n for n in names)

def test_lixia_fixture_has_lixia_court():
    names = [r["name"] for r in load("place_court_lixia.json")["results"]]
    assert any("历下区人民法院" in n for n in names)

def test_law_firm_fixture_not_empty():
    assert load("place_law_firm.json")["results"]

def test_legal_aid_fixture_is_valid():
    data = load("place_legal_aid.json")
    assert data["status"] == 0
    assert isinstance(data.get("results"), list)

def test_route_fixture_has_distance():
    route = load("route_west_station.json")["result"]["routes"][0]
    assert route["distance"] > 0 and route["duration"] > 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_fixtures.py -q`
Expected: FAIL，`FileNotFoundError`

- [ ] **Step 3: 实现录制脚本并运行**

`scripts/record_fixtures.py` 从 `.env` 读 `BAIDU_AK`，脚本顶部把项目根加入 `sys.path` 再 `import config`，用 `httpx` 或 `urllib` 调：
- `place/v2/search`：query=`法院`、region=`济南`、page_size=10 → `place_court.json`
- `place/v2/search`：query=`人民法院`、region=`历下区`、page_size=5 → `place_court_lixia.json`
- `place/v2/search`：query=`律师事务所`、region=`济南`、page_size=5 → `place_law_firm.json`
- `place/v2/search`：query=`法律援助`、region=`济南`、page_size=5 → `place_legal_aid.json`
- `geocoding/v3`：address=`济南市中级人民法院` → `geocode_court.json`
- `geocoding/v3`：address=`济南西站` → `geocode_west_station.json`
- 先用两个 geocode 结果取坐标，再调 `direction/v2/driving` → `route_west_station.json`
- 若 `region=历下区` 的结果里没有“历下区人民法院”，改用 `query=历下区人民法院`、`region=济南` 重录，文件名仍是 `place_court_lixia.json`。

脚本必须检查 `status == 0`；任何一条非 0 就打印 `message` 并以非 0 退出，不写坏 fixture。AK 不写入 fixture。法律援助 POI 可能为空，允许 `results: []`，不要伪造。

Run:
```powershell
python scripts/record_fixtures.py --out fixtures/baidu
```
Expected: 7 个文件，全部 `status: 0`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_fixtures.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/record_fixtures.py fixtures/baidu tests/test_fixtures.py
git commit -m "test: record baidu fixtures for mock mode"
```

---

## Task 6: `BaiduClient`（mock/live/缓存/预算/错误映射）

**Files:**
- Create: `baidu.py`
- Create: `tests/test_baidu.py`

**Interfaces:**
- Consumes: `Settings`、`fixtures/baidu/*.json`
- Produces: `BaiduClient(settings, transport=None, now=None)`
- Produces: `.place_search(query: str, region: str, page_size: int) -> list[dict]`
- Produces: `.geocode(address: str) -> tuple[float, float]`
- Produces: `.route(origin: tuple[float, float], destination: tuple[float, float], mode: str) -> dict`
- Produces: 错误码 `AK_INVALID` / `QUOTA_EXCEEDED` / `UPSTREAM_TIMEOUT` / `UPSTREAM_ERROR` / `BUDGET_EXHAUSTED` / `NO_RESULTS`

- [ ] **Step 1: 写失败测试**

`tests/test_baidu.py`：

```python
import json
from pathlib import Path
import httpx
import pytest
from baidu import BaiduClient
from config import load_settings
from errors import ToolError

ROOT = Path(__file__).resolve().parents[1]

def settings(tmp_path, **env):
    base = {
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
    }
    base.update(env)
    return load_settings(env=base, base_dir=tmp_path)

def test_mock_place_court(tmp_path):
    c = BaiduClient(settings(tmp_path))
    rows = c.place_search("人民法院", "济南", 10)
    assert any("济南市中级人民法院" in r["name"] for r in rows)

def test_mock_geocode(tmp_path):
    c = BaiduClient(settings(tmp_path))
    lng, lat = c.geocode("济南市中级人民法院")
    assert 116 < lng < 118 and 36 < lat < 38

def test_mock_route(tmp_path):
    c = BaiduClient(settings(tmp_path))
    r = c.route((36.67, 117.0), (36.68, 117.1), "driving")
    assert r["distance_m"] > 0 and r["duration_s"] > 0

def test_live_quota_maps(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"status": 220, "message": "quota"})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "QUOTA_EXCEEDED"
    assert "test-ak" not in exc.value.message

def test_live_ak_invalid_maps(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"status": 203, "message": "invalid ak"})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "AK_INVALID"

def test_live_timeout_maps(tmp_path):
    def handler(request):
        raise httpx.TimeoutException("timeout")
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "UPSTREAM_TIMEOUT"

def test_live_upstream_error_maps(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"status": 500, "message": "boom"})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 5)
    assert exc.value.code == "UPSTREAM_ERROR"

def test_live_budget_exhausted(tmp_path):
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"status": 0, "results": []})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak", LIVE_BUDGET="1")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    c.place_search("人民法院", "济南", 5)
    # 不同 page_size = 缓存未命中，才会检查预算
    with pytest.raises(ToolError) as exc:
        c.place_search("人民法院", "济南", 6)
    assert exc.value.code == "BUDGET_EXHAUSTED"
    assert calls["n"] == 1

def test_live_cache_hit_does_not_spend(tmp_path):
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"status": 0, "results": [{"name": "x"}]})
    s = settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak", LIVE_BUDGET="5")
    c = BaiduClient(s, transport=httpx.MockTransport(handler))
    c.place_search("人民法院", "济南", 5)
    c.place_search("人民法院", "济南", 5)
    assert calls["n"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_baidu.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'baidu'`

- [ ] **Step 3: 实现 `BaiduClient`**

要点：
- mock 模式按设计文档 8.4/9 的映射读 fixture；`route` 统一返回 `route_west_station.json`（测试/演示用）；找不到对应 fixture 抛 `ToolError("NO_RESULTS", ...)`。
- live 模式：
  - 先查缓存（缓存存在且未过期 → 直接返回，不花预算）。
  - 再检查预算并自增（`cache/budget.json`，`{used, limit, updated_at}`，不按日重置）。
  - `httpx.Client(transport=..., timeout=10).get(url, params=...)`。
  - `status == 0` → 写缓存并返回；`203/210/211/302` → `AK_INVALID`；`220` → `QUOTA_EXCEEDED`；其他非 0 → `UPSTREAM_ERROR`。
  - `httpx.TimeoutException` → `UPSTREAM_TIMEOUT`；`httpx.HTTPError` → `UPSTREAM_ERROR`。
- 错误信息里不拼接带 `ak=` 的 URL；只带 status 和 message。
- 缓存键用去掉 `ak` 的参数排序后 SHA256；缓存文件含 `fetched_at` 和 `data`。
- 结果映射：
  - `place_search` → `data["results"]`
  - `geocode` → `(data["result"]["location"]["lng"], data["result"]["location"]["lat"])`
  - `route` → `{"distance_m": routes[0]["distance"], "duration_s": routes[0]["duration"], "steps": [...]}`

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_baidu.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add baidu.py tests/test_baidu.py
git commit -m "feat: add baidu client with mock, cache, and budget"
```

---

## Task 7: `find_legal_service` 与 `plan_route` 工具

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/legal_service.py`
- Create: `tools/route.py`
- Create: `tests/test_tools_baidu.py`

**Interfaces:**
- Consumes: `AppContext`、`BaiduClient`、`run_tool`
- Produces: `register_legal_service(server, ctx)`
- Produces: `register_route(server, ctx)`
- Produces: `parse_point(s: str) -> tuple[float, float] | None`
- Produces: 工具名 `find_legal_service` / `plan_route`

- [ ] **Step 1: 写失败测试**

`tests/test_tools_baidu.py`：

```python
import json
from pathlib import Path
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
from baidu import BaiduClient
from config import load_settings
from context import AppContext
from laws import LawCorpus
from tools.legal_service import register_legal_service
from tools.route import register_route, parse_point

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
    register_legal_service(mcp, ctx)
    register_route(mcp, ctx)
    return mcp

async def call(mcp, name, args):
    result = await mcp.call_tool(name, args)
    return json.loads(result.content[0].text)

async def test_find_court(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "city": "济南"})
    assert any("济南市中级人民法院" in r["name"] for r in data)

async def test_find_law_firm(server):
    data = await call(server, "find_legal_service", {"keyword": "律师事务所", "limit": 5})
    assert len(data) >= 1

async def test_find_lixia_court(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "district": "历下区", "limit": 5})
    assert any("历下区人民法院" in r["name"] for r in data)

async def test_city_not_found(server):
    data = await call(server, "find_legal_service", {"keyword": "法院", "city": "火星"})
    assert data["error"]["code"] == "CITY_NOT_FOUND"

async def test_limit_schema_rejects_11(server):
    with pytest.raises(MCPToolError):
        await server.call_tool("find_legal_service", {"keyword": "法院", "limit": 11})

def test_parse_point_accepts_coordinates():
    assert parse_point("36.67,117.0") == (36.67, 117.0)

def test_parse_point_rejects_address_with_comma():
    assert parse_point("济南市历下区,经十路") is None

async def test_no_results(server, monkeypatch):
    monkeypatch.setattr(BaiduClient, "place_search", lambda *a, **k: [])
    data = await call(server, "find_legal_service", {"keyword": "法院"})
    assert data["error"]["code"] == "NO_RESULTS"

async def test_plan_route_with_addresses(server):
    data = await call(server, "plan_route", {"origin": "济南西站", "destination": "济南市中级人民法院"})
    assert data["distance_m"] > 0

async def test_plan_route_address_with_comma_is_not_coordinates(server):
    data = await call(server, "plan_route", {"origin": "济南市历下区,经十路", "destination": "济南市中级人民法院"})
    assert "distance_m" in data or data["error"]["code"] == "GEOCODE_FAILED"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_baidu.py -q`
Expected: FAIL，`ModuleNotFoundError: tools`

- [ ] **Step 3: 实现工具**

`find_legal_service` 和 `plan_route` 都用 `structured_output=False`，返回 `str`（`json.dumps(..., ensure_ascii=False)` 的结果）；错误 dict 也 json 序列化。MCP SDK 2.x 会把 list 返回值当成多个 content block，只保留第一个，所以不能直接返回 list。
- 参数：`keyword: Literal["法院","律师事务所","法律援助中心"]`、`city="济南"`、`district=None`、`limit: Annotated[int, Field(ge=1, le=10)] = 5`。
- 济南白名单：`{"济南","济南市"}` + 区县 `{"历下区","市中区","槐荫区","天桥区","历城区","长清区","章丘区","济阳区","莱芜区","钢城区","平阴县","商河县"}`。
- `city` 不在白名单 → `CITY_NOT_FOUND`；`district` 不在白名单 → `CITY_NOT_FOUND`。
- query 映射：`法院`→`人民法院`；`法律援助中心`→`法律援助`；律所原样。
- region：有 district 用 district，否则用 city。
- 空结果 → `NO_RESULTS`。
- 返回 `name/address/telephone/lat/lng`，缺失字段为 `None`；mock fixture 可能多于 `limit`，返回前 `[:limit]`。

`plan_route`：
- 参数：`origin`、`destination`、`mode: Literal["driving","walking"]="driving"`。
- `_parse_point` 只接受 `^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$`；`"济南市历下区,经十路"` 不匹配，必须走 geocode。
- 地址解析失败 → `GEOCODE_FAILED`。
- 返回 `distance_m/duration_s/steps`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_baidu.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add tools tests/test_tools_baidu.py
git commit -m "feat: add legal service and route tools"
```

---

## Task 8: `search_law` 与 `verify_citation` 工具

**Files:**
- Create: `tools/law_search.py`
- Create: `tools/citation.py`
- Create: `tests/test_tools_law.py`

**Interfaces:**
- Consumes: `AppContext`、`LawCorpus`、`parse_citations`、`normalize_text`
- Produces: `register_law_search(server, ctx)`、`register_citation(server, ctx)`
- Produces: `citation_status(article) -> str`（`exists` / `amended`）
- Produces: 工具名 `search_law` / `verify_citation`

- [ ] **Step 1: 写失败测试**

`tests/test_tools_law.py`：

```python
import json
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_law.py -q`
Expected: FAIL，`ModuleNotFoundError: tools.law_search`

- [ ] **Step 3: 实现工具**

`search_law` 与 `verify_citation` 都用 `structured_output=False`，返回 `str`（`json.dumps(..., ensure_ascii=False)` 的结果）；错误 dict 也 json 序列化。

`search_law`：
- 参数：`query: str`、`law: Literal["民法典","合同编通则司法解释"] | None = None`、`limit: Annotated[int, Field(ge=1, le=10)] = 5`。
- 先 `parse_citations(query)`：有引用且 `scope_of` 不是 `in_corpus` → `OUT_OF_SCOPE`；是 `in_corpus` → 直接返回该条。
- 否则 `ctx.corpus.search(query, law, limit)`。
- 返回 `[article.to_tool_dict()]`。

`verify_citation`：
- `parse_citations` 为空 → `NO_CITATION_FOUND`。
- 去重 `(law, number)`；逐条 `scope_of`：
  - `in_corpus` → `article = corpus.get(...)`；`status = citation_status(article)`（`article.status == "有效"` → `exists`，否则 `amended`）；`official_text = article.text`；`mismatch = _mismatch(text, citation, article.text)`。
  - `out_of_scope` → `status="out_of_scope"`，`official_text=None`，`mismatch=None`。
  - `not_found` → `status="not_found"`，`official_text=None`，`mismatch=None`。
- `_mismatch`：引用后 200 字符内找 `[“"](.{2,200}?)[”"]`；没有引文返回 `None`；有则比较 `normalize_text(quote) in normalize_text(official_text)`，不在则 `True`，在则 `False`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_law.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add tools/law_search.py tools/citation.py tests/test_tools_law.py
git commit -m "feat: add law search and citation verification tools"
```

---

## Task 9: server 注册、stdio 集成测试、transcript

**Files:**
- Modify: `server.py`（注册全部 4 个工具）
- Create: `tests/test_mcp_stdio.py`
- Create: `scripts/mcp_transcript.py`

**Interfaces:**
- Consumes: `register_legal_service`、`register_route`、`register_law_search`、`register_citation`
- Produces: stdio server 暴露 4 个工具
- Produces: `python scripts/mcp_transcript.py > docs/mcp-transcript.json`

- [ ] **Step 1: 写失败测试**

`tests/test_mcp_stdio.py`：

```python
import json, os, sys
from pathlib import Path
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.asyncio
async def test_stdio_lists_four_tools():
    env = {**os.environ, "USE_MOCK": "1", "USE_LIVE": "0", "LAW_DATA_DIR": str(ROOT / "data" / "laws")}
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "find_legal_service", "plan_route", "search_law", "verify_citation"
            }
            result = await session.call_tool("search_law", {"query": "违约金过高"})
            data = json.loads(result.content[0].text)
            assert data[0]["article"] == "第五百八十五条"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_mcp_stdio.py -q`
Expected: FAIL，工具集合为空或不匹配

- [ ] **Step 3: 实现 server 注册与 transcript**

`server.py` 的 `create_server()` 创建 `MCPServer("legal-aid-mcp")`，构造 `ctx`，依次调用 4 个 `register_*`。

`scripts/mcp_transcript.py`：
- 用 `stdio_client` + `ClientSession` 启动 `server.py`。
- 记录 `initialize`、`tools/list`、以及 4 个示例调用（`find_legal_service`、`plan_route`、`search_law`、`verify_citation`）。
- 输出 JSON：`{"tools": [...], "calls": [{"name":..., "arguments":..., "result":...}]}`。
脚本在创建 server 前强制 `USE_LIVE=0`、`USE_MOCK=1`（或直接传 `load_settings(env={"USE_LIVE": "0", "USE_MOCK": "1", ...})`），确保只走 mock、不耗百度额度。

- [ ] **Step 4: 跑测试确认通过**

Run:
```powershell
python -m pytest tests/test_mcp_stdio.py -q
python scripts/mcp_transcript.py > docs/mcp-transcript.json
```
Expected: `1 passed`；transcript 文件包含 4 个工具和 4 次调用。

- [ ] **Step 5: 提交**

```bash
git add server.py tests/test_mcp_stdio.py scripts/mcp_transcript.py docs/mcp-transcript.json
git commit -m "feat: register all tools and verify stdio transport"
```

---

## Task 10: README、测试报告、学习笔记、仓库收尾

**Files:**
- Create: `README.md`
- Create: `docs/test-report.md`
- Create: `docs/learning-notes.md`
- Modify: `.gitignore`
- Modify: `.env.example`

**Interfaces:**
- Consumes: 全部实现与测试
- Produces: 可交接的仓库

- [ ] **Step 1: 写 README**

必须包含：
- 项目是什么、4 个工具、目录结构。
- 安装：`python -m venv .venv`、`.venv\Scripts\activate`、`pip install -r requirements.txt`。
- 配置：复制 `.env.example` 为 `.env`，填 `BAIDU_AK`；说明 `USE_LIVE=1` 才真实调用。
- 运行：`python server.py`（stdio）。
- MCP Inspector 接入命令（按实际版本写）。
- WorkBuddy 接入片段：command `python`，args `["Z:\\project-mcp\\server.py"]`，env 里传 `BAIDU_AK`；说明以 WorkBuddy 实际版本为准。
- 测试：`python -m pytest -q`、`python scripts/verify_laws.py`。
- 法条来源与范围：民法典合同编 463–988、司法解释 69 条；找不到时会明说。
- 安全：AK 不进仓库，`.env` 已 gitignore。

- [ ] **Step 2: 写 8 条测试报告**

`docs/test-report.md` 用表格记录执行书 5.3 的 8 条场景：问题、实际工具调用、返回摘要、是否符合预期、备注（mock/真实/缓存）。至少包含一次多工具组合。WorkBuddy 不可用时，用 `docs/mcp-transcript.json` 和 Inspector 截图作为证据，并标注“WorkBuddy 待人工复测”。如果有 GUI，启动 `npx @modelcontextprotocol/inspector python server.py`，截图工具列表和一次调用，保存到 `docs/screenshots/`；无 GUI 就记录原因并用 transcript 代替。

- [ ] **Step 3: 写学习笔记**

`docs/learning-notes.md` 一页以内：initialize → tools/list → tools/call 三阶段；踩坑（MCP 2.x 把 FastMCP 改名 MCPServer、百度状态码、法条 docx 解析、UTF-8 编码）与解决办法。

- [ ] **Step 4: 更新 `.gitignore` 与 `.env.example`**

`.gitignore` 至少包含：`.env`、`.env.*`、`!.env.example`、`.venv/`、`cache/`、`data/raw/`、`__pycache__/`、`.pytest_cache/`、`*.pyc`。

- [ ] **Step 5: 初始化 git 并提交**

```bash
git add .
git commit -m "docs: add readme, test report, and learning notes"
```

- [ ] **Step 6: 最终验证**

Run:
```powershell
python -m pytest -q
python scripts/verify_laws.py --data-dir data/laws
python -c "import server; print('server import ok')"
git check-ignore .env
git ls-files | Select-String -Pattern "^\.env$"
```
Expected: pytest 全绿；verify 输出 526/69；import ok；`git check-ignore` 输出 `.env`；`git ls-files` 没有输出。

把原始输出贴给用户，未通过就停在失败任务，不宣称完成。

---

## 执行顺序与依赖

```text
Task 1 → Task 2 → Task 3 → Task 4
Task 1 → Task 5 → Task 6
Task 4 + Task 6 → Task 7
Task 4 → Task 8
Task 7 + Task 8 → Task 9 → Task 10
```

Task 5 需要真实百度调用（7 次）；Task 3 需要真实 flk 下载。其余测试全部离线。
