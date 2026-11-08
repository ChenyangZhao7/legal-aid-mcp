# 法律援助一条龙 MCP · v2 设计文档

> 日期：2026-11-08
> 状态：待用户批准
> 依据：`执行书.md`、`HANDOFF.md`、2026-11-08 的需求讨论
> 范围：地图多源交叉验证、民事诉讼语料扩展、12348/民政部/节假日接入、本地计算器

---

## 1. 一句话

在现有 4 个工具的基础上，把地图从“只依赖百度”改成“百度 + 腾讯 + 天地图多源 failover / 交叉验证”，把法条覆盖从合同编扩到民事诉讼核心包，并接入 12348 法律援助目录、民政部行政区划、免费节假日 API 和本地诉讼费/期间计算，形成 v2。

## 2. 意图与成功标准

### 给谁用

- 普通当事人：找法院/法律援助/律所、查路线、算诉讼费、算上诉期。
- 律师/法务：查民事诉讼条文、核对引用、快速核对期间和费用。

### 成功的样子

1. 地图至少有 1 个源可用就能返回结果；2 个以上源可用时能给出交叉验证结论。
2. 百度/腾讯任一 key 失效、配额用尽、接口超时，MCP 不崩溃，按顺序降级。
3. `search_law` / `verify_citation` 覆盖民事诉讼法、民诉法解释、证据规定、诉讼费用交纳办法、法律援助法。
4. 12348 可用时优先返回官方法律援助中心；不可用时退回本地快照或地图 POI。
5. 诉讼费、保全费、上诉期/期间计算有官方条文依据，且明确标注计算假设。
6. 所有自动化测试离线运行，不依赖任何 key，不发真实网络请求。

## 3. 目标 / 非目标 / 反目标

### 目标

1. 地图多 provider：Baidu、Tencent、Tianditu，统一 `Place` / `Route` 结构。
2. 交叉验证：POI 名称/地址/电话/坐标一致性；路线距离/时间一致性；输出 `confidence` 和 `discrepancies`。
3. 民事诉讼语料：5 部新法，共 1083 条。
4. 12348 法律援助目录：按济南区县查询、缓存、快照兜底。
5. 民政部行政区划：校验济南区县，提供 12 位区划码和 12348 需要的 6 位码。
6. 节假日：timor.tech + 本地快照 + 周末兜底。
7. `legal_calculator`：诉讼费、保全费、期间/上诉期。
8. 保持现有 4 个工具的名称和主要参数不变。

### 非目标

- 不接高德（用户明确不用）。
- 不把付费 API 作为硬依赖。
- 不判断管辖法院、不预测胜诉、不评价律师水平。
- 不抓裁判文书网、企业信用系统等无公开 API/反爬严格的站点。
- 不做 LLM 事实裁判；LLM 不是地图或法条的事实源。
- 不在运行时高频抓取 12348；只做低频、缓存、可关闭的目录查询。

### 反目标（技术跑通也算失败）

- 为了“有结果”而编造地址、电话、坐标、法条或费用。
- 地图源冲突时静默选一个，不告诉模型。
- 把 12348 反爬失败伪装成“没有法律援助中心”。
- 诉讼费/期间计算没有条文依据或没有标注假设。
- 把 key、用户输入、案宗写进日志/仓库。
- 在 mock/离线模式下偷偷访问 12348、timor.tech 或任何外部接口。

## 4. 约束与已验证事实

| 事实 | 证据 |
|---|---|
| 高德 key 不可用，且用户明确不用 | 历史记录 `INVALID_USER_KEY`；本轮决策 |
| 百度地图已有 key，免费额度有限 | 现有 `BaiduClient`，`LIVE_BUDGET=20` |
| 腾讯位置服务个人开发者有免费日额度 | 官方配额页：地点搜索 200/日，地理编码/路线 6000/日 |
| 天地图有免费 Web 服务 API，需要 tk | 官方文档；无 key 时 provider 自动禁用 |
| 民政部国家地名信息库可查区划 | `dmfw.mca.gov.cn/9095/xzqh/getList?code=370100000000&maxLevel=3` 实测返回济南 12 区县 |
| 12348 有可用的机构查询接口 | `POST /legalList/getlegalList`，需 `v_key/guid/number/crawlerCookie`；历下、市中实测成功 |
| timor.tech 节假日 API 免费 | 官方页面；2026 年数据已更新 |
| flk 官方语料可抓 | 现有 `fetch_laws.py`；民事诉讼法 306 条、民诉法解释 550 条、证据规定 100 条、诉讼费办法 56 条、法律援助法 71 条均已实测解析 |
| 运行环境 | Windows、Python 3.14.7、`mcp==2.3.0`、stdio |

