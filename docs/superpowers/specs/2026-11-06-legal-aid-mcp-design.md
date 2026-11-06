# 法律援助一条龙 MCP · 设计文档

> 日期：2026-11-06
> 状态：待用户批准（批准后才进入实施计划）
> 依据：`执行书.md`（v1.0）
> 说明：本文件是执行书的实现级设计；两者冲突时以执行书为准，本文只补充执行书没写死的实现决策。

---

## 1. 一句话

做一个面向济南的 **stdio MCP Server**：普通人能找法院/法律援助/律所、查路线；律师能查民法典合同编条文、核对引用。外部地图能力用百度地图开放平台，法条用国家法律法规数据库的官方原文，默认 mock，真实调用有预算上限。

## 2. 意图与成功标准

- **给谁用**：普通当事人（该找谁、怎么去、依据是什么）；律师/法务（快速查条文、核对 AI 或对方文书里的引用）。
- **为什么做**：实习任务书要求把一个国内可直连的公开 API 包成 MCP Server；法律场景天然需要“地图 + 法条”两类能力。
- **成功的样子**：
  1. WorkBuddy 或 MCP Inspector 能通过 stdio 加载 server；
  2. 4 个工具都能被模型按描述正确调用；
  3. 8 条测试场景有记录，含一次多工具组合；
  4. 法条回答只来自本地官方语料，找不到就明说，不编造；
  5. AK 只从环境变量读，仓库里没有密钥。

## 3. 目标 / 非目标 / 反目标

### 目标

1. 找机构：法院、律师事务所、法律援助中心，返回名称、地址、电话、经纬度。
2. 查路线：驾车/步行，返回距离、时间、主要步骤。
3. 查法条：民法典合同编（第 463–988 条）+ 合同编通则司法解释。
4. 核引用：识别文字中的法条引用，判断存在/不存在/已修改，能对比原文时给出差异。

### 非目标（v1 明确不做）

- 不判断管辖法院、不预测胜诉、不评价律师水平。
- 不代写诉状、不整理证据、不处理案宗。
- 不训练模型，不把案宗或用户输入发给第三方。
- v1 不放宪法、案例、地方性法规；只做合同编 + 合同编通则司法解释。

### 反目标（即使技术跑通也算失败）

- 为了“看起来能答”而编造法条、地址、电话或路线。
- 把 AK、用户输入或案宗写进日志/仓库。
- 真实调用失控，把百度配额跑超。
- 工具描述含糊，模型只能靠猜参数。

## 4. 约束与已验证事实

| 事实 | 证据 |
|---|---|
| 百度 AK 可用 | 2026-11-06 实测：地点检索、地理编码、驾车路线均返回 `status: 0` |
| 百度返回字段够用 | 地点检索返回 name/address/telephone；地理编码返回 lng/lat；路线返回 distance/duration |
| 法条官方源可用 | `flk.npc.gov.cn` 的搜索、详情、docx 下载接口均返回 200 |
| 民法典规模 | 官方 docx 解析出 1260 条；合同编 463–988 共 526 条，首尾已核对 |
| 司法解释规模 | 官方 docx 解析出 69 条 |
| 运行环境 | Python 3.14.7；`mcp` 2.3.0 声明 `requires_python >=3.10`，并对 3.14 有专门依赖分支；2.x 把 `FastMCP` 更名为 `MCPServer`（`mcp.server.mcpserver.MCPServer`） |
| pi agent | `pi 1.4.0`，模型 `deepseek/deepseek-flash`；有 bash，可用 `curl` 访问 flk；没有 webfetch |
| 仓库现状 | `Z:\project-mcp` 目前只有执行书和 `.opencode` 配置，不是 git 仓库 |

## 5. 方案选择

### 5.1 外部能力：百度地图 + 本地法条（方案 A，已选）

- **A（选）**：百度地图开放平台 + 本地民法典/司法解释语料。满足“公开 API”要求，地图与法条互补，AK 已实测可用。
- **B（不选）**：Open-Meteo 保底。零 Key，但失去法院/律所/路线场景，法律部分还得另做；用户已提供百度 AK，不需要保底。
- **C（不选）**：纯国家法律法规数据库。没有地图工具，不满足“找机构/查路线”的目标，且公开 API 合规性有争议。

