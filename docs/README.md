# 《现代 AI Agent 架构：从原理到生产实践》

> 从核心概念与理论出发，逐步实现一个可对话、可调用工具、可安装扩展并能完成简单编码任务的教学型 AI Agent

[![Build Status](https://img.shields.io/github/actions/workflow/status/dollarser/modern-ai-agent-architecture/build-check.yml?style=flat-square)](https://github.com/dollarser/modern-ai-agent-architecture/actions)
[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue?style=flat-square)](LICENSE)
[![MkDocs](https://img.shields.io/badge/docs-mkdocs%20material-blue?style=flat-square)](https://squidfunk.github.io/mkdocs-material/)

---

## 关于本书

本书面向希望理解并动手构建 AI Agent 的开发者：先解释 Prompt、Context、Reasoning、Planning、Memory、Tools、Function Calling、Runtime 等概念与理论，再实现可运行的 Agent 闭环，并逐步加入 Skill、MCP Server 与 Plugin 的安装、发现、启停和治理。最终教学目标是让读者能够构建一个支持多轮对话、受控工具调用和简单编码任务的 Agent Host，同时理解它与 Claude Code、Codex、GitHub Copilot 等产品公开能力之间的共性和边界。

本书不以复刻任何商业 Coding Agent 为目标，也不把教学适配器描述为生产实现。涉及文件修改、Shell、第三方扩展和模型调用时，正文始终要求经过 Runtime、Policy、Approval 与 Sandbox，而不是把宿主权限直接交给模型。

### 全书最终学习成果

完成全书后，读者应能够：

- 区分 AgentHost、Agent、Subagent、Tool、Skill、MCP、Connector 与 Plugin 等核心概念；
- 实现 Task / Run 驱动的 Agent Loop，以及 Session、Memory、Checkpoint 和 Trace 的基本协作；
- 注册本地 Tool，连接 MCP Server，并安装、启用、禁用和卸载 Skill 或 Plugin；
- 为文件读取、补丁修改、构建和测试等编码操作设置路径、命令、审批和资源边界；
- 组装一个能够对话、使用工具并完成简单编码任务的教学型 Agent，而不是只停留在单轮 Function Calling。

## 目标读者

- **初学者**：希望系统理解 AI Agent 架构
- **AI 应用开发者**：需要集成 Agent 能力
- **Agent Framework 开发者**：需要设计或扩展框架
- **IDE 插件开发者**：需要理解 Coding Agent 内部机制
- **企业平台开发者**：需要评估和选型 Agent 方案

## 内容概览

全书共 20 章，分为六个部分：

| 模块 | 章节 | 主题 |
|------|------|------|
| **第一部分：基础认知** | 1-4 | 历史演进、五类正交概念、总体架构、Prompt/Instructions、Context 管理 |
| **第二部分：构建首个 Agent** | 5-7 | Reasoning/Planning、Tools/Function Calling、Agent MVP |
| **第三部分：可靠运行** | 8-11 | Memory、Runtime、Hooks、Tool Registry |
| **第四部分：扩展与互操作** | 12-14 | Skills、MCP、Connector、Plugin 体系 |
| **第五部分：规模化与生产** | 15-18 | 设计模式、Agent Host 组装、工程实践、最佳实践与评估 |
| **第六部分：案例与索引** | 19-20 | 框架分析、常见架构问题、选型指南 |

## 快速开始

### 在线阅读

访问 [https://blog.sunlingzhang.com/modern-ai-agent-architecture/](https://blog.sunlingzhang.com/modern-ai-agent-architecture/)

### 本地运行

```bash
# 创建本地虚拟环境并安装依赖
uv venv .venv
uv pip install -r requirements-docs.txt

# 启动开发服务器
.venv/bin/mkdocs serve

# 构建静态站点
.venv/bin/mkdocs build --strict
```

### 运行示例代码

```bash
# Python 示例
cd examples/hello-agent/python
pip install -r requirements.txt
python main.py

# TypeScript 示例
cd examples/hello-agent/typescript
npm install
npm run start
```

## 项目结构

```text
.
├── docs/                  # 书稿、20 章正文、附录与 MkDocs 首页
├── examples/              # 15 个独立 Python/TypeScript 示例工程
├── specs/                 # 现行书籍规范、共创方法与历史需求归档
├── reviews/               # 审查报告、出版基线与维护记录
├── scripts/               # 内部链接和 Mermaid 校验脚本
├── .github/workflows/     # 构建、链接、图表与双语言 CI
├── mkdocs.yml             # MkDocs 配置
├── requirements-docs.txt  # 固定的文档构建依赖
├── package.json           # 文档图表校验依赖与脚本
├── CONTRIBUTING.md        # GitHub 贡献入口
└── README.md              # GitHub 项目入口
```

## 验收指标

| 指标 | 目标 | 状态 |
|------|------|------|
| 正文字量 | 以结构完整、可导航、无明显重复和可维护为准 | ✅ |
| 章节数 | 20 章 | ✅ |
| Mermaid 图 | 54 张 | ✅ 已满足 |
| 可运行代码示例 | 15 个独立工程、Python/TypeScript 共 30 个入口；包含 Skill/Plugin 安装、MCP Server 管理与可插拔 Agent Host | ✅ 已验证 |
| 简单编码任务闭环 | 受限工作区内读取/搜索 → Patch → 测试 → 结果汇报；覆盖默认拒绝和路径越界 | ✅ 双语言纵向切片已验证；生产沙箱不在教学实现范围内 |
| 多轮对话身份闭环 | Session 聚合 Message；每条用户消息创建独立 Task/Run；历史经裁剪进入新 Run | ✅ 双语言 Application 层契约已验证 |
| Markdown 表格 | 160 个（当前清点；不以数量作为质量目标） | ✅ 已清点 |
| 完整术语表 | 1 份 | ✅ |
| 官方参考文献 | 每章至少一个可追溯来源；协议和产品事实使用直接官方来源 | ⚠️ 需定期校验链接 |
| 框架分析 | 6 个代表性方案，区分公开事实与推导 | ✅ |
| 学习路线 | 10 阶段 | ✅ |

## 写作原则

- **Why → What → How → When → Trade-off**：每个知识点说明为什么需要、是什么、怎么做、什么时候用、有什么取舍
- **事实可验证**：每个重要结论标注来源类型（官方文档 / 源码 / RFC / 论文 / 推导 / 观点）
- **区分四类信息**：Fact（事实）、Inference（推导）、Opinion（作者观点）、To Be Verified（待验证）
- **禁止编造**：不编造 API 接口、协议字段、官方实现细节、产品能力

## 版本历史

| 版本 | 核心贡献 |
|------|---------|
| V1 | 核心概念速览、架构图、常见混淆澄清 |
| V2~V3 | 章节规划、术语规范、工程化基础 |
| V4 | 历史演进、框架源码分析、设计模式、学习路线 |
| V5 | 项目工程化、发布部署 |
| V6 | 开源项目结构、CI/CD、配套文档、示例工程 |
| V7 | 整合 V1~V6，形成完整统一的需求规格 |

## 许可证

本书采用 [CC BY-SA 4.0](LICENSE) 许可证。示例代码采用 [MIT](examples/LICENSE) 许可证。

## 贡献

欢迎通过 Issue 和 Pull Request 参与贡献。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

> **最终定位：** 一本兼顾概念、理论与开发实践，并以可扩展教学型 Agent Host 为落点的《现代 AI Agent 架构：从原理到生产实践》开源技术书。
