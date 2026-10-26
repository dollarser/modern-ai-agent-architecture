# Agent Host 与 Database Review Agent - 最终组装参考实现

这是第 16 章的完整可运行教学示例。它不复制第 8～15 章的生产级实现，而是把各章能力提炼为稳定端口，为每个端口提供离线最小适配器，并通过一个端到端场景证明这些组件能够真正组装。

执行 API 使用 `run_id` 作为单次可恢复运行的身份和 Checkpoint 键。它不把应用级 Session 冒充为一次执行：一个 Session 聚合多个 Task/Run 的存储与消息模型由上层应用负责。

## 已实现能力

- `MemoryBackend`：短期追加与读取、长期记忆、确定性检索，支持同步或异步 Backend
- `CheckpointStore`：可注入的同步或异步状态存储；默认使用 JSON 原子替换
- `CapabilitySnapshot`：Checkpoint 绑定 Tool/Skill/Policy/配置摘要，能力变化时拒绝静默恢复
- `PolicyEngine`：统一返回 `allow / ask / deny`；`ApprovalGate` 只处理 `ask` 的交互
- `ConfigScope + PolicyLayer`：支持 managed/project/user/local/session，跨层 `deny` 不可被覆盖
- `HookPipeline`：Run、Plan、Tool、Approval、Error、Finish 生命周期事件
- Guard Hook fail-closed；Observer Hook 错误隔离并写入 Trace
- `ToolRegistry + ToolRouter`：来源、来源名称、状态、标签、参数 Schema、审批标记
- `MCPToolAdapter`：发现 MCP Tool、转换 Schema、注册并代理调用
- MCP 内部始终使用 `<server>.<tool>` canonical name；无歧义短名只是显式 Alias
- `InstalledSkillProvider + MCPServerProvider + InstalledPluginProvider`：接入第 12--14 章安装型子系统，并管理启动与关闭
- `CatalogSkillProvider + ManagerMCPProvider + CatalogPluginProvider`：把三个真实安装/管理 API 转换为上述运行期 Port
- 扩展初始化使用 single-flight/锁和失败回滚；关闭采用 best-effort 清理并聚合错误
- `PluginLoader`：加载/卸载 Plugin，并注册/移除 Plugin 贡献的 Tool、Skill 和 Hook
- `ApprovalGate`：默认拒绝、显式自动或脚本化审批；拒绝后不调用 Tool Handler
- `HandoffCoordinator + ReviewSubagent + EventBusPort`：支持异步 Adapter 的最小编排闭环
- Skill 先发现元数据，再按策略选择并加载正文；发现/加载事件写入 Trace
- 每次 Run 捕获冻结的 Tool Registry；运行中热加载/卸载只影响后续 Run
- 通用 `AgentHost` 不包含业务 Tool；`DatabaseReviewAgent` 与 `CodingAgent` 分别显式组合审查和受限编码场景
- `CodingAgent`：工作区内列举、读取、搜索、精确 Patch 和预注册测试；写入与执行均需审批
- `ConversationApplication + JsonSessionStore`：一个 Session 聚合多轮 Message 和多个 Task/Run，并把裁剪后的历史传给新 Run
- `HostA2AAdapter`：将远程 A2A Task 绑定到 Host `run_id`，发布任务事件并按租户/主体读取 Artifact；不负责远程 Transport 和认证
- 依赖感知并行、结构化重试、Tool 超时、JSON Checkpoint 和诚实终止状态
- Python 与 TypeScript 对等实现和契约测试

默认实现完全离线，不需要 API Key，也不访问网络。数据库审查入口不读写业务文件；独立 `CodingAgent` 只在调用方显式指定的工作区内读写，并以固定参数启动预注册测试，不接受任意 Shell 字符串。真实 Provider、Memory Store、MCP Client、Approval UI 和远程 Event Bus 都可以通过构造函数替换，不需要修改 Runtime。

