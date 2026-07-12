# FAQ 问题索引

本页只用于快速定位问题；完整回答、选型依据、延伸阅读和跨主题工程建议统一维护在[第 20 章「常见架构问题与选型指南」](../chapters/20-faq/README.md)。这样可以避免同一结论在两个位置独立演进而彼此矛盾。

| 主题 | 快速判断 | 进一步阅读 |
|------|----------|------------|
| Agent 与普通 LLM 应用 | 是否需要循环决策、外部能力或可恢复的多步执行？若否，优先保持为简单调用。 | [第 1 章](../chapters/01-introduction/README.md)、[第 2 章](../chapters/02-architecture/README.md) |
| Workflow、Agent 与 Orchestrator | 确定性控制流用 Workflow；动态决策用 Agent；Orchestrator 负责调度，不必是 Agent。 | [第 2 章](../chapters/02-architecture/README.md)、[第 15 章](../chapters/15-design-patterns/README.md) |
| Task、Run、Session 与 Trace | Task 是目标，Run 是一次尝试，Session 是交互作用域，Checkpoint 用于恢复，Trace 用于观测。 | [第 2 章](../chapters/02-architecture/README.md)、[第 9 章](../chapters/09-runtime/README.md) |
| Prompt 与 Instructions | 当前任务目标放 Prompt；跨任务的行为和安全约束放 Instructions。 | [第 3 章](../chapters/03-prompt-instructions/README.md) |
| Context、Memory 与知识库 | Context 是本轮输入预算；Memory 是可读写的状态；知识库/RAG 提供可检索证据。 | [第 4 章](../chapters/04-context-management/README.md)、[第 8 章](../chapters/08-memory/README.md) |
| Tool、Function Calling 与 Skill | Tool 是可执行能力，Function Calling 是结构化调用机制，Skill 是按需加载的工作流指导。 | [第 6 章](../chapters/06-tools-function-calling/README.md)、[第 12 章](../chapters/12-skills/README.md) |
| MCP、Plugin 与 Built-in Tool | MCP 用于标准化的外部能力互操作；Plugin 是 Host 定义的扩展包；高频且稳定的能力可直接内置。 | [第 13 章](../chapters/13-mcp/README.md)、[第 14 章](../chapters/14-plugin-system/README.md) |
| Runtime、Registry 与 Hooks | Runtime 协调一次执行；Registry 管理可见 Tool；Hooks 承担日志、审批等横切控制，不能替代授权。 | [第 10 章](../chapters/10-hooks/README.md)、[第 9 章](../chapters/09-runtime/README.md)、[第 11 章](../chapters/11-tool-registry/README.md) |
| Policy、Approval 与 Sandbox | Policy 决策，Approval 处理 ask，Guardrails 执行约束，Hook 提供挂载点，Sandbox 强制资源边界。 | [第 17 章](../chapters/17-engineering-practice/README.md)、[第 16 章](../chapters/16-agent-host/README.md) |
| 单 Agent 与多 Agent | 先验证单 Agent 是否足够；只有子任务能独立交付、可并行或需要隔离上下文时才委派。 | [第 15 章](../chapters/15-design-patterns/README.md) |
| 从 MVP 到生产 | 先验证任务价值，再按动态规划、并行、恢复和可观测性的真实信号逐项升级。 | [第 7 章](../chapters/07-agent-mvp/README.md)、[第 16 章](../chapters/16-agent-host/README.md) |
| 安全、评估与运维 | 每次 Tool 执行都要授权；对关键轨迹做回归评估；日志和回放须最小化、脱敏并受控。 | [第 17 章](../chapters/17-engineering-practice/README.md)、[第 18 章](../chapters/18-best-practices/README.md) |

> **维护规则：** 新 FAQ 先写入第 20 章或对应专题章节；本页只增加稳定的定位条目，避免复制长答案。
