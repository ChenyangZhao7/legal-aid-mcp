# 法律援助一条龙 MCP · 交接与优化清单

> 日期：2026-11-08
> 当前分支：`v2`（基于 `master` 的 v1.2）
> 状态：**v2 实现完成**；`200 passed`；默认 `USE_MOCK=1`；百度真实调用预算 `20`，已用 10
>
> 2026-11-08 本轮：v1.2 修复 P0-1～P0-4 并补齐参数 description；v2 增加多源地图、民事诉讼语料、12348/区划/节假日/计算器（见 CHANGELOG）。

---

## 0. 一句话

一个面向济南的 stdio MCP Server，提供 `find_legal_service`、`plan_route`、`search_law`、`verify_citation`、`legal_calculator` 5 个工具。地图走百度/腾讯/天地图多源 failover + 交叉验证；法条来自国家法律法规数据库官方 docx/PDF；法律援助、区划、节假日来自免费官方/公共数据源；默认 mock，真实调用有硬预算。

---

## 1. 当前可用状态

| 项 | 状态 |
|---|---|
| MCP 工具 | 5 个，stdio 可加载 |
| WorkBuddy | 已挂载，配置条目 `legal-aid-mcp` |
| 自动化测试 | `200 passed` |
| 语料 | 1678 条：民法典合同编 526 + 合同编司法解释 69 + 民诉法 306 + 民诉法解释 550 + 证据规定 100 + 诉讼费办法 56 + 法律援助法 71 |
| 地图 | 百度 primary；腾讯/天地图可选（无 key 自动跳过） |
| 免费数据源 | 12348 法援目录、民政部区划、timor 节假日，均有本地快照 |
| 真实百度调用 | 已用 10 次 / 上限 20 |
| 默认模式 | `USE_MOCK=1`，不耗额度 |
| 安全 | tracked files 无 AK；`.env` 已 gitignore |
| Inspector | 工具列表截图 + JSON 已保存 |
| WorkBuddy 8 条人工场景 | **待执行** |

### 快速验证

```powershell
cd legal-aid-mcp
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
.venv\Scripts\python scripts\check_secrets.py
```

最近一次输出：

```text
200 passed in 4.69s
OK: 1678 条；民法典合同编 526 条；司法解释 69 条；民事诉讼核心包已校验
OK: no secrets in tracked files
```

---

## 2. WorkBuddy 环境

- 程序：`D:\workbuddy\WorkBuddy.exe`
- MCP 配置：`%USERPROFILE%\.workbuddy\connectors\default\mcp.json`
- 配置备份：`%USERPROFILE%\.workbuddy\connectors\default\mcp.json.bak-20261108-200348`
- 条目名：`legal-aid-mcp`
- 当前环境变量：`USE_MOCK=1`、`USE_LIVE=0`
- 工具审批：第一次调用需批准 5 个工具
- 日志：
  - `%USERPROFILE%\.workbuddy\logs`
  - `D:\workbuddy\debug.log`

当前条目：

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

### 改真实调用

把 `env` 改成：

```json
"env": {
  "USE_LIVE": "1",
  "BAIDU_AK": "你的百度服务端AK"
}
```

然后完全退出 WorkBuddy（托盘也要退出）再打开。`USE_MOCK` 可以保留 1，`USE_LIVE=1` 会优先走真实调用。

### 注意

- 不要用这份单条目 JSON **整个覆盖** `mcp.json`，会丢掉 WorkBuddy 现有的 200 多个 MCP 条目；只合并 `mcpServers` 下的键。
- 改完配置必须重启 WorkBuddy 才生效。
- 不要在没有确认的情况下杀 WorkBuddy 进程，可能丢失当前会话。

---

## 3. 代码地图

