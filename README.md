# 法律援助一条龙 MCP

面向济南的 stdio MCP Server：普通人能找法院/法律援助/律所、查路线；律师能查民法典合同编条文、核对引用。

## 4 个工具

| 工具 | 作用 |
|---|---|
| `find_legal_service` | 在济南搜索法院、律师事务所、法律援助中心，返回名称、地址、电话、经纬度 |
| `plan_route` | 规划驾车/步行路线，返回距离、预计时间、主要步骤 |
| `search_law` | 在本地民法典合同编（463–988）和合同编通则司法解释中检索条文 |
| `verify_citation` | 核对文字里的法条引用：存在 / 不存在 / 已修改 / 不在收录范围 |

## 目录

```text
server.py                 MCP server 入口（stdio）
config.py                 环境变量与路径
errors.py                 统一错误结构与 run_tool
context.py                AppContext
baidu.py                  百度地图客户端（mock/live/缓存/预算）
laws.py                   中文数字、引用解析、语料加载与检索
tools/                    4 个工具
scripts/fetch_laws.py     从国家法律法规数据库抓官方 docx/pdf
scripts/verify_laws.py    校验 526/69 条、条号、抽样和 SHA256
scripts/record_fixtures.py 录制百度样本
scripts/mcp_transcript.py 生成 stdio JSON-RPC 对话记录
data/laws/                已生成的语料 JSON + manifest
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

## 运行

```powershell
python server.py
```

这是 stdio server，直接运行会等待 MCP Client 输入；用下面的 Inspector 或 WorkBuddy 连接。

### MCP Inspector

```powershell
npx @modelcontextprotocol/inspector python server.py
```

在 Inspector 里应看到 4 个工具；`search_law("违约金过高")` 应返回民法典第五百八十五条。

### WorkBuddy

按 WorkBuddy 的 MCP 配置格式加入（字段名以实际版本为准）：

```json
{
  "mcpServers": {
    "legal-aid": {
      "command": "Z:\\project-mcp\\.venv\\Scripts\\python.exe",
      "args": ["Z:\\project-mcp\\server.py"],
      "env": {
        "BAIDU_AK": "你的百度服务端AK",
        "USE_MOCK": "1",
        "USE_LIVE": "0"
      }
    }
  }
}
```

如果 WorkBuddy 用自己的 Python 环境，把 `command` 换成该环境的 `python`，并确保已安装 `requirements.txt`。

## 测试

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws --require-raw
.venv\Scripts\python scripts\mcp_transcript.py --out docs\mcp-transcript.json
```

`--require-raw` 用于 CI 或干净 clone：`data/raw/` 不存在时直接失败，而不是只 WARN。

当前结果：`106 passed`；语料校验输出 `OK: 民法典合同编 526 条；司法解释 69 条`。

## 交付证据

- `docs/screenshots/inspector-tools.jpeg`：MCP Inspector 工具列表
- `docs/inspector-tools.json`：Inspector `tools/list` 的 JSON 输出
- `docs/mcp-transcript.json`：stdio 4 个工具调用记录
- `docs/workbuddy-test-guide.md`：WorkBuddy 8 条人工测试步骤
- `docs/test-report.md`：8 条场景与真实调用记录

## 法条来源与范围

- 来源：国家法律法规数据库 `flk.npc.gov.cn` 的官方 docx（解析用）和公报 PDF（存证用）。
- 民法典合同编：第 463–988 条，共 526 条。
- 合同编通则司法解释：第 1–69 条，共 69 条。
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
- 只收录民法典合同编和合同编通则司法解释；民法典其他编、民诉法、旧合同法等返回 `out_of_scope`，不会说成“不存在”。
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
