# 法律援助一条龙 MCP v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 4 个工具上增加地图多源 failover/交叉验证、民事诉讼语料、12348/民政部/节假日/本地计算器，形成 5 个工具的 v2。

**Architecture:** 新增 `maps/` provider 层（Baidu/Tencent/Tianditu）统一输出 WGS-84；`MapService` 负责顺序降级、去重并集和交叉验证。新增 `divisions.py`、`holidays.py`、`legal_aid.py`、`calculators.py` 作为独立数据/计算模块。工具层只做参数校验和结果组装。

**Tech Stack:** Python 3.14、`mcp==2.3.0`、`httpx`、`pytest`；现有 `BaiduClient`、`LawCorpus`、`CacheStore`、`BudgetStore` 复用。

**Spec:** `docs/superpowers/specs/2026-11-08-legal-aid-mcp-v2-design.md`

## Global Constraints

- 不接高德；腾讯/天地图是可选 provider，无 key 自动禁用。
- `USE_LIVE=0` 是全局离线开关：测试不得访问任何外部接口。
- 内部坐标统一 WGS-84；`plan_route` 默认输入 WGS-84，支持 `coord_system=wgs84|gcj02|bd09`。
- 保留现有 4 个工具名；新增 `legal_calculator`，共 5 个工具。
- 法条只来自 `flk.npc.gov.cn` 官方 docx/pdf；新增后总计 1678 条。
- 12348 查询必须按区县；live → 快照 → 地图 POI 三级兜底，不得把失败伪装成“没有中心”。
- 每项先写失败测试，再实现；每个任务结束提交一次。
- 不把 key、用户输入写进日志/错误信息/仓库。

## Review Focus

1. **坐标系统**：`plan_route("36.67,117.0")` 默认按 WGS-84 解释；传 `bd09` 时不能偏 300–600 米。
2. **provider 失败**：任一 provider 超时/配额/411 不能导致其他 provider 的结果丢失，也不能让工具崩溃。
3. **12348 部分失败**：某区县失败时不能返回“该区县没有法律援助中心”；必须给 `coverage`/`warnings`。
4. **期间计算**：`start_date` 当天不计入；最后一天是周末/法定节假日必须顺延；不得从判决日期推断送达日期。
5. **交叉验证冲突**：两个地图源坐标差 > 1km 或名称明显不同时必须返回 `conflict`/`discrepancies`，不能静默选一个。

---

### Task 1: 坐标转换模块

**Files:**
- Create: `coord.py`
- Test: `tests/test_coord.py`

**Interfaces:**
- Produces: `bd09_to_gcj02(lng, lat) -> tuple[float, float]`
- Produces: `gcj02_to_bd09(lng, lat) -> tuple[float, float]`
- Produces: `gcj02_to_wgs84(lng, lat) -> tuple[float, float]`
- Produces: `wgs84_to_gcj02(lng, lat) -> tuple[float, float]`
- Produces: `bd09_to_wgs84(lng, lat) -> tuple[float, float]`
- Produces: `wgs84_to_bd09(lng, lat) -> tuple[float, float]`
- Produces: `haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float`（tuple 为 `(lng, lat)`）

- [ ] **Step 1: 写失败测试**

`tests/test_coord.py`：
```python
import pytest
from coord import (bd09_to_gcj02, gcj02_to_bd09, gcj02_to_wgs84,
                   wgs84_to_gcj02, bd09_to_wgs84, wgs84_to_bd09, haversine_m)

def test_gcj02_bd09_roundtrip():
    lng, lat = 116.404, 39.915
    back = bd09_to_gcj02(*gcj02_to_bd09(lng, lat))
    assert back == pytest.approx((lng, lat), abs=1e-6)

def test_gcj02_wgs84_roundtrip():
    lng, lat = 116.404, 39.915
    back = gcj02_to_wgs84(*wgs84_to_gcj02(lng, lat))
    assert back == pytest.approx((lng, lat), abs=1e-6)

def test_bd09_wgs84_roundtrip():
    lng, lat = 116.404, 39.915
    back = bd09_to_wgs84(*wgs84_to_bd09(lng, lat))
    assert back == pytest.approx((lng, lat), abs=1e-5)

def test_haversine_jinan():
    # 济南西站到济南中院直线约 11km
    meters = haversine_m((116.890, 36.670), (117.013, 36.672))
    assert 9000 < meters < 13000
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_coord.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'coord'`

