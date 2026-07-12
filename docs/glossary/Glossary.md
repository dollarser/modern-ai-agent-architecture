# 术语表（Glossary）

> 本书统一术语的中英文对照及定义。首次出现的术语标注英文原文，全书保持一致。

## A

| 术语 | 英文 | 定义 |
|------|------|------|
| Agent | Agent | 在 Host 内接收目标、基于上下文决策并请求执行能力的运行主体；自主性受 Policy、预算和 Runtime 约束 |
| Agent Run | Agent Run | Agent 对某个 Task 的一次有独立 ID、预算、状态和终态的执行尝试；重试通常创建新 Run |
| Agent Host | Agent Host | 运行 Agent 的应用宿主，提供 Runtime、Policy、Registry、Checkpoint、Sandbox 与扩展生命周期；本身不是 Agent |
| A2A | Agent-to-Agent | 面向跨系统 Agent 协作的互操作协议类别；与应用内 Handoff 和 MCP 的职责不同 |
| Agent Loop | Agent Loop | Agent 的主循环：Reasoning → Planning → Tool Calling → Observation → Reasoning ... |
| Agent Runtime | Agent Runtime | 管理 Agent 生命周期、调度 Tool 调用、协调各组件的运行环境 |
| Agentic Workflow | Agentic Workflow | 在确定性 Workflow 边界内嵌入有限 Agent 决策节点的混合架构 |
| Agentic Engineering | Agentic Engineering | 将 Prompt、Context、Tool、Workflow、Harness、Loop 与评估、安全、运维组合为生产 Agent 系统的工程总框架；不是单个组件 |
| ACP | Agent Client Protocol | 标准化编辑器/客户端与 Coding Agent 进程交互的开放协议；本书使用该特定含义，避免与其他同名缩写混用 |
| App | App | 面向用户展示、授权和使用某个产品集成的产品表面；本书将其与 Host 内部 Connector 区分 |
| Approval | Approval | 对 Policy `ask` 决定进行交互、持久化和恢复的机制；不等于身份认证或通用授权 |
| Artifact | Artifact | Tool 或任务产生的大型、可持久化结果；Context 通常只保存其摘要、引用和校验信息 |
| Authentication | Authentication | 验证主体身份的过程，回答“是谁” |
| Authorization | Authorization | 判断已认证主体能否访问具体资源或执行动作的过程 |

## B

| 术语 | 英文 | 定义 |
|------|------|------|
| Built-in Tool | Built-in Tool | Agent 框架内置的工具，无需额外安装，直接调用 |

## C

| 术语 | 英文 | 定义 |
|------|------|------|
| Context | Context | 模型当前可用的信息窗口，包含 Prompt、Instructions、历史对话、Tool 结果等 |
| Context Engineering | Context Engineering | 设计模型当前可见信息的来源、权限、选择、排序、预算、表达、安全、生命周期与评估 |
| Context Window | Context Window | 模型一次能处理的最大 token 数量 |
| Connector | Connector | 面向具体产品或服务的集成单元，管理服务身份、凭据引用、授权范围、端点、数据映射和健康状态；可基于 MCP、API 或 SDK 实现 |
| Chain-of-Thought (CoT) | Chain-of-Thought | 通过逐步推理（"让我们一步步思考"）提高复杂问题准确性的 Prompting 技术 |
| Checkpoint | Checkpoint | Agent 运行状态的快照，用于故障恢复和状态回滚 |
| Circuit Breaker | Circuit Breaker | 当某个操作失败率超过阈值时自动熔断，防止级联故障的保护机制 |
| CLI | Command-Line Interface | 命令行交互入口，通常通过参数、退出码和帮助信息提供可脚本化、自文档化的操作方式 |
| Capability | Capability | Host 可向运行主体提供的能力；本书主要包括可调用的 Tool 与可加载的 Skill |
| Catalog | Catalog | 保存已安装对象的版本、来源、完整性与启用状态的安装期索引 |
| Conversation | Conversation | Session 中面向用户或参与者的消息序列，不等于完整 Runtime 状态 |
| Credential | Credential | 用于证明身份的 Token、证书或 Secret；应以引用方式管理并限制 Scope 与生命周期 |

## D

| 术语 | 英文 | 定义 |
|------|------|------|
| 分发单元 | Distribution Unit | 用于安装、版本化、启停和分发一组扩展的边界；本书主要对应 Plugin |
| Delegation Grant | Delegation Grant | 上游主体授予子 Run 的有限、可过期权限；只能收窄资源、Tool 和凭据范围 |

