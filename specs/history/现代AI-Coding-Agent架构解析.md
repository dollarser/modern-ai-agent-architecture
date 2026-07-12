# 现代 AI Coding Agent 架构解析

> 本文从 Agent 的运行流程出发，解释
> Prompt、Instructions、Skills、Tools、MCP、Hooks 等概念及其关系。

## 1. 整体架构

``` text
User
 │
Prompt
 │
Instructions
 │
Agent
 ├── Reasoning
 ├── Planning
 ├── Memory
 └── Tool Calling
      ├── Built-in Tools
      └── MCP Tools
           │
      Observation
           │
         Hooks
           │
      下一轮 Reasoning
```

## 2. Agent 主循环

``` text
Prompt
 ↓
Reasoning
 ↓
Planning
 ↓
(按需读取 Skills)
 ↓
Tool Calling
 ↓
Observation
 ↓
Reasoning ...
```

其中： - Prompt：告诉 Agent 做什么。 - Instructions：告诉 Agent
如何做。 - Skills：提供推荐工作流。 - Tool：真正执行动作。 -
MCP：提供额外 Tool。 - Hook：监听生命周期事件。

------------------------------------------------------------------------

# Prompt

**定义**

一次任务的目标。

**读取时机**

任务开始时。

**调用时机**

不会被调用，只会被读取。

**最小示例**

``` text
帮我修复 login bug
```

------------------------------------------------------------------------

# Instructions

**定义**

长期有效的规则。

**读取时机**

Session 初始化，并始终放入上下文。

**示例**

``` text
Always write tests.
不要修改 generated 文件。
```

------------------------------------------------------------------------

# Skills

**定义**

可复用的工作流，而不是执行能力。

**作用**

影响 Reasoning 和 Planning。

**什么时候读取**

当 Agent 判断当前任务匹配某个 Skill 时。

**什么时候调用**

不会真正调用，只会读取内容作为推理参考。

**最小示例**

``` text
Review PR Skill

1. git diff
2. 查看测试
3. 总结风险
```

------------------------------------------------------------------------

# Tools

**定义**

模型能够调用的执行接口。

**什么时候调用**

Planning 完成后。

**最小示例**

``` python
read_file("README.md")
```

------------------------------------------------------------------------

# Built-in Tools

Agent 自带能力，例如：

-   read_file
-   write_file
-   terminal
-   search_code

无需安装。

------------------------------------------------------------------------

# MCP

**定义**

一种开放协议，用于向 Agent 动态提供 Tool。

MCP 本身不是 Tool。

例如 GitHub MCP 提供：

-   create_issue
-   merge_pr
-   list_pr

------------------------------------------------------------------------

# Hooks

生命周期事件。

例如：

``` text
Before Tool
After Tool
Before Write
After Write
```

最小示例：

``` text
Before Write
    ↓
clang-format
    ↓
write_file
```

------------------------------------------------------------------------

# Tool 与 Function Calling

Tool 是能力。

Function Calling 是一次调用 Tool 的协议。

``` text
Tool:
read_file()

↓

Function Call(JSON)

↓

Runtime

↓

真正执行
```

------------------------------------------------------------------------

# Built-in Tool 与 MCP Tool

  Built-in             MCP
  -------------------- ------------------
  IDE 自带             MCP Server 提供
  无需安装             动态扩展
  LLM 看起来没有区别   Runtime 知道来源

------------------------------------------------------------------------

# Agent 一次完整执行流程

用户：

``` text
修复登录 Bug
```

执行：

``` text
Prompt
 ↓
Instructions
 ↓
Reasoning
 ↓
Planning
 ↓
发现 Debug Skill
 ↓
读取 Skill
 ↓
read_file()
 ↓
grep()
 ↓
write_file()
 ↓
pytest()
 ↓
Hook
 ↓
完成
```

------------------------------------------------------------------------

# 常见混淆

## Prompt vs Instructions

Prompt 是任务。

Instructions 是规则。

## Skill vs Tool

Skill 告诉 Agent 怎么做。

Tool 真正去做。

## Tool vs MCP

Tool 是能力。

MCP 是提供 Tool 的协议。

## Tool vs Function Calling

Tool 是能力。

Function Calling 是调用方式。

------------------------------------------------------------------------

# 为什么 Agent 主流程没有 Skill Calling 和 MCP Calling？

Skill 不执行，只参与推理。

MCP 不提供推理能力，只负责提供 Tool。

因此：

``` text
Reasoning
 ↓
Planning
 ↓
Tool Calling
```

是统一抽象。

------------------------------------------------------------------------

# 最小 Agent MVP

``` text
agent/
├── prompt.py
├── instructions.py
├── planner.py
├── memory.py
├── skill_loader.py
├── tool_registry.py
├── tools/
├── mcp/
├── hooks/
└── runtime.py
```

执行流程：

``` text
Prompt
 ↓
Instructions
 ↓
Planner
 ↓
Skill Loader
 ↓
Tool Registry
 ↓
Built-in / MCP Tool
 ↓
Observation
 ↓
Hook
 ↓
Finish
```

------------------------------------------------------------------------

# 总结

  概念            本质
  --------------- ----------------------
  Prompt          当前任务
  Instructions    全局规则
  Skills          工作流模板
  Tools           执行动作
  Built-in Tool   内置 Tool
  MCP             提供 Tool 的协议
  Hooks           生命周期事件
  Agent           推理、规划、调度中心
