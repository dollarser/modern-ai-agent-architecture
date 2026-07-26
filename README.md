# 现代 AI Agent 架构：从原理到生产实践

一本面向开发者的中文开源技术书：从模型调用、Prompt 和 Agent Loop 出发，逐步构建具备工具调用、记忆、扩展、互操作、安全治理和多轮对话能力的教学型 Agent Host。

它同时覆盖 MCP、A2A、个人 AI 助理和 Code Agent，并提供 Python/TypeScript 双语言示例、契约测试和可验证的工程边界。

[![Build Status](https://img.shields.io/github/actions/workflow/status/dollarser/modern-ai-agent-architecture/build-check.yml?style=flat-square)](https://github.com/dollarser/modern-ai-agent-architecture/actions)
[![Release](https://img.shields.io/github/v/release/dollarser/modern-ai-agent-architecture?style=flat-square)](https://github.com/dollarser/modern-ai-agent-architecture/releases/latest)
[![Online Book](https://img.shields.io/badge/read-online-blue?style=flat-square)](https://blog.sunlingzhang.com/modern-ai-agent-architecture/)
[![Book License](https://img.shields.io/badge/book-CC%20BY--SA%204.0-blue?style=flat-square)](LICENSE)
[![Code License](https://img.shields.io/badge/examples-MIT-green?style=flat-square)](examples/LICENSE)

## 这本书适合谁

- 想系统理解 AI Agent 内部运行机制的开发者；
- 正在开发 Agent 应用、Agent Framework 或 Agent Host 的工程师；
- 需要设计 Tool、MCP Server、Plugin、Memory、Approval 和 Sandbox 边界的团队；
- 希望比较个人 AI 助理、Code Agent、Multi-Agent 和主流 SDK 的架构人员。

## 你将学到什么

- 区分 AgentHost、Agent、Subagent、Tool、Skill、MCP、A2A、Connector 和 Plugin；
- 实现 Task/Run 驱动的 Agent Loop，以及 Session、Memory、Checkpoint 和 Trace 的基本协作；
- 理解 MCP 的工具互操作和 A2A 的 Agent 协作边界；
- 为文件、Shell、补丁、网络和第三方扩展设置 Policy、Approval、Sandbox 与审计边界；
- 组装一个支持多轮对话、受控工具调用和简单编码任务的教学型 Agent Host；
- 对比 Agent Framework/SDK、Personal Assistant Host 和 Code Agent 的选型取舍。

## 从哪里开始

| 目标 | 推荐入口 |
| --- | --- |
| 直接阅读 | [在线阅读](https://blog.sunlingzhang.com/modern-ai-agent-architecture/) |
| 浏览完整目录 | [20 章目录](docs/SUMMARY.md) |
| 按阶段学习 | [学习路线](docs/roadmap/Roadmap.md) |
| 运行代码 | [代码示例索引](docs/references/CodeExamples.md) |
| 查看正式版本 | [v1.0.0 Release](https://github.com/dollarser/modern-ai-agent-architecture/releases/tag/v1.0.0) |
| 报告问题或提出建议 | [Issues](https://github.com/dollarser/modern-ai-agent-architecture/issues) |

全书保持现有 20 章和六大部分结构：基础认知、构建首个 Agent、可靠运行、扩展与互操作、规模化与生产、案例与选型。

## 30 秒运行第一个 Agent

最小示例不需要 API Key，也不访问网络，适合先验证本地环境：

```bash
git clone https://github.com/dollarser/modern-ai-agent-architecture.git
cd modern-ai-agent-architecture

# Python
python examples/agent-mvp-minimal/python/main.py

# TypeScript
cd examples/agent-mvp-minimal/typescript
npm install
npm run start
```

示例会展示 `task → instructions → reason → plan → execute → observe → finish` 的基本闭环。每个示例目录都有独立的运行说明、教学边界和测试入口。

## 示例按学习目标分类

| 学习目标 | 示例 |
| --- | --- |
| Agent Loop 与基础能力 | `hello-agent`、`agent-mvp-minimal`、`planning`、`tool-calling` |
| Runtime 与状态控制 | `runtime`、`memory`、`hooks` |
| Tool 与扩展管理 | `tool-registry`、`skills`、`mcp-manager`、`plugin-manager` |
| MCP 与 A2A 互操作 | `mcp-client`、`mcp-server`、`a2a-task-artifact` |
| Agent Host 与应用闭环 | `agent-host`、`coding-agent-mvp` |
| 工程验证 | `evaluation-contract`、`model-capability-contract` |

仓库包含 18 个独立示例工程、Python/TypeScript 共 36 个入口。示例优先采用离线、确定性适配器，重点验证协议模型、状态转换、安全边界和组件装配；它们是教学实现，不等同于生产级沙箱、远程传输或完整商业产品。

## 本地阅读与完整检查

```bash
# 安装文档依赖并启动 MkDocs
uv venv .venv
uv pip install -r requirements-docs.txt
.venv/bin/mkdocs serve

# 构建与检查
.venv/bin/mkdocs build --strict
.venv/bin/python scripts/check_internal_links.py .
npm install
npm run check:mermaid
```

## 全书结构

| 部分 | 章节 | 内容 |
| --- | --- | --- |
| 第一部分 | 1–4 | Agent 基础概念、总体架构、Prompt/Instructions、Context |
| 第二部分 | 5–7 | Reasoning、Planning、Tools、Function Calling、Agent MVP |
| 第三部分 | 8–11 | Memory、Runtime、Hooks、Tool Registry |
| 第四部分 | 12–14 | Skills、MCP/A2A、Connector、Plugin |
| 第五部分 | 15–18 | Multi-Agent、Agent Host、工程实践、安全与评估 |
| 第六部分 | 19–20 | 框架与开源项目分析、迁移、选型与常见问题 |

## 项目结构

```text
.
├── docs/                  # MkDocs 书稿、20 章正文与附录
├── examples/              # Python/TypeScript 教学示例与契约测试
├── specs/                 # 现行书籍规范与历史需求归档
├── reviews/               # 审查报告、出版基线与维护记录
├── scripts/               # 链接与 Mermaid 校验脚本
├── .github/               # GitHub Actions
├── mkdocs.yml             # 文档站配置
├── requirements-docs.txt  # 固定的文档构建依赖
└── README.md              # GitHub 项目入口
```

## 内容边界与证据原则

- 书稿区分官方事实、公开行为、推导、观点和待验证内容；
- 不把教学适配器、内存模型或离线协议模型描述为完整生产实现；
- 涉及文件、Shell、第三方扩展和模型调用时，默认经过 Runtime、Policy、Approval 和 Sandbox；
- 框架与产品分析优先引用官方文档、源码、RFC 或论文，不编造未公开的内部实现。

## 参与贡献

欢迎提交事实修正、链接更新、示例测试、错别字修复和可读性改进。请先阅读 [贡献指南](CONTRIBUTING.md)，再通过 [Issue](https://github.com/dollarser/modern-ai-agent-architecture/issues) 或 Pull Request 参与。项目后续可以使用 GitHub Discussions 进行开放式问答和架构讨论。

## 许可证

- 书稿与文档：[CC BY-SA 4.0](LICENSE)
- 示例代码：[MIT](examples/LICENSE)