### 5.2 法条数据来源：官方 docx + pi 驱动抓取 + 独立复核（已选）

- **不选“让 pi 凭记忆生成法条”**：无法保证不编造，`verify_citation` 会失去可信度。
- **不选随机 GitHub 法条 JSON**：版本、条文号、错别字都无法保证，来源也不够权威。
- **选官方 docx**：从 `flk.npc.gov.cn` 搜索到 `bbbs`，用下载接口拿到官方 docx，按段落解析条文。pi 负责执行抓取/抽取脚本；主控用独立脚本复核条数、边界和抽样原文。

### 5.3 运行时：Python + MCP SDK 2.x `MCPServer`（已选）

- 执行书要求 Python MCP SDK + FastMCP，stdio 启动；2.x 中 `FastMCP` 已更名为 `MCPServer`（`from mcp.server.mcpserver import MCPServer`），本设计按 2.x 的 `MCPServer` 实现。
- 依赖尽量少：`mcp==2.3.0`、`httpx`、`python-dotenv`、`pytest`、`pytest-asyncio`。docx 解析用标准库 `zipfile` + XML，不额外装 `python-docx`。

## 6. 架构

```text
WorkBuddy / MCP Inspector
  └─ MCP Client (stdio)
       └─ legal-aid-mcp (Python, FastMCP)
            ├─ tools/legal_service.py  → 百度 place/v2/search
            ├─ tools/route.py          → 百度 geocoding/v3 + direction/v2
            ├─ tools/law_search.py     → data/laws/*.json
            ├─ tools/citation.py       → data/laws/*.json
            ├─ baidu.py                → HTTP、超时、错误映射、缓存、预算
            └─ laws.py                 → 语料加载、条文号转换、检索/核对
```

### 模块职责

| 模块 | 职责 |
|---|---|
| `server.py` | 创建 `MCPServer`，注册 4 个工具，stdio 启动 |
| `config.py` | 读取 `.env`/环境变量，默认值，路径解析 |
| `errors.py` | 统一错误类型与中文提示，禁止把原始异常直接抛给模型 |
| `baidu.py` | 百度 HTTP 客户端；mock/live 切换；缓存；预算；状态码映射 |
| `laws.py` | 加载语料；中文数字 ↔ 整数；检索打分；引用解析与核对 |
| `tools/*.py` | 每个工具的参数校验、调用、返回结构 |
| `scripts/fetch_laws.py` | 从 flk 抓官方 docx 并生成语料 JSON |
| `scripts/verify_laws.py` | 校验条数、边界、重复、抽样原文、docx 哈希 |

## 7. 工具契约

所有工具返回 **JSON 可序列化的 dict/list**；失败时返回统一结构：

```json
{"error": {"code": "CITY_NOT_FOUND", "message": "在济南未找到...，请提供更具体的区县或换关键词"}}
```

不把 Python traceback、URL、AK 返回给模型。

### 7.1 `find_legal_service`

- **描述**：在指定城市搜索法院、律师事务所或法律援助中心，返回机构名称、地址、电话和经纬度。用户问“去哪个法院立案”“附近有没有法律援助”“找律师”时使用。只返回机构信息，不判断管辖，也不评价律师水平。
- **参数**：
  - `keyword`: `法院` / `律师事务所` / `法律援助中心`，必填
  - `city`: 默认 `济南`
  - `district`: 可选，如 `历下区`
  - `limit`: 1–10，默认 5
- **百度调用**：`/place/v2/search`，`query` 按关键词映射（`法院`→`人民法院`，`法律援助中心`→`法律援助` 作为降级），`region=city`，`scope=2`，`page_size=limit`；单次请求，不翻页。
- **城市校验**：v1 维护济南市及区县白名单；`city` 明显不在白名单时直接返回 `CITY_NOT_FOUND`，不发请求。白名单外的城市仍允许尝试，空结果返回 `NO_RESULTS`，不臆断“城市不存在”。
- **返回**：`[{"name","address","telephone","lat","lng"}]`；地址或电话缺失时保留 `null`，不编造。
- **错误**：`CITY_NOT_FOUND` / `NO_RESULTS` / `AK_INVALID` / `QUOTA_EXCEEDED` / `UPSTREAM_TIMEOUT` / `BUDGET_EXHAUSTED`。