## 代码结构

```text
agent-host/
├── python/
│   ├── runtime_state.py  # RunState、PlanStep 与 Memory Port
│   ├── coordination.py   # Event Bus 与 Subagent Handoff
│   ├── assembly.py       # 其余端口、执行器与通用 AgentHost；重导出公共契约
│   ├── application.py    # Session / Message / Task 与 AgentHost 的应用层衔接
│   ├── governance.py     # Policy Engine 与 Capability Snapshot 工具
│   ├── database_review_scenario.py # 数据库审查场景与 DatabaseReviewAgent
│   ├── coding_scenario.py # 受限编码场景与 CodingAgent
│   ├── installed_adapters.py # Skill/MCP/Plugin 安装面到运行面的 Adapter
│   ├── a2a_adapter.py       # A2A Task/Artifact 到 Host 的适配层
│   ├── sandbox_profile.py   # Shell/文件/网络沙箱配置校验
│   ├── main.py           # 中断恢复演示入口
│   ├── test_main.py      # 最终组装契约测试
│   ├── test_a2a_adapter.py
│   └── test_sandbox_profile.py
└── typescript/
    ├── runtime-state.ts  # RunState、PlanStep 与 Memory Port
    ├── coordination.ts   # Event Bus 与 Subagent Handoff
    ├── assembly.ts       # 双语言对等的执行器与通用 AgentHost；重导出公共契约
    ├── application.ts
    ├── governance.ts
    ├── database-review-scenario.ts
    ├── coding-scenario.ts
    ├── installed-adapters.ts
    ├── a2a-adapter.ts
    ├── sandbox-profile.ts
    ├── main.ts
    └── test.ts
```

## 运行方式

### Python

```bash
cd python
python main.py
python -m unittest -v test_main.py
```

仅依赖 Python 3.10+ 标准库。

### TypeScript

```bash
cd typescript
npm ci
npm run build
npm test
npm start
```

需要 Node.js 18+。

## 端到端场景

```text
Task
→ Skill 匹配 + Memory 检索
→ Planner
→ MCP Tool 查找候选
→ Built-in Tool 检查文件
→ Plugin-contributed Tool 汇总
→ Human Approval Gate
→ Plugin-contributed Tool 生成变更建议
→ delegate_review Built-in Tool
→ Handoff 给 Review Subagent
→ Event Bus 发布父子任务事件
→ 组合结果并保存 Memory / Trace / Checkpoint
```

入口程序先中断再恢复。测试还验证 MCP/Plugin 来源、Tool 状态过滤、Plugin 卸载、扩展失败回滚与重试、能力快照不兼容恢复、审批拒绝不产生副作用、Guard/Observer 的不同失败策略、Handoff 事件、Memory 可替换、重试计数和失败不误报成功。

第二条纵向切片由测试直接运行：在临时工作区创建一个有缺陷的 `add` 函数，依次执行 `list_files → read_file / search_code → apply_patch → run_check → report_change`。默认 Gate 会在 Patch 前拒绝且文件保持不变；脚本化审批通过后才原子替换文件，并通过固定 argv 运行 Python `unittest` 或 Node `--test`。路径解析拒绝 `../` 越界，已存在的外部符号链接也不能作为工作区文件访问。

应用层测试再发送两轮消息：`ConversationApplication` 为每条用户消息分配新的 `task_id` 与 `run_id`，先持久化用户意图和执行身份，再调用 Run-scoped Agent；完成后把 Assistant Message 与终态回写同一个 Session。第二轮收到经过条数限制的历史 Context，但不会复用第一轮 `run_id`。

安装面到运行面的契约测试使用三个具体 Adapter：Skill Catalog 记录转换成带 Owner 的运行期 Skill；MCP Manager 的已启用 Connection 转换成 MCP Client，并保留 `call_tool`；Plugin Catalog 只通过 Host 预注册的可信 Factory 构造 Plugin，并按依赖拓扑排序。缺失 Factory、身份不匹配、循环依赖或已启用依赖缺失都会在 Runtime 启动前失败。

