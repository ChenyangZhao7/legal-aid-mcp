# 测试报告 · 法律援助一条龙 MCP

- 日期：2026-11-06
- 环境：Windows、Python 3.14.7、`mcp==2.3.0`
- 模式：自动化测试全部 `USE_MOCK=1`；百度 fixtures 和法条语料在 2026-11-06 用真实接口录制/抓取
- 证据：`docs/mcp-transcript.json`、`pytest` 输出、`scripts/verify_laws.py` 输出
- WorkBuddy：当前环境没有 WorkBuddy，8 条人工场景待在有 WorkBuddy 的环境复测；本报告用 MCP Inspector/stdio transcript 代替

## 8 条场景

| # | 类型 | 问题 | 实际工具调用 | 返回摘要 | 是否符合预期 | 备注 |
|---|---|---|---|---|---|---|
| 1 | 单工具 | 济南市中级人民法院在哪？ | `find_legal_service(keyword="法院", city="济南", limit=3)` | 济南市中级人民法院；经二路1号；(0531)12368 | 是 | mock fixture 录制自真实百度响应 |
| 2 | 单工具 | 违约金过高，法律怎么规定？ | `search_law(query="违约金过高", limit=3)` | 民法典第五百八十五条，正文含“违约金”“过分高于” | 是 | 本地语料，未调用外部服务 |
| 3 | 多工具 | 我在济南西站，要去济南中院立案，附近有法律援助吗？ | `find_legal_service(keyword="法律援助中心", limit=3)` → `plan_route(origin="济南西站", destination="济南市中级人民法院")` | 济南市法律援助中心等 3 条；路线 14205 m / 2462 s | 是 | mock 路线是固定样本，真实坐标会不同 |
| 4 | 多工具 | 这份答辩状引用了民法典第 585 条，帮我核对，并找济南的律所 | `verify_citation(text="依据民法典第585条")` → `find_legal_service(keyword="律师事务所", limit=3)` | 第 585 条 `exists`；山东昌平律师事务所 | 是 | 引用存在且原文匹配 |
| 5 | 参数模糊 | 历下法院怎么走？ | `find_legal_service(keyword="法院", district="历下区", limit=5)` → `plan_route(origin="<历下区法院坐标>", destination="济南市中级人民法院")` | 5 条中含“济南市历下区人民法院”；路线 14205 m / 2462 s | 是 | 第一条是高新区法院，模型需按名称筛选；mock 路线固定 |
| 6 | 异常 | 济南市不存在法院在哪？ | `find_legal_service(keyword="法院", city="火星")` | `CITY_NOT_FOUND`：暂不支持城市“火星” | 是 | 用“火星”代表白名单外城市；没有编造结果 |
| 7 | 无需工具 | 什么是违约金？ | 不调用工具，直接回答 | 解释违约金的定义和常见调整规则 | 待复测 | 属于模型行为，需在 WorkBuddy 里人工确认 |
| 8 | 伪造引用 | 民法典第 9999 条怎么说？ | `verify_citation(text="民法典第9999条怎么说？")` | `status: not_found`，`official_text: null` | 是 | 民法典全文 1260 条，9999 条不存在 |

## 自动化结果

```text
.venv\Scripts\python -m pytest -q
68 passed in 1.74s
```

```text
.venv\Scripts\python scripts\verify_laws.py --data-dir data/laws
OK: 民法典合同编 526 条；司法解释 69 条
```

```text
.venv\Scripts\python scripts\mcp_transcript.py > docs/mcp-transcript.json
tools = find_legal_service, plan_route, search_law, verify_citation
calls = 4
search_law -> 第五百八十五条
```

## 真实调用记录

| 阶段 | 调用 | 次数 |
|---|---|---:|
| 百度权限验证 | 地点检索、地理编码、驾车路线 | 3 |
| 百度 fixtures 录制 | 法院、历下法院、律所、法律援助、两个地理编码、路线 | 7 |
| 法条抓取 | flk 搜索/下载（民法典 docx+pdf、司法解释 docx+pdf） | 4 个文件 |
| 合计百度真实调用 | — | 10 |

`LIVE_BUDGET=20` 是项目生命周期硬上限；上述 10 次之后仍有 10 次余量。

## 已知差异与待办

- mock 路线是 `route_west_station.json` 固定样本，所有 mock 路线都会返回 14205 m / 2462 s；真实调用会按实际起终点计算。
- `place_court_lixia.json` 的前三条是高新区法院、历城区法院、历下区法院；模型需要按名称筛选“历下区人民法院”。
- WorkBuddy 的 8 条人工场景、Inspector 截图待在有 GUI/WorkBuddy 的环境补；本仓库用 `docs/mcp-transcript.json` 记录 stdio 证据。
- 高德 key 实测返回 `INVALID_USER_KEY`，未接入；百度当前可用。
