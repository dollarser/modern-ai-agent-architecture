# 贡献指南

感谢你对《现代 AI Agent 架构：从原理到生产实践》的关注！

## 贡献方式

### 报告问题

如果你发现：

- 事实性错误
- 过时的信息
- 代码示例无法运行
- 文档链接失效
- 术语不一致

请提交 [Issue](https://github.com/dollarser/modern-ai-agent-architecture/issues)，并附上：

- 问题所在章节/文件
- 具体问题描述
- 建议的修正方案（如适用）

### 提交内容

#### 章节内容

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/chapter-XX`
3. 遵循写作规范撰写内容
4. 提交 Pull Request

#### 代码示例

1. 确保代码可运行
2. 包含 `requirements.txt`（Python）或 `package.json`（TypeScript）
3. 包含 README.md 说明运行方式
4. 通过 CI 测试

### 写作规范

请严格遵循以下规范：

1. **Why → What → How → When → Trade-off** 结构
2. **区分四类信息**：Fact / Inference / Opinion / To Be Verified
3. **禁止编造**：API 接口、协议字段、官方实现细节、产品能力
4. **引用规范**：官方文档 > 源码 > RFC > 论文 > 官方博客 > 社区共识
5. **术语统一**：使用 [术语表](glossary/Glossary.md) 中的标准译法

### 章节结构

章节必须有学习目标、适用读者或前置知识、核心正文、来源和 Checklist。架构图、代码、FAQ、反模式等只在能提升理解时加入，不机械填充固定栏目。完整要求以 [BookSpec 章节规范](https://github.com/dollarser/modern-ai-agent-architecture/blob/main/specs/book/02-chapter-specification.md) 为准。

## 审阅流程

1. 自动化检查（CI）必须通过
2. 至少一位维护者审阅
3. 事实性内容需标注来源
4. 代码示例需经测试验证

## 行为准则

- 尊重不同观点
- 建设性讨论
- 基于事实论证
- 保持专业和友好
