# 法律援助一条龙 MCP

面向济南的 stdio MCP Server：普通人能找法院/法律援助/律所、查路线、算诉讼费和期间；律师能查民事诉讼条文、核对引用。

## 5 个工具

| 工具 | 作用 |
|---|---|
| `find_legal_service` | 在济南搜索法院、律师事务所、法律援助中心，返回名称、地址、电话、经纬度、来源和置信度 |
| `plan_route` | 规划驾车/步行路线，返回距离、预计时间、主要步骤；可多地图源交叉验证 |
| `search_law` | 在民法典合同编、民诉法、民诉法解释、证据规定、诉讼费办法、法律援助法中检索条文 |
| `verify_citation` | 核对文字里的法条引用：存在 / 不存在 / 已修改 / 不在收录范围 |
| `legal_calculator` | 计算诉讼费、保全费、上诉期/答辩期/自定义期间，附官方条文依据 |

## 选型与任务书对照

任务书要求自选 API 满足“国内直连、有免费额度、HTTPS、有官方文档”。本项目选百度地图开放平台：

| 要求 | 本项目情况 |
|---|---|
| 国内直连 | `https://api.map.baidu.com`，2026-11-06 实测地点检索、地理编码、驾车路线均返回 `status: 0` |
| 有免费额度 | 百度地图开放平台个人开发者有免费配额，具体以控制台“配额”页为准；项目另设 `LIVE_BUDGET=20` 生命周期硬上限，默认 mock 不耗额度 |
| HTTPS | 全部请求走 HTTPS |
| 官方文档 | <https://lbsyun.baidu.com/> |

高德 key 实测返回 `INVALID_USER_KEY`，且用户明确不用高德；v2 不接高德，改用**百度 + 腾讯 + 天地图**多源：

| provider | key | 说明 |
|---|---|---|
| 百度地图 | `BAIDU_AK` | 默认 primary；有免费个人配额 |
| 腾讯位置服务 | `TENCENT_MAP_KEY` | 可选；无 key 自动跳过 |
| 天地图 | `TIANDITU_KEY` | 可选；官方地理信息，无 key 自动跳过 |

- 默认顺序 `MAP_PROVIDERS=baidu,tencent,tianditu`。
- 任一 provider 超时/配额/key 失效，自动尝试下一个；全部失败时按 `MAP_LIVE_FAILURE_MODE` 处理（默认 `cache`）。
- 有 2 个以上源成功时，返回 `confidence` 和 `discrepancies`；结果取去重并集，不丢 secondary 独有 POI。
- 坐标统一输出 WGS-84；`plan_route` 的坐标输入默认 WGS-84，可用 `coord_system=gcj02|bd09` 兼容旧坐标。

## 免费数据源

| 数据源 | 用途 | 失败时 |
|---|---|---|
| 12348 中国法律服务网 | 济南区县法律援助中心名称/地址/电话 | 本地快照 → 地图 POI |
| 民政部国家地名信息库 | 济南 12 区县校验和区划码 | 本地快照 |
| timor.tech 节假日 | 诉讼期间/上诉期顺延 | 本地快照 → 仅周末 |
| flk.npc.gov.cn | 全部法条原文 | 已提交的本地语料 |
| 本地计算器 | 诉讼费/保全费/期间 | 不依赖外部服务 |

12348 接口是官方页面使用的未公开接口，带反爬签名；本项目做了低频查询、24 小时缓存和快照兜底。它变化时不会阻塞法条、计算器或地图工具。

## 目录

```text
server.py                 MCP server 入口（stdio）
config.py                 环境变量与路径
errors.py                 统一错误结构与 run_tool
context.py                AppContext
coord.py                  BD-09 / GCJ-02 / WGS-84 转换
baidu.py                  百度地图客户端（mock/live/缓存/预算）
maps/                     多地图 provider、failover、交叉验证
divisions.py              民政部区划索引（济南 12 区县）
holidays.py               节假日/工作日计算
legal_aid.py              12348 法律援助目录客户端
calculators.py            诉讼费、保全费、期间计算
laws.py                   中文数字、引用解析、语料加载与检索
tools/                    5 个工具
scripts/fetch_laws.py     从国家法律法规数据库抓官方 docx/pdf
scripts/verify_laws.py    校验 1678 条、条号、抽样和 SHA256
scripts/fetch_divisions.py 抓取济南区划快照
scripts/fetch_holidays.py 抓取节假日快照
scripts/fetch_legal_aid.py 抓取 12348 济南法援中心快照
scripts/record_fixtures.py 录制百度样本
scripts/mcp_transcript.py 生成 stdio JSON-RPC 对话记录
data/laws/                已生成的语料 JSON + manifest
data/divisions/           济南区划快照
data/holidays/            2025/2026 节假日快照
data/legal_aid/           12348 济南法援中心快照
fixtures/baidu/           百度样本（测试/演示默认走这里）
docs/                     设计、计划、测试报告、学习笔记
```

## 安装