## 5. 方案选择

### 方案 1（已选）：4 个核心工具 + `legal_calculator`，地图多源 failover + 交叉验证

- 工具数从 4 增加到 5；用户确认任务书的“2–4 个”只是建议，不是硬限制。
- 地图 provider 顺序可配置，默认 `baidu,tencent,tianditu`。
- 每次查询先走 primary；primary 失败再走下一个；有 2 个以上成功源时做交叉验证。
- 12348、民政部、节假日都在现有工具内部或 `legal_calculator` 中使用，不新增更多工具。
- 优点：工具数量可控、模型容易选、每个 provider 可独立降级、测试可离线。
- 缺点：需要坐标转换和匹配逻辑；12348 接口非官方，需要兜底。

### 方案 2（不选）：扩成 7–8 个工具

`find_legal_service`、`plan_route`、`search_law`、`verify_citation`、`legal_calculator`、`search_legal_aid`、`lookup_division`、`get_holidays`。功能最直观，但工具太多会让模型选择困难，且 12348 已经能并入 `find_legal_service`。

### 方案 3（不选）：仍只保留 4 个工具，把新能力全塞进参数

会让 `find_legal_service` 的参数爆炸，模型难以正确填写。不采用。

## 6. 架构

```text
server.py
  └─ AppContext
       ├─ MapService
       │    ├─ BaiduProvider      (BD-09 → WGS-84)
       │    ├─ TencentProvider    (GCJ-02 → WGS-84, 可选 key)
       │    ├─ TiandituProvider   (CGCS2000 ≈ WGS-84, 可选 key)
       │    ├─ CrossChecker
       │    ├─ CacheStore / BudgetStore (按 provider)
       │    └─ fixtures (mock)
       ├─ LegalAidClient          (12348 + 本地快照)
       ├─ DivisionIndex           (民政部区划 + 本地快照)
       ├─ HolidayCalendar         (timor.tech + 本地快照)
       ├─ LawCorpus               (flk 官方语料)
       └─ Calculators             (诉讼费/保全费/期间)
```

### 模块职责

| 模块 | 职责 |
|---|---|
| `coord.py` | BD-09 / GCJ-02 / WGS-84 互转 |
| `map/base.py` | `Place`、`Route`、`MapProvider` 协议、`MapError` |
| `map/baidu_provider.py` | 包装现有 `BaiduClient`，输出统一结构 |
| `map/tencent_provider.py` | 腾讯地点搜索/地理编码/路线 |
| `map/tianditu_provider.py` | 天地图地名搜索/地理编码/驾车 |
| `map/service.py` | provider 顺序、failover、交叉验证、缓存、预算 |
| `map/crosscheck.py` | 名称/地址/电话/坐标/路线一致性判断 |
| `legal_aid.py` | 12348 目录查询、缓存、快照兜底 |
| `divisions.py` | 民政部区划加载、区县校验、adcode 映射 |
| `holidays.py` | 节假日加载、缓存、工作日/节假日判断 |
| `calculators.py` | 诉讼费、保全费、期间/上诉期 |
| `tools/*.py` | 工具参数、调用、返回结构 |
| `scripts/fetch_divisions.py` | 刷新民政部济南区划快照 |
| `scripts/fetch_legal_aid.py` | 刷新 12348 济南法律援助快照 |
| `scripts/fetch_holidays.py` | 刷新节假日快照 |

## 7. 地图多源设计

### 7.1 统一数据结构

```python
@dataclass
class GeoPoint:
    lat: float
    lng: float
    system: str  # "wgs84" / "gcj02" / "bd09"

@dataclass
class Place:
    provider: str
    name: str
    address: str | None
    telephone: str | None
    point: GeoPoint       # 已转 WGS-84
    native: GeoPoint      # provider 原始坐标
    raw: dict             # 仅内部使用

@dataclass
class Route:
    provider: str
    distance_m: int
    duration_s: int
    steps: list[dict]
```

