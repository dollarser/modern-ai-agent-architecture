# 第 2 章：总体架构与生命周期

> **难度等级：** ⭐⭐⭐
> **所属模块：** 第一部分：基础认知
> **来源可信度：** 官方文档 / 源码 / 论文 / 推导 / 观点
> **状态：** ✅ 已完成

---

## 学习目标

完成本章学习后，你将能够：

1. 理解 AI Agent 的完整架构及各组件职责
2. 掌握 Agent 主循环的完整流程
3. 理解 Agent 生命周期的 7 个关键阶段
4. 理解各组件之间的交互时序
5. 建立从整体架构到具体组件的认知框架

---

## 前置知识

- 阅读第 1 章「AI Agent 简介与历史演进」
- 了解 Agent 核心概念的基本定义

---

## 1. 背景

### 1.1 为什么需要理解总体架构

在学习具体组件（Tools、Memory、Hooks 等）之前，必须先建立对 Agent 整体架构的认知。这就像在建造一座房子时，你需要先看建筑设计图，而不是直接从某个房间的装修开始。

理解总体架构可以帮助你回答以下问题：

- Agent 有哪些核心组件？它们之间的关系是什么？
- 一个用户请求如何从输入变成最终输出？
- 每个组件在什么时机被调用？承担什么职责？
- 如果要自己实现一个 Agent，需要设计哪些模块？

> **来源类型：** 推导分析 —— 基于对主流 Agent 框架（Claude Code、OpenAI Agents SDK、LangGraph）的共性架构归纳

### 1.2 架构设计的核心原则

现代 AI Agent 的架构设计遵循以下核心原则：

1. **关注点分离（Separation of Concerns）：** 推理、规划、执行、记忆各自独立
2. **可扩展性（Extensibility）：** 通过 Plugin、MCP 等机制动态扩展能力
3. **可观测性（Observability）：** 通过 Hooks 暴露生命周期事件
4. **可组合性（Composability）：** 组件可独立替换和组合

---

## 2. 核心概念

### 2.1 整体架构

现代 AI Agent 的架构由以下核心组件构成：

```mermaid
graph TD
    User[User<br/>用户] -->|输入| Prompt[Prompt<br/>任务目标]
    Prompt --> Agent[Agent Core<br/>Agent 核心]
    Instructions[Instructions<br/>全局规则] -->|约束| Agent
    Agent --> Reasoning[Reasoning<br/>推理引擎]
    Agent --> Planning[Planning<br/>规划器]
    Agent --> Memory[Memory<br/>记忆管理]
    Agent --> TC[Tool Calling<br/>工具调用]
    TC --> BT[Built-in Tools<br/>内置工具]
    TC --> MCP[MCP Tools<br/>协议工具]
    MCP --> MCP-S[MCP Server<br/>工具服务]
    TC -->|返回| OB[Observation<br/>观察结果]
    OB -->|反馈| Reasoning
    Agent --> Hooks[Hooks<br/>生命周期钩子]
    Agent --> Skills[Skills<br/>工作流模板]
```

> **图 2-1：** Agent 整体架构。核心组件包括 Reasoning、Planning、Memory、Tool Calling，以及支撑性的 Hooks 和 Skills。

### 2.2 组件职责总览

| 组件 | 职责 | 类比 |
|------|------|------|
| Prompt | 承载当前任务目标 | 用户说的话 |
| Instructions | 全局行为规则，始终在上下文 | 员工手册 |
| Reasoning | 基于上下文进行逻辑推理 | 大脑思考 |
| Planning | 将复杂任务分解为可执行步骤 | 制定计划 |
| Memory | 存储和检索历史信息 | 记忆 |
| Tool Calling | 调用外部工具执行操作 | 使用工具 |
| Skills | 可复用工作流模板 | 操作手册 |
| Hooks | 生命周期事件回调 | 监控告警 |
| MCP | 连接外部 Tool、Resource、Prompt 等能力的互操作协议 | 外部能力接口标准 |

