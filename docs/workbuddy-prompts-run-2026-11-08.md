# WorkBuddy v2 Prompt 实测记录（2026-11-08 23:46）

依据 `docs/workbuddy-prompts.md`（v2，12 条）逐条运行。完整原始返回见
`docs/workbuddy-prompts-run-2026-11-08.json`。

## 运行环境与偏差

- 项目版本：`git 899e86d`（v2，23:27 提交），5 个工具：`find_legal_service`、`plan_route`、
  `search_law`、`verify_citation`、`legal_calculator`。
- 启动方式：**本地 stdio 子进程**连 `legal-aid-mcp\server.py`，env `USE_MOCK=1 / USE_LIVE=0`。
  原因是当前 WorkBuddy 会话挂载的仍是 v1 的 4 个工具（`legal_calculator` 查不到），
  需按文档前置第 1 条「完全退出 WorkBuddy（托盘也退出）再打开」后，才能在会话内直接测。
- 与文档前置的偏差：
  - 模型不是 DeepSeek V4.1 Flash；本次按每条「期望」显式指定工具与参数，
    因此**测的是工具返回是否符合预期，不是模型自主工具选择能力**。
  - 12 条在同一 MCP 会话内顺序执行，未逐条新建对话。
  - 第 7 条按文档要求不调用任何工具。
- 结论：**11 条完全符合预期，第 5 条部分符合**。

## 记录表

| # | 问题 | 实际工具 / 参数 | 最终回答摘要 | 符合预期 | 备注 |
|---|---|---|---|---|---|
| 1 | 济南市中级人民法院在哪？ | `find_legal_service(keyword="法院", city="济南")` | 济南市中级人民法院，经二路 1 号，0531-12368；附 WGS84 坐标及来源/置信度标记 | ✅ | 共 5 家，电话未编造；v2 新增 `source=map`、`confidence=low`、`sources[]`、bd09→wgs84 转换 |
| 2 | 违约金过高，法律怎么规定？ | `search_law(query="违约金过高")` | 民法典第 585 条（过分高于损失可请求适当减少）+ 合同编通则司法解释第 64 条（举证责任） | ✅ | 正文含「违约金」「过分高于」 |
| 3 | 济南西站→中院立案，附近有法援吗？规划路线 | `find_legal_service(keyword="法律援助中心", city="济南")` + `plan_route(济南西站→济南市中级人民法院)` | 历下区法援（历山路 151 号，0531-88580775）等 5 家；路线 14.2 km / 约 41 分钟 | ✅ | 返回 `{results, coverage, warnings}`；12 区县全部 snapshot，12 条 `LEGAL_AID_PARTIAL` 提示实时查询不可用 |
| 4 | 核对民法典第 585 条，并找济南律所 | `verify_citation(text="这份答辩状引用了民法典第585条")` + `find_legal_service(keyword="律师事务所", city="济南")` | 第 585 条 `exists`，附官方原文；律所 5 家 | ✅ | 未把「存在」说成「不存在」；山东舜达 `address` 仍是其自身名称 |
| 5 | 历下法院怎么走？ | `find_legal_service(keyword="法院", district="历下区")` + `plan_route(origin="济南西站", destination="历山路147号")` | 历下区人民法院（历山路 147 号，0531-12368）；**路线规划失败** | ⚠️ 部分 | `GEOCODE_FAILED: 无法解析地址：历山路147号`；详见问题 1 |
| 6 | 火星上有法院吗？ | `find_legal_service(keyword="法院", city="火星")` | 不支持火星，查不到 | ✅ | `CITY_NOT_FOUND`，未编造机构；文案仍写「v1 只覆盖济南」 |
| 7 | 什么是违约金？ | **未调用任何工具** | 直接解释违约金定义与常见调整规则 | ✅ | 符合「不调工具」要求 |
| 8 | 民法典第 9999 条怎么说？ | `verify_citation(text="民法典第9999条")` | 该条不存在，不编造内容 | ✅ | `not_found` |
| 9 | 民诉法第 85 条怎么规定期间计算？ | `search_law(query="民诉法第85条")` | 民事诉讼法第 85 条（2024-01-01 施行）：期间以时/日/月/年计算，开始的时和日不计入，末日为法定休假日则顺延 | ✅ | v2 新增民诉法语料生效，正文含「期间」「法定休假日」 |
| 10 | 历下区法律援助中心在哪？电话多少？ | `find_legal_service(keyword="法律援助中心", district="历下区")` | 山东省济南市历下区法律援助中心，历山路 151 号，0531-88580775 | ✅ | 返回 `{results, coverage, warnings}`；`source=snapshot`、`sources[0].provider=12348`、`confidence=official` |
| 11 | 诉讼请求 100 万元，财产案件受理费？ | `legal_calculator(action="litigation_fee", amount=1000000, case_type="财产案件")` | **13,800 元**，按《诉讼费用交纳办法》第 13 条分段累计 | ✅ | 附 5 段明细与条文依据，与期望 `fee=13800` 一致 |
| 12 | 2026-11-06 送达，上诉期到哪天？ | `legal_calculator(action="deadline", start_date="2026-11-06", days=15, deadline_type="appeal_judgment")` | **2026-11-23**（原届满 11-21 为周六顺延至周一），送达当天不计入 | ✅ | `holiday_source=timor.tech`，附民诉法第 171 条；notes 明确两条规则 |