### 7.2 `plan_route`

- **描述**：规划从起点到终点的驾车或步行路线，返回距离、预计时间和主要路段。用户问“怎么去法院/律所/法律援助中心”时使用。起点和终点可以是地址或 `纬度,经度`；如果只有机构名，先用 `find_legal_service` 查地址。
- **参数**：
  - `origin`: 必填，地址或 `lat,lng`
  - `destination`: 必填，地址或 `lat,lng`
  - `mode`: `driving` / `walking`，默认 `driving`
- **百度调用**：地址先走 `/geocoding/v3/`，再走 `/direction/v2/{mode}`；`lat,lng` 直接用。
- **返回**：`{"distance_m": int, "duration_s": int, "steps": [{"instruction": str, "distance_m": int, "duration_s": int}]}`。
- **错误**：`GEOCODE_FAILED` / `NO_ROUTE` / `AK_INVALID` / `QUOTA_EXCEEDED` / `UPSTREAM_TIMEOUT`。

### 7.3 `search_law`

- **描述**：在本地民法典合同编和合同编通则司法解释中检索条文，返回条文号、原文、生效日期和出处。用户问“法律怎么规定”“违约金能不能调”“合同解除条件”时使用。只返回检索到的原文，不编造；没有匹配时明确说未找到。
- **参数**：
  - `query`: 必填
  - `law`: `民法典` / `合同编通则司法解释`，可选
  - `limit`: 1–10，默认 5
- **检索**：本地打分，不调用外部服务。
  - 查询里出现“第 X 条” → 精确条号命中，最高分；
  - 关键词命中正文 → 按出现次数加分；
  - 关键词命中编/章/节标题 → 少量加分；
  - 同分按条文号升序，保证结果稳定。
- **返回**：`[{"law","article","text","effective_date","source_url","status"}]`。
- **范围**：只检索 463–988 和司法解释 69 条；查询明确指向范围外条文时返回 `OUT_OF_SCOPE`，不把“没收录”说成“不存在”。
- **错误**：`NO_MATCH` / `OUT_OF_SCOPE` / `CORPUS_NOT_LOADED`。

### 7.4 `verify_citation`

- **描述**：核对一段文字中引用的法条是否存在、是否现行有效、原文是否一致。用户提供答辩状、合同、AI 回答，要求“核对法条”“看看引用对不对”时使用。返回逐条核对结果；未找到的条文明确标为不存在，不猜测。
- **参数**：`text`: 必填。
- **引用识别**：正则匹配 `民法典` / `中华人民共和国民法典` / `合同编通则司法解释` 等前缀 + `第[中文数字或阿拉伯数字]+条`；支持“第 585 条”“第五百八十五条”。
- **返回**：`[{"citation","status","official_text","mismatch"}]`
  - `status`: `exists` / `not_found` / `amended` / `out_of_scope`
    - `exists`：在 v1 语料内且现行有效；
    - `not_found`：属于 v1 收录的法律，但条号超出该法律全文范围（如民法典第 9999 条 > 1260）；
    - `amended`：该条存在但时效性为“已修改/已废止”（v1 语料当前均为有效，保留字段）；
    - `out_of_scope`：真实存在但不在 v1 收录范围（民法典合同编以外的条文、民诉法、旧合同法等），**不能**标成 `not_found`。
  - `mismatch`: 输入里带引号原文时做归一化比对，返回 `true/false/null`；没带原文时 `null`
- **错误**：`NO_CITATION_FOUND` / `CORPUS_NOT_LOADED`。

## 8. 数据管线

### 8.1 抓取步骤（`scripts/fetch_laws.py`）