> **来源类型：** 推导分析 —— 基于 Claude Code、OpenAI Agents SDK 等框架的组件设计

### 2.3 组件间的关系

各组件的核心关系可以概括为：

- **Prompt + Instructions → Agent 的输入约束**
- **Reasoning + Planning → Agent 的决策层**
- **Tool Calling + MCP → Agent 的执行层**
- **Memory → Agent 的状态层**
- **Hooks → Agent 的横切关注点**
- **Skills → Agent 的知识层**

### 2.4 Scaffolding、Harness、Runtime 与 Orchestration

这些术语经常被混用，但它们描述的是不同层次；也没有一套被所有框架共同采用的严格定义。本书使用下图和下表作为工程讨论中的工作定义。

```mermaid
graph TD
    Scaffold[Scaffolding<br/>Profile / Instructions / Policy<br/>Tool Schema / Output Contract] --> Harness[Harness<br/>执行循环与状态协调]
    Harness --> Model[Model<br/>生成、推理与结构化输出]
    Harness --> Runtime[Runtime Services<br/>并发、超时、持久化、Tracing]
    Harness --> Tools[Tools / MCP]
    Orchestrator[Orchestration<br/>任务分解、委派与汇总] --> Harness
    Orchestrator --> Subagents[Subagents<br/>独立上下文与预算]
```

> **图 2-5：** 从静态配置到单 Agent 执行，再到多 Agent 编排的职责边界。图中是工程抽象，不代表任一产品的内部实现。

| 术语 | 本书中的工作定义 | 不应误解为 |
|------|------------------|-------------|
| Model | 负责理解、生成与结构化输出的模型能力 | 单独完成权限、状态或工具执行的完整 Agent |
| Scaffolding | 影响行为的静态或缓慢变化的配置：Profile、Instructions、Policy、Tool Schema、输出契约等 | 每轮任务都动态产生的计划或上下文 |
| Harness | 驱动模型调用、工具循环、状态更新和终止条件的执行骨架 | 所有框架都公开存在同名模块 |
| Runtime | Harness 依赖的运行时服务，如并发、超时、持久化、资源管理和 Tracing | 仅等同于主循环 |
| Orchestration | 在多个 Agent 或工作流之间做分解、调度、汇总和故障处理 | 只要有多个 Prompt 就天然具备编排能力 |

`Profile` 和 `Policy` 更适合作为 Scaffolding 的组成部分：前者描述角色与职责，后者定义权限、人工确认和安全边界。简单单 Agent 可以把 Harness 与 Runtime 放在同一个类中；出现并发、恢复或子代理后，再拆分这些边界通常更容易维护。

> **来源类型：** 推导分析 —— 基于 Agent 工程中的常用术语和本书第 3、12、16、18 章的职责划分

### 2.5 Model Layer：能力、选择与可替换性

模型是 Agent 的推理与生成核心，但生产系统不应把“某个模型名称”当成架构。Harness 应面向能力约束来选择和调用模型，并通过 Provider 适配层隔离不同 API 的消息格式、Tool Calling、Token 统计和流式协议。

| 选择维度 | 需要问的问题 | 常见架构影响 |
|----------|--------------|--------------|
| 任务质量 | 是否需要复杂推理、代码理解、多模态或严格结构化输出？ | 决定默认模型、评估集和回退模型 |
| Tool 能力 | 是否可靠支持结构化 Tool 调用、并行调用或流式结果？ | 决定 Tool Schema 和执行循环的适配范围 |
| 上下文与知识 | 任务需要多长上下文，是否要先检索或压缩？ | 影响 Context Manager 与 RAG 策略 |
| 延迟与成本 | 哪些任务需要低延迟，哪些可用更高推理预算？ | 决定模型路由、缓存、预算与超时 |
| 数据与部署 | 数据能否离开边界，是否需要区域、本地或私有部署？ | 影响 Provider 选择、审计和降级方案 |