```text
server.py                     MCP server 入口（stdio）
config.py                     环境变量、路径、ConfigError
errors.py                     ToolError / run_tool / 统一错误结构
context.py                    AppContext
baidu.py                      百度客户端：mock/live/缓存/预算/错误映射
laws.py                       中文数字、引用解析、语料加载、检索、范围判断
tools/
  legal_service.py            find_legal_service
  route.py                    plan_route
  law_search.py               search_law
  citation.py                 verify_citation
scripts/
  fetch_laws.py               抓官方 docx/pdf 并生成语料
  verify_laws.py              校验 1678 条、条号、抽样、SHA256
  record_fixtures.py          录制百度样本
  mcp_transcript.py           生成 stdio JSON-RPC 记录
  check_secrets.py            扫描 tracked files 里的 AK
data/laws/                    已提交的语料 JSON + manifest
data/raw/                     原始 docx/pdf（gitignored）
fixtures/baidu/               百度样本（默认 mock 使用）
tests/                        200 条测试
docs/                         设计、测试报告、学习笔记、WorkBuddy 指南
```

---

## 4. 已知漏洞 / 待优化（按优先级）

### P0 · 正确性 / 安全

1. **`BaiduClient` 非 JSON 响应未映射**（v1.2 已修复）
   - 位置：`baidu.py` 的 `response.json()`
   - 问题：上游返回 HTML/空响应时抛 `JSONDecodeError`，最终变成 `INTERNAL`。
   - 建议：捕获 `json.JSONDecodeError` / `ValueError`，映射 `UPSTREAM_ERROR`；加测试。

2. **预算文件并发写没有锁**（v1.2 已修复）
   - 位置：`baidu.py::BudgetStore`
   - 问题：两个 WorkBuddy 会话/进程同时读 `used`，可能都认为没超限。
   - 建议：文件锁或 SQLite 原子更新；或用 `msvcrt.locking`/`portalocker`；加双进程测试。
   - 当前单进程 stdio 下风险较低，但 WorkBuddy 可能开多个会话。

3. **`mismatch` 匹配窗口太窄**（v1.2 已修复）
   - 位置：`tools/citation.py::_mismatch`
   - 问题：只检查引用后 200 字符内的引号文本；引文在引用前、或引文很长会漏。
   - 建议：双向查找、窗口放宽到 500、或让工具接受“被引原文”参数；加测试。

4. **`search_law` 多引用只取第一个**（v1.2 已修复）
   - 位置：`tools/law_search.py::_search`
   - 问题：`民法典第585条和合同法第114条` 只处理第一个引用。
   - 建议：返回全部 in-corpus 引用，或明确“一次只核对一个”；需要产品决定。

5. **`amended` 状态当前不可达**
   - 位置：`tools/citation.py::citation_status`
   - 问题：语料全是 `sxx=3`，`amended` 没有真实数据。
   - 建议：加一个合成 `Article(status="已修改")` 的集成测试，或明确文档写“保留字段”。

6. **`search_law` 无前缀引用仍默认民法典**（v1.2 已补：传 `law` 时按 `law` 解释；不传仍默认民法典，且已写进工具描述）
   - 位置：`tools/law_search.py`
   - 问题：`verify_citation` 已改为 `ambiguous` + `law_hint`，但 `search_law("第585条")` 仍默认民法典。
   - 建议：给 `search_law` 也加 `law_hint`，或明确 v1 行为。

7. **POI / 路线数据质量**
   - `find_legal_service(district="历下区")` 已按名称优先过滤，但真实百度结果顺序可能变化；建议加“只返回名称命中区县”的严格模式。
   - `route_west_station.json` 是固定样本，所有 mock 路线都返回 14,205 m；建议再录 2–3 条（济南西站→历下法院、历下法院→中院）。

8. **WorkBuddy 8 条真实模型场景未跑**
   - 这是当前最大的交付缺口；`docs/workbuddy-test-guide.md` 有步骤。
   - 第 7 条“什么是违约金”必须确认模型不调用工具。

### P1 · 检索与工程

9. **`search_law` 依赖硬编码 relevance prior**
   - 位置：`laws.py::_PRIORS`
   - 当前 `违约金`→585、`合同解除`→563 是手工先验；泛查询已加 law-aware tie-break。
   - 建议：后续用 IDF/BM25 + section 权重替代，保留测试。

