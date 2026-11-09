# 测试报告 · 法律援助一条龙 MCP（v2）

- 代码版本：`git b00610b`（v2），5 个工具：`find_legal_service`、`plan_route`、`search_law`、`verify_citation`、`legal_calculator`
- 环境：Windows 11、Python 3.14.7、`mcp==2.3.0`、Node 22.22.2（仅 Inspector 用）
- 运行模式：`USE_MOCK=1`、`USE_LIVE=0`（不消耗地图额度）；fixtures 与法条语料于 2026-11-06 用真实接口录制/抓取
- 报告更新时间：2026-11-09 10:07

## 结论速览

| 层面 | 状态 | 说明 |
|---|---|---|
| 自动化测试 | ✅ `200 passed in 5.76s` | 本次重跑确认 |
| 语料校验 | ✅ `1678 条` | 民法典合同编 526 + 司法解释 69 + 民事诉讼核心包 |
| WorkBuddy 工具级实测 | ✅ 11 通过 / 1 部分通过 | 12 条清单，第 5 条为 mock 地理编码限制 |
| WorkBuddy 模型行为 | ⏳ 未验证 | 非 DeepSeek V4.1 Flash，需逐条新建对话复测 |
| 交付截图 | ⚠️ 3 合格 / 2 待补 | 缺工具调用块；2 张 Inspector 图含 API token 待打码 |

---

## 一、自动化基线（2026-11-09 10:06 重跑）

```text
.venv\Scripts\python -m pytest -q
200 passed in 5.76s
```

v2 覆盖范围：坐标转换、地图 provider failover/并集/冲突、腾讯/天地图 mock、12348 签名与快照兜底、
民政部区划、节假日/调休、诉讼费/保全费/期间计算、5 工具 stdio。

```text
.venv\Scripts\python scripts\verify_laws.py --data-dir data/laws
OK: 1678 条；民法典合同编 526 条；司法解释 69 条；民事诉讼核心包已校验
WARN: data\raw\ 下 3 个 docx/pdf 不存在（已 gitignore），跳过原始文件校验
```

```text
.venv\Scripts\python scripts\mcp_transcript.py --out docs/mcp-transcript.json
tools = find_legal_service, plan_route, search_law, verify_citation, legal_calculator
calls = 5
search_law -> 第五百八十五条
legal_calculator -> 诉讼费 2300 元（10 万元财产案件）
```

---

## 二、WorkBuddy 12 条实测（2026-11-09 00:03）

在 WorkBuddy 会话内直接调用**原生 MCP 工具**（非本地 stdio 子进程）。前置条件已满足：完全退出并重启
WorkBuddy 后工具列表为 5 个，`mcp-approvals.json` 有批准记录。

> 性质说明：工具与参数按测试清单的「期望」显式指定，验证的是**工具返回是否正确**，
> 不是模型自主工具选择能力。逐条记录表另见 `docs/workbuddy-test-2026-11-09.md` 第 3 节。

### 8 条核心

