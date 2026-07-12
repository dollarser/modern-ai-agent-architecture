# 当前实现与出版基线

> **快照日期：** 2026-07-13。动态事实以自动化检查、`docs/SUMMARY.md` 和当前代码为准；修改数量或能力后必须同步本文件。

## 内容规模

| 项目 | 当前基线 |
|---|---:|
| 章节 | 20 章，六部分 |
| Mermaid | 54 张，索引与正文一致 |
| 示例工程 | 15 个 |
| Python/TypeScript 入口 | 30 个 |
| Python 测试 | 7 个工程、39 项 |
| TypeScript | 15 个工程全部构建；有 `test` 的工程全部通过 |

数量是维护快照，不是扩写目标。删除重复或低价值内容后可以下降，但目录、索引和验收记录必须同步。

仓库顶层职责固定为：`docs/` 放可发布书稿，`examples/` 放独立示例，`specs/` 放现行规范、共创方法与历史需求，`reviews/` 放维护审查记录，`scripts/` 放校验工具。审查报告不得重新散落到仓库根目录。

## 关键实现闭环

```text
ConversationApplication
→ Session / Message
→ Task / Run
→ AgentHost / Runtime
→ Skill / Tool / MCP / Plugin
→ Policy / Approval
→ Observation / Checkpoint / Trace
→ Assistant Message / Artifact
```

- 第 7 章：只读、单轮 Agent MVP。
- `coding-agent-mvp`：跨组件模拟组合预览，不是最终实现。
- 第 16 章：Run-scoped AgentHost、DatabaseReviewAgent、受限 CodingAgent 和 Application Session。
- Skill、MCP Server 与 Plugin 分别有安装/管理子系统，并通过 Provider Adapter 进入 AgentHost。
- CodingAgent 只在指定 Workspace 内 Read/Search/Patch，并运行预注册检查；写入和执行需要 Approval，不提供任意 Shell。

## 架构不变量

- `AgentHost ≠ Agent`
- `ExpertProfile ≠ Subagent`
- `Connector ≠ MCP`
- `Plugin ≠ Tool`
- Skill 脚本不得绕过 Runtime/Tool、Policy、Approval 与 Sandbox
- Session 可以包含多个 Task/Run；`session_id`、`task_id`、`run_id` 和 `idempotency_key` 不互换
- Task 级新尝试创建新 Run；同一 Run 内有限 Tool 重试不创建新 Run
- Checkpoint 用于恢复，Trace 用于观测，Memory 用于检索，三者不互相替代
- 安装成功不等于启用、对当前 Run 可见或获准执行

## 当前协议与事实基线

- MCP：Current `2025-11-25`；初始化时仍需协商共同版本。
- A2A：用于独立 Agent 系统互操作；`contextId` 可组合多个 Task/Message。
- ACP：本书特指 Agent Client Protocol，用于 Editor/Client 与 Coding Agent 进程交互。
- OpenTelemetry：仅作为通用 Trace/Span/Metrics 来源，不定义 Agent、Task、Run 或 Session。
- 产品和快速变化的开源项目：以第 19 章直接官方来源和核查日期为准，不推断闭源内部实现。

## 发布阻塞标准

- P0/P1 必须为 0。
- P2 必须修复或在审查报告记录明确取舍。
- MkDocs strict build、内部链接、54 张 Mermaid、全部 Python 测试、全部 TypeScript build/test 和 `git diff --check` 必须通过。
- 冻结后不再增加外围模块，只接受事实、安全、可运行性、图文一致性和必要出版润色修订。