工具对外统一输出 WGS-84 的 `lat`/`lng`，并附 `coord_system: "wgs84"`。每个 `sources[]` 保留 provider 原始坐标和坐标系，避免信息丢失。

### 7.2 provider 顺序与降级

配置：

```text
MAP_PROVIDERS=baidu,tencent,tianditu
MAP_CROSS_CHECK=1
MAP_LIVE_FAILURE_MODE=cache   # cache | error | fixtures
```

规则：

1. 只启用有 key 的 provider；`USE_LIVE=0` 时只用百度 fixtures。
2. 按 `MAP_PROVIDERS` 顺序尝试；第一个成功的是 primary。
3. 若 `MAP_CROSS_CHECK=1`，继续查询其余可用 provider 作为 secondary；secondary 失败只记录 warning，不影响主结果。
4. 结果集是**去重后的并集**，不是只取 primary：primary 的条目排在前面，secondary 独有的 POI 追加在后面；每条结果带 `sources`，`limit` 作用于合并后的列表。这样不会因为百度漏掉某个机构就完全看不到腾讯/天地图的结果。
5. 所有 provider 都失败：
   - `cache`：返回最近缓存（标记 `cached: true`）；
   - `fixtures`：返回 mock 数据（仅演示用，标记 `mock: true`）；
   - `error`：返回 `ALL_SOURCES_FAILED`，附每个 provider 的错误码。
6. 地图工具失败不影响法条/计算器工具。

### 7.3 交叉验证规则

POI：

- 名称归一化后相似度 ≥ 0.6；或一方名称包含另一方核心词。
- 地址相似度 ≥ 0.5；或坐标距离 ≤ 500 米。
- 电话都有时，统一去掉区号/空格/横线后比较。
- 至少满足“名称 + (地址或坐标)”才算 match。
- `confidence`：
  - `high`：2+ 源名称、地址/坐标、电话（如有）都一致；
  - `medium`：2+ 源名称和地址/坐标一致，但电话不同或缺失；
  - `low`：只有 1 源，或 2 源名称不一致；
  - `conflict`：2+ 源坐标距离 > 1 km 或名称明显不同。
- `discrepancies` 列出具体差异（地址不同、坐标相差 820m、电话不同等）。
- 不静默选一个：合并结果按 provider 顺序排序，但每条结果的 `confidence`/`discrepancies` 必须返回；冲突条目不隐藏。

路线：

- 距离差 ≤ 15% 且时间差 ≤ 30% → `high`；
- 距离差 ≤ 30% → `medium`；
- 更大差异 → `low`/`conflict`。
- `sources` 返回各 provider 的距离/时间；steps 取 primary。

### 7.4 坐标系转换

`coord.py` 提供：

- `bd09_to_gcj02` / `gcj02_to_bd09`
- `gcj02_to_wgs84` / `wgs84_to_gcj02`
- `bd09_to_wgs84` / `wgs84_to_bd09`

内部统一 WGS-84。测试使用已知北京点（116.404, 39.915）验证往返误差 < 1e-5 度。

`plan_route` 的坐标输入默认按 WGS-84 解释，并新增可选参数 `coord_system`（`wgs84` / `gcj02` / `bd09`，默认 `wgs84`）。这样 `find_legal_service` 返回的坐标可以直接传给 `plan_route`。需要兼容 v1 的百度坐标时，显式传 `coord_system="bd09"`。

### 7.5 缓存与预算

- Baidu：沿用 `cache/budget.json`，保持已用 10 次的记录。
- Tencent：`cache/budget_tencent.json`，默认上限 `TENCENT_BUDGET=20`。
- Tianditu：`cache/budget_tianditu.json`，默认上限 `TIANDITU_BUDGET=20`。
- 缓存键加 provider 前缀，避免不同 provider 的结果串用。
- 相同请求命中缓存不消耗预算。
- 预算锁沿用 v1.2 的线程锁 + 文件锁。

## 8. 民事诉讼语料扩展