| # | 问题 | 实际工具 / 参数 | 返回摘要 | 判定 | 备注 |
|---|---|---|---|---|---|
| 1 | 济南市中级人民法院在哪？ | `find_legal_service(keyword="法院", city="济南")` | 5 家法院；济南中院 经二路 1 号，(0531)12368 | ✅ | `source="mock"`、`mock=true`、`confidence=low`；电话未编造 |
| 2 | 违约金过高，法律怎么规定？ | `search_law(query="违约金过高")` | 民法典第 585 条 + 司法解释第 64/65/66 条 + 第 580 条 | ✅ | 第 585 条正文含「违约金」「过分高于」，附官方出处 |
| 3 | 济南西站 → 中院立案，附近有法援吗？规划路线 | `find_legal_service(keyword="法律援助中心", city="济南")` → `plan_route(origin="济南西站", destination="济南市中级人民法院")` | 历下区法援 历山路 151 号 0531-88580775 等 5 家；路线 14205 m / 2462 s | ✅ | 法援返回 `{results, coverage, warnings}`；12 区县均 snapshot，12 条 `LEGAL_AID_PARTIAL` |
| 4 | 核对民法典第 585 条，并找济南律所 | `verify_citation(text="这份答辩状引用了民法典第585条")` → `find_legal_service(keyword="律师事务所", city="济南")` | 第 585 条 `exists` + 官方原文；律所 5 家 | ✅ | 山东舜达 `address=null` 并带 `ADDRESS_MISSING` 告警（脏数据已修） |
| 5 | 历下法院怎么走？ | `find_legal_service(keyword="法院", district="历下区")` → `plan_route(origin="济南西站", destination="历山路147号")` | 2 条均为历下区法院（含历下区人民法院 历山路 147 号）；路线失败 | ⚠️ 部分 | district 匹配正确、无跨区县混入；`GEOCODE_FAILED: 无法解析地址：历山路147号`，mock 仅 2 个地理编码样本 |
| 6 | 火星上有法院吗？ | `find_legal_service(keyword="法院", city="火星")` | 明确说查不到 | ✅ | `CITY_NOT_FOUND`：「当前只覆盖济南及下属区县」（「v1」字样已修） |
| 7 | 什么是违约金？ | **未调用任何工具** | 直接解释定义与调整规则 | ✅ | 零工具调用 |
| 8 | 民法典第 9999 条怎么说？ | `verify_citation(text="民法典第9999条")` | 该条不存在，不编造 | ✅ | `status: not_found`，`official_text: null` |

### 4 条 v2 扩展

| # | 问题 | 实际工具 / 参数 | 返回摘要 | 判定 |
|---|---|---|---|---|
| 9 | 民诉法第 85 条怎么规定期间？ | `search_law(query="民诉法第85条")` | 民事诉讼法第 85 条（2024-01-01 施行）：期间开始的时和日不计入，末日为法定休假日顺延 | ✅ |
| 10 | 历下区法律援助中心在哪？电话多少？ | `find_legal_service(keyword="法律援助中心", district="历下区")` | 山东省济南市历下区法律援助中心，历山路 151 号，0531-88580775 | ✅ |
| 11 | 100 万财产案件受理费？ | `legal_calculator(action="litigation_fee", amount=1000000, case_type="财产案件")` | **13,800 元**，5 段明细（50+2250+2000+4500+5000），附《诉讼费用交纳办法》第十三条 | ✅ |
| 12 | 2026-11-06 送达，上诉期到哪天？ | `legal_calculator(action="deadline", start_date="2026-11-06", days=15, deadline_type="appeal_judgment")` | **2026-11-23**（原届满 11-21 周六顺延），送达日不计入，附民诉法第 171 条 | ✅ |

**合计 11 通过 / 1 部分通过。** 第 7 条「不调用工具」、第 5 条「正确匹配历下区」两项关键判定均通过。

### 本轮修复验证（git `30f6eef`）

| 上一轮问题 | 状态 | 本次证据 |
|---|---|---|
| `mock: false` 与实际 `USE_MOCK=1` 不一致 | 已修 | 地图类返回 `source="mock"`、`mock=true`；12348 快照为 `mock=false`（语义正确） |
| `CITY_NOT_FOUND` 文案残留「v1」 | 已修 | 第 6 条返回「当前只覆盖济南及下属区县」 |
| 山东舜达 `address` 填自身名称 | 已修 | `address=null` + `ADDRESS_MISSING`「已置空，请电话确认」 |
| `plan_route` 任意地址 `GEOCODE_FAILED` | 未修（清单已豁免） | 第 5 条命中；属 mock 样本限制，真实编码需 `USE_LIVE=1` + 地图 key |
| district 静默降级（v1 遗留） | 已修 | `tools/legal_service.py:186-193`；第 5、10 条均无跨区县混入 |

---

## 三、交付截图（2026-11-09 09:58 采集，10:02 归档）