- [ ] **Step 3: 实现 `coord.py`**

使用标准 GCJ-02/BD-09 偏移算法；`out_of_china` 判断在中国境外时直接返回原值。`haversine_m` 使用地球半径 6371000 米。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_coord.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add coord.py tests/test_coord.py
git commit -m "feat: add coordinate conversion and distance helpers"
```

---

### Task 2: 地图数据模型与交叉验证

**Files:**
- Create: `maps/__init__.py`
- Create: `maps/base.py`
- Create: `maps/crosscheck.py`
- Test: `tests/test_map_crosscheck.py`

**Interfaces:**
- Produces: `GeoPoint(lat, lng, system="wgs84")`
- Produces: `Place(provider, name, address, telephone, point, native, adcode=None, sources=[], confidence="low", discrepancies=[], data_source=None, raw={})`
- Produces: `Route(provider, distance_m, duration_s, steps, sources=[], confidence="low", discrepancies=[])`
- Produces: `GeocodeResult(point, sources, confidence, discrepancies)`
- Produces: `normalize_name(name) -> str`
- Produces: `name_similarity(a, b) -> float`
- Produces: `match_places(a: Place, b: Place) -> bool`
- Produces: `place_confidence(sources: list[dict]) -> str`
- Produces: `place_discrepancies(sources: list[dict]) -> list[str]`
- Produces: `route_confidence(sources: list[dict]) -> str`
- Produces: `route_discrepancies(sources: list[dict]) -> list[str]`

- [ ] **Step 1: 写失败测试**

`tests/test_map_crosscheck.py`：
```python
from maps.base import GeoPoint, Place
from maps.crosscheck import (normalize_name, name_similarity, match_places,
                             place_confidence, place_discrepancies)

def place(provider, name, address, lng=117.0, lat=36.67, phone=None):
    return Place(provider=provider, name=name, address=address,
                 telephone=phone, point=GeoPoint(lat, lng),
                 native=GeoPoint(lat, lng, "wgs84"))

def test_normalize_name():
    assert normalize_name("济南市历下区人民法院") == normalize_name("山东省济南市历下区人民法院")

def test_name_similarity():
    assert name_similarity("济南市中级人民法院", "济南市中级人民法院") == 1.0
    assert name_similarity("济南市中级人民法院", "济南市历下区人民法院") < 0.8

def test_match_same_place():
    a = place("baidu", "济南市中级人民法院", "经二路1号")
    b = place("tencent", "济南市中级人民法院", "经二路1号", lng=117.0005, lat=36.6705)
    assert match_places(a, b)

def test_match_far_apart():
    a = place("baidu", "济南市中级人民法院", "经二路1号")
    b = place("tianditu", "济南市中级人民法院", "经二路1号", lng=117.02, lat=36.68)
    assert not match_places(a, b)

def test_confidence_high():
    assert place_confidence([
        {"name": "济南市中级人民法院", "address": "经二路1号", "telephone": "12368", "lng": 117.0, "lat": 36.67},
        {"name": "济南市中级人民法院", "address": "经二路1号", "telephone": "12368", "lng": 117.0005, "lat": 36.6705},
    ]) == "high"

def test_discrepancies_distance():
    got = place_discrepancies([
        {"provider": "baidu", "name": "济南市中级人民法院", "address": "经二路1号", "lng": 117.0, "lat": 36.67},
        {"provider": "tencent", "name": "济南市中级人民法院", "address": "经二路1号", "lng": 117.02, "lat": 36.68},
    ])
    assert any("距离" in item for item in got)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_map_crosscheck.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'maps'`

- [ ] **Step 3: 实现模型与匹配**

`maps/base.py` 用 dataclass；`maps/crosscheck.py` 用 `difflib.SequenceMatcher`，名称归一化去掉省/市/区前缀和空白标点。坐标距离用 `coord.haversine_m`。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_map_crosscheck.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add maps/__init__.py maps/base.py maps/crosscheck.py tests/test_map_crosscheck.py
git commit -m "feat: add map models and cross-check helpers"
```

---

### Task 3: Baidu provider 与通用 live 客户端