### 8.1 新增语料

| 法律 | 条数 | 类型 | 文件 |
|---|---:|---|---|
| 中华人民共和国民事诉讼法 | 306 | 法律 | `civil_procedure_law.json` |
| 最高人民法院关于适用《中华人民共和国民事诉讼法》的解释 | 550 | 司法解释 | `civil_procedure_interpretation.json` |
| 最高人民法院关于民事诉讼证据的若干规定 | 100 | 司法解释 | `civil_evidence_rules.json` |
| 诉讼费用交纳办法 | 56 | 行政法规 | `litigation_fee_rules.json` |
| 中华人民共和国法律援助法 | 71 | 法律 | `legal_aid_law.json` |

总计新增 1083 条；加现有 595 条，共 1678 条。

### 8.2 抓取与校验

- `scripts/fetch_laws.py` 的 `TARGETS` 增加 5 项；`min_article`/`max_article`/`full_range`/`in_scope` 按上表。
- `scripts/verify_laws.py` 改成数据驱动：从 `EXPECTED` 表读取条数、首尾、抽样关键词。
- 抽样：
  - 民诉法第 85 条含“期间”；第 171 条含“十五日”；
  - 民诉法解释第 1 条含“管辖”或“第一条”正文；
  - 证据规定第 1 条含“证据”；
  - 诉讼费办法第 13 条含“案件受理费”；第 14 条含“申请费”；
  - 法律援助法第 2 条含“法律援助”。
- `data/laws/manifest.json` 重新生成，记录 SHA256、公布/施行日期、条数、范围。

### 8.3 别名与检索

- `laws.py` 增加别名：
  - 民事诉讼法：`中华人民共和国民事诉讼法`、`民事诉讼法`、`民诉法`
  - 民诉法解释：`最高人民法院关于适用《中华人民共和国民事诉讼法》的解释`、`民诉法解释`、`民诉解释`
  - 证据规定：`最高人民法院关于民事诉讼证据的若干规定`、`民事诉讼证据规定`、`证据规定`
  - 诉讼费用交纳办法：`诉讼费用交纳办法`、`诉讼费办法`
  - 法律援助法：`中华人民共和国法律援助法`、`法律援助法`
- 工具 `law` / `law_hint` 的 Literal 增加 5 个短名。
- 增加少量检索先验：
  - `起诉条件` → 民诉法 122
  - `答辩期` → 民诉法 128
  - `上诉期` → 民诉法 171
  - `期间计算` → 民诉法 85
  - `保全` → 民诉法 103/104（以检索结果为准）
  - `诉讼费` → 诉讼费用交纳办法 13
  - `法律援助` → 法律援助法 2

## 9. 12348 法律援助目录

### 9.1 接口

- 地址：`POST https://www.12348.gov.cn/legalList/getlegalList`
- 请求体：

```json
{
  "pageNum": 1,
  "pageSize": 50,
  "xzqh": "370102",
  "mc": "",
  "v_key": "<uuid>",
  "guid": "<uuid>",
  "number": 360,
  "crawlerCookie": "<uuid>"
}
```

- `number` 算法（从前端反爬代码还原）：
  - `raw = v_key + guid + pageNum + "." + pageSize`
  - `md5 = MD5(raw)`
  - `number = sum(md5.charCodeAt(i) for i in (5, 3, 1, 6, 8, 10))`
- `crawlerCookie`：随机 UUID，同时放入请求体和 Cookie。
- 返回：`{total, page, list: [{xzqh, mc, dz, dh, jgyd, jd, wd, id}]}`。

### 9.2 查询策略

- 12348 的城市级查询返回 0；必须按区县码查询。
- 济南 12 个区县：从 `DivisionIndex` 取 6 位码。
- `district` 指定时只查该区县；否则查全部 12 个（首次），结果按区县缓存 24 小时。
- 请求之间做 100–200ms 间隔；不并发轰炸。
- `LEGAL_AID_LIVE=1` 默认开启；设为 0 时只读本地快照。`USE_LIVE=0` 是全局离线开关，优先于 `LEGAL_AID_LIVE`，离线模式下绝不发 12348 请求。
- 失败（411/超时/非 JSON/格式变化）→ 使用 `data/legal_aid/jinan.json` 快照；快照也没有 → 返回地图 POI 并标记 `source: "map"`。
- 每个区县独立处理：live 成功用 live，失败用该区县快照，再失败用地图 POI；不要因为一个区县失败就丢掉其他区县。

