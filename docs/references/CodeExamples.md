# 代码示例索引

> 全书所有可运行代码示例的索引，按章节和示例工程组织。

## 示例工程

| 工程 | 路径 | 覆盖概念 | 语言 | 相关章节 |
|------|------|---------|------|---------|
| Hello Agent | `examples/hello-agent/` | 最小 Agent Loop | Python, TypeScript | 第1, 2章 |
| Tool Calling | `examples/tool-calling/` | Function Calling, Tool 抽象 | Python, TypeScript | 第6章 |
| Memory | `examples/memory/` | Memory 读写, 上下文窗口 | Python, TypeScript | 第 8 章 |
| Runtime | `examples/runtime/` | 终态、步数耗尽、单步超时与协作式取消 | Python, TypeScript | 第 9 章 |
| Planning | `examples/planning/` | Plan-and-Execute | Python, TypeScript | 第5章 |
| Hooks | `examples/hooks/` | Before/After Hook | Python, TypeScript | 第 10 章 |
| MCP Client | `examples/mcp-client/` | MCP 协议, Tool 发现 | Python, TypeScript | 第 13 章 |
| MCP Server | `examples/mcp-server/` | Tool 暴露, 协议实现 | Python, TypeScript | 第 13 章 |
| Tool Registry | `examples/tool-registry/` | 动态注册, 路由 | Python, TypeScript | 第 11 章 |
| Agent MVP Minimal | `examples/agent-mvp-minimal/` | 任务、规则规划、内置 Tool、观察与终止条件 | Python, TypeScript | 第5--7章 |
| Coding Agent 组合预览 | `examples/coding-agent-mvp/` | 轻量 Memory、Tool 映射与回调的补充演示（非最终架构） | Python, TypeScript | 第 8--11、15--16 章 |
| Enhanced Agent | `examples/enhanced-agent/` | 可插拔 Memory/Hook/Tool 端口，以及 Skills、MCP、Plugin、Approval、Handoff/Subagent、Event Bus 的最终组装 | Python, TypeScript | 第 16 章 |

## 运行方式

### Python 示例

```bash
cd examples/<example-name>/python
# 仅当当前示例目录包含 requirements.txt 时执行
pip install -r requirements.txt
python main.py
```

`agent-mvp-minimal`、`enhanced-agent` 与 `tool-calling` 仅依赖 Python 标准库，可直接执行 `python main.py`。

### TypeScript 示例

```bash
cd examples/<example-name>/typescript
npm install
npm run start
```

## 示例规范

每个示例包含独立 README.md，说明：

- 学习目标
- 前置知识
- 运行方式
- 预期输出
- 相关章节

---

> **维护说明：** 新增示例时请更新此索引，保持路径和描述的准确性。