**Files:**
- Create: `maps/live.py`
- Create: `maps/baidu_provider.py`
- Test: `tests/test_baidu_provider.py`

**Interfaces:**
- Consumes: `BaiduClient`、`CacheStore`、`BudgetStore`
- Produces: `LiveJsonClient(name, base_url, settings, transport=None, now=None, budget_limit=20, budget_path=None)`
- Produces: `LiveJsonClient.get(path, params) -> dict`
- Produces: `BaiduProvider(settings, transport=None, now=None)`
- Produces: `BaiduProvider.place_search(query, region, limit) -> list[Place]`
- Produces: `BaiduProvider.geocode(address) -> GeoPoint`
- Produces: `BaiduProvider.route(origin: GeoPoint, destination: GeoPoint, mode) -> Route`

- [ ] **Step 1: 写失败测试**

`tests/test_baidu_provider.py`：mock 模式返回 Place，坐标转换后 `system == "wgs84"`；live 模式 `MockTransport` 返回地点/地理编码/路线；`LiveJsonClient` 非 JSON → `UPSTREAM_ERROR`。

```python
def test_mock_place_is_wgs84(tmp_path):
    settings = load_settings(env={"USE_MOCK": "1", "USE_LIVE": "0", ...}, base_dir=tmp_path)
    provider = BaiduProvider(settings)
    places = provider.place_search("人民法院", "济南", 5)
    assert places[0].name
    assert places[0].point.system == "wgs84"
    assert places[0].native.system == "bd09"

def test_live_non_json_maps_to_upstream_error(tmp_path):
    # LiveJsonClient with httpx.MockTransport returning text/html
    ...
    assert exc.value.code == "UPSTREAM_ERROR"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_baidu_provider.py -q`
Expected: FAIL，`ImportError`

- [ ] **Step 3: 实现**

`maps/live.py` 复用 `CacheStore`/`BudgetStore`，缓存键带 provider 前缀；处理超时、非 JSON、非 dict、HTTP 错误；预算路径默认 `cache/budget_<name>.json`。`BaiduProvider` 包装 `BaiduClient`，BD-09 ↔ WGS-84。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_baidu_provider.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add maps/live.py maps/baidu_provider.py tests/test_baidu_provider.py
git commit -m "feat: add baidu map provider"
```

---

### Task 4: Tencent 与 Tianditu provider

**Files:**
- Create: `maps/tencent_provider.py`
- Create: `maps/tianditu_provider.py`
- Test: `tests/test_tencent_provider.py`
- Test: `tests/test_tianditu_provider.py`

**Interfaces:**
- Produces: `TencentProvider(settings, transport=None, now=None)`，无 key 时 `enabled=False`
- Produces: `TiandituProvider(settings, transport=None, now=None)`，无 tk 时 `enabled=False`
- 两者均实现 `place_search/geocode/route`，返回 `Place`/`GeoPoint`/`Route`

- [ ] **Step 1: 写失败测试**

用 `httpx.MockTransport` 返回腾讯/天地图样例 JSON；断言名称、地址、坐标转为 WGS-84；断言非 0 状态映射为 `UPSTREAM_ERROR`/`AK_INVALID`。无 key 时 `enabled is False`。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_tencent_provider.py tests/test_tianditu_provider.py -q`
Expected: FAIL，`ImportError`

- [ ] **Step 3: 实现**

腾讯：`place/v1/search`（`boundary=region(...)`）、`geocoder/v1`、`direction/v1/{mode}`；GCJ-02 ↔ WGS-84。
天地图：`v2/search`、`geocoder`、`drive`；`postStr` JSON + `tk`；CGCS2000 视为 WGS-84。
错误码：腾讯 120 → `QUOTA_EXCEEDED`，121/122 → `UPSTREAM_ERROR`，123–134 → `AK_INVALID`；天地图非成功返回 → `UPSTREAM_ERROR`。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_tencent_provider.py tests/test_tianditu_provider.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add maps/tencent_provider.py maps/tianditu_provider.py tests/test_tencent_provider.py tests/test_tianditu_provider.py
git commit -m "feat: add tencent and tianditu map providers"
```

---

### Task 5: MapService failover、并集、交叉验证

**Files:**
- Create: `maps/service.py`
- Test: `tests/test_map_service.py`

**Interfaces:**
- Consumes: providers from Task 3/4、crosscheck from Task 2
- Produces: `MapService(settings, providers=None, transport=None, now=None, cross_check=None, failure_mode=None)`
- Produces: `MapService.place_search(query, region, limit) -> list[Place]`
- Produces: `MapService.geocode(address) -> GeocodeResult`
- Produces: `MapService.route(origin, destination, mode) -> Route`

- [ ] **Step 1: 写失败测试**

```python
def test_failover_uses_second_provider(settings, fake_providers):
    service = MapService(settings, providers=[FailingProvider(), FakeProvider("tencent")])
    places = service.place_search("法院", "济南", 5)
    assert places[0].provider == "tencent"

