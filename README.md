# 现代 AI Agent 架构：从原理到生产实践

一本系统讲解现代 AI Agent 架构的中文开源技术书，从核心原理、最小 Agent 循环和 Tool Calling，一直延伸到 Memory、Runtime、Hooks、Skills、MCP、Plugin、多 Agent、生产部署与评估。

[![Build Status](https://img.shields.io/github/actions/workflow/status/dollarser/modern-ai-agent-architecture/build-check.yml?style=flat-square)](https://github.com/dollarser/modern-ai-agent-architecture/actions)
[![License](https://img.shields.io/badge/docs-CC%20BY--SA%204.0-blue?style=flat-square)](LICENSE)
[![Examples](https://img.shields.io/badge/examples-MIT-green?style=flat-square)](examples/LICENSE)

## 阅读与导航

- [在线阅读](https://blog.sunlingzhang.com/modern-ai-agent-architecture/)
- [完整目录](docs/SUMMARY.md)
- [前言](docs/PREFACE.md)
- [学习路线](docs/roadmap/Roadmap.md)
- [代码示例索引](docs/references/CodeExamples.md)

全书共 20 章，按六部分组织：基础认知、构建首个 Agent、可靠运行、扩展与互操作、规模化与生产、案例与索引。

## 本地阅读

```bash
uv venv .venv
uv pip install mkdocs-material mkdocs-minify-plugin
.venv/bin/mkdocs serve
```

## 示例代码

仓库包含 10 个独立示例工程，每个主题均提供 Python 与 TypeScript 实现。依赖和运行方式见各示例目录中的 `README.md`。

```bash
# Python
python examples/agent-mvp-minimal/python/main.py

# TypeScript
cd examples/agent-mvp-minimal/typescript
npm install
npm run start
```

## 许可证

- 书稿与文档：[CC BY-SA 4.0](LICENSE)
- 示例代码：[MIT](examples/LICENSE)

欢迎通过 Issue 和 Pull Request 参与事实校验、内容改进与示例维护。
