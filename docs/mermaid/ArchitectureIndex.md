# 架构图索引

> 全书关键架构图的快速导航索引。

## 核心架构图

### Agent 整体架构

```
User → Prompt → Instructions → Agent → Tool Calling → MCP Tools
```

详见：[图 2-1] Agent 整体架构（第 2 章）

### Agent 主循环

```
Reasoning → Planning → Skills → Tool Calling → Observation → Reasoning ...
```

详见：[图 2-2] Agent 主循环（第 2 章）

### Agent 生命周期

```
Load → Read → Reasoning → Planning → Execute → Observe → Finish
```

详见：[图 2-3] Agent 生命周期状态机（第 2 章）

## 组件架构图

| 组件 | 架构图 | 章节 |
|------|--------|------|
| Prompt / Instructions | [图 3-1：Prompt 与 Instructions 的关系](../chapters/03-prompt-instructions/README.md) | 第 3 章 |
| Context | [图 4-1：Context 组成结构](../chapters/04-context-management/README.md) | 第 4 章 |
| Tools | [图 6-2：Tool 抽象层次](../chapters/06-tools-function-calling/README.md) | 第 6 章 |
| Skills | [图 12-1：Skill 的组成结构](../chapters/12-skills/README.md) | 第 12 章 |
| Hooks | [图 10-1：Hook 在生命周期中的位置](../chapters/10-hooks/README.md) | 第 10 章 |
| MCP | [图 13-1：MCP 架构](../chapters/13-mcp/README.md) | 第 13 章 |
| Plugin | [图 14-1：Plugin 的组成结构](../chapters/14-plugin-system/README.md) | 第 14 章 |
| Memory | [图 8-1：Memory 分级存储模型](../chapters/08-memory/README.md) | 第 8 章 |
| Runtime | [图 9-1：Runtime 的核心职责](../chapters/09-runtime/README.md) | 第 9 章 |
| Tool Registry | [图 11-1：Tool Registry 架构](../chapters/11-tool-registry/README.md) | 第 11 章 |

## 流程与交互图

| 流程 | 图表 | 章节 |
|------|------|------|
| Function Calling | [图 6-1] Function Calling 时序图 | 第 6 章 |
| Tool 调用决策 | [图 6-3] Tool 调用决策树 | 第 6 章 |
| ReAct 循环 | [图 5-1] ReAct 循环 | 第 5 章 |
| Plan-and-Execute | [图 5-2] Plan-and-Execute 流程 | 第 5 章 |
| Context 管理 | [图 4-2] Context Window 管理策略 | 第 4 章 |

---

> **维护说明：** 新增架构图时请更新此索引，保持与 Mermaid 图索引的交叉引用。
