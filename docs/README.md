# 《现代 AI Agent 架构：从原理到生产实践》

> 一本可持续维护、工程化、事实可验证、可发布、可扩展的 AI Agent 技术参考书

[![Build Status](https://img.shields.io/github/actions/workflow/status/dollarser/modern-ai-agent-architecture/build-check.yml?style=flat-square)](https://github.com/dollarser/modern-ai-agent-architecture/actions)
[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue?style=flat-square)](LICENSE)
[![MkDocs](https://img.shields.io/badge/docs-mkdocs%20material-blue?style=flat-square)](https://squidfunk.github.io/mkdocs-material/)

---

## 关于本书

本书系统性地解析现代 AI Agent 的架构设计，从基础概念到生产实践，覆盖 Prompt、Instructions、Reasoning、Planning、Memory、Tools、Function Calling、MCP、Hooks、Skills、Runtime 等核心组件，并比较 GitHub Copilot、Claude Code、Cursor 等主流 Coding Agent 的公开能力与可验证的架构模式。

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
| **第一部分：基础认知** | 1-4 | 历史演进、总体架构、Prompt/Instructions、Context 管理 |
| **第二部分：构建首个 Agent** | 5-7 | Reasoning/Planning、Tools/Function Calling、Agent MVP |
| **第三部分：可靠运行** | 8-11 | Memory、Runtime、Hooks、Tool Registry |
| **第四部分：扩展与互操作** | 12-14 | Skills、MCP、Plugin 体系 |
| **第五部分：规模化与生产** | 15-18 | 设计模式、增强实现、工程实践、最佳实践与评估 |
| **第六部分：案例与索引** | 19-20 | 框架分析、常见架构问题、选型指南 |

## 快速开始

### 在线阅读

访问 [https://blog.sunlingzhang.com/modern-ai-agent-architecture/](https://blog.sunlingzhang.com/modern-ai-agent-architecture/)

### 本地运行

```bash
# 创建本地虚拟环境并安装依赖
uv venv .venv
uv pip install mkdocs-material mkdocs-minify-plugin

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

```
book/
├── LICENSE                # 许可证
├── mkdocs.yml             # MkDocs 配置
├── docs/                  # 书稿源文件
│   ├── README.md          # 项目说明
│   ├── SUMMARY.md         # 目录
│   ├── PREFACE.md         # 前言
│   ├── CHANGELOG.md       # 变更日志
│   ├── CONTRIBUTING.md    # 贡献指南
│   ├── glossary/          # 术语表
│   ├── faq/               # 常见问题
│   ├── references/        # 参考文献
│   ├── roadmap/           # 学习路线
│   ├── chapters/          # 章节内容（20章）
│   └── mermaid/           # 图索引
├── examples/              # 可运行示例代码（Python + TypeScript）
├── assets/                # 预留的静态资源目录
├── diagrams/              # 预留的外部图表源文件目录；正文图使用 Mermaid
├── scripts/               # 预留的维护脚本目录
├── tests/                 # 预留的项目级测试目录；示例按各工程独立验证
└── .github/workflows/     # CI/CD 流水线
```

## 验收指标

| 指标 | 目标 | 状态 |
|------|------|------|
| 正文字量 | 以结构完整、可导航、无明显重复和可维护为准 | ✅ |
| 章节数 | 20 章 | ✅ |
| Mermaid 图 | 47 张 | ✅ 已满足 |
| 可运行代码示例 | 12 个独立工程、Python/TypeScript 共 24 个入口；包含最小 MVP、Runtime、跨组件预览与可插拔最终组装 Enhanced Agent | ✅ 已验证 |
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

> **最终定位：** 一本可持续维护、工程化、事实可验证、可发布、可扩展的《现代 AI Agent 架构：从原理到生产实践》开源技术参考书。
