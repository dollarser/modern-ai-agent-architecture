# 规范与写作方法

## 当前有效规范

书籍维护、审阅和发布验收只使用 [`book/`](book/README.md)。实际章节顺序以 [`../docs/SUMMARY.md`](../docs/SUMMARY.md) 为准，代码和指标以当前工作树及自动化验证结果为准。

希望把本项目的方法复用到其他技术主题时，阅读 [`technical-book-coauthoring-workflow.md`](technical-book-coauthoring-workflow.md)。它覆盖需求撰写、BookSpec 升级、正式写作、多轮审查、纵向架构修订、最终需求回写和出版冻结。

## 历史资料

- `history/AI-Agent-Book-Specification-V6-Docs/`：V6 时代的拆分需求，已废止。
- `history/现代AI-Agent架构解析-文档生成需求（整合版V7）.md`：V7 整合需求，已被 BookSpec 1.0 和当前实现取代。
- `history/` 中的其他文件：更早的 V4/V6/Coding Agent 需求快照。

历史资料用于解释决策演进，不得覆盖当前章节编号、类名、目录、协议版本、数量指标和验收结论。若历史记录与当前内容冲突，按以下优先级处理：

```text
官方规范/源码
→ 已验证的当前实现与 docs/SUMMARY.md
→ specs/book/
→ 当前书稿中的时效性声明
→ V7 / V6 / history
```