## E

| 术语 | 英文 | 定义 |
|------|------|------|
| Event Bus | Event Bus | 事件驱动的组件通信机制，组件通过发布/订阅事件进行解耦通信 |
| Elicitation | Elicitation | MCP Client 可选能力之一，允许 Server 通过 Host 向用户请求额外信息 |
| Expert Profile | Expert Profile | 配置 Agent 或 Subagent 专业角色的 Profile，包含领域指令、Skill、Tool 权限、预算和评估标准；不是独立的委派关系 |

## F

| 术语 | 英文 | 定义 |
|------|------|------|
| Function Calling | Function Calling | 模型输出结构化函数调用请求的能力，是 Tool Calling 的实现机制之一 |

## G

| 术语 | 英文 | 定义 |
|------|------|------|
| Guardrails | Guardrails | 分布在输入、模型输出、Tool 调用和最终输出边界的可执行安全与合规控制 |

## H

| 术语 | 英文 | 定义 |
|------|------|------|
| Hook | Hook | 在 Agent 生命周期的特定事件前后触发的回调机制 |
| Hook Pipeline | Hook Pipeline | 多个 Hook 按优先级顺序在生命周期节点上依次执行的管道模式 |
| Handoff | Handoff | Agent 间任务委托模式，一个 Agent 将任务显式转移给另一个更合适的 Agent |
| Harness | Harness | 驱动模型交互、工具循环、状态更新和终止条件的执行骨架；并非所有框架都公开使用这一名称 |
| Harness Engineering | Harness Engineering | 设计 Agent 单次 Run 的 Context、工具、工作区、权限、沙箱、反馈、恢复与资源边界的工程实践；不等于 Agent Host 组件 |

## I

| 术语 | 英文 | 定义 |
|------|------|------|
| Instructions | Instructions | 约束 Agent 行为的规则；由 Host 按任务和会话组装、版本化并注入 Context，通常比单次 Prompt 更稳定，但不必在每轮完整加载 |
| Idempotency Key | Idempotency Key | 下游用于识别和去重一次副作用意图的键；不等于 Task、Run 或 Session ID |

## K

| 术语 | 英文 | 定义 |
|------|------|------|
| Knowledge System | Knowledge System | 受控的外部知识源及其索引、检索、权限、版本和引用机制；与 Agent Memory 的生命周期不同 |

## L

| 术语 | 英文 | 定义 |
|------|------|------|
| LLM | Large Language Model | 大语言模型，Agent 的推理核心 |
| Loader | Loader | 将静态定义解析为内存对象的组件；加载 Skill/Plugin 不代表执行其中代码 |
| Loop Engineering | Loop Engineering | 设计跨 Run 的触发、工作发现、隔离执行、验证、状态、预算、停止和人工门禁；属于新兴工作术语 |
| Model Provider | Model Provider | 提供模型 API、流式协议、Tool Calling 和 Token 统计等能力的服务或本地运行时适配层 |

## M

| 术语 | 英文 | 定义 |
|------|------|------|
| MCP | Model Context Protocol | 开放协议，标准化 LLM 应用与外部上下文和能力的连接；Server 可提供 Tool、Resource、Prompt 等能力，Client 与 Server 在 Host 中协商使用范围 |
| MCP Client | MCP Client | Host 内部为每个 MCP Server 建立连接、消费其能力的协议客户端 |
| MCP Server | MCP Server | 通过 MCP 协议暴露 Tool、Resource、Prompt 等能力的服务端 |
| Memory | Memory | Agent 的状态与记忆管理模块，负责存储和检索历史信息 |
| Manager | Manager | 管理连接、进程、刷新、启停与健康状态等完整生命周期的控制组件 |
| Multi-Agent | Multi-Agent | 多个 Agent 协作完成任务的架构模式 |

## O

| 术语 | 英文 | 定义 |
|------|------|------|
| Observation | Observation | Tool 执行后返回的结果，作为下一轮推理的输入 |
| Orchestration | Orchestration | 在多个 Agent 或工作流之间进行任务分解、调度、汇总和故障处理的协调层 |
| Orchestrator | Orchestrator | 调度 Workflow、Agent Run 或外部 Job 的组件；自身不必进行模型决策 |

## P