## 接入真实实现

| 端口 | 默认适配器 | 可替换实现 |
|------|------------|------------|
| `LLMAdapter` | `DeterministicLLMAdapter` | 任意模型 Provider Adapter |
| `MemoryBackend` | `InMemoryMemoryBackend` | SQL、文档数据库或向量数据库 |
| `CheckpointStore` | `JsonCheckpointStore` | SQL 或工作流状态存储 |
| `MCPClient` | `FakeMCPClient` | 官方 SDK 或自定义 Transport Client |
| `InstalledSkillProvider` | 未配置 | `examples/skills/` 的 Catalog Adapter |
| `MCPServerProvider` | 未配置 | `examples/mcp-manager/` 的 Manager Adapter |
| `InstalledPluginProvider` | 未配置 | `examples/plugin-manager/` 的 Catalog + Factory Adapter |
| `ApprovalGate` | `DenyApprovalGate` | CLI、Web、工单或策略审批 |
| `AgentRunner` | `ReviewSubagent` | 进程内或远程子 Agent |
| `EventBusPort` | 内存发布/订阅 | 持久化消息系统 |

## 安全与恢复契约（2026-10-26）

Python 与 TypeScript 均有对应回归用例：

| 边界 | 当前执行行为 |
|---|---|
| 临时文件 | Patch、Checkpoint、Session 均独占创建随机临时文件后替换，不写入可预建的 `<target>.tmp`；Patch 保留原文件权限 |
| 工具别名 | 解析为 canonical name 后授权；只有别名在 allowlist 中不会获得权限；原名或本次调用别名的 deny 均拒绝 |
| 能力升级 | 快照包含 Handler / prepare 代码摘要、实现版本、审批标记、Tool 状态和默认策略内容；缺失或不同快照均拒绝恢复 |
| 审批绑定 | 审批键绑定 Run、步骤、canonical name、快照、实际参数和重新计算的 preview；Coding preview 包含目标路径与原内容摘要或工作目录和命令 |
| 并行执行 | 每步保存结果，不等待整批成功才写入；异步 Checkpoint 写入按序提交；已完成兄弟步骤不因另一任务取消而丢失 |
| 未知结果 | 调用前保存 `executions` 标记。超时返回 `outcome_unknown=true`；恢复遇到未收尾标记或未知结果时返回 `reconciliation_required / unknown_side_effect`，禁止自动重放 |
| 参数校验 | Handler 和审批之前递归校验参数；错误 Schema 和不支持的关键字拒绝执行 |

Schema 是明确受限的教学子集：`type`（单类型）、`properties`、`required`、布尔 `additionalProperties`、`items`（单 Schema）、`enum`、`minimum/maximum`、`minLength/maxLength`、`minItems/maxItems`；`title/description/default` 仅作注释。空 Schema 不施加约束。`$ref`、组合 Schema、正则等不在支持范围，不会被静默忽略；接入完整 MCP Schema 时应替换为标准校验器。

Tool 的 `implementation_version` / `implementationVersion` 默认是 `"1"`。维护者必须在闭包配置、默认值、外部依赖、远端工具或 callable 对象行为变化时更新版本；本地函数代码摘要不是传递依赖摘要。自定义 Policy 同样必须在规则变化时更新 `version`。Python 与 TypeScript 快照仅用于各自运行环境，不能跨语言或任意运行时版本迁移。

