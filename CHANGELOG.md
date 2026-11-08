# Changelog

## v2.0 — 2026-11-08

### 地图

- 新增 `maps/` provider 层：百度、腾讯、天地图；腾讯/天地图无 key 时自动跳过。
- `MapService` 支持顺序 failover、去重并集、交叉验证、`confidence`/`discrepancies`/`sources`。
- 内部坐标统一 WGS-84；新增 `coord.py` 的 BD-09/GCJ-02/WGS-84 转换。
- `plan_route` 新增 `coord_system`（默认 `wgs84`，可选 `gcj02`/`bd09`）。
- 每个 provider 独立缓存和预算；百度保留 `cache/budget.json`。

### 法律

- 新增民事诉讼核心包：民事诉讼法 306 + 民诉法解释 550 + 证据规定 100 + 诉讼费办法 56 + 法律援助法 71。
- 总计 1678 条；`fetch_laws.py` 和 `verify_laws.py` 已扩展。
- `search_law` / `verify_citation` 的 `law` / `law_hint` 支持 7 部法律。
- 新增起诉条件、答辩期、上诉期、期间、诉讼费、法律援助等检索先验。

### 免费数据源与计算

- 新增 12348 法律援助目录客户端：按区县查询、24h 缓存、快照/地图三级兜底。
- 新增民政部区划索引：校验济南 12 区县，提供 12 位/6 位区划码。
- 新增节假日日历：timor.tech + 本地快照 + 周末兜底。
- 新增 `legal_calculator` 工具：诉讼费、保全费、上诉期/答辩期/自定义期间。

### 工程

- `USE_LIVE=0` 是全局离线开关，测试不联网。
- 测试从 116 条增加到 184 条。
- 新增区划、节假日、12348 快照脚本和 `.env.example` 配置。

## v1.2 — 2026-11-08

### 正确性

- 百度返回非 JSON 或非对象响应时映射为 `UPSTREAM_ERROR`，不再落到 `INTERNAL`。
- `BudgetStore` 的读取-自增-写回增加线程锁和文件锁，多个会话并发时不会突破 `LIVE_BUDGET`。
- `verify_citation` 的引文比对改为双向查找，窗口从 200 字符放宽到 500 字符；引文在法条引用之前也能识别。
- `search_law` 支持一次查询多个法条引用，返回全部在收录范围内的条文；混合范围外引用时仍返回已命中的条文。
- `search_law` 的无前缀引用（如“第 1 条”）会使用 `law` 参数作为法律提示，不再误判为法律冲突。

### 工具 Schema

- 4 个工具的所有参数补充 description，模型可从 `tools/list` 直接看到参数含义、取值范围和使用时机。
- 增加测试：非 JSON 响应、JSON 非对象、预算并发、多引用、引文前置/长窗口、`amended` 状态、参数说明齐全。
- 测试从 106 条增加到 116 条。

## v1.1 — 2026-11-08

### 工具行为

- `plan_route` 的步骤现在返回 `road_name`，并用它生成 `instruction`（如“沿无名路”）；百度没有 `instruction` 时不再返回空字符串。
- `verify_citation` 增加 `law_hint`；没有写法律名的引用（如“第585条”）返回 `ambiguous`，不再默认民法典。
- `BUDGET_EXHAUSTED` 文案改为“本次请求未发送”，不再声称已自动切换缓存。
- `cache/budget.json` 损坏时 fail-closed，停止真实调用。

### 配置与检索

- 配置数字解析失败统一为中文 `ConfigError`；`USE_MOCK=0` 且 `USE_LIVE=0` 启动失败。
- `LawCorpus.load` 捕获 `OSError`，统一返回 `CORPUS_NOT_LOADED`。
- 中文 2-gram 文本得分上限 20。
- `verify_laws.py` 增加 `--require-raw`。
- v1 明确只支持济南及下属区县。

### 测试与工程

- 测试从 68 条增加到 106 条：cache TTL、budget 持久化、210/211/302、mismatch=False、重复引用、坐标路线、limit 裁剪、司法解释过滤、配置错误、secret scan、Inspector artifact。
- 增加 `scripts/check_secrets.py` 和 GitHub Actions CI。
- 增加 `docs/workbuddy-test-guide.md`、`docs/inspector-tools.json`。
- 重新抓取官方语料，更新 `manifest.fetched_at`。

## v1.0 — 2026-11-06

- 4 个工具：`find_legal_service`、`plan_route`、`search_law`、`verify_citation`。
- 民法典合同编 526 条 + 合同编通则司法解释 69 条，官方 docx/PDF 存证。
- mock/live/缓存/预算，stdio MCP server，8 条场景报告。