1. `POST /law-search/search/list`，按标题精确检索，拿 `bbbs`、`title`、`gbrq`、`sxrq`、`sxx`、`flxz`。
2. `GET /law-search/download/pc?bbbs=...&format=docx`，拿签名 URL。
3. 下载 docx（用于解析文本）和 PDF（公报原版，用于存证/抽查），分别计算 SHA256。
4. 解压 `word/document.xml`，提取 `<w:p>` 段落文本；跳过以 `<w:` 开头的脏段落。
5. 按 `^第[零〇一二三四五六七八九十百千]+条` 切分条文；后续段落归入当前条文。
6. 记录编/章/节标题，作为每条的 `section`。
7. 民法典只保留 463–988；司法解释保留全部 69 条。
8. 输出 JSON + `manifest.json`（来源、条数、SHA256、抓取时间）。

### 8.2 语料字段

```json
{
  "law": "中华人民共和国民法典",
  "short_name": "民法典",
  "article": "第五百八十五条",
  "article_number": 585,
  "text": "第五百八十五条　当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金……",
  "section": ["第三编 合同", "第二分编 典型合同", "第八章 违约责任"],
  "promulgation_date": "2020-05-28",
  "effective_date": "2021-01-01",
  "status": "有效",
  "sxx": 3,
  "source_url": "https://flk.npc.gov.cn/detail?id=<bbbs>&type=法律&title=中华人民共和国民法典",
  "bbbs": "<bbbs>",
  "source_sha256": "<docx sha256>",
  "pdf_sha256": "<公报原版 pdf sha256>"
}
```

**法律范围元数据**（放在 `manifest.json`）：

| 法律 | 全文条号范围 | v1 收录 | 说明 |
|---|---|---|---|
| 民法典 | 1–1260 | 463–988 | 合同编；其余条号返回 `out_of_scope` |
| 合同编通则司法解释 | 1–69 | 1–69 | 全量 |

`sxx` 映射：1=已废止、2=已修改、3=有效、4=尚未生效（来自 flk 前端枚举）。`verify_citation` 的 `amended` 由 `sxx` 不是 3 触发。

### 8.3 校验规则（`scripts/verify_laws.py`）

- 民法典合同编条数必须为 **526**，首条 463、末条 988，条号连续、无重复。
- 司法解释条数必须为 **69**，首条 1、末条 69，条号连续、无重复。
- 抽样：585 条正文含“违约金”；563 条含“解除”；司法解释第 1 条含“合同条款”。
- 范围：民法典第 100 条应判 `out_of_scope`，第 9999 条应判 `not_found`；民诉法引用应判 `out_of_scope`。
- PDF 存证文件存在，SHA256 与 `manifest.json` 一致。
- 每条 `text` 长度 > 20，`source_url` 非空。
- 失败时退出码非 0，打印具体条号。

### 8.4 pi 的角色

- 抓取是实施计划的**阻塞步骤**，不是外部前置条件：主控用 `scripts/fetch_laws.py` 抓取，pi 通过 `bash` + `curl` 执行同一脚本或独立抓一份 docx 做交叉核对。
- 原始 docx + PDF 放 `data/raw/`（gitignore），仓库只提交解析后的 JSON + `manifest.json`（含两者的 SHA256）。
- **pi 不凭记忆生成法条**；任何进入语料的文本都必须能追溯到官方 docx。
- 主控用独立脚本复核 pi 的产出；复核不通过就不入库。

## 9. 配置、缓存、预算、安全

| 变量 | 默认 | 作用 |
|---|---|---|
| `BAIDU_AK` | 无（必填） | 百度服务端 AK |
| `USE_MOCK` | `1` | 非 live 时读 `fixtures/baidu/`，不请求百度 |
| `USE_LIVE` | `0` | `1` 即进入真实调用；与 `USE_MOCK` 同时为 1 时 live 优先并写 stderr 警告 |
| `LIVE_BUDGET` | `20` | **项目生命周期**真实调用硬上限，不按日重置 |
| `CACHE_DIR` | `cache/` | 缓存目录 |
| `CACHE_TTL_HOURS` | `24` | 缓存有效期 |
| `LAW_DATA_DIR` | `data/laws/` | 语料目录 |

