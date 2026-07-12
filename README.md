# 现代 AI Agent 架构：从原理到生产实践

一本兼顾 AI Agent 概念、理论与开发实践的中文开源技术书。从 Prompt、Context、Reasoning 和 Tool Calling 出发，逐步实现 Runtime、Memory、Skills、MCP、Plugin、Subagent、治理体系，以及支持多轮对话和简单编码任务的教学型 Agent Host。

[![Build Status](https://img.shields.io/github/actions/workflow/status/dollarser/modern-ai-agent-architecture/build-check.yml?style=flat-square)](https://github.com/dollarser/modern-ai-agent-architecture/actions)
[![License](https://img.shields.io/badge/docs-CC%20BY--SA%204.0-blue?style=flat-square)](LICENSE)
[![Examples](https://img.shields.io/badge/examples-MIT-green?style=flat-square)](examples/LICENSE)

## 阅读与导航

- [在线阅读](https://blog.sunlingzhang.com/modern-ai-agent-architecture/)
- [完整目录](docs/SUMMARY.md)
- [前言](docs/PREFACE.md)
- [学习路线](docs/roadmap/Roadmap.md)
- [代码示例索引](docs/references/CodeExamples.md)
- [当前实现与出版基线](specs/book/11-current-baseline.md)
- [完整技术书共创工作流](specs/technical-book-coauthoring-workflow.md)

全书共 20 章，按六部分组织：基础认知、构建首个 Agent、可靠运行、扩展与互操作、规模化与生产、案例与索引。

## 本地阅读

```bash
uv venv .venv
uv pip install -r requirements-docs.txt
.venv/bin/mkdocs serve
```

## 示例代码

仓库包含 15 个独立示例工程、Python/TypeScript 共 30 个入口。除概念示例外，还包括 Skill Installer、MCP Server Manager、Plugin Manager、Application Session 和受限 Coding Agent。依赖和运行方式见各示例目录中的 `README.md`。

```bash
# Python
python examples/agent-mvp-minimal/python/main.py

# TypeScript
cd examples/agent-mvp-minimal/typescript
npm install
npm run start
```

完整检查：

```bash
.venv/bin/mkdocs build --strict
.venv/bin/python scripts/check_internal_links.py .
npm run check:mermaid
```

## 仓库结构

```text
.
├── docs/          # MkDocs 书稿、20 章正文与附录
├── examples/      # 15 个独立 Python/TypeScript 教学工程
├── specs/         # 现行书籍规范、共创方法与历史需求归档
├── reviews/       # 审查报告、出版基线和维护记录
├── scripts/       # 链接与 Mermaid 校验脚本
├── .github/       # GitHub Actions
├── mkdocs.yml     # 文档站配置
├── requirements-docs.txt # 固定的文档构建依赖
└── README.md      # GitHub 项目入口
```

维护优先级为：官方规范/源码 → 当前代码与 `docs/SUMMARY.md` → `specs/book`。`specs/history/` 中的 V4～V7 资料只用于历史追溯。

## 贡献

欢迎提交事实修正、链接更新、示例测试和可读性改进。提交前请阅读 [贡献指南](CONTRIBUTING.md)。内部审查记录集中在 [`reviews/`](reviews/README.md)，不作为正文目录的一部分。

## 许可证

- 书稿与文档：[CC BY-SA 4.0](LICENSE)
- 示例代码：[MIT](examples/LICENSE)
