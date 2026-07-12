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
- 依赖感知并行、结构化重试、Tool 超时、JSON Checkpoint 和诚实终止状态
- Python 与 TypeScript 对等实现和契约测试

默认实现完全离线，不需要 API Key，也不访问网络。数据库审查入口不读写业务文件；独立 `CodingAgent` 只在调用方显式指定的工作区内读写，并以固定参数启动预注册测试，不接受任意 Shell 字符串。真实 Provider、Memory Store、MCP Client、Approval UI 和远程 Event Bus 都可以通过构造函数替换，不需要修改 Runtime。

## 代码结构

```text
agent-host/
├── python/
│   ├── assembly.py       # 端口、最小适配器、Runtime 与通用 AgentHost
│   ├── application.py    # Session / Message / Task 与 AgentHost 的应用层衔接
│   ├── governance.py     # Policy Engine 与 Capability Snapshot 工具
│   ├── database_review_scenario.py # 数据库审查场景与 DatabaseReviewAgent
│   ├── coding_scenario.py # 受限编码场景与 CodingAgent
│   ├── installed_adapters.py # Skill/MCP/Plugin 安装面到运行面的 Adapter
│   ├── main.py           # 中断恢复演示入口
│   └── test_main.py      # 最终组装契约测试
└── typescript/
    ├── assembly.ts       # 双语言对等的通用 AgentHost
    ├── application.ts
    ├── governance.ts
    ├── database-review-scenario.ts
    ├── coding-scenario.ts
    ├── installed-adapters.ts
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

## 教学边界

“最终组装”表示能力闭环完整，不等于生产基础设施完整。JSON Session/Checkpoint 不支持多进程并发；内存检索不是语义向量检索；Fake MCP Client 不验证真实 Transport；安装型 Provider 仍需由 Host 适配；Plugin 在同一进程运行，没有签名和沙箱；审批没有外部 UI；Event Bus 不持久化。Coding 场景只演示精确文本替换和预注册测试，不是通用 Shell 或完整 Patch 解析器。生产环境还需要事务、幂等键、认证授权、OS/容器级资源隔离、迁移、数据保留和可观测后端。

## 相关章节

- 第 7 章：Agent MVP
- 第 8～11 章：Memory、Runtime、Hooks、Tool Registry
- 第 12～14 章：Skills、MCP、Plugin
- 第 15～17 章：编排模式、最终组装与生产工程