`executions` 只是保守的本地派发标记，不是外部执行回执或 exactly-once 保证。超时仅停止等待，Python 线程或 Promise 仍可能继续执行；取消也不能证明工具已停止。应先核对执行器和下游状态，再由应用决定补录结果或创建新 Run，不能靠删除标记绕过。Host 提供 `reconcile(run_id, step_id, verify)` / `reconcile(runId, stepId, verify)`：可信 Adapter 查询下游并返回非空 `evidence` 和确定的 `result`。活跃本地调用尚未结束时拒绝对账；确认后补录结果与 Trace，不重置步骤、不自动重试。该入口不注册为模型 Tool，不提供下游查询实现或人工审批 UI。工具声明 `retryable=true` 意味着 Adapter 已确认该次失败可安全重试，不能用它掩盖未知副作用。

随机临时文件防止预建符号链接攻击，但没有消除恶意进程并发替换目录的竞态。工作区检查和固定 argv 不构成 OS 沙箱；工作区测试本身仍能运行任意代码。Python 检查超时时回收直接子进程，进程树隔离仍需生产 Adapter。

## 消息幂等、恢复与稳定回放

- 同一进程/事件循环内，同一 JSON 存储路径与 `run_id` 的调用串行执行；不同 Host 实例共享互斥。自定义 Store 使用对象身份，跨实例或跨进程共享存储必须在 Adapter 层实现原子认领/租约。
- `send(..., idempotency_key="client-message-1")`（TS 第三个参数）将客户端消息键绑定到 Session 内的原始内容、Task/Run 和结果。相同键与内容返回已保存结果；不同内容拒绝。未提供键仍表示新的消息。
- 用户意图、裁剪后的原始 Context 和执行身份先落盘。取消或异常回写 Task 状态；再次发送同一键不会静默重跑，调用方需 `resume(session_id, task_id)`（TS `resume(sessionId, taskId)`）。可用 `get_session/getSession` 找出待处理任务；未实现自动启动扫描和后台恢复服务。
- 同一 Session 串行，不同 Session 可以并发。`max_context_messages=0` / `maxContextMessages=0` 表示不传历史。
- Host 先保存 `finalizing`，生成答案后保存 `final_answer/finalAnswer` 与 `completed`，再执行 Memory/Hook/Event 交付。答案生成失败可恢复，已完成 Tool 不重复执行；已保存答案的回放不调用模型。旧完成快照没有答案时只补生成一次。
- `resume` 对已经完成的消息直接返回；其他状态继续原 Run。若已对账，Host 使用补录结果继续，Application 更新同一 Run 的 Assistant Message，不新增重复消息。

这些操作仍非一个跨存储事务。消息交付可靠性、跨进程锁、身份认证和下游幂等需生产 Adapter 实现；可信核对器必须验证原 Run、步骤、参数、远程请求身份及回执来源，不能只相信模型提供的字符串。

## 教学边界

“最终组装”表示能力闭环完整，不等于生产基础设施完整。JSON Session/Checkpoint 不支持多进程并发；内存检索不是语义向量检索；Fake MCP Client 不验证真实 Transport；安装型 Provider 仍需由 Host 适配；Plugin 在同一进程运行，没有签名和沙箱；审批没有外部 UI；Event Bus 不持久化。Coding 场景只演示精确文本替换和预注册测试，不是通用 Shell 或完整 Patch 解析器。生产环境还需要事务、幂等键、认证授权、OS/容器级资源隔离、迁移、数据保留和可观测后端。

## 生产接入验收边界（2026-10-26）

第 16 章新增真实 Provider / MCP 接入切片及崩溃窗口验收表。当前测试只验证本地确定性装配，不涵盖真实传输、持久化执行回执、跨进程租约、外部提交后的对账或设备操作。接入时先验证只读链路，再验证测试资源上的写入；分别记录 SDK / Server 版本、协议分支、模型、能力 Hash 和脱敏 Trace。副作用未知时禁止自动重试，取消后仍需等待底层执行器确认退出。

## 相关章节

- 第 7 章：Agent MVP
- 第 8～11 章：Memory、Runtime、Hooks、Tool Registry
- 第 12～14 章：Skills、MCP、Plugin
- 第 15～17 章：编排模式、最终组装与生产工程