def test_union_keeps_secondary_only_poi(settings, fake_providers):
    places = service.place_search("法院", "济南", 5)
    assert {p.name for p in places} == {"济南市中级人民法院", "济南市历下区人民法院"}

def test_conflict_surfaces(settings, fake_providers):
    places = service.place_search("法院", "济南", 5)
    assert places[0].confidence in {"low", "conflict"}
    assert places[0].discrepancies
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_map_service.py -q`
Expected: FAIL，`ImportError`

- [ ] **Step 3: 实现**

provider 顺序执行；第一个成功为 primary；`cross_check` 开启时继续查询其余 provider；按 `match_places` 合并并集；`limit` 作用于合并列表；失败按 `cache|fixtures|error` 降级。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_map_service.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add maps/service.py tests/test_map_service.py
git commit -m "feat: add multi-provider map service with cross-check"
```

---

### Task 6: 民事诉讼语料扩展

**Files:**
- Modify: `scripts/fetch_laws.py`
- Modify: `scripts/verify_laws.py`
- Modify: `laws.py`
- Modify: `tools/law_search.py`
- Modify: `tools/citation.py`
- Modify: `tests/test_law_data.py`
- Modify: `tests/test_laws.py`
- Modify: `tests/test_law_corpus.py`
- Modify: `tests/test_tools_law.py`
- Generate: `data/laws/civil_procedure_law.json`
- Generate: `data/laws/civil_procedure_interpretation.json`
- Generate: `data/laws/civil_evidence_rules.json`
- Generate: `data/laws/litigation_fee_rules.json`
- Generate: `data/laws/legal_aid_law.json`
- Generate: `data/laws/manifest.json`

**Interfaces:**
- `TARGETS` 增加 5 项，`short_name` 分别为：`民事诉讼法`、`民诉法解释`、`证据规定`、`诉讼费用交纳办法`、`法律援助法`
- `EXPECTED` 条数：306/550/100/56/71
- `_LAW_ALIASES` 增加对应别名
- `search_law` / `verify_citation` 的 Literal 增加 5 个短名

- [ ] **Step 1: 写失败测试**

```python
def test_new_laws_counts():
    assert len(load("civil_procedure_law.json")) == 306
    assert len(load("civil_procedure_interpretation.json")) == 550
    assert len(load("civil_evidence_rules.json")) == 100
    assert len(load("litigation_fee_rules.json")) == 56
    assert len(load("legal_aid_law.json")) == 71

async def test_search_civil_procedure_period(server):
    data = await call(server, "search_law", {"query": "民诉法第85条"})
    assert data[0]["article"] == "第八十五条"
    assert "期间" in data[0]["text"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_law_data.py tests/test_tools_law.py -q`
Expected: FAIL（缺文件/条数不符）

- [ ] **Step 3: 实现抓取与别名**

`fetch_laws.py` 增加 target；`verify_laws.py` 改成数据驱动；`laws.py` 增加别名；工具 Literal 扩 5 项；增加检索先验（起诉条件/答辩期/上诉期/期间计算/诉讼费/法律援助）。

- [ ] **Step 4: 抓取并校验**

