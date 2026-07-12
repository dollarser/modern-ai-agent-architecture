# 贡献指南

感谢参与《现代 AI Agent 架构：从原理到生产实践》。详细写作、证据和代码要求见 [站点贡献指南](docs/CONTRIBUTING.md) 与 [BookSpec 1.0](specs/book/README.md)。

提交 Issue 或 Pull Request 时，请说明：

- 涉及的章节、示例或协议版本；
- 修改属于 Fact、Inference、Opinion 还是教学实现；
- 直接官方来源或可复现步骤；
- 已运行的构建和测试。

常用检查：

```bash
uv pip install -r requirements-docs.txt
.venv/bin/mkdocs build --strict
.venv/bin/python scripts/check_internal_links.py .
python scripts/extract_mermaid.py . /tmp/mermaid-snippets
node scripts/check_mermaid.mjs /tmp/mermaid-snippets
```

示例工程按各目录 README 运行。请勿在 PR 中提交真实凭据、`node_modules/`、`.venv/`、`site/` 或测试生成物。