## 发现的问题

1. **第 5 条路线规划对任意地址失败** — `plan_route(destination="历山路147号")` 返回
   `GEOCODE_FAILED: 无法解析地址：历山路147号`。改用经纬度
   `36.65824279814486,117.03171147408166` 后「成功」，但返回与第 3 条**完全相同**的固定样本
   （14205 m / 2462 s / 20 段），说明 mock 模式按 origin 命中 fixture、忽略 destination，
   这个「成功」是假阳性，不能当作真实路线。真实地理编码需 `USE_LIVE=1` + 地图 key。
2. **错误文案残留 v1** — 第 6 条仍返回「暂不支持城市"火星"，**v1** 只覆盖济南及下属区县」，
   v2 应改成不带版本号的措辞。
3. **脏数据未修** — 第 4 条「山东舜达律师事务所」的 `address` 字段值仍是律所自身名称
   （v1 遗留问题，v2 未处理）。
4. **字段语义待核对** — 各条返回体中 `mock: false`，但实际以 `USE_MOCK=1` 运行，
   建议确认该字段是否指「该条记录来自 mock 传输层」而非运行模式。

## 已修复确认

上一轮报告的 district 静默降级 bug **在 v2 已修**：`tools/legal_service.py:186-193` 现在是
「名称含区县 → 否则按地址过滤」，无匹配则由 `if not merged` 走 `NO_RESULTS`，
不再「都不匹配就原样返回全部」。第 5、10 条结果均只含历下区，验证通过。
法援查询另走 12348 官方目录（`client.search(district=...)`），不再依赖地图字符串匹配。

## 修复结果（2026-11-08 补）

- **v1 文案**：已改为“当前只覆盖济南及下属区县”，工具描述同步更新。
- **脏地址**：输出时若 `address` 与 `name` 相同，置为 `null` 并加 `ADDRESS_MISSING` warning；不再把律所名当地址返回。
- **`mock` 语义**：mock 模式下 `find_legal_service` 和 `plan_route` 现在返回 `mock: true`、`source: "mock"`；fixtures 兜底仍标 `source: "fixtures"`。
- **第 5 条 mock 路线**：仍只支持 `geocode_court`/`geocode_west_station` 两个 fixture，且路线固定；这是 mock 数据限制，不是路线算法错误。真实路线需 `USE_LIVE=1` + 地图 key。
- 回归测试：`200 passed`。

## 下一步

1. 按文档前置第 1 条完全退出 WorkBuddy（含托盘）再打开，确认 5 个工具挂载
   （当前会话仍是 v1 的 4 个）。
2. 用 DeepSeek V4.1 Flash，每条 prompt 单独新建对话，复测**模型自主工具选择**，
   重点看第 7 条会不会误调 `search_law`、第 5 条会不会追问或选对 district。
3. 3 个代码问题已修；第 5 条 mock 路线限制保留说明。重启 WorkBuddy 后按新 prompt 重跑，把结果并入 `docs/test-report.md`。