- **mock**：`USE_LIVE=0` 时按“关键词 + 城市 + 区县”读 fixture；找不到就返回 `NO_RESULTS`，不偷偷发真实请求。
- **live**：`USE_LIVE=1` 即进入真实调用（不要求同时改 `USE_MOCK`）；每次请求前检查预算；成功后写缓存并计数。
- **缓存键**：规范化后的完整 URL 的 SHA256；缓存文件含 `fetched_at` 和原始响应。
- **预算**：`cache/budget.json` 记录 `{used, limit, updated_at}`，跨天不重置；`LIVE_BUDGET=20` 是项目生命周期硬上限。超限返回 `BUDGET_EXHAUSTED`，提示“真实调用额度已用完，已切换到缓存/样本”，不会因为跨天自动解锁。
- **安全**：AK 只从环境变量读；日志只写 stderr；错误信息里不出现 AK；`.env` 在 `.gitignore` 里；提交前用脚本扫描仓库确认没有密钥。

## 10. 测试策略

### 10.1 自动化

| 文件 | 覆盖 |
|---|---|
| `tests/test_law_data.py` | 条数、边界、重复、抽样原文、source_url |
| `tests/test_laws.py` | 中文数字转换、条号解析、检索打分、引用识别、`out_of_scope`/`not_found` 区分 |
| `tests/test_baidu.py` | mock 模式、状态码映射、超时、缓存、预算 |
| `tests/test_tools.py` | 4 个工具的正常/异常返回结构 |
| `tests/test_mcp_stdio.py` | 启动 stdio server，`tools/list`、`tools/call` 各一次 |

验证命令：

```powershell
python -m pytest -q
python scripts/verify_laws.py
```

### 10.2 执行书 8 条场景

1. 济南市中级人民法院在哪？→ `find_legal_service`
2. 违约金过高，法律怎么规定？→ `search_law` → 585 条
3. 济南西站 → 济南中院，附近有法律援助吗？→ `find_legal_service` → `plan_route`
4. 核对答辩状里的 585 条，并找济南律所 → `verify_citation` → `find_legal_service`
5. 历下法院怎么走？→ 追问或匹配“历下区人民法院”
6. 济南市不存在法院在哪？→ 明确说查不到
7. 什么是违约金？→ 不调用工具，直接回答
8. 民法典第 9999 条怎么说？→ `verify_citation` → `not_found`

其中 1–6、8 可以用脚本直接调工具验证；7 属于模型行为，写进测试报告手工记录。WorkBuddy 不可用时就附 MCP Inspector 的调用截图和说明；如果 GUI 不可用，用 `scripts/mcp_transcript.py` 生成 stdio JSON-RPC 对话记录作为证据，并明确标注“截图待人工补”。

### 10.3 验收命令（最终交付前必须贴原始输出）

```powershell
python -m pytest -q
python scripts/verify_laws.py
python -c "import server; print('server import ok')"
python scripts/mcp_transcript.py --out docs/mcp-transcript.json
```

## 11. 交付物与目录

```text
legal-aid-mcp/                      （即 Z:\project-mcp）
├─ server.py
├─ config.py
├─ errors.py
├─ baidu.py
├─ laws.py
├─ tools/
│  ├─ __init__.py
│  ├─ legal_service.py
│  ├─ route.py
│  ├─ law_search.py
│  └─ citation.py
├─ data/laws/
│  ├─ civil_code_contract.json
│  ├─ contract_interpretation_2023.json
│  └─ manifest.json
├─ data/raw/              （gitignore，原始 docx + 公报 PDF）
├─ fixtures/baidu/
│  ├─ place_court.json          # 法院（含济南中院）
│  ├─ place_court_lixia.json    # 历下区人民法院（场景 5）
│  ├─ place_law_firm.json       # 律师事务所（场景 4）
│  ├─ place_legal_aid.json      # 法律援助中心（场景 3）
│  ├─ geocode_court.json
│  ├─ geocode_west_station.json # 济南西站（场景 3）
│  └─ route_west_station.json
├─ scripts/
│  ├─ fetch_laws.py
│  ├─ verify_laws.py
│  └─ mcp_transcript.py
├─ tests/
├─ docs/
│  ├─ test-report.md
│  └─ learning-notes.md
├─ cache/                （gitignore）
├─ README.md
├─ requirements.txt
├─ .env.example
└─ .gitignore
```

