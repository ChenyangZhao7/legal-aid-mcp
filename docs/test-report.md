# 测试报告 · 法律援助一条龙 MCP

- 日期：2026-11-09（v2）
- 环境：Windows、Python 3.14.7、`mcp==2.3.0`
- 模式：自动化测试全部 `USE_MOCK=1`；百度 fixtures 和法条语料在 2026-11-06 用真实接口录制/抓取
- 证据：`docs/mcp-transcript.json`、`docs/inspector-tools.json`、`docs/screenshots/inspector-tools.jpeg`、`docs/workbuddy-test-2026-11-09.md`、`docs/workbuddy-prompts-run-2026-11-08.json`、`pytest` 输出、`scripts/verify_laws.py` 输出
- WorkBuddy：2026-11-09 已在 WorkBuddy 会话内做**工具级**复测 12 条（不是模型自主选择），结果见文末「2026-11-09 WorkBuddy 会话实测」；模型行为和截图仍待补

## 8 条场景

| # | 类型 | 问题 | 实际工具调用 | 返回摘要 | 是否符合预期 | 备注 |
|---|---|---|---|---|---|---|
| 1 | 单工具 | 济南市中级人民法院在哪？ | `find_legal_service(keyword="法院", city="济南", limit=3)` | 济南市中级人民法院；经二路1号；(0531)12368 | 是 | mock fixture 录制自真实百度响应 |
| 2 | 单工具 | 违约金过高，法律怎么规定？ | `search_law(query="违约金过高", limit=3)` | 民法典第五百八十五条，正文含“违约金”“过分高于” | 是 | 本地语料，未调用外部服务 |
| 3 | 多工具 | 我在济南西站，要去济南中院立案，附近有法律援助吗？ | `find_legal_service(keyword="法律援助中心", limit=3)` → `plan_route(origin="济南西站", destination="济南市中级人民法院")` | 济南市法律援助中心等 3 条；路线 14205 m / 2462 s | 是 | mock 路线是固定样本，真实坐标会不同 |
| 4 | 多工具 | 这份答辩状引用了民法典第 585 条，帮我核对，并找济南的律所 | `verify_citation(text="依据民法典第585条")` → `find_legal_service(keyword="律师事务所", limit=3)` | 第 585 条 `exists`；山东昌平律师事务所 | 是 | 引用存在且原文匹配 |
| 5 | 参数模糊 | 历下法院怎么走？ | `find_legal_service(keyword="法院", district="历下区", limit=5)` → `plan_route(origin="<历下区法院坐标>", destination="济南市中级人民法院")` | 5 条中含“济南市历下区人民法院”；路线 14205 m / 2462 s | 是 | 第一条是高新区法院，模型需按名称筛选；mock 路线固定 |
| 6 | 异常 | 济南市不存在法院在哪？ | `find_legal_service(keyword="法院", city="火星")` | `CITY_NOT_FOUND`：暂不支持城市“火星” | 是 | 用“火星”代表白名单外城市；没有编造结果 |
| 7 | 无需工具 | 什么是违约金？ | 不调用工具，直接回答 | 解释违约金的定义和常见调整规则 | 工具层面通过 | 2026-11-09 已确认零工具调用；模型自主行为仍需 DeepSeek V4.1 Flash 复测 |
| 8 | 伪造引用 | 民法典第 9999 条怎么说？ | `verify_citation(text="民法典第9999条怎么说？")` | `status: not_found`，`official_text: null` | 是 | 民法典全文 1260 条，9999 条不存在 |

补充：`verify_citation("第585条")` 现在返回 `ambiguous`；传 `law_hint="民法典"` 返回 `exists`。这样不会在刑法/合同混合文书里把无前缀引用误判成民法典。

## 工具描述改进记录（参数级）

任务书要求记录“修改工具描述前后的对比”。本轮把参数说明补进工具的 JSON Schema：改动前模型只能看到参数名、类型、枚举和默认值；改动后可以直接看到参数含义与使用时机。`docs/inspector-tools.json` 已按新 Schema 重新导出。

| 工具.参数 | 改动前 | 改动后 |
|---|---|---|
| `find_legal_service.keyword` | 只有枚举，无说明 | “要查找的机构类型：法院、律师事务所或法律援助中心” |
| `find_legal_service.district` | 只有类型，无说明 | “济南下属区县，如‘历下区’；不填则在全市范围搜索” |
| `plan_route.origin` | 只有类型，无说明 | “起点地址，或‘纬度,经度’坐标，如 36.67,117.0” |
| `plan_route.mode` | 只有枚举，无说明 | “出行方式：driving 驾车（默认）或 walking 步行” |
| `search_law.query` | 只有类型，无说明 | “检索关键词或法条引用……可以同时包含多个引用” |
| `verify_citation.text` | 只有类型，无说明 | “包含法条引用的文字，如答辩状、合同或 AI 回答” |

自动化测试 `test_every_tool_parameter_has_description` 会检查 5 个工具的所有参数都带 description。模型行为层面的前后对比仍需在 WorkBuddy 里用 DeepSeek V4.1 Flash 复测后补充。

## 自动化结果

```text
.venv\Scripts\python -m pytest -q
200 passed in 4.69s
```