### 9.3 合并与交叉验证规则

- `find_legal_service(keyword="法律援助中心")`：
  1. 先取 12348 官方目录；
  2. 再取地图 POI；
  3. 按名称/地址/坐标匹配；匹配上的 12348 条目和地图条目合并成一条，`sources` 同时列出 `12348` 和地图 provider；
  4. 没匹配上的 12348 条目保留，`sources` 只有 `12348`；没匹配上的地图 POI 追加在后面，`sources` 只有地图 provider。
- 置信度：
  - `official`：只有 12348，官方目录单源；
  - `high`：12348 + 地图名称、地址/坐标一致；
  - `medium`：12348 + 地图名称一致但地址/坐标有差异；
  - `low`：只有地图单源，或地图之间冲突；
  - `conflict`：12348 与地图名称/坐标明显不一致。
- 12348 结果坐标按 WGS-84 处理（页面使用天地图）。
- 每条结果标记 `data_source: "12348" | "map" | "snapshot"`；合并结果可有多个 `sources`。

### 9.4 快照完整性与部分失败

- `data/legal_aid/jinan.json` 必须覆盖济南 12 个区县；生成脚本校验每个区县的覆盖率，空结果要显式记录为 `empty`，不能把“没抓到”当成“没有中心”。
- 城市级查询返回 `coverage`：

```json
{
  "districts_total": 12,
  "districts_live": 9,
  "districts_snapshot": 2,
  "districts_map": 1,
  "districts_failed": 0
}
```

- 某个区县 live 失败且无快照/地图兜底时：
  - 不返回“该区县没有法律援助中心”；
  - 在 `warnings` 中加 `{"code": "LEGAL_AID_PARTIAL", "district": "..."}`；
  - 如果所有区县都失败且无任何结果，返回 `LEGAL_AID_UNAVAILABLE`，不是 `NO_RESULTS`。

## 10. 民政部行政区划

- 数据源：`https://dmfw.mca.gov.cn/9095/xzqh/getList?code=370100000000&maxLevel=3`
- 返回树：济南市 → 12 个区县 → 街道。
- 本地快照：`data/divisions/jinan.json`，结构为 `{code, name, level, type, children}`。
- `DivisionIndex`：
  - `districts() -> list[Division]`
  - `find(name) -> Division | None`
  - `adcode12(name) -> str | None`
  - `adcode6(name) -> str | None`（12 位前 6 位，用于 12348）
- `find_legal_service` 用 `DivisionIndex` 校验 `district`，替代硬编码白名单；未知区县返回 `CITY_NOT_FOUND`。
- 刷新脚本：`scripts/fetch_divisions.py`，默认 30 天缓存；失败时保留旧快照。

## 11. 节假日与期间计算

- 数据源：`https://timor.tech/api/holiday/year/{year}?type=Y&week=Y`
- 本地快照：`data/holidays/2025.json`、`data/holidays/2026.json`（从 timor.tech 生成，注明来源）。
- `HolidayCalendar`：
  - `is_holiday(date) -> bool`
  - `is_workday(date) -> bool`
  - `next_workday(date) -> date`
  - `workdays_between(start, end) -> int`
- 失败降级：本地快照 → 仅周末（返回 `holiday_source: "weekend-only"`，并给 warning）。
- 期间计算规则（民诉法第 85 条）：
  - `start_date` 是**触发日**：上诉期用判决书/裁定书送达日，答辩期用收到起诉状副本日，其他期间用事件发生日；
  - 触发日当天不计算在内：第 1 天是 `start_date + 1`；
  - `day_type="natural"` 按自然日数；`day_type="working"` 按工作日数；
  - 期间届满最后一日是法定休假日的，顺延到休假日后的第一日；
  - 期间不包括在途时间。
- 上诉期（民诉法第 171 条）：
  - 判决 15 日；
  - 裁定 10 日。
