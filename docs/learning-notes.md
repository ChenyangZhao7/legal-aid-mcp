# 学习笔记 · 把公开 API 包成 MCP Server

## 三阶段

1. **initialize**：Client 发 `initialize`，带协议版本、客户端信息、能力；Server 回 `serverInfo` 和 `capabilities`（本项目只用到 `tools`）。之后 Client 发 `notifications/initialized`。
2. **tools/list**：Client 拉工具清单。每个工具包含 `name`、`description`、`inputSchema`。模型主要靠 `description` 决定什么时候调用，所以“何时用、返回什么、和相近工具的区别”要写进描述。
3. **tools/call**：Client 发工具名 + 参数；Server 校验参数、执行、返回 `content`。本项目统一返回 JSON 文本；错误也返回 `{"error": {"code", "message"}}`，让模型能读懂并纠正。

## 踩坑与解决

### 1. MCP 2.x 把 FastMCP 改名 MCPServer

`mcp==2.3.0` 里 `from mcp.server.fastmcp import FastMCP` 会报错，正确入口是：

```python
from mcp.server.mcpserver import MCPServer
```

工具装饰器仍是 `@server.tool(description=...)`，stdio 启动是 `server.run("stdio")`。

### 2. 返回 list 会被当成多个 content block

`MCPServer` 对 `list` 返回值只保留第一个元素（把它当成多个 content block）。解决：工具返回 `json.dumps(..., ensure_ascii=False)` 的字符串，并加 `structured_output=False`。这样 `content[0].text` 就是完整 JSON，`json.loads` 后仍是 list。

### 3. 百度状态码

百度不是 HTTP 错误，而是 HTTP 200 + `status`：

- `0` 成功；
- `203/210/211/302` AK 权限/IP 白名单/SN 问题；
- `220` 配额超限；
- 其他非 0 按上游错误处理。

错误信息不要拼带 `ak=` 的 URL，否则密钥会进日志。

### 4. 法条 docx 解析

flk 的 docx 是 `word/document.xml`，用标准库 `zipfile` 解压后按 `<w:p>` / `<w:t>` 取文本。坑：

- 目录和正文都会出现“第X编/第X章”，要维护层级栈，后出现的正文标题会覆盖目录标题；
- 全角空格 `　` 要保留在 section 标题里，但比较时要归一化；
- 中文条号要自己转整数，`零〇` 是两个不同字符，不能用 `enumerate` 直接映射；
- 司法解释的标题是“一、一般规定”，不是“第X章”。

### 5. PowerShell 与 UTF-8

Windows 终端默认编码容易把中文输出成乱码。脚本内部一律 `encoding="utf-8"`；命令行验证时用 `python -X utf8`，或把输出重定向到文件再用 `Get-Content -Raw` 读。

### 6. 缓存与预算

真实调用前先查缓存（按去掉 `ak` 的参数哈希），命中就不花预算；未命中才自增 `cache/budget.json`。这样同一请求重复调试不会把额度跑超。`LIVE_BUDGET=20` 是生命周期硬上限，不按日重置。

### 7. pi 交叉核对

pi 没有 webfetch，但能用 `bash` + `curl` 访问 flk。让 pi 独立跑一个只依赖标准库的抓取脚本，比较 docx SHA256 与主控抓取是否一致；这次两边都是 `6926a597...`，说明语料来源一致。不要让 pi 凭记忆生成法条。

## 一句话

MCP 的核心不是“包一层函数”，而是把**工具描述、参数 Schema、错误信息**设计成模型能独立使用的接口；法条类工具还要把“没找到”和“不存在”分开说清楚。
