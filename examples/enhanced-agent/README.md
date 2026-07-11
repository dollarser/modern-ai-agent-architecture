# Enhanced Agent - 最终组装参考实现

这是第 16 章的完整可运行教学示例。它不复制第 8～15 章的生产级实现，而是把各章能力提炼为稳定端口，为每个端口提供离线最小适配器，并通过一个端到端场景证明这些组件能够真正组装。

## 已实现能力

- `MemoryBackend`：短期追加与读取、长期记忆、确定性检索，可替换 Backend
- `HookPipeline`：Run、Plan、Tool、Approval、Error、Finish 生命周期事件
- Guard Hook fail-closed；Observer Hook 错误隔离并写入 Trace
- `ToolRegistry + ToolRouter`：来源、来源名称、状态、标签、参数 Schema、审批标记
- `MCPToolAdapter`：发现 MCP Tool、转换 Schema、注册并代理调用
- `PluginLoader`：加载/卸载 Plugin，并注册/移除 Plugin Tool、Skill 和 Hook
- `ApprovalGate`：自动审批和脚本化审批；拒绝后不调用 Tool Handler
- `HandoffCoordinator + ReviewSubagent + EventBus`：受深度限制的最小编排闭环
- Skill 在规划前匹配并注入 Context；Memory 检索结果同时参与规划
- 依赖感知并行、结构化重试、Tool 超时、JSON Checkpoint 和诚实终止状态
- Python 与 TypeScript 对等实现和契约测试

默认实现完全离线，不需要 API Key，不访问网络，不读写业务文件，也不执行 Shell。真实 Provider、Memory Store、MCP Client、Approval UI 和远程 Event Bus 都可以通过构造函数替换，不需要修改 Runtime。

## 代码结构

```text
enhanced-agent/
├── python/
│   ├── assembly.py       # 端口、最小适配器、Runtime 与 Composition Root
│   ├── main.py           # 中断恢复演示入口
│   └── test_main.py      # 最终组装契约测试
└── typescript/
    ├── assembly.ts
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
npm install
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
→ Plugin Tool 汇总
→ Human Approval Gate
→ Plugin Tool 生成变更建议
→ Handoff 给 Review Subagent
→ Event Bus 发布父子任务事件
→ 组合结果并保存 Memory / Trace / Checkpoint
```

入口程序先中断再恢复。测试还验证 MCP/Plugin 来源、Tool 状态过滤、Plugin 卸载、审批拒绝不产生副作用、Guard/Observer 的不同失败策略、Handoff 事件、Memory 可替换、重试计数和失败不误报成功。

## 接入真实实现

| 端口 | 默认适配器 | 可替换实现 |
|------|------------|------------|
| `LLMAdapter` | `DeterministicLLMAdapter` | 任意模型 Provider Adapter |
| `MemoryBackend` | `InMemoryMemoryBackend` | SQL、文档数据库或向量数据库 |
| `MCPClient` | `FakeMCPClient` | 官方 SDK 或自定义 Transport Client |
| `ApprovalGate` | `AutoApproveGate` | CLI、Web、工单或策略审批 |
| `AgentRunner` | `ReviewSubagent` | 进程内或远程子 Agent |
| `EventBus` | 内存发布/订阅 | 持久化消息系统 |

## 教学边界

“最终组装”表示能力闭环完整，不等于生产基础设施完整。JSON Checkpoint 不支持多进程并发；内存检索不是语义向量检索；Fake MCP Client 不验证真实 Transport；Plugin 在同一进程运行，没有签名和沙箱；审批没有外部 UI；Event Bus 不持久化。生产环境还需要事务、幂等键、认证授权、资源隔离、迁移、数据保留和可观测后端。

## 相关章节

- 第 7 章：Agent MVP
- 第 8～11 章：Memory、Runtime、Hooks、Tool Registry
- 第 12～14 章：Skills、MCP、Plugin
- 第 15～17 章：编排模式、最终组装与生产工程