原图在 `Z:\project-mcp\screenshot\`，已复制为规范文件名到 `docs/screenshots/`（原图保留未删）。
分辨率 1820–1934 px，均满足 ≥1280。

| 文件 | 内容 | 判定 | 问题 |
|---|---|---|---|
| `inspector-tools-5.png` | Inspector `Tools (5)`，5 个工具名齐全 | ✅ 合格 | 地址栏 token 已打码 |
| `inspector-search-law.png` | `TOOLS/CALL search_law` + Results 中 `"article": "第五百八十五条"` | ⚠️ 基本合格 | 参数 `违约金过高` 未直接展示；地址栏 token 已打码 |
| `workbuddy-multi-tool.png` | 最终回答：流程图 + 法援机构表 + 14km/30-40分、1.7km/步行20分，模型 `DeepSeek-V4.1-Flash` | ❌ 待补 | **未见 `find_legal_service` / `plan_route` 调用块** |
| `workbuddy-no-tool.png`（+ `-2` 续屏） | 佣金定义与调整规则，无任何工具调用块 | ✅ 合格 | — |
| `workbuddy-calculator.png`（+ `-2` 续屏） | 结论 13,800 元 + 分段明细 + 第十三条第（一）项 | ⚠️ 待补 | **未见 `legal_calculator` 调用块与 `amount` 参数** |

数据核对：截图中的 14 km / 30-40 分与本仓库 mock 样本（14205 m / 2462 s）一致，回答内容与工具返回吻合，非编造。

---

## 四、工具描述改进记录（参数级）

把参数说明补进工具的 JSON Schema：改动前模型只能看到参数名、类型、枚举和默认值；改动后可直接看到参数含义与使用时机。

| 工具.参数 | 改动前 | 改动后 |
|---|---|---|
| `find_legal_service.keyword` | 只有枚举，无说明 | “要查找的机构类型：法院、律师事务所或法律援助中心” |
| `find_legal_service.district` | 只有类型，无说明 | “济南下属区县，如‘历下区’；不填则在全市范围搜索” |
| `plan_route.origin` | 只有类型，无说明 | “起点地址，或‘纬度,经度’坐标，如 36.67,117.0” |
| `plan_route.mode` | 只有枚举，无说明 | “出行方式：driving 驾车（默认）或 walking 步行” |
| `search_law.query` | 只有类型，无说明 | “检索关键词或法条引用……可以同时包含多个引用” |
| `verify_citation.text` | 只有类型，无说明 | “包含法条引用的文字，如答辩状、合同或 AI 回答” |

自动化测试 `test_every_tool_parameter_has_description` 检查 5 个工具的所有参数都带 description。
模型行为层面的前后对比仍需 DeepSeek V4.1 Flash 复测后补充。

---

## 五、真实调用记录

| 阶段 | 调用 | 次数 |
|---|---|---:|
| 百度权限验证 | 地点检索、地理编码、驾车路线 | 3 |
| 百度 fixtures 录制 | 法院、历下法院、律所、法律援助、两个地理编码、路线 | 7 |
| 法条抓取 | flk 搜索/下载（民法典 docx+pdf、司法解释 docx+pdf） | 4 个文件 |
| 合计百度真实调用 | — | 10 |

`LIVE_BUDGET=20` 是百度项目生命周期硬上限，上述 10 次后仍有 10 次余量。
腾讯/天地图 key 未配置，未产生真实调用；12348/民政部/timor 只走本地快照和低频查询。

---

## 六、已知限制与待办

**限制（设计如此，不算缺陷）**

- mock 路线是 `route_west_station.json` 固定样本，所有 mock 路线都返回 14205 m / 2462 s；真实调用按实际起终点计算。
- mock 地理编码只有 2 个样本（济南西站、济南中院），其他地址 `plan_route` 会 `GEOCODE_FAILED`。
- 不接高德；腾讯/天地图 key 未配置时自动跳过，百度/mock/法条/计算器仍可工作。
- `verify_citation` 只核对条号存在性与官方原文，`mismatch` 恒为 `null`，不校验用户转述文字是否与原文一致。

**待办（按优先级）**

1. **补拍 2 张**：`workbuddy-multi-tool.png`、`workbuddy-calculator.png` —— 在 WorkBuddy 里点回答顶部
   「已完成 …s ›」展开工具调用，露出 `find_legal_service` / `plan_route` / `legal_calculator` 与参数后重截。
2. ~~Inspector 两张打码~~：已用黑条遮挡地址栏 `MCP_INSPECTOR_API_TOKEN`；标签页标题仍能证明是 Inspector。
3. **模型行为复测**：用 DeepSeek V4.1 Flash，每条新建对话跑 12 条，重点看第 7 条是否误调 `search_law`、
   第 5 条是否追问或正确选 district、第 3/5 条是否按「先找机构再规划路线」的顺序调用。
4. 可选：`inspector-search-law.png` 补一张带参数面板的，使「参数 `违约金过高`」也可见。

---

## 七、证据文件索引

| 文件 | 用途 |
|---|---|
| `docs/test-report.md` | 本文件，总报告 |
| `docs/workbuddy-test-2026-11-09.md` | 12 条验收清单：前置检查、逐条 prompt、通过标准、记录表、执行结果 |
| `docs/workbuddy-screenshot-requirements.md` | 5 张截图要求、归档记录、待补事项 |
| `docs/workbuddy-prompts-run-2026-11-08.json` | 12 条 stdio 全量原始返回（每次 tools/call 的完整 JSON） |
| `docs/workbuddy-prompts-run-2026-11-08.md` | 上一轮 stdio 实测记录表与环境偏差 |
| `docs/mcp-transcript.json` | 5 个工具的 stdio 对话记录（`scripts/mcp_transcript.py` 生成） |
| `docs/inspector-tools.json` | Inspector `tools/list` 导出的 5 工具 schema |
| `docs/screenshots/` | 7 张 PNG（5 规范名 + 2 续屏）+ 1 张 v1 旧图 `inspector-tools.jpeg` |
| `docs/learning-notes.md` / `docs/v1.1-improvements.md` | 设计笔记与 v1.1 改进记录 |

---

## 附录：v1 历史记录（2026-11-06，4 工具时期）

保留用于对比，工具集为 `find_legal_service` / `plan_route` / `search_law` / `verify_citation`（无计算器）。

| # | 类型 | 问题 | 实际工具调用 | 返回摘要 | 是否符合预期 |
|---|---|---|---|---|---|
| 1 | 单工具 | 济南市中级人民法院在哪？ | `find_legal_service(keyword="法院", city="济南", limit=3)` | 济南市中级人民法院；经二路1号；(0531)12368 | 是 |
| 2 | 单工具 | 违约金过高，法律怎么规定？ | `search_law(query="违约金过高", limit=3)` | 民法典第五百八十五条，正文含“违约金”“过分高于” | 是 |
| 3 | 多工具 | 济南西站→中院，附近有法律援助吗？ | `find_legal_service(keyword="法律援助中心")` → `plan_route(...)` | 济南市法律援助中心等 3 条；14205 m / 2462 s | 是 |
| 4 | 多工具 | 核对民法典第 585 条，并找律所 | `verify_citation(...)` → `find_legal_service(keyword="律师事务所")` | 第 585 条 `exists`；山东昌平律师事务所 | 是 |
| 5 | 参数模糊 | 历下法院怎么走？ | `find_legal_service(keyword="法院", district="历下区")` → `plan_route(...)` | 5 条中含“济南市历下区人民法院”；14205 m / 2462 s | 是 |
| 6 | 异常 | 火星上有法院吗？ | `find_legal_service(keyword="法院", city="火星")` | `CITY_NOT_FOUND` | 是 |
| 7 | 无需工具 | 什么是违约金？ | 不调用工具，直接回答 | 解释定义与调整规则 | 待复测（当时无 WorkBuddy） |
| 8 | 伪造引用 | 民法典第 9999 条怎么说？ | `verify_citation(text="民法典第9999条怎么说？")` | `status: not_found` | 是 |

v1 补充：`verify_citation("第585条")` 返回 `ambiguous`；传 `law_hint="民法典"` 返回 `exists`，
避免在刑法/合同混合文书里把无前缀引用误判成民法典。