- 答辩期（民诉法第 128 条）：15 日。
- 示例：`start_date=2026-11-06`（周五），15 个自然日 → 第 1 天 11-07，原届满日 11-21（周六）→ 顺延到 11-23（周一）。
- 工具不会从“判决日期”推断送达日期；调用方必须传送达/收到日期，否则期间会算错。

## 12. 工具契约

### 12.1 `find_legal_service`（名称不变）

参数：

- `keyword`: `法院` / `律师事务所` / `法律援助中心`
- `city`: 默认 `济南`
- `district`: 可选
- `limit`: 1–10，默认 5

返回每条：

```json
{
  "name": "...",
  "address": "...",
  "telephone": "...",
  "lat": 36.67,
  "lng": 117.01,
  "coord_system": "wgs84",
  "adcode": "370102",
  "source": "12348",
  "confidence": "high",
  "sources": [
    {"provider": "12348", "name": "...", "address": "...", "telephone": "...", "lat": ..., "lng": ..., "coord_system": "wgs84"},
    {"provider": "baidu", "name": "...", "address": "...", "telephone": "...", "lat": ..., "lng": ..., "coord_system": "bd09"}
  ],
  "discrepancies": []
}
```

### 12.2 `plan_route`（名称不变）

参数不变。返回：

```json
{
  "distance_m": 14205,
  "duration_s": 2462,
  "steps": [...],
  "confidence": "high",
  "sources": [
    {"provider": "baidu", "distance_m": 14205, "duration_s": 2462},
    {"provider": "tencent", "distance_m": 14010, "duration_s": 2500}
  ],
  "discrepancies": []
}
```

### 12.3 `search_law`（名称不变）

参数 `law` 增加 5 个枚举值。其余行为不变；多引用继续返回全部 in-corpus 条文。

### 12.4 `verify_citation`（名称不变）

`law_hint` 增加 5 个枚举值。`ambiguous` 候选列表自动包含新法。

### 12.5 `legal_calculator`（新增）

参数：

- `action`: `litigation_fee` / `preservation_fee` / `deadline`
- `amount`: 金额（诉讼费/保全费）
- `case_type`: `财产案件` / `离婚` / `人格权` / `知识产权` / `劳动争议` / `行政-商标专利海事` / `行政-其他` / `其他非财产`
- `start_date`: `YYYY-MM-DD`
- `days`: 期间天数
- `deadline_type`: `appeal_judgment` / `appeal_ruling` / `answer` / `custom`
- `day_type`: `natural` / `working`

返回：

```json
{
  "action": "litigation_fee",
  "fee": 8800.0,
  "breakdown": [...],
  "legal_basis": {"law": "诉讼费用交纳办法", "article": "第十三条", "text": "...", "source_url": "..."},
  "notes": ["按财产案件分段累计计算"]
}
```

期间返回：

```json
{
  "action": "deadline",
  "start_date": "2026-11-06",
  "days": 15,
  "day_type": "natural",
  "original_end_date": "2026-11-21",
  "end_date": "2026-11-23",
  "adjusted": true,
  "holiday_source": "timor",
  "legal_basis": {"law": "民事诉讼法", "article": "第八十五条", "text": "...", "source_url": "..."},
  "notes": ["期间开始日不计算在内", "原届满日 2026-11-21 是周六，顺延至 2026-11-23"]
}
```

## 13. 配置

| 变量 | 默认 | 说明 |
|---|---|---|
| `TENCENT_MAP_KEY` | 空 | 腾讯位置服务 key；空则禁用 |
| `TIANDITU_KEY` | 空 | 天地图 tk；空则禁用 |
| `MAP_PROVIDERS` | `baidu,tencent,tianditu` | 启用的 provider 顺序 |
| `MAP_CROSS_CHECK` | `1` | 是否做交叉验证 |
| `MAP_LIVE_FAILURE_MODE` | `cache` | `cache` / `error` / `fixtures` |
| `TENCENT_BUDGET` | `20` | 腾讯真实调用上限 |
| `TIANDITU_BUDGET` | `20` | 天地图真实调用上限 |
| `LEGAL_AID_LIVE` | `1` | 是否查询 12348；`USE_LIVE=0` 时强制关闭 |
| `LEGAL_AID_CACHE_HOURS` | `24` | 12348 缓存 |
| `DIVISION_CACHE_DAYS` | `30` | 区划缓存 |
| `HOLIDAY_API` | `https://timor.tech/api/holiday` | 节假日 API |
| `HOLIDAY_LIVE` | `1` | 是否查询 timor.tech；`USE_LIVE=0` 时强制关闭 |
| `HOLIDAY_CACHE_DAYS` | `30` | 节假日缓存 |