推荐为每个关键任务定义“可接受能力”而非绑定单一供应商：例如要求 JSON Schema 校验通过、首字延迟不超过目标、失败可切换到兼容模型。模型路由是优化手段，不应绕过 Guardrails、权限检查或统一评估。

> **来源类型：** 推导分析 —— 基于第 4、6、12、18、19 章的上下文、Tool、运行时、成本和评估要求

---

## 3. Agent 主循环

### 3.1 主循环流程

Agent 的主循环（Agent Loop）是 Agent 运行的核心机制：

```mermaid
flowchart TD
    Start([开始]) --> Prompt[接收 Prompt]
    Prompt --> Read[读取 Instructions]
    Read --> Reason[Reasoning<br/>推理分析]
    Reason --> Plan[Planning<br/>制定计划]
    Plan --> CheckSkill{需要<br/>Skill?}
    CheckSkill -->|是| LoadSkill[加载 Skill]
    LoadSkill --> CallTool
    CheckSkill -->|否| CallTool[Tool Calling<br/>调用工具]
    CallTool --> Observe[Observation<br/>观察结果]
    Observe --> Decide{任务<br/>完成?}
    Decide -->|否| Reason
    Decide -->|是| Finish([完成])
```

> **图 2-2：** Agent 主循环。从 Prompt 到 Reasoning → Planning → Tool Calling → Observation 的循环，直到任务完成。

### 3.2 主循环各阶段详解

**阶段 1：接收 Prompt**

用户输入 Prompt，Agent 开始处理。Prompt 是当前任务的描述，可能包含具体指令、上下文信息或预期输出格式。

**阶段 2：读取 Instructions**

Agent 读取全局 Instructions（System Prompt 的一部分）。Instructions 定义 Agent 的行为准则，如「始终使用中文回复」「不要编造信息」「遇到不确定的情况请询问用户」。

**阶段 3：Reasoning（推理）**

Agent 基于当前上下文（Prompt + Instructions + 历史对话 + Memory）进行推理。推理的目标是分析任务需求、确定需要哪些信息、判断是否需要调用工具。

**阶段 4：Planning（规划）**

如果任务较为复杂，Agent 需要制定执行计划。规划可以是：
- 隐式规划（模型内部推理）
- 显式规划（输出结构化的步骤列表）
- 动态规划（根据执行结果调整计划）

**阶段 5：Skill 匹配（可选）**

Agent 检查是否有匹配的 Skill 可以指导当前任务。Skill 提供工作流模板，告诉 Agent 如何处理特定类型的任务。注意：Skill 是读取，不是调用——Agent 将 Skill 内容加载到上下文中作为参考。

**阶段 6：Tool Calling（工具调用）**

Agent 调用 Tool 执行具体操作。Tool 可以是：
- Built-in Tool：框架内置工具（如文件读写、搜索）
- MCP Tool：通过 MCP 协议发现的第三方工具

**阶段 7：Observation（观察）**

Agent 接收 Tool 的执行结果。Observation 是下一轮 Reasoning 的输入，Agent 基于结果判断任务是否完成，或是否需要调整策略。

**阶段 8：循环判断**

Agent 判断任务是否完成。如果完成，输出最终结果；如果未完成，回到 Reasoning 阶段，基于新的 Observation 继续推理。

> **来源类型：** 推导分析 —— 基于 ReAct 论文 (Yao et al., 2022) 和 Claude Code 的实际执行流程

### 3.3 主循环的终止条件

Agent 主循环不会无限进行。终止条件包括：

1. **任务完成：** Agent 判断任务已完成
2. **最大步数：** 达到预设的最大循环次数
3. **超时：** 执行时间超过限制
4. **用户中断：** 用户主动停止
5. **错误终止：** 遇到不可恢复的错误

---

## 4. 生命周期

### 4.1 生命周期状态机

Agent 的生命周期可以用以下状态机描述：

