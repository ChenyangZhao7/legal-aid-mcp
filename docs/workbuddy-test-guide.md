# WorkBuddy 人工测试指南

> 目标：在 WorkBuddy 里复测执行书 5.3 的 8 条场景，记录模型实际调用的工具和最终回答。
> 当前仓库的自动化测试只覆盖工具层和 stdio；WorkBuddy 的模型行为需要人工确认。

## 接入

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

先用 `USE_MOCK=1` 跑通流程；需要真实地图调用时再改 `USE_LIVE=1`，并确认 `cache/budget.json` 余量。

## 8 条场景

逐条记录：问题、模型调用的工具和参数、最终回答、是否符合预期、截图文件名。

- [ ] **1. 单工具**：济南市中级人民法院在哪？
  - 期望：调用 `find_legal_service(keyword="法院", city="济南")`
  - 期望返回：济南市中级人民法院；经二路1号；(0531)12368
- [ ] **2. 单工具**：违约金过高，法律怎么规定？
  - 期望：调用 `search_law(query="违约金过高")`
  - 期望返回：民法典第五百八十五条，正文含“违约金”“过分高于”
- [ ] **3. 多工具**：我在济南西站，要去济南中院立案，附近有法律援助吗？
  - 期望：`find_legal_service(keyword="法律援助中心")` → `plan_route(origin="济南西站", destination="济南市中级人民法院")`
  - 期望返回：法律援助机构 + 路线距离/时间
- [ ] **4. 多工具**：这份答辩状引用了民法典第 585 条，帮我核对，并找济南的律所
  - 期望：`verify_citation(text=...)` → `find_legal_service(keyword="律师事务所")`
  - 期望返回：585 条 `exists` + 律所列表
- [ ] **5. 参数模糊**：历下法院怎么走？
  - 期望：`find_legal_service(keyword="法院", district="历下区")` → `plan_route`
  - 期望返回：结果里有“济南市历下区人民法院”，路线可用
- [ ] **6. 异常**：济南市不存在法院在哪？
  - 期望：明确说查不到，不编造
  - 期望错误码：`CITY_NOT_FOUND` 或 `NO_RESULTS`
- [ ] **7. 无需工具**：什么是违约金？
  - 期望：不调用工具，直接解释违约金定义和调整规则
- [ ] **8. 伪造引用**：民法典第 9999 条怎么说？
  - 期望：调用 `verify_citation`
  - 期望返回：`status: "not_found"`，明确说不存在

## 截图清单

- [ ] MCP Inspector 工具列表（4 个工具）
- [ ] MCP Inspector 一次 `search_law` 调用结果
- [ ] WorkBuddy 一次多工具问答（能看到工具调用过程）
- [ ] WorkBuddy 场景 7 的“不调用工具”回答

## 记录后

把结果填进 `docs/test-report.md`，标注哪些是 `mock`、哪些是真实调用、哪些是缓存回放。如果模型没调用工具，先改工具描述里的“何时用”，再复测并记录前后对比。