```powershell
.venv\Scripts\python scripts\fetch_laws.py --out data\laws --raw-dir data\raw
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
```
Expected: `OK: ... 1678 条`

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add scripts/fetch_laws.py scripts/verify_laws.py laws.py tools/law_search.py tools/citation.py tests data/laws
git commit -m "feat: add civil procedure law corpus"
```

---

### Task 7: 民政部行政区划

**Files:**
- Create: `divisions.py`
- Create: `scripts/fetch_divisions.py`
- Create: `data/divisions/jinan.json`
- Test: `tests/test_divisions.py`

**Interfaces:**
- Produces: `Division(code, name, level, type, children)`
- Produces: `DivisionIndex.load(path) -> DivisionIndex`
- Produces: `DivisionIndex.from_mca_payload(payload) -> DivisionIndex`
- Produces: `.districts() -> list[Division]`
- Produces: `.find(name) -> Division | None`
- Produces: `.adcode12(name) -> str | None`
- Produces: `.adcode6(name) -> str | None`

- [ ] **Step 1: 写失败测试**

```python
def test_jinan_districts():
    index = DivisionIndex.load(ROOT / "data" / "divisions" / "jinan.json")
    assert len(index.districts()) == 12
    assert index.adcode6("历下区") == "370102"
    assert index.adcode12("历下区") == "370102000000"
    assert index.find("火星") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_divisions.py -q`
Expected: FAIL

- [ ] **Step 3: 实现并生成快照**

`scripts/fetch_divisions.py` 调 `https://dmfw.mca.gov.cn/9095/xzqh/getList?code=370100000000&maxLevel=3`，写 `data/divisions/jinan.json`；失败时保留旧文件并以非 0 退出。

- [ ] **Step 4: 生成并跑测试**

```powershell
.venv\Scripts\python scripts\fetch_divisions.py
.venv\Scripts\python -m pytest tests/test_divisions.py -q
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add divisions.py scripts/fetch_divisions.py data/divisions tests/test_divisions.py
git commit -m "feat: add MCA division index for Jinan"
```

---

### Task 8: 节假日与期间基础

**Files:**
- Create: `holidays.py`
- Create: `scripts/fetch_holidays.py`
- Create: `data/holidays/2025.json`
- Create: `data/holidays/2026.json`
- Test: `tests/test_holidays.py`

**Interfaces:**
- Produces: `HolidayCalendar.load(data_dir, year, live=False, transport=None, now=None) -> HolidayCalendar`
- Produces: `.is_holiday(date) -> bool`
- Produces: `.is_workday(date) -> bool`
- Produces: `.next_workday(date) -> date`
- Produces: `.workdays_between(start, end) -> int`
- Produces: `.source: str`

- [ ] **Step 1: 写失败测试**

```python
def test_2026_national_day_holiday():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    assert cal.is_holiday(date(2026, 10, 1))
    assert not cal.is_workday(date(2026, 10, 1))

def test_2026_makeup_workday():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    assert cal.is_workday(date(2026, 10, 10))

def test_weekend_fallback(tmp_path):
    cal = HolidayCalendar.load(tmp_path, 2030)
    assert cal.is_holiday(date(2030, 1, 5))  # Saturday
    assert cal.source == "weekend-only"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_holidays.py -q`
Expected: FAIL

- [ ] **Step 3: 实现并生成快照**

`scripts/fetch_holidays.py` 调 `https://timor.tech/api/holiday/year/{year}?type=Y&week=Y`，转成 `{date: {holiday, name}}`；写 2025/2026。`HolidayCalendar` 读取快照，缺年份只用周末并标 `weekend-only`。

- [ ] **Step 4: 生成并跑测试**

```powershell
.venv\Scripts\python scripts\fetch_holidays.py
.venv\Scripts\python -m pytest tests/test_holidays.py -q
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add holidays.py scripts/fetch_holidays.py data/holidays tests/test_holidays.py
git commit -m "feat: add holiday calendar with free API fallback"
```

---

### Task 9: 诉讼费/保全费/期间计算器

**Files:**
- Create: `calculators.py`
- Test: `tests/test_calculators.py`

**Interfaces:**
- Produces: `litigation_fee(amount: float | None, case_type: str) -> dict`
- Produces: `preservation_fee(amount: float | None) -> dict`
- Produces: `deadline(start_date: date, days: int, day_type: str, holiday: HolidayCalendar) -> dict`
- 返回 dict 包含 `fee`/`breakdown`/`end_date`/`original_end_date`/`adjusted`/`notes`

- [ ] **Step 1: 写失败测试**

