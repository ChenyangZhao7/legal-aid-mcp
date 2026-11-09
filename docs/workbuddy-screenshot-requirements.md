# WorkBuddy 截图要求（给 WorkBuddy 执行）

> 目标：补齐任务书要求的运行截图，证明 5 个工具能在 WorkBuddy / MCP Inspector 中真实调用。
> 只拍真实界面，不要 P 图、不要伪造工具调用、不要补造返回结果。
> 保存目录：`legal-aid-mcp\docs\screenshots\`
> 执行状态：**2026-11-09 09:58 已采集 7 张，10:02 归档为规范文件名；3 处待补，见第 7 节。**

---

## 0. 给 WorkBuddy 的直接指令

请按下面的顺序完成 5 张截图，并保存到 `legal-aid-mcp\docs\screenshots\`：

1. `inspector-tools-5.png`：MCP Inspector 的工具列表，必须能看到 5 个工具名。
2. `inspector-search-law.png`：Inspector 执行 `search_law(query="违约金过高")` 的结果，必须能看到返回的民法典第五百八十五条。
3. `workbuddy-multi-tool.png`：WorkBuddy 里问“我在济南西站，要去济南中院立案，附近有法律援助吗？帮我规划路线。”，必须能看到 `find_legal_service` 和 `plan_route` 的工具调用块。
4. `workbuddy-no-tool.png`：WorkBuddy 里问“什么是违约金？”，必须能看到**没有任何工具调用**，只有直接回答。
5. `workbuddy-calculator.png`：WorkBuddy 里问“诉讼请求金额 100 万元，财产案件受理费大概多少？”，必须能看到 `legal_calculator` 调用和 13,800 元结果。

拍完把实际文件名、截图时间、对应问题填到第 4 节表格。

---

## 1. 通用要求

- [x] 用真实 WorkBuddy / MCP Inspector 界面，不摆拍、不拼接
- [x] 截图包含完整窗口或完整对话区域，不要只截一小块
- [ ] 工具名、参数、返回结果必须清晰可读 — 第 3、5 张缺工具调用块，见第 7 节
- [x] 分辨率建议宽度 ≥ 1280px；PNG 或 JPEG — 实际 1820–1934px
- [ ] 不要出现 API key、`.env`、个人隐私、无关聊天记录 — Inspector 两张地址栏含 API token，见第 7 节
- [x] 不要出现其他项目的 MCP 配置
- [x] 截图里的工具名必须是以下 5 个：
  - `find_legal_service`
  - `plan_route`
  - `search_law`
  - `verify_citation`
  - `legal_calculator`
- [x] 如果某一步失败，保留失败截图并记录错误，不要用别的截图冒充

---

## 2. 五张必拍截图

### 2.1 `inspector-tools-5.png`

**拍什么：** MCP Inspector 的 Tools 页面。

**必须看到：**

- 5 个工具名完整出现
- 工具描述/参数区域能看出是 MCP 工具
- 浏览器地址或 Inspector 标题能证明是 Inspector

**通过标准：** 一眼能数出 5 个工具，且包含 `legal_calculator`。

- [x] 已拍 · `docs/screenshots/inspector-tools-5.png` · 2026-11-09 09:58 · **合格**（`Tools (5)` 与 5 个工具名齐全；浏览器标签标题为 MCP Inspector）

---

### 2.2 `inspector-search-law.png`

**拍什么：** 在 Inspector 里调用：

```json
{
  "name": "search_law",
  "arguments": {
    "query": "违约金过高"
  }
}
```

**必须看到：**

- 工具名 `search_law`
- 参数 `违约金过高`
- 返回结果里出现 `第五百八十五条`
- 返回结果里出现“违约金”或“过分高于”

**通过标准：** 能证明 `search_law` 在 Inspector 里真实返回了正确条文。

- [x] 已拍 · `docs/screenshots/inspector-search-law.png` · 2026-11-09 09:58 · **基本合格**：左侧选中 `search_law`、右侧 Messages 有 `TOOLS/CALL search_law`、Results 可见 `"article": "第五百八十五条"` 与条文正文；**参数 `违约金过高` 未在画面直接展示**（如需严格达标，可展开该次调用或补一张带参数面板的图）

---

### 2.3 `workbuddy-multi-tool.png`

**拍什么：** 在 WorkBuddy 新建对话，模型选 **DeepSeek V4.1 Flash**，问：

```text
我在济南西站，要去济南中院立案，附近有法律援助吗？帮我规划路线。
```

**必须看到：**

- 工具调用块 `find_legal_service`
- 工具调用块 `plan_route`
- 最终回答里有法援机构和路线距离/时间

**通过标准：** 能证明模型组合调用了至少 2 个工具，且顺序合理（先找机构，再规划路线）。

- [ ] 已拍 — **未达标**：`docs/screenshots/workbuddy-multi-tool.png` 只有最终回答（流程图 + 法援机构表 + 14km/30-40分、1.7km/步行20分）与模型名 `DeepSeek-V4.1-Flash`，**画面未出现两个工具调用块**；需展开「已完成 …s」/调用详情后补拍

---

### 2.4 `workbuddy-no-tool.png`

**拍什么：** 在 WorkBuddy 新建对话，模型选 **DeepSeek V4.1 Flash**，问：

```text
什么是违约金？
```

**必须看到：**

- **没有任何工具调用块**
- 只有模型直接回答违约金定义/调整规则

**通过标准：** 截图里没有 `search_law`、`verify_citation` 等工具调用。

- [x] 已拍 · `docs/screenshots/workbuddy-no-tool.png` + `workbuddy-no-tool-2.png`（同对话上下两屏）· 2026-11-09 09:58 · **合格**：全程无工具调用块，模型 `DeepSeek-V4.1-Flash`，仅直接解释

---

### 2.5 `workbuddy-calculator.png`

**拍什么：** 在 WorkBuddy 新建对话，模型选 **DeepSeek V4.1 Flash**，问：

```text
诉讼请求金额 100 万元，财产案件受理费大概多少？
```

**必须看到：**

- 工具调用块 `legal_calculator`
- 参数含 `amount=1000000`、`case_type=财产案件`
- 结果含 **13,800 元**（或 13800）
- 最好能看到《诉讼费用交纳办法》第十三条依据

**通过标准：** 能证明 `legal_calculator` 在 WorkBuddy 里被真实调用并返回正确金额。

- [ ] 已拍 — **部分达标**：`workbuddy-calculator.png` + `workbuddy-calculator-2.png` 可见 **结论 13,800 元**、分段明细、《诉讼费用交纳办法》第十三条第（一）项、模型 `DeepSeek-V4.1-Flash`；**但未出现 `legal_calculator` 工具调用块与 `amount` 参数**，需展开调用详情后补拍

---

## 3. 命名与保存

统一保存到：

```text
legal-aid-mcp\docs\screenshots\
```

文件名必须是：

```text
inspector-tools-5.png
inspector-search-law.png
workbuddy-multi-tool.png
workbuddy-no-tool.png
workbuddy-calculator.png
```

如果必须用 `.jpg` / `.jpeg`，保持同名，只改扩展名，并同步修改第 4 节表格。

---

## 4. 截图记录表

| 文件 | 截图时间 | 对应问题/操作 | 是否含工具调用 | 备注 |
|---|---|---|---|---|
| `inspector-tools-5.png` | 2026-11-09 09:58 | Inspector Tools 列表 | — | 合格，`Tools (5)`；⚠️ 地址栏含 Inspector API token，建议打码后重存 |
| `inspector-search-law.png` | 2026-11-09 09:58 | `search_law("违约金过高")` | 是 | 返回第五百八十五条 ✅；参数值未直接展示；⚠️ 同样含 token |
| `workbuddy-multi-tool.png` | 2026-11-09 09:58 | 济南西站 → 中院 + 法援 | 未见 | ❌ 缺 `find_legal_service` / `plan_route` 调用块，仅最终回答；待补拍 |
| `workbuddy-no-tool.png` | 2026-11-09 09:58 | 什么是违约金？ | 否 | 合格；另有 `workbuddy-no-tool-2.png` 为同对话下半屏 |
| `workbuddy-calculator.png` | 2026-11-09 09:58 | 100 万诉讼费 | 未见 | 金额 13,800 元正确 ✅；缺 `legal_calculator` 调用块与参数；另有 `workbuddy-calculator-2.png` 为续屏 |

---

## 5. 验收 checklist

- [x] 5 张截图全部存在，文件名正确 — 已归档 5 个规范名 + 2 张续屏
- [x] Inspector 工具列表能看到 5 个工具
- [x] Inspector 的 `search_law` 返回第五百八十五条
- [ ] WorkBuddy 多工具问答能看到 `find_legal_service` + `plan_route` — **未达标，待补拍**
- [x] WorkBuddy “什么是违约金”没有工具调用
- [x] WorkBuddy 诉讼费返回 13,800 元 — 金额达标；调用块待补
- [ ] 截图里没有 API key、`.env`、个人隐私 — **未达标**：Inspector 两张地址栏可见 `MCP_INSPECTOR_API_TOKEN=…`
- [x] 第 4 节表格已填写
- [x] 截图已提交到仓库 `docs/screenshots/` — 已放入工作区，尚未 `git add`

---

## 6. 如果 WorkBuddy 当前只显示 4 个工具

说明它挂载的还是旧会话/旧进程，按下面处理：

1. 完全退出 WorkBuddy（托盘图标也要退出）
2. 重新打开
3. 确认 MCP 设置里 `legal-aid-mcp` 已启用
4. 确认工具列表出现 `legal_calculator`
5. 再开始拍第 2.3–2.5 张

如果仍然只有 4 个工具，先截图记录，不要继续拍多工具截图。

---

## 7. 归档与待补事项（2026-11-09 10:02）

**归档**：原图在 `Z:\project-mcp\screenshot\`（7 张，原始名 `test1/2/3/4.1/4.2/5.1/5.2.png`），
已复制为规范文件名到 `docs/screenshots/`。原图保留未删。

**三处待补**：

1. `workbuddy-multi-tool.png`：需展开工具调用详情，露出 `find_legal_service` 与 `plan_route` 两个调用块。
   做法：在该对话里点回答顶部的「已完成 …s ›」或工具步骤区域展开，再截一次。
2. `workbuddy-calculator.png`：同样展开调用详情，露出 `legal_calculator` 及 `amount=1000000`、`case_type=财产案件`。
3. `inspector-search-law.png`：如需严格满足「参数 `违约金过高` 可见」，可在 Inspector 左侧选中 `search_law`、
   填好 query 后再截（连带参数面板与 Results 一起）。

**一处合规问题**：`inspector-tools-5.png` 与 `inspector-search-law.png` 的浏览器地址栏完整显示了
`MCP_INSPECTOR_API_TOKEN`（本地 Inspector 临时令牌）。第 1 节要求「不要出现 API key」，
建议对地址栏 token 部分打码，或截掉地址栏（标签页标题已能证明是 MCP Inspector）。
打码敏感信息不属于「伪造截图」，可以接受。

**数据核对**：`workbuddy-multi-tool.png` 的路线数字（14km / 30-40分）与本仓库 mock 样本
（14205 m / 2462 s ≈ 14.2 km / 41 分）一致，回答内容与工具返回吻合，非编造。