交付物：仓库、8 条测试报告、Inspector 截图、WorkBuddy 接入说明、一页学习笔记。

## 12. 风险与应对

| 风险 | 应对 |
|---|---|
| 百度 AK 权限/配额问题 | 已有 3 条实测；真实调用全部走预算和缓存；失败时给可操作提示 |
| 百度整体不可用 | 高德作为备选，但需要“Web 服务”类型 key；2026-11-06 实测用户提供的 key 返回 `INVALID_USER_KEY`，暂不可用，待换有效 key 后再加适配器 |
| “法律援助中心”POI 不全 | 降级搜“法律援助”；仍无结果就明说，不编造 |
| POI 不返回“擅长领域” | 不编造；提示用户电话确认 |
| 法条 docx 结构变化 | 抓取脚本记录 SHA256；校验脚本失败就停止入库；保留原始 docx 以便回溯 |
| Python 3.14 兼容性 | `mcp` 2.3.0 已声明支持；若装不上，用 `uv` 建 3.12 venv，README 写清 |
| WorkBuddy 不可用 | 用 MCP Inspector 验证 stdio；测试报告标注哪些是真实调用、哪些是 mock |
| pi 编造内容 | 只让 pi 执行抓取/抽取脚本；语料以官方 docx 为准，独立复核 |
| 模型不调用工具 | 工具描述写清“何时用/返回什么/和相近工具的区别”；测试报告做前后对比 |

## 13. 留给实现阶段的决定

- 检索打分的具体权重和停用词表（先用简单可解释规则，测试驱动调整）。
- 缓存文件的具体目录层级和清理命令。
- 重试策略：只对超时/网络错误重试 1 次，不对 4xx/配额错误重试。
- README 里 WorkBuddy 配置片段的具体字段名（以用户实际版本为准）。

## 14. 验收标准

- [ ] `python -m pytest -q` 全绿，原始输出已记录。
- [ ] `python scripts/verify_laws.py` 输出 526 / 69，抽样通过。
- [ ] `python server.py` 能通过 stdio 启动，`tools/list` 返回 4 个工具。
- [ ] 8 条场景有记录，至少 1 条多工具组合。
- [ ] 仓库里搜不到 AK；`.env` 未提交。
- [ ] README 能让他人从零安装、配置、接入 Inspector/WorkBuddy。
- [ ] 法条回答只来自本地语料；找不到时有明确中文提示。

## 15. Builder check 决议（2026-11-06）

1. **`amended` / `out_of_scope`**：新增 `out_of_scope` 状态，避免把“v1 没收录”说成“不存在”。民法典第 100 条 → `out_of_scope`；第 9999 条 → `not_found`；民诉法/旧合同法 → `out_of_scope`。`amended` 由 flk 的 `sxx=2` 触发，v1 语料当前不会产生。
2. **fixtures 不够**：补录 4 条真实样本——律所、法律援助中心、济南西站地理编码、历下区人民法院。加上已验证的 3 条，共 7 次真实调用；`LIVE_BUDGET=20` 是生命周期上限，留 13 次余量。
3. **预算**：`LIVE_BUDGET=20` 项目生命周期硬上限，跨天不重置；不是每日配额。
4. **抓取归属**：抓取是计划里的阻塞步骤，由主控执行，pi 用 `bash`+`curl` 跑同一脚本或独立交叉核对；原始 docx 放 `data/raw/` 并 gitignore。
5. **配置语义**：`USE_LIVE=1` 即真实调用，live 优先；不再要求同时设置 `USE_MOCK=0`，避免“以为在演示真实调用、实际还在 mock”。
6. **limit 与 page_size**：`page_size=limit`（1–10），单次请求，不翻页；不承诺超过 10 条。
7. **CITY_NOT_FOUND**：用济南市及区县白名单判断；明显不在白名单直接报错，不发请求；白名单外城市空结果报 `NO_RESULTS`。
8. **Inspector 截图**：优先用 MCP Inspector + 浏览器截图；GUI 不可用时用 `scripts/mcp_transcript.py` 生成 stdio JSON-RPC 记录，并在测试报告标注“截图待人工补”。
