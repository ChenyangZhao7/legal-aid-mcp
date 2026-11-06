---
description: 以完整 Superpowers 流程处理任务
agent: superpowers
---

用 Superpowers 完整流程处理：$ARGUMENTS

要求：

1. 先加载对应 skill，从 brainstorming 开始，一次只问一个问题；达成共识前不写实现代码。
2. 用 writing-plans 输出 `IMPLEMENTATION_PLAN.md`，每步包含要改的文件、验收标准和验证命令，然后等我确认。
3. 计划确认后用 test-driven-development 实现：先失败测试，再最小实现。
4. 完成后用 verification-before-completion 实际运行命令并粘贴原始输出。
5. 最后做 code review 和收尾。

不要跳过任何阶段，不要把主控流程交给 subagent。
