# WorkBuddy 截图要求（给 WorkBuddy 执行）

> 目标：补齐任务书要求的运行截图，证明 5 个工具能在 WorkBuddy / MCP Inspector 中真实调用。
> 只拍真实界面，不要 P 图、不要伪造工具调用、不要补造返回结果。
> 保存目录：`legal-aid-mcp\docs\screenshots\`

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

- [ ] 用真实 WorkBuddy / MCP Inspector 界面，不摆拍、不拼接
- [ ] 截图包含完整窗口或完整对话区域，不要只截一小块
- [ ] 工具名、参数、返回结果必须清晰可读
- [ ] 分辨率建议宽度 ≥ 1280px；PNG 或 JPEG
- [ ] 不要出现 API key、`.env`、个人隐私、无关聊天记录
- [ ] 不要出现其他项目的 MCP 配置
- [ ] 截图里的工具名必须是以下 5 个：
  - `find_legal_service`
  - `plan_route`
  - `search_law`
  - `verify_citation`
  - `legal_calculator`
- [ ] 如果某一步失败，保留失败截图并记录错误，不要用别的截图冒充

---

## 2. 五张必拍截图

### 2.1 `inspector-tools-5.png`

**拍什么：** MCP Inspector 的 Tools 页面。

**必须看到：**

- 5 个工具名完整出现
- 工具描述/参数区域能看出是 MCP 工具
- 浏览器地址或 Inspector 标题能证明是 Inspector

**通过标准：** 一眼能数出 5 个工具，且包含 `legal_calculator`。

- [ ] 已拍

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

- [ ] 已拍

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

- [ ] 已拍

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

- [ ] 已拍

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

- [ ] 已拍

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
| `inspector-tools-5.png` |  | Inspector Tools 列表 | — |  |
| `inspector-search-law.png` |  | `search_law("违约金过高")` | 是 |  |
| `workbuddy-multi-tool.png` |  | 济南西站 → 中院 + 法援 | 是（2 个） |  |
| `workbuddy-no-tool.png` |  | 什么是违约金？ | 否 |  |
| `workbuddy-calculator.png` |  | 100 万诉讼费 | 是（1 个） |  |

---

## 5. 验收 checklist

- [ ] 5 张截图全部存在，文件名正确
- [ ] Inspector 工具列表能看到 5 个工具
- [ ] Inspector 的 `search_law` 返回第五百八十五条
- [ ] WorkBuddy 多工具问答能看到 `find_legal_service` + `plan_route`
- [ ] WorkBuddy “什么是违约金”没有工具调用
- [ ] WorkBuddy 诉讼费返回 13,800 元
- [ ] 截图里没有 API key、`.env`、个人隐私
- [ ] 第 4 节表格已填写
- [ ] 截图已提交到仓库 `docs/screenshots/`

---

## 6. 如果 WorkBuddy 当前只显示 4 个工具

说明它挂载的还是旧会话/旧进程，按下面处理：

1. 完全退出 WorkBuddy（托盘图标也要退出）
2. 重新打开
3. 确认 MCP 设置里 `legal-aid-mcp` 已启用
4. 确认工具列表出现 `legal_calculator`
5. 再开始拍第 2.3–2.5 张

如果仍然只有 4 个工具，先截图记录，不要继续拍多工具截图。