`USE_LIVE=0` 是**全局离线开关**：地图只用 fixtures，12348/民政部/timor 只用本地快照，测试和演示都不会偷偷联网。`LEGAL_AID_LIVE`、`HOLIDAY_LIVE` 只能在 `USE_LIVE=1` 时进一步关闭，不能覆盖 `USE_LIVE=0`。

## 14. 测试策略

全部离线，不发真实网络请求。

### 14.1 新增测试

- `tests/test_coord.py`：BD-09/GCJ-02/WGS-84 往返转换。
- `tests/test_map_crosscheck.py`：名称/地址/电话/坐标匹配；一致/冲突/单源。
- `tests/test_tencent_provider.py`：MockTransport 返回地点/路线；错误码映射。
- `tests/test_tianditu_provider.py`：MockTransport 返回地名/地理编码/路线。
- `tests/test_map_service.py`：provider failover、缓存、预算、`MAP_LIVE_FAILURE_MODE`、多源结果并集、secondary-only POI 不被丢掉。
- `tests/test_legal_aid.py`：签名 `number` 计算、区县查询、缓存、411 降级、快照兜底、部分区县失败时的 `coverage`/`warnings`。
- `tests/test_divisions.py`：区县/12 位码/6 位码映射。
- `tests/test_holidays.py`：节假日、调休、周末、降级。
- `tests/test_calculators.py`：财产案件分段、保全费上限、期间顺延、上诉期、`start_date` 当天不计入、周六/法定节假日顺延。
- `tests/test_law_data.py`：新增 5 部法的条数/边界/抽样。
- `tests/test_tools_law.py`：新法检索、引用核对、`law_hint`。
- `tests/test_tools_baidu.py`：`find_legal_service` 多源输出、12348 合并、区划校验；`plan_route` 交叉验证、`coord_system` 输入转换（wgs84/gcj02/bd09）。
- `tests/test_tools_calculator.py`：工具层 JSON 结构、错误码。

### 14.2 回归测试

- 现有 116 条全部继续通过。
- `search_law("违约金过高")` 仍返回民法典第 585 条。
- 4 个原工具的 mock 行为不变；仅新增字段。
- `MCP_PROFILE` 不设或设为 `task2` 时仍暴露 4 个工具（可选兼容）。

## 15. 错误码

新增：

- `ALL_SOURCES_FAILED`：所有地图源失败；`details` 列出每个 provider 的错误。
- `LEGAL_AID_UNAVAILABLE`：12348 失败且无快照/地图兜底。
- `CALCULATION_INVALID`：金额/日期/参数不合法。
- `DIVISION_NOT_FOUND`：区县不在民政部数据中。

保留：

- `CITY_NOT_FOUND`、`NO_RESULTS`、`AK_INVALID`、`QUOTA_EXCEEDED`、`UPSTREAM_TIMEOUT`、`UPSTREAM_ERROR`、`BUDGET_EXHAUSTED`、`NO_MATCH`、`OUT_OF_SCOPE`、`NO_CITATION_FOUND`、`CORPUS_NOT_LOADED`、`NO_ROUTE`、`GEOCODE_FAILED`。

## 16. 数据与交付物

新增数据文件：

```text
data/laws/civil_procedure_law.json
data/laws/civil_procedure_interpretation.json
data/laws/civil_evidence_rules.json
data/laws/litigation_fee_rules.json
data/laws/legal_aid_law.json
data/divisions/jinan.json
data/legal_aid/jinan.json
data/holidays/2025.json
data/holidays/2026.json
```

新增脚本：

```text
scripts/fetch_divisions.py
scripts/fetch_legal_aid.py
scripts/fetch_holidays.py
```

更新：

```text
scripts/fetch_laws.py
scripts/verify_laws.py
laws.py
config.py
server.py
tools/*.py
README.md
CHANGELOG.md
HANDOFF.md
.env.example
```