v2 新增测试覆盖：坐标转换、地图 provider failover/并集/冲突、腾讯/天地图 mock、12348 签名与快照兜底、民政部区划、节假日/调休、诉讼费/保全费/期间、5 工具 stdio。

```text
.venv\Scripts\python scripts\verify_laws.py --data-dir data/laws
OK: 1678 条；民法典合同编 526 条；司法解释 69 条；民事诉讼核心包已校验
```

```text
.venv\Scripts\python scripts\mcp_transcript.py --out docs/mcp-transcript.json
tools = find_legal_service, plan_route, search_law, verify_citation, legal_calculator
calls = 5
search_law -> 第五百八十五条
legal_calculator -> 诉讼费 2300 元（10 万元财产案件）
```

MCP Inspector：工具列表截图见 `docs/screenshots/inspector-tools.jpeg`；工具列表 JSON 见 `docs/inspector-tools.json`。在 Inspector 里执行 `search_law(query="违约金过高")` 也返回了民法典第五百八十五条。

## 真实调用记录

| 阶段 | 调用 | 次数 |
|---|---|---:|
| 百度权限验证 | 地点检索、地理编码、驾车路线 | 3 |
| 百度 fixtures 录制 | 法院、历下法院、律所、法律援助、两个地理编码、路线 | 7 |
| 法条抓取 | flk 搜索/下载（民法典 docx+pdf、司法解释 docx+pdf） | 4 个文件 |
| 合计百度真实调用 | — | 10 |

`LIVE_BUDGET=20` 是百度项目生命周期硬上限；上述 10 次之后仍有 10 次余量。腾讯/天地图 key 未配置，未产生真实调用；12348/民政部/timor 只走本地快照和低频查询。

## 已知差异与待办

- mock 路线是 `route_west_station.json` 固定样本，所有 mock 路线都会返回 14205 m / 2462 s；真实调用会按实际起终点计算。
- `place_court_lixia.json` 的前三条是高新区法院、历城区法院、历下区法院；模型需要按名称筛选“历下区人民法院”。
- 2026-11-09 已在 WorkBuddy 里做工具级 12 条复测（11 通过 / 1 部分通过）；模型自主选择（DeepSeek V4.1 Flash）和 UI 截图仍待补。
- 不接高德；腾讯/天地图 key 未配置时自动跳过，百度/mock/法条/计算器仍可工作。

## 2026-11-09 WorkBuddy 会话实测

依据 `docs/workbuddy-test-2026-11-09.md`（12 条验收清单）执行。前置条件已满足：完全退出并重启
WorkBuddy 后工具列表为 5 个（含 `legal_calculator`），`mcp-approvals.json` 已有批准记录。
本次在 WorkBuddy 会话内直接调用原生 MCP 工具，未修改代码；属于**工具级验证**，不是模型自主工具选择测试。

| 项目 | 结果 |
|---|---|
| 8 条核心 | 7 通过、1 部分通过（第 5 条路线 `GEOCODE_FAILED`，district 匹配正确，清单已注记为 mock 限制） |
| 4 条 v2 扩展 | 4 通过（民诉法第 85 条、12348 历下区法援、诉讼费 13,800 元、上诉期 2026-11-23） |
| 合计 | **11 通过 / 1 部分通过** |
| 结束条件 | 工具层面达标；第 7 条零工具调用、第 5 条正确匹配历下区均已确认 |

逐条工具、参数与返回摘要见 `docs/workbuddy-test-2026-11-09.md` 第 3 节记录表；
上一轮 stdio 全量原始返回见 `docs/workbuddy-prompts-run-2026-11-08.json`。

**执行偏差**：模型非 DeepSeek V4.1 Flash（工具与参数按期望显式指定，未验证模型自主选工具）；
12 条在同一会话顺序执行，未逐条新建对话；未采集清单第 4 节的 5 项 UI 截图。
模型行为层面与截图仍需补齐。

**上一轮 4 个问题的修复验证**（git `30f6eef`）：

| 问题 | 状态 | 本次证据 |
|---|---|---|
| `mock` 标记与 `USE_MOCK=1` 不一致 | 已修 | 法院/律所/路线返回 `source="mock"`、`mock=true`；12348 快照为 `mock=false` |
| 错误文案残留「v1」 | 已修 | 第 6 条返回「当前只覆盖济南及下属区县」 |
| 山东舜达 `address` 填自身名称 | 已修 | `address=null` + `ADDRESS_MISSING` 告警「已置空，请电话确认」 |
| `plan_route` 任意地址解析失败 | 未修（清单已豁免） | 第 5 条 `GEOCODE_FAILED`，属 mock 数据限制；真实编码需 `USE_LIVE=1` + 地图 key |

另：上一轮报告的 district 静默降级 bug 在 v2 已修，本次第 5、10 条均未出现跨区县混入。

## 结论

- **工具层**：自动化 `200 passed`；WorkBuddy 工具级 12 条中 11 通过、1 部分通过（第 5 条 mock 路线限制）。
- **任务书验收**：还差 DeepSeek V4.1 Flash 的模型自主工具选择复测，以及 Inspector/WorkBuddy 截图。
- 补齐这两项后，任务书的 8 条测试与交付物才算完整。