| 术语 | 英文 | 定义 |
|------|------|------|
| Planning | Planning | Agent 将复杂任务分解为可执行步骤的过程 |
| Plugin | Plugin | 由 Host 定义的分发和生命周期单元，可打包 Tool、Skill、Hook、Connector 预设、MCP 配置或 Agent 定义；安装不等于运行授权 |
| Product Integration | Product Integration | 将 Host 接入具体外部产品的架构层，典型实现是 Connector |
| Protocol | Protocol | 跨进程或跨系统交换消息、能力和状态的约定；MCP 与 A2A 分别服务不同互操作边界 |
| Plugin Registry | Plugin Registry | 插件化扩展系统，管理插件的注册、激活、停用和卸载等完整生命周期 |
| Policy | Policy | 定义 Agent 权限、安全边界、人工确认和拒绝行为的规则集合，通常属于 Scaffolding |
| Prompt | Prompt | 用户输入的任务目标或问题描述 |
| Prompt Engineering | Prompt Engineering | 设计和优化 Prompt 以提升模型输出质量的技术 |
| Profile | Profile | 描述 Agent 角色、职责和协作定位的配置，通常是 Scaffolding 的组成部分 |
| 角色配置 | Role Configuration | 用于配置一次 Agent Run 的角色、能力偏好、权限上限、预算和验收标准；ExpertProfile 是本书的具体表达 |

## R

| 术语 | 英文 | 定义 |
|------|------|------|
| ReAct | Reasoning + Acting | 一种将推理和行动交替进行的 Agent 模式 |
| Reasoning | Reasoning | 模型基于当前上下文进行逻辑推理的过程 |
| Reflection | Reflection | Agent 对自身输出进行自我评估和修正的模式 |
| RAG | Retrieval-Augmented Generation | 从受控外部知识源检索相关内容并注入上下文的生成方法，强调来源、版本和权限 |
| Resolver | Resolver | 解析名称、版本、依赖、别名和冲突并生成唯一身份的组件 |
| Resource | Resource | 外部系统中可读取的数据对象；MCP Resource 是其协议暴露形式之一，不等于 Memory |
| 运行主体 | Runtime Subject | 在 Host 内接收目标并执行决策循环的主体，包括顶层 Agent 和被委派的 Subagent |

## S

| 术语 | 英文 | 定义 |
|------|------|------|
| Skill | Skill | 可发现、按需加载的工作流知识，告诉 Agent 如何完成任务；随附脚本仍必须通过受控 Tool/Runtime 执行 |
| Scaffolding | Scaffolding | 影响 Agent 行为的静态或缓慢变化配置集合，如 Profile、Instructions、Policy、Tool Schema 和输出契约 |
| Sandbox | Sandbox | 隔离的执行环境，限制 Agent 对文件系统和系统命令的访问范围，保障安全性 |
| Session | Session | 多轮交互、参与者身份和可共享状态的作用域；可以包含多个 Task 和 Agent Run |
| Slash Command | Slash Command | 由用户显式输入的快捷工作流入口，如 `/review`；不自动获得后续高风险操作的批准 |
| Subagent | Subagent | 由上层 Agent 委派、拥有独立执行上下文和预算的 Agent 实例 |
| System Prompt | System Prompt | 在对话开始时注入的全局指令，定义 Agent 的行为准则 |

## T

| 术语 | 英文 | 定义 |
|------|------|------|
| Token | Token | 模型处理文本的最小单位，可以是单词、子词或字符 |
| Tool | Tool | 具有名称、描述、Schema 和执行契约的可调用能力，可以是本地计算，也可以访问外部系统 |
| Tool Engineering | Tool Engineering | 设计 Tool Schema、Handler、Observation、副作用、幂等、权限和评估的工程实践 |
| Tool Calling | Tool Calling | Agent 调用 Tool 执行具体操作的过程 |
| Tool Handler | Tool Handler | Runtime 在校验和授权后执行某个 Tool 的具体实现 |
| Tool Registry | Tool Registry | 统一管理 Tool 注册、发现和调度的组件 |
| Tool Router | Tool Router | 智能路由到合适 Tool 的组件 |
| Task | Task | 用户或上游希望完成的目标；一次 Task 可以对应多次执行尝试 |
| Trace | Trace | 记录 Run、子 Run、模型与 Tool 调用之间因果关系的观测事件链；不等于 Checkpoint |

## W

| 术语 | 英文 | 定义 |
|------|------|------|
| Workflow | Workflow | 由代码、DAG 或状态机主要决定控制流的可重复执行定义；不同于模型动态决定下一步的 Agent |
| Workflow Engineering | Workflow Engineering | 设计确定性步骤、状态、依赖、重试、补偿和人工节点的工程实践 |

---

> **维护说明：** 新增术语时请按字母顺序添加，保持中英文对照和定义的一致性。