```powershell
cd Z:\project-mcp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

也可以用 `uv`：

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

## 配置

```powershell
copy .env.example .env
notepad .env
```

至少填：

```text
BAIDU_AK=你的百度服务端AK
```

默认 `USE_MOCK=1`、`USE_LIVE=0`，测试和演示都读 `fixtures/baidu/`，不消耗百度额度。要做真实调用时改：

```text
USE_LIVE=1
```

`USE_MOCK=0` 且 `USE_LIVE=0` 会启动失败，避免“关掉 mock 却仍在读样本”。`LIVE_BUDGET=20` 是项目生命周期真实调用硬上限，不按日重置。相同请求会走 `cache/`，不重复花预算。

v2 新增：

```text
TENCENT_MAP_KEY=          # 可选
TIANDITU_KEY=             # 可选
MAP_PROVIDERS=baidu,tencent,tianditu
MAP_CROSS_CHECK=1
MAP_LIVE_FAILURE_MODE=cache
LEGAL_AID_LIVE=1
HOLIDAY_LIVE=1
```

`USE_LIVE=0` 是全局离线开关：地图只用 fixtures，12348/民政部/节假日只用本地快照，测试不会联网。没有腾讯/天地图 key 时它们自动跳过，百度/mock/法条/计算器照常工作。

## 运行

```powershell
python server.py
```

这是 stdio server，直接运行会等待 MCP Client 输入；用下面的 Inspector 或 WorkBuddy 连接。

### MCP Inspector

```powershell
npx @modelcontextprotocol/inspector python server.py
```

在 Inspector 里应看到 5 个工具；`search_law("违约金过高")` 应返回民法典第五百八十五条。

### WorkBuddy

本机已写入 WorkBuddy 的 MCP 配置：

```text
C:\Users\21165\.workbuddy\connectors\default\mcp.json
```

条目名 `legal-aid-mcp`，当前是 `USE_MOCK=1`、`USE_LIVE=0`，不消耗百度额度。重启 WorkBuddy 后在 MCP / Connectors 设置里启用，并批准 5 个工具。

完整条目：

```json
"legal-aid-mcp": {
  "type": "stdio",
  "command": "Z:\\project-mcp\\.venv\\Scripts\\python.exe",
  "args": ["Z:\\project-mcp\\server.py"],
  "env": {
    "USE_MOCK": "1",
    "USE_LIVE": "0"
  },
  "timeout": 120000,
  "disabled": false
}
```

需要真实地图调用时，把 `env` 改成 `USE_LIVE=1` 并加 `BAIDU_AK`，然后重启 WorkBuddy。详细步骤见 `docs/workbuddy-test-guide.md`。

## 测试

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws --require-raw
.venv\Scripts\python scripts\mcp_transcript.py --out docs\mcp-transcript.json
```

`--require-raw` 用于 CI 或干净 clone：`data/raw/` 不存在时直接失败，而不是只 WARN。

当前结果：`184 passed`；语料校验输出 `OK: 1678 条；民法典合同编 526 条；司法解释 69 条；民事诉讼核心包已校验`。

## 交付证据

- `HANDOFF.md`：交接与优化清单（下一 session 先读这个）
- `docs/screenshots/inspector-tools.jpeg`：MCP Inspector 工具列表
- `docs/inspector-tools.json`：Inspector `tools/list` 的 JSON 输出
- `docs/mcp-transcript.json`：stdio 5 个工具调用记录
- `docs/workbuddy-test-guide.md`：WorkBuddy 8 条人工测试步骤
- `docs/test-report.md`：8 条场景与真实调用记录

## 法条来源与范围

- 来源：国家法律法规数据库 `flk.npc.gov.cn` 的官方 docx（解析用）和公报 PDF（存证用）。
- 民法典合同编：第 463–988 条，共 526 条。
- 合同编通则司法解释：第 1–69 条，共 69 条。
- 民事诉讼法（2023 修正）：306 条。
- 民诉法解释（2022 修正）：550 条。
- 民事诉讼证据规定：100 条。
- 诉讼费用交纳办法：56 条。
- 法律援助法：71 条。
- 合计 1678 条。
- 元数据：`data/laws/manifest.json` 记录条数、全文条号范围、公布/施行日期、docx/PDF SHA256。
- 重新生成：

```powershell
.venv\Scripts\python scripts\fetch_laws.py --out data\laws --raw-dir data\raw
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
```

`data/raw/` 里的原始 docx/PDF 已 gitignore；仓库只提交解析后的 JSON。

## 安全

- AK 只从环境变量 `BAIDU_AK` 读取，不写进代码、日志、错误信息或缓存元数据。
- `.env` 已 gitignore；提交前用 `git check-ignore .env` 和 `git ls-files` 确认。
- 错误信息只带百度 `status`/`message`，不拼接带 `ak=` 的 URL。

## v1 限制

- 只覆盖济南及下属区县；其他城市返回 `CITY_NOT_FOUND`。
- 收录民法典合同编、合同编通则司法解释、民事诉讼法、民诉法解释、民事诉讼证据规定、诉讼费用交纳办法、法律援助法；其他法律（民法典其他编、旧合同法、刑法等）返回 `out_of_scope`，不会说成“不存在”。
- `verify_citation` 对没有写法律名的引用（如“第585条”）返回 `ambiguous`；传 `law_hint` 或写明“民法典第585条”才会核对。这是为了避免刑法/合同混合文书误判。
- 不判断管辖、不预测胜诉、不推荐“最好的律师”、不代写诉状。
- 高德地图仅作为百度整体不可用时的备选；当前提供的 key 返回 `INVALID_USER_KEY`，v1 未实现高德适配器。
- WorkBuddy 的 8 条人工测试待在有 WorkBuddy 的环境复测；本仓库提供 `docs/mcp-transcript.json` 作为 stdio 证据。

## 8 条场景

见 `docs/test-report.md`。常用问法：

- “济南市中级人民法院在哪？”
- “违约金过高，法律怎么规定？”
- “我在济南西站，要去济南中院立案，附近有法律援助吗？”
- “这份答辩状引用了民法典第 585 条，帮我核对，并找济南的律所。”
- “历下法院怎么走？”
- “民法典第 9999 条怎么说？”