## 17. 风险与应对

| 风险 | 应对 |
|---|---|
| 12348 接口非官方、反爬变化 | 缓存 + 本地快照 + 地图 POI 三级兜底；`LEGAL_AID_LIVE=0` 可关闭 |
| 腾讯/天地图无 key | provider 自动禁用；不影响百度/mock/法条/计算器 |
| 坐标系转换误差 | 统一 WGS-84 内部；已知点测试；阈值判断 |
| 交叉验证误报 | 阈值 + `confidence` + `discrepancies`，不静默选一个 |
| 节假日 API 失败 | 本地快照 + 周末兜底，明确标注 `holiday_source` |
| 法条抓取失败 | 保留现有语料；`verify_laws.py` 失败即停止入库 |
| 语料变大影响检索 | 1678 条仍在内存可接受；后续可预计算 `text_norm` |
| 地图/12348 请求慢 | 缓存；12348 请求间隔；不并发轰炸 |

## 18. 留给实现阶段的决定

- 交叉验证的具体阈值（名称相似度算法、坐标距离、路线差异）先用可解释规则，测试驱动调整。
- 12348 首次全量查询 12 个区县的耗时；如果太慢，改成按需查询 + 后台刷新。
- 腾讯/天地图的具体接口字段映射以官方文档为准；无 key 时用 fixture 测试。
- 诉讼费“离婚/人格权/知识产权”等幅度型收费，返回 min/max，并提示以当地标准为准。
- 期间计算对“工作日”与“自然日”的默认值：默认自然日；`working` 需用户显式指定。

## 19. 验收标准

- [ ] 5 个工具可加载，原 4 个工具名称不变。
- [ ] 地图 provider 至少百度可用；腾讯/天地图无 key 时自动跳过。
- [ ] 百度失败时按配置降级；不崩溃。
- [ ] 2 源可用时返回 `confidence` 和 `discrepancies`。
- [ ] 5 部新法入库，`verify_laws.py` 输出 1678 条。
- [ ] `search_law("民诉法第85条")` 返回期间条文；`verify_citation` 能核对新法。
- [ ] 12348 可查询历下区法律援助中心；失败时有快照/地图兜底。
- [ ] `legal_calculator` 的诉讼费、保全费、上诉期有官方条文依据。
- [ ] 全部测试离线通过；无 key 也能跑 mock 测试。
- [ ] README/CHANGELOG/HANDOFF 更新；`.env.example` 增加新变量占位。

## 20. Builder check 决议（2026-11-08）

以下 6 项由实现方定案，不再阻塞设计批准：

1. **`deadline.start_date` 语义**：它是触发日（送达日/收到日/事件发生日），当天不计入；第 1 天是 `start_date + 1`。工具不推断送达日。文档示例已修正为 `2026-11-06 + 15 天 → 原 11-21（周六）→ 顺延 11-23（周一）`。
2. **`plan_route` 坐标输入**：默认 WGS-84，新增可选 `coord_system`（`wgs84` / `gcj02` / `bd09`）。`find_legal_service` 输出可直接传给 `plan_route`；需要 v1 百度坐标时显式传 `bd09`。
3. **`USE_LIVE` 全局离线开关**：`USE_LIVE=0` 时地图只用 fixtures，12348/民政部/timor 只用本地快照，测试不联网。`LEGAL_AID_LIVE`、`HOLIDAY_LIVE` 只能进一步关闭，不能覆盖 `USE_LIVE=0`。
4. **地图结果集**：多源时返回去重后的并集，primary 优先排序，secondary 独有的 POI 不丢弃；`limit` 作用于合并列表。
5. **12348 与地图**：12348 是 provider 之一，与地图结果交叉验证并合并；只有 12348 时 `confidence: "official"`，与地图一致时 `high`，有差异时 `medium`，明显冲突时 `conflict`。
6. **12348 部分失败**：按区县独立合并 live / snapshot / map；快照必须覆盖 12 个区县；部分失败返回 `coverage` 和 `warnings`，全部失败且无结果返回 `LEGAL_AID_UNAVAILABLE`，不伪装成 `NO_RESULTS`。