```mermaid
stateDiagram-v2
    [*] --> Load: 初始化
    Load --> Read: 加载 Instructions
    Read --> Reasoning: 接收 Prompt
    Reasoning --> Planning: 推理完成
    Planning --> Execute: 规划完成
    Execute --> Observe: Tool 执行完毕
    Observe --> Reasoning: 任务未完成
    Observe --> Finish: 任务完成
    Finish --> [*]

    state Load {
        [*] --> LoadInstructions
        LoadInstructions --> LoadSkills
        LoadSkills --> InitMemory
        InitMemory --> [*]
    }

    state Execute {
        [*] --> SelectTool
        SelectTool --> CallTool
        CallTool --> GetResult
        GetResult --> [*]
    }
```

> **图 2-3：** Agent 生命周期状态机。7 个阶段：Load → Read → Reasoning → Planning → Execute → Observe → Finish。

### 4.2 生命周期各阶段详解

#### 阶段 1：Load（加载）

Agent 启动时加载必要的资源：

- Instructions（全局规则）
- Skills 索引（可用工作流模板列表）
- Memory 数据（如果有持久化记忆）
- Tool Registry（注册可用工具）

> **来源类型：** 推导分析 —— 基于 Claude Code 的初始化流程

#### 阶段 2：Read（读取）

Agent 读取当前上下文：

- 用户 Prompt
- Instructions（始终在上下文）
- 历史对话（如果有）
- 加载的 Skill 内容（如果有匹配的 Skill）

#### 阶段 3：Reasoning（推理）

Agent 基于完整上下文进行推理：

- 分析任务需求和约束
- 确定需要的信息和工具
- 评估当前状态和下一步方向

#### 阶段 4：Planning（规划）

Agent 制定执行计划：

- 将复杂任务分解为子任务
- 确定每个子任务需要的工具
- 设定执行顺序和依赖关系

#### 阶段 5：Execute（执行）

Agent 调用工具执行操作：

- 选择最合适的 Tool
- 构造 Tool 调用参数
- 执行 Tool 调用
- 处理执行错误

#### 阶段 6：Observe（观察）

Agent 处理 Tool 执行结果：

- 解析执行结果
- 评估结果质量
- 更新 Memory 和上下文
- 判断是否需要重试或调整

#### 阶段 7：Finish（完成）

Agent 完成所有任务：

- 输出最终结果
- 更新 Memory（持久化）
- 触发完成 Hook
- 释放资源

---

## 5. 组件交互时序

### 5.1 完整交互时序

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Instructions
    participant Planner
    participant Skills
    participant ToolRegistry
    participant Tool
    participant Memory
    participant Hooks

    User->>Agent: Prompt
    Agent->>Hooks: BeforeLoad
    Agent->>Instructions: 读取全局规则
    Instructions-->>Agent: 规则内容
    Agent->>Memory: 读取历史记忆
    Memory-->>Agent: 记忆上下文
    Agent->>Hooks: AfterLoad

    Agent->>Hooks: BeforeReasoning
    Agent->>Agent: Reasoning（推理）
    Agent->>Hooks: AfterReasoning

    Agent->>Hooks: BeforePlanning
    Agent->>Planner: 规划任务
    Planner-->>Agent: 执行计划
    Agent->>Hooks: AfterPlanning

    Agent->>Skills: 检查匹配 Skill
    Skills-->>Agent: Skill 内容（如有）

    Agent->>Hooks: BeforeToolCall
    Agent->>ToolRegistry: 查找 Tool
    ToolRegistry-->>Agent: Tool 描述
    Agent->>Tool: 调用 Tool
    Tool-->>Agent: 执行结果
    Agent->>Hooks: AfterToolCall

    Agent->>Hooks: BeforeObservation
    Agent->>Agent: 观察结果
    Agent->>Memory: 更新记忆
    Agent->>Hooks: AfterObservation

    Agent->>Agent: 判断是否完成

    alt 任务未完成
        Agent->>Agent: 下一轮 Reasoning
    else 任务完成
        Agent->>Hooks: BeforeFinish
        Agent->>User: 最终结果
        Agent->>Memory: 持久化记忆
        Agent->>Hooks: AfterFinish
    end
