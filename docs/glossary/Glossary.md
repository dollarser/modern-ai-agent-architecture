# 术语表（Glossary）

> 本书统一术语的中英文对照及定义。首次出现的术语标注英文原文，全书保持一致。

## A

| 术语 | 英文 | 定义 |
|------|------|------|
| Agent | Agent | 能够自主感知环境、推理、规划并执行动作的 AI 系统 |
| A2A | Agent-to-Agent | 面向跨系统 Agent 协作的互操作协议类别；与应用内 Handoff 和 MCP 的职责不同 |
| Agent Loop | Agent Loop | Agent 的主循环：Reasoning → Planning → Tool Calling → Observation → Reasoning ... |
| Agent Runtime | Agent Runtime | 管理 Agent 生命周期、调度 Tool 调用、协调各组件的运行环境 |

## B

| 术语 | 英文 | 定义 |
|------|------|------|
| Built-in Tool | Built-in Tool | Agent 框架内置的工具，无需额外安装，直接调用 |

## C

| 术语 | 英文 | 定义 |
|------|------|------|
| Context | Context | 模型当前可用的信息窗口，包含 Prompt、Instructions、历史对话、Tool 结果等 |
| Context Window | Context Window | 模型一次能处理的最大 token 数量 |
| Chain-of-Thought (CoT) | Chain-of-Thought | 通过逐步推理（"让我们一步步思考"）提高复杂问题准确性的 Prompting 技术 |
| Checkpoint | Checkpoint | Agent 运行状态的快照，用于故障恢复和状态回滚 |
| Circuit Breaker | Circuit Breaker | 当某个操作失败率超过阈值时自动熔断，防止级联故障的保护机制 |
| CLI | Command-Line Interface | 命令行交互入口，通常通过参数、退出码和帮助信息提供可脚本化、自文档化的操作方式 |

## E

| 术语 | 英文 | 定义 |
|------|------|------|
| Event Bus | Event Bus | 事件驱动的组件通信机制，组件通过发布/订阅事件进行解耦通信 |
| Elicitation | Elicitation | MCP Client 可选能力之一，允许 Server 通过 Host 向用户请求额外信息 |

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

## I

| 术语 | 英文 | 定义 |
|------|------|------|
| Instructions | Instructions | 约束 Agent 行为的规则；由 Host 按任务和会话组装、版本化并注入 Context，通常比单次 Prompt 更稳定，但不必在每轮完整加载 |

## K

| 术语 | 英文 | 定义 |
|------|------|------|
| Knowledge System | Knowledge System | 受控的外部知识源及其索引、检索、权限、版本和引用机制；与 Agent Memory 的生命周期不同 |

## L

| 术语 | 英文 | 定义 |
|------|------|------|
| LLM | Large Language Model | 大语言模型，Agent 的推理核心 |
| Model Provider | Model Provider | 提供模型 API、流式协议、Tool Calling 和 Token 统计等能力的服务或本地运行时适配层 |

## M

| 术语 | 英文 | 定义 |
|------|------|------|
| MCP | Model Context Protocol | 开放协议，标准化 LLM 应用与外部上下文和能力的连接；Server 可提供 Tool、Resource、Prompt 等能力，Client 与 Server 在 Host 中协商使用范围 |
| MCP Client | MCP Client | Host 内部为每个 MCP Server 建立连接、消费其能力的协议客户端 |
| MCP Server | MCP Server | 通过 MCP 协议暴露 Tool、Resource、Prompt 等能力的服务端 |
| Memory | Memory | Agent 的状态与记忆管理模块，负责存储和检索历史信息 |
| Multi-Agent | Multi-Agent | 多个 Agent 协作完成任务的架构模式 |

## O

| 术语 | 英文 | 定义 |
|------|------|------|
| Observation | Observation | Tool 执行后返回的结果，作为下一轮推理的输入 |
| Orchestration | Orchestration | 在多个 Agent 或工作流之间进行任务分解、调度、汇总和故障处理的协调层 |

## P

| 术语 | 英文 | 定义 |
|------|------|------|
| Planning | Planning | Agent 将复杂任务分解为可执行步骤的过程 |
| Plugin | Plugin | 可动态加载的扩展模块，提供额外的 Tool 或能力 |
| Plugin Registry | Plugin Registry | 插件化扩展系统，管理插件的注册、激活、停用和卸载等完整生命周期 |
| Policy | Policy | 定义 Agent 权限、安全边界、人工确认和拒绝行为的规则集合，通常属于 Scaffolding |
| Prompt | Prompt | 用户输入的任务目标或问题描述 |
| Prompt Engineering | Prompt Engineering | 设计和优化 Prompt 以提升模型输出质量的技术 |
| Profile | Profile | 描述 Agent 角色、职责和协作定位的配置，通常是 Scaffolding 的组成部分 |

## R

| 术语 | 英文 | 定义 |
|------|------|------|
| ReAct | Reasoning + Acting | 一种将推理和行动交替进行的 Agent 模式 |
| Reasoning | Reasoning | 模型基于当前上下文进行逻辑推理的过程 |
| Reflection | Reflection | Agent 对自身输出进行自我评估和修正的模式 |
| RAG | Retrieval-Augmented Generation | 从受控外部知识源检索相关内容并注入上下文的生成方法，强调来源、版本和权限 |

## S

| 术语 | 英文 | 定义 |
|------|------|------|
| Skill | Skill | 可复用的工作流模板，告诉 Agent 怎么做，但不真正执行 |
| Scaffolding | Scaffolding | 影响 Agent 行为的静态或缓慢变化配置集合，如 Profile、Instructions、Policy、Tool Schema 和输出契约 |
| Sandbox | Sandbox | 隔离的执行环境，限制 Agent 对文件系统和系统命令的访问范围，保障安全性 |
| Slash Command | Slash Command | 由用户显式输入的快捷工作流入口，如 `/review`；不自动获得后续高风险操作的批准 |
| Subagent | Subagent | 由上层 Agent 委派、拥有独立执行上下文和预算的 Agent 实例 |
| System Prompt | System Prompt | 在对话开始时注入的全局指令，定义 Agent 的行为准则 |

## T

| 术语 | 英文 | 定义 |
|------|------|------|
| Token | Token | 模型处理文本的最小单位，可以是单词、子词或字符 |
| Tool | Tool | 可执行的接口，Agent 通过调用 Tool 与外部世界交互 |
| Tool Calling | Tool Calling | Agent 调用 Tool 执行具体操作的过程 |
| Tool Registry | Tool Registry | 统一管理 Tool 注册、发现和调度的组件 |
| Tool Router | Tool Router | 智能路由到合适 Tool 的组件 |

---

> **维护说明：** 新增术语时请按字母顺序添加，保持中英文对照和定义的一致性。