```python
def test_property_fee_100k():
    result = litigation_fee(100000, "财产案件")
    assert result["fee"] == 2300.0

def test_preservation_cap():
    assert preservation_fee(10_000_000)["fee"] == 5000.0

def test_deadline_skips_start_day():
    cal = HolidayCalendar.load(ROOT / "data" / "holidays", 2026)
    result = deadline(date(2026, 11, 6), 15, "natural", cal)
    assert result["original_end_date"] == "2026-11-21"
    assert result["end_date"] == "2026-11-23"
    assert result["adjusted"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_calculators.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**

财产案件按《诉讼费用交纳办法》第 13 条分段累计；保全费按第 14 条(二) 30 元起、1%/0.5%、上限 5000；期间按民诉法第 85 条，`start_date` 当天不计入，最后一日为节假日顺延。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_calculators.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add calculators.py tests/test_calculators.py
git commit -m "feat: add litigation fee and deadline calculators"
```

---

### Task 10: 12348 法律援助目录

**Files:**
- Create: `legal_aid.py`
- Create: `scripts/fetch_legal_aid.py`
- Create: `data/legal_aid/jinan.json`
- Test: `tests/test_legal_aid.py`

**Interfaces:**
- Produces: `LegalAidCenter(name, address, telephone, lat, lng, adcode, id)`
- Produces: `LegalAidClient(settings, divisions, transport=None, now=None)`
- Produces: `.search(district=None, keyword=None, limit=5) -> LegalAidResult`
- Produces: `LegalAidResult(centers, coverage, warnings, source)`
- Produces: `sign_payload(page_num, page_size, xzqh, mc, v_key=None, guid=None, crawler_cookie=None) -> dict`

- [ ] **Step 1: 写失败测试**

```python
def test_number_signature():
    payload = sign_payload(1, 14, "370102", "", v_key="a", guid="b")
    assert payload["number"] == 503

def test_search_lixia(tmp_path):
    # MockTransport 返回一条历下区法律援助中心
    result = client.search(district="历下区")
    assert result.centers[0].name == "山东省济南市历下区法律援助中心"

def test_411_falls_back_to_snapshot(tmp_path):
    # MockTransport 返回 {"success": false, "errorcode": "411"}
    result = client.search(district="历下区")
    assert result.source in {"snapshot", "map"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_legal_aid.py -q`
Expected: FAIL

- [ ] **Step 3: 实现并生成快照**

按设计 9.1 的签名算法；按区县查询；缓存 24h；live → 快照 → 地图；`coverage`/`warnings`。`scripts/fetch_legal_aid.py` 用 `DivisionIndex` 的 6 位码查询 12 个区县，写快照，并校验每个区县有 `ok`/`empty` 标记。

- [ ] **Step 4: 生成并跑测试**

```powershell
.venv\Scripts\python scripts\fetch_legal_aid.py
.venv\Scripts\python -m pytest tests/test_legal_aid.py -q
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add legal_aid.py scripts/fetch_legal_aid.py data/legal_aid tests/test_legal_aid.py
git commit -m "feat: add 12348 legal aid directory client"
```

---

### Task 11: 工具集成（find_legal_service / plan_route）

**Files:**
- Modify: `context.py`
- Modify: `config.py`
- Modify: `tools/legal_service.py`
- Modify: `tools/route.py`
- Modify: `tests/test_tools_baidu.py`

**Interfaces:**
- `AppContext` 增加 `maps: MapService | None = None`、`divisions: DivisionIndex | None = None`、`legal_aid: LegalAidClient | None = None`、`holidays: HolidayCalendar | None = None`，用默认值保持现有测试 fixture 兼容；工具在 `None` 时按 settings 懒构造。
- `find_legal_service` 使用 `DivisionIndex` 校验、`MapService` 查地图、`LegalAidClient` 查 12348
- `plan_route` 新增 `coord_system` 参数，默认 `wgs84`
- `config.py` 的 `Settings` 增加新字段；`tests/test_config.py` 增加默认值断言

- [ ] **Step 1: 写失败测试**