```

> **图 2-4：** 组件交互时序图。展示从 Prompt 到 Finish 的完整交互顺序，以及 Hooks 在生命周期中的拦截点。

---

## 6. 最小可运行示例

### 6.1 Agent 主循环实现

以下代码展示了 Agent 主循环的完整实现：

```python
"""
Agent 主循环完整实现
运行环境：Python 3.10+
依赖：无
预期输出：Agent 完整执行一次推理-规划-执行-观察循环
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional


class AgentState(Enum):
    """Agent 生命周期状态"""
    LOAD = auto()
    READ = auto()
    REASONING = auto()
    PLANNING = auto()
    EXECUTE = auto()
    OBSERVE = auto()
    FINISH = auto()


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_steps: int = 10
    timeout_seconds: int = 30
    instructions: str = ""


@dataclass
class AgentMemory:
    """Agent 记忆"""
    messages: list[str] = field(default_factory=list)
    tool_results: list[str] = field(default_factory=list)

    def add_message(self, msg: str):
        self.messages.append(msg)

    def add_result(self, result: str):
        self.tool_results.append(result)


class AgentRuntime:
    """Agent 运行时 - 完整主循环实现"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = AgentState.LOAD
        self.memory = AgentMemory()
        self.tools: dict[str, Tool] = {}
        self.hooks: dict[str, list[Callable]] = {
            "before_reasoning": [],
            "after_reasoning": [],
            "before_tool_call": [],
            "after_tool_call": [],
            "before_finish": [],
        }
        self.step_count = 0

    # ── Hook 系统 ──────────────────────────────

    def register_hook(self, event: str, callback: Callable):
        """注册生命周期钩子"""
        if event in self.hooks:
            self.hooks[event].append(callback)

    def _trigger_hooks(self, event: str, *args):
        """触发钩子"""
        for hook in self.hooks.get(event, []):
            hook(*args)

    # ── Tool 管理 ──────────────────────────────

    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool

    # ── 生命周期阶段 ──────────────────────────

    def _load(self):
        """Load 阶段：加载资源"""
        self.state = AgentState.LOAD
        self.memory.add_message(f"[Load] Agent 启动，指令: {self.config.instructions[:50]}...")

    def _read(self, prompt: str):
        """Read 阶段：读取上下文"""
        self.state = AgentState.READ
        self.memory.add_message(f"[Read] 接收 Prompt: {prompt}")

    def _reasoning(self, prompt: str) -> str:
        """Reasoning 阶段：推理分析"""
        self.state = AgentState.REASONING
        self._trigger_hooks("before_reasoning", prompt)

        # 简化的推理逻辑：分析任务类型
        if "搜索" in prompt or "查询" in prompt:
            thought = "需要调用搜索工具获取信息"
        elif "计算" in prompt:
            thought = "需要调用计算工具"
        else:
            thought = f"分析任务: {prompt}，确定执行策略"

        self.memory.add_message(f"[Reasoning] {thought}")
        self._trigger_hooks("after_reasoning", thought)
        return thought

    def _planning(self, thought: str) -> list[str]:
        """Planning 阶段：制定计划"""
        self.state = AgentState.PLANNING

        # 简化的规划逻辑
        steps = [
            "Step 1: 确定所需工具",
            "Step 2: 调用工具执行",
            "Step 3: 检查执行结果",
            "Step 4: 评估任务完成度",
        ]
        self.memory.add_message(f"[Planning] 制定 {len(steps)} 步执行计划")
        return steps

    def _execute(self, step: str) -> str:
        """Execute 阶段：执行操作"""
        self.state = AgentState.EXECUTE
        self._trigger_hooks("before_tool_call", step)

        # 模拟工具调用
        result = f"执行完成: {step}"

        self._trigger_hooks("after_tool_call", step, result)
        return result

    def _observe(self, result: str) -> bool:
        """Observe 阶段：观察结果，返回是否完成"""
        self.state = AgentState.OBSERVE
        self.memory.add_result(result)

        # 简化判断：如果执行了所有步骤则完成
        self.step_count += 1
        return self.step_count >= self.config.max_steps

    def _finish(self) -> str:
        """Finish 阶段：输出结果"""
        self.state = AgentState.FINISH
        self._trigger_hooks("before_finish")

        summary = "\n".join(self.memory.messages + self.memory.tool_results)
        return f"任务完成。\n执行摘要:\n{summary}"

    # ── 主循环 ──────────────────────────────

    def run(self, prompt: str) -> str:
        """Agent 主循环"""
        self._load()
        self._read(prompt)

        while self.step_count < self.config.max_steps:
            # Reasoning
            thought = self._reasoning(prompt)

            # Planning
            plan = self._planning(thought)

            # Execute + Observe
            for step in plan:
                result = self._execute(step)
                task_complete = self._observe(result)

                if task_complete:
                    return self._finish()

        return self._finish()