10. **`LawCorpus.search` 每次查询都重新归一化全部条文**
    - 位置：`laws.py::LawCorpus.search`
    - 595 条问题不大；条文增长后可预计算 `text_norm` / `section_norm`。

11. **`server.create_server` 启动时同步加载语料**
    - 语料缺失时 server 直接启动失败；可改成 lazy load + `CORPUS_NOT_LOADED` 工具错误。

12. **结构化日志缺失**
    - 目前只有 `traceback.print_exc`；建议统一 stderr 日志：工具名、耗时、错误码，不记录 AK/用户原文。

13. **CI 未实际触发**
    - `.github/workflows/ci.yml` 已加；仓库没有 remote，push 后才会跑。

14. **高德 adapter 未实现**
    - 提供的 key 返回 `INVALID_USER_KEY`；百度当前可用。
    - 后续如需降级：抽 `MapProvider` 接口，Baidu/Amap 两个 adapter。

15. **打包/发布**
    - 目前是 `requirements.txt` + 源码；可选 `pyproject.toml`、版本号、license、changelog。

### P2 · 交付与文档

16. **WorkBuddy 截图**
    - 工具列表截图已有：`docs/screenshots/inspector-tools.jpeg`
    - WorkBuddy 内一次多工具问答截图仍待人工补。

17. **测试报告**
    - `docs/test-report.md` 的 8 条场景目前是 mock/自动化 + Inspector 证据；WorkBuddy 人工结果待补。
    - 补完后把“实际工具调用/最终回答/截图文件名”填进去。

18. **法条数据定期刷新**
    - `manifest.fetched_at` 当前是 2026-11-08；后续用 `scripts/fetch_laws.py` 重抓并跑 `verify_laws.py`。

---

## 5. 下一 session 建议顺序

1. 先跑 WorkBuddy 8 条场景，填 `docs/test-report.md`（当前唯一未完成的交付项）。
2. P0 的 1–4 已在 v1.2 修复；v2 已完成地图多源、民事诉讼语料、12348/区划/节假日/计算器（200 passed）。
3. 做一次真实百度小流量验收：1 次机构 + 1 次路线，确认预算计数和缓存。
4. 再考虑 IDF/BM25、Amap adapter、打包。

---

## 6. 不要做的事

- 不要把 `.env`、`data/raw/`、`cache/` 提交进仓库。
- 不要把真实 AK 写进代码、README、测试、日志或 WorkBuddy 的 mock 配置。
- 不要用单条目 JSON 覆盖 WorkBuddy 的 `mcp.json`。
- 不要在没跑 WorkBuddy 的情况下宣称“WorkBuddy 8 条已通过”。
- 不要在没有失败测试的情况下改检索/引用逻辑。

---

## 7. 交付物 / 证据

| 文件 | 内容 |
|---|---|
| `README.md` | 安装、配置、运行、WorkBuddy、测试 |
| `CHANGELOG.md` | v1.0 / v1.1 变更 |
| `docs/superpowers/specs/2026-11-06-legal-aid-mcp-design.md` | 设计文档 |
| `IMPLEMENTATION_PLAN.md` | 原始实施计划（10 任务） |
| `docs/v1.1-improvements.md` | v1.1 改进清单 |
| `docs/test-report.md` | 8 条场景、真实调用记录 |
| `docs/learning-notes.md` | initialize → tools/list → tools/call 学习笔记 |
| `docs/workbuddy-test-guide.md` | WorkBuddy 8 条人工测试步骤 |
| `docs/mcp-transcript.json` | stdio 5 个工具调用记录 |
| `docs/inspector-tools.json` | Inspector `tools/list` JSON |
| `docs/screenshots/inspector-tools.jpeg` | Inspector 工具列表截图 |
| `.github/workflows/ci.yml` | pytest + verify_laws + secret scan |
| `scripts/check_secrets.py` | tracked files 密钥扫描 |