```python
async def test_find_legal_aid_prefers_12348(server):
    data = await call(server, "find_legal_service", {"keyword": "法律援助中心", "district": "历下区"})
    assert any(r["source"] == "12348" for r in data)

async def test_find_returns_confidence_and_sources(server):
    data = await call(server, "find_legal_service", {"keyword": "法院"})
    assert "confidence" in data[0]
    assert data[0]["sources"]

async def test_plan_route_accepts_wgs84(server):
    data = await call(server, "plan_route", {"origin": "36.67,117.0", "destination": "36.68,117.1"})
    assert data["distance_m"] > 0

async def test_plan_route_bd09(server):
    data = await call(server, "plan_route", {"origin": "36.67,117.0", "destination": "36.68,117.1", "coord_system": "bd09"})
    assert "distance_m" in data
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_tools_baidu.py -q`
Expected: FAIL（缺字段/参数）

- [ ] **Step 3: 实现**

`config.py` 增加新字段；`context.py` 扩展；`server.py` 构造依赖；`find_legal_service` 合并 12348 + 地图 + 区划；`plan_route` 解析 `coord_system`，地址走 `MapService.geocode`，坐标走转换。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_tools_baidu.py tests/test_divisions.py tests/test_legal_aid.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add context.py config.py server.py tools/legal_service.py tools/route.py tests/test_tools_baidu.py
git commit -m "feat: integrate multi-provider maps and legal aid into tools"
```

---

### Task 12: `legal_calculator` 工具

**Files:**
- Create: `tools/calculator.py`
- Modify: `server.py`
- Modify: `scripts/mcp_transcript.py`
- Modify: `tests/test_artifacts.py`
- Create: `tests/test_tools_calculator.py`
- Modify: `tests/test_mcp_stdio.py`

**Interfaces:**
- Produces: `register_calculator(server, ctx)`
- 工具名 `legal_calculator`，参数见设计 12.5

- [ ] **Step 1: 写失败测试**

```python
async def test_tool_lists_five_tools(server):
    tools = await server.list_tools()
    assert {t.name for t in tools} == {"find_legal_service", "plan_route", "search_law", "verify_citation", "legal_calculator"}

async def test_calculator_fee(server):
    data = await call(server, "legal_calculator", {"action": "litigation_fee", "amount": 100000, "case_type": "财产案件"})
    assert data["fee"] == 2300.0
    assert data["legal_basis"]["article"] == "第十三条"

async def test_calculator_deadline(server):
    data = await call(server, "legal_calculator", {"action": "deadline", "start_date": "2026-11-06", "days": 15, "day_type": "natural"})
    assert data["end_date"] == "2026-11-23"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_tools_calculator.py -q`
Expected: FAIL，`legal_calculator` 不存在

- [ ] **Step 3: 实现**

工具用 `run_tool` + `json.dumps(..., ensure_ascii=False)`；从 `ctx.corpus` 取第 13/14/85/171 条作为 `legal_basis`；日期解析失败返回 `CALCULATION_INVALID`。`server.py` 注册。`scripts/mcp_transcript.py` 增加 `legal_calculator` 调用；`tests/test_artifacts.py` 和 `tests/test_mcp_stdio.py` 的工具集合改成 5 个；`docs/inspector-tools.json` 重新导出。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_tools_calculator.py tests/test_mcp_stdio.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tools/calculator.py server.py tests/test_tools_calculator.py tests/test_mcp_stdio.py
git commit -m "feat: add legal calculator tool"
```

---

### Task 13: 文档、配置与最终验证

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `HANDOFF.md`
- Modify: `.env.example`
- Modify: `docs/test-report.md`

- [ ] **Step 1: 更新文档**

README 增加：5 个工具、地图 provider、key 配置、12348/民政部/timor 说明、离线模式、1678 条语料。`.env.example` 增加 `TENCENT_MAP_KEY`、`TIANDITU_KEY`、`MAP_*`、`LEGAL_AID_*`、`HOLIDAY_*`。CHANGELOG 增加 v2。HANDOFF 更新状态和下一步。

- [ ] **Step 2: 最终验证**

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
.venv\Scripts\python scripts\check_secrets.py
.venv\Scripts\python scripts\mcp_transcript.py --out docs\mcp-transcript.json
.venv\Scripts\python -c "import server; print('server import ok')"
```
Expected: 全绿；语料 1678 条；无密钥；transcript 含 5 个工具。

- [ ] **Step 3: 提交**

```bash
git add README.md CHANGELOG.md HANDOFF.md .env.example docs
git commit -m "docs: document v2 multi-source maps, civil procedure corpus, and calculators"
```