if __name__ == "__main__":
    # 创建 Agent 配置
    config = AgentConfig(
        max_steps=5,
        instructions="你是一个友好的助手，始终使用中文回复。"
    )

    # 创建 Agent
    agent = AgentRuntime(config)

    # 注册一个日志 Hook
    agent.register_hook(
        "before_tool_call",
        lambda step: print(f"[Hook] 即将执行: {step}")
    )
    agent.register_hook(
        "after_tool_call",
        lambda step, result: print(f"[Hook] 执行完成: {step}")
    )

    # 注册一个工具
    agent.register_tool(Tool(
        name="search",
        description="搜索信息",
        func=lambda q: f"搜索结果: {q}"
    ))

    # 运行 Agent
    result = agent.run("搜索今天的天气")
    print("=" * 50)
    print(result)
    print("=" * 50)
    print(f"最终状态: {agent.state}")
    print(f"执行步数: {agent.step_count}")
```

**预期输出：**

```
[Hook] 即将执行: Step 1: 确定所需工具
[Hook] 执行完成: Step 1: 确定所需工具
[Hook] 即将执行: Step 2: 调用工具执行
[Hook] 执行完成: Step 2: 调用工具执行
[Hook] 即将执行: Step 3: 检查执行结果
[Hook] 执行完成: Step 3: 检查执行结果
[Hook] 即将执行: Step 4: 评估任务完成度
[Hook] 执行完成: Step 4: 评估任务完成度
[Hook] 即将执行: Step 1: 确定所需工具
[Hook] 执行完成: Step 1: 确定所需工具
==================================================
任务完成。
执行摘要:
[Load] Agent 启动，指令: 你是一个友好的助手，始终使用中文回复。...
[Read] 接收 Prompt: 搜索今天的天气
[Reasoning] 需要调用搜索工具获取信息
[Planning] 制定 4 步执行计划
执行完成: Step 1: 确定所需工具
执行完成: Step 2: 调用工具执行
执行完成: Step 3: 检查执行结果
执行完成: Step 4: 评估任务完成度
[Reasoning] 需要调用搜索工具获取信息
[Planning] 制定 4 步执行计划
执行完成: Step 1: 确定所需工具
==================================================
最终状态: AgentState.FINISH
执行步数: 5
```

> **运行方式：** 本章代码为架构演示的简化实现，完整可运行版本见 `examples/hello-agent/python/main.py`

---

## 7. 最佳实践

1. **先理解架构，再深入细节：** 在阅读后续章节之前，确保对整体架构有清晰认知。每学一个新组件，都在整体架构图中定位它的位置。
2. **关注生命周期：** 理解每个组件在生命周期中的激活时机。这有助于理解组件之间的依赖关系和交互顺序。
3. **使用 Hooks 做可观测性：** 在 Agent 开发中，通过 Hooks 记录关键生命周期事件，便于调试和监控。
4. **控制循环深度：** 始终设置最大步数和超时时间，防止 Agent 陷入无限循环。
5. **保持组件职责单一：** 每个组件只做一件事。不要让 Planning 组件直接操作 Memory，不要让 Hooks 包含业务逻辑。

---

## 8. 反模式

| 反模式 | 风险 | 推荐方案 |
|--------|------|---------|
| 单体 Agent 设计 | 所有逻辑耦合在一起，难以维护和测试 | 遵循关注点分离，组件化设计 |
| 无限制循环 | Agent 无限执行，消耗资源 | 设置最大步数、超时、Token 预算 |
| 跳过 Planning 阶段 | 复杂任务执行效率低，容易出错 | 为复杂任务显式规划步骤 |
| 忽略 Observation | 不评估 Tool 执行结果，盲目继续 | 每次 Tool 调用后必须评估结果 |
| Hooks 承担业务逻辑 | 耦合严重，难以调试 | Hooks 只做横切关注点（日志、监控、权限） |

---

## 9. FAQ

### Q: Agent 主循环和 ReAct 循环是什么关系？

Agent 主循环（Reasoning → Planning → Tool Calling → Observation）是 ReAct 循环（Thought → Action → Observation）的工程化扩展。ReAct 提供了基础范式，Agent 主循环在此基础上增加了 Planning（显式规划）、Skills（工作流模板）、Hooks（生命周期管理）等工程化组件。

### Q: 为什么需要显式的 Planning 阶段？

对于简单任务，模型可以隐式规划（在推理中完成）。但对于复杂多步骤任务，显式规划可以：
- 提高执行效率（避免反复试错）
- 提高可解释性（用户可以看到执行计划）
- 便于错误恢复（某步失败时从失败步骤重试）

### Q: Agent 生命周期和 Web 请求生命周期有什么相似之处？

两者都遵循「请求 → 处理 → 响应」的模式，但 Agent 生命周期是循环的（处理可能多次迭代），而 Web 请求通常是线性的。Agent 的 Hooks 类似于 Web 框架的 Middleware，都是在关键节点提供拦截能力。

### Q: 如何判断 Agent 是否「完成任务」？

这是一个开放问题。常见策略包括：
- 模型自主判断（通过特定的 finish reason）
- 达到最大步数上限
- 连续 N 轮没有新的 Tool 调用
- 用户定义的完成条件（如特定 Tool 返回成功标记）

---

## 10. 官方参考

| 编号 | 来源 | 类型 | 说明 |
|------|------|------|------|
| REF-1 | [ReAct Paper](https://arxiv.org/abs/2210.03629) (Yao et al., 2022) | 论文 | Agent 循环的基础范式 |
| REF-2 | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | 源码 | Agent Runtime 的参考实现 |
| REF-3 | [Anthropic Claude Code Architecture](https://docs.anthropic.com/en/docs/claude-code) | 官方文档 | Claude Code 的架构设计 |
| REF-4 | [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) | 官方文档 | 图状态机在 Agent 中的应用 |

---

## 11. 延伸阅读

- [Agent Design Patterns](https://arxiv.org/abs/2401.03568) —— Agent 设计模式综述
- [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) —— Anthropic 的 Agent 构建指南
- [OpenAI Agents SDK Lifecycle](https://openai.github.io/openai-agents-python/) —— Agent 生命周期的参考实现

---

## 本章小结

总体架构的核心是职责分离：Prompt 表达任务，Instructions 约束行为，Planner 组织步骤，Tool 执行动作，Memory 保存状态，Runtime 协调整个生命周期。组件是否需要独立，取决于替换、测试、恢复和治理需求，而不是架构图是否足够复杂。

---

## 本章 Checklist

- [ ] 能画出 Agent 整体架构图
- [ ] 理解 7 个组件的职责和关系
- [ ] 能描述 Agent 主循环的 8 个阶段
- [ ] 理解生命周期的 7 个状态及转换条件
- [ ] 能画出组件交互时序图
- [ ] 运行了 Agent 主循环示例代码
- [ ] 理解 Hooks 在生命周期中的位置
- [ ] 知道如何设置循环终止条件
