# 变更日志

> 历史条目中的 “Enhanced Agent” 是第 16 章旧称；当前对应 `AgentHost` 与 `examples/agent-host/`，不表示仍保留兼容类型或旧目录。

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [Unreleased] - 2026-07-11

### 最终版定位
- 冻结最终学习成果：兼顾 AI Agent 概念、理论与开发，并以可对话、可安装扩展、可完成简单编码任务的教学型 Agent Host 为落点。
- 新增最终版出版审查基线与验收矩阵；当时识别的 Patch/测试闭环和 Application Session → Run 两项 P1 已在本版本后续修复并通过双语言测试。
- 为 Agent Host 新增 Python/TypeScript 对等的受限 Coding Agent：工作区 Read/Search、需审批的精确 Patch、固定 argv 测试与结果汇报；覆盖默认拒绝和路径越界。
- 新增 Python/TypeScript 对等的 `ConversationApplication + JsonSessionStore`，实现 Session 多轮消息到独立 Task/Run 的映射，并将受限历史显式传入新 Run 的 Planner Context。
- 完成执行、状态、扩展、协作、治理与工程实践六条纵向主线终审；统一 Task 级重试与 Tool 重试、Policy 身份、扩展阶段、审批状态和 Plugin 清理失败语义。
- 新增 Skill Catalog、MCP Server Manager、Plugin Catalog 到 AgentHost 的双语言可运行 Adapter；MCP Manager Connection 补齐 Tool 调用和已启用会话输出。
- 重构 PRD 权威层级：BookSpec 1.0 更新为当前目录、概念体系、AgentHost 能力和 2026-07-13 验收基线；V6/V7 明确标为历史归档，并新增统一当前基线快照。
- 整理 GitHub 仓库结构：审查记录迁入 `reviews/`，新增根贡献入口，更新根 README、真实项目树、文档校验脚本和过时示例数量。
- 新增可复用的《与 AI 协作编写完整技术书》工作流，覆盖需求、BookSpec、正式写作、专项/纵向审查、架构修订、最终 PRD 回写与出版冻结。
- 补充作者对领域了解但不完全熟悉时的方法：认知边界、证据扫描、L1～L7 成果阶梯、行为验收契约、代表性任务、依赖图章节规划、暂定章节状态和二维覆盖矩阵。
- 将 V6 拆分规范和整合版 V7 统一迁入 `specs/history/`；现行规范收敛到 `specs/book/`，共创方法保留在 `specs/` 根目录。
- 将原 `PRD/` 重命名为更准确的 `specs/`，并统一现行规范文件为小写 kebab-case；历史文件保留原名。
- 完成 GitHub 发布前校检：Mermaid CI 改用根锁文件，Python CI 正确区分测试工程与需参数 CLI，Actions 默认权限收窄为只读，并将根入口和现行规范纳入 Markdown lint。
- 新增 `requirements-docs.txt` 固定已验证的 MkDocs 构建依赖，避免 CI 因上游最新版本漂移而无故失败。

### 重构
- 将第 16 章重构为最终组装章：以 Port / Adapter 和 Composition Root 组合 Memory、完整生命周期 Hooks、带来源与状态的 Tool Router、MCP、Plugin、Human Approval、Handoff/Subagent 和 Event Bus。
- 重构 `examples/agent-host/` 的 Python 与 TypeScript 实现，新增上述能力的离线最小适配器与端到端契约测试，明确功能闭环与生产基础设施的边界。

### 修正
- 将 Tool Calling 与 Tool Registry 双语言示例中的 `eval` / `Function` 动态执行替换为受限算术解析器，只允许数字、括号和白名单运算符，并限制复杂度、指数与结果范围。
- 修正第 9 章将取消、暂停和步数耗尽覆盖为 `FINISHED` 的终态错误；新增 `EXHAUSTED`，只有明确完成条件才能成功。
- 统一第 16 章韧性执行片段与 Enhanced Agent 的 `retryable` 契约，并将第 17 章未配置权限策略的 Tool 改为默认拒绝。
- 修正第 9 章在执行前检查单步耗时、并在 `as_completed` 后设置无效 timeout 的问题，改为 Future 等待上限，并明确底层取消与幂等边界。
- 修正第 10 章对新版 MVP 的过期回调描述，统一 Guard Hook 与观测 Hook 的失败策略，让 After Hook 的输出变换显式返回，并同步双语言示例的真实拦截行为。
- 重写第 17 章已引用旧版 `AgentMVP` 的失效测试片段，改为链接并摘录当前最小与 Enhanced Agent 的可运行契约测试。
- 修正 6 个示例 README 中因章节重排遗留的章节号，并清理 Coding Agent 组合预览中的“完整 MVP”旧名称。
- 收敛第 7 章为单轮最小纵向闭环：统一正文与可运行示例，修正 Instructions、步数、失败状态、测试和运行路径语义，并移除提前拼装后续组件的重复实现。
- 修正架构图索引中第 5 章 ReAct 与 Plan-and-Execute 的图号引用。
- 修正第 7 章图 7-1 的组件边界：将简单 Runtime Loop 纳入 Agent MVP，并移除最小示例中尚不存在的 LLM Interface。
- 重排第 5 章图 5-1 为三列等高策略对比，缩短图形高度并保留三种策略的核心差异。
- 将 Mermaid CI 改为无需启动浏览器的语法解析，并为现有中文技术书排版提供项目级 Markdown Lint 规则。
- 修正第 18 章将 MCP 简化为“只提供 Tool”的跨章概念冲突，并统一其与第 13 章的职责边界。
- 将 Mermaid、Python 示例与链接 CI 从告警式检查改为真实失败门禁，新增 Mermaid 提取和内部链接检查脚本。
- 按 MCP v2025-06-18 修订第 13 章的协议边界与 Transport 描述，并明确旧示例的历史范围。
- 收紧第 19 章对闭源产品内部机制的断言，补充框架分析的证据边界。
- 修正不存在的 Skills 示例工程声明，并如实更新验收指标状态。
- 修正 MkDocs 的文档根目录和许可证入口；严格构建现已可通过。

### 新增
- 新增 `examples/runtime/` 双语言状态机及契约测试，覆盖完成、步数耗尽、及时超时和取消；为 Hooks 双语言示例补充 Guard、结果传播和观测失败隔离测试。
- 新增 TypeScript 示例 CI，在 Node.js 18、20、22 上对全部工程执行锁文件安装、严格编译和可选测试。
- 新增 `examples/agent-host/` 的 Python 与 TypeScript 可运行实现及契约测试，覆盖 Adapter、Skills、依赖并行、重试、Hooks、Memory、Checkpoint 恢复和诚实终止状态。
- 第 16 章补充从第 7 章 MVP 逐章演进而来的最终 Agent 能力总览，明确 Runtime、Context、模型、Tool/MCP/Plugin、状态、编排与治理边界。
- 为全部 20 章增加章末小结，统一收束核心边界、适用条件和工程取舍。
- 第 2 章补充 Scaffolding、Harness、Runtime 与 Orchestration 的职责图和术语边界。
- 第 8 章补充 Agent Memory、Knowledge System 与 RAG 的边界及反模式。
- 第 15 章补充 Subagent 委派契约；第 17 章补充 Guardrails 纵深防御与 Trace 回放的数据最小化要求。
- 第 2、7、10、11 章补充模型层选择、渐进式 Skills、Plugin 可选能力与命令入口、可引用 RAG 知识接入流程。
- 第 13 章补充 MCP 能力协商、Client 侧能力与远程授权边界；第 16、18 章补充跨系统协作和持久化人工审批语义。
- 第 4、12、13、17 章补充 Context、Runtime、Tool Registry 与 Enhanced Agent 的适用信号、职责边界和工程代价；BookSpec 新增 Why → What → How → When → Trade-off 的审阅规则。
- 收敛附录 FAQ 为快速索引，并将完整问答统一到第 20 章；第 18 章补充轨迹级评估契约，收紧固定比例、成本收益和模型名等不可泛化表述。
- 第 19 章移除不可复核的框架排名象限，改为约束驱动的试点选型表；第 20 章将趋势预测改为带不确定性说明的观察方向。

### 维护
- 以 `modern-ai-agent-architecture` 作为公开仓库名，书名统一为《现代 AI Agent 架构：从原理到生产实践》，补充 GitHub 仓库首页并适配根目录 CI 与 Pages 路径。
- 压缩第 18 章重复的文本树与 Mermaid 表达；统一双层初学者阅读路径、FAQ 索引命名和第 20 章定位；将第 19 章主观排名式措辞改为可核查的条件化描述。
- 将 `specs/book/` 补充为当前有效的书稿维护、审阅和验收规范；V7 仅保留为历史需求基线。
- 重构为六部分学习路径：基础认知、构建首个 Agent、可靠运行、扩展与互操作、规模化与生产、案例与索引；MVP 前移至第 7 章，框架分析后移至第 19 章，并同步章节目录、链接、图号、学习路线和索引。
- 新增 `examples/agent-mvp-minimal/` 的 Python 与 TypeScript 最小纵向切片；保留 `coding-agent-mvp` 作为跨组件组合预览，并收紧其 MCP 能力声明。
- 复核当前数量：20 个章节、45 张 Mermaid 图、12 个独立示例工程、24 个双语言入口和 160 个 Markdown 表格；同步修正主页与 BookSpec 指标。
- 发布前复审：修复第 18 章的 Markdown 围栏，收紧第 19 章的产品断言，并移除 Memory、Context 预算、成本和模型示例中的不可泛化固定阈值与默认值。
- 复核并优化流程图的方向和连接语义：将长链流程改为纵向主链，修正 Tool 路由评分、MCP/Plugin 选型和 Memory/RAG 决策关系，并补充 Mermaid 图方向规范。
- 审校跨章节表格：收紧单轮 LLM/Agent、Built-in/MCP、Prompt/Instructions、Memory 与 Hook 的绝对表述；将模式、性能和框架能力表改为条件化的选型与试点核查表。
- 复审术语和安全示例：修正 Glossary 对 Instructions 与 MCP 的过度简化；完整 MVP 的 Shell 教学片段改为无 Shell 的 `echo` 允许列表，并明确生产环境的沙箱、授权与审计要求。
- 复审引用链路：补齐 19 篇论文、系统卡与研究文章的一手链接，并将 OpenAI Agents SDK 索引切换为正式文档入口。
- 复审读者路径与 FAQ：修复无依赖 Python 示例的运行说明；第 20 章的 Tool 选型、Memory 遗忘、重试、超时、随机性和趋势表述改为条件化、可验证的工程建议。

## [V7.0] - 2026-07-08

### 新增
- 初始化项目结构，包含 20 章完整骨架
- 第 1 章「AI Agent 简介与历史演进」完整内容
- 第 2 章「总体架构与生命周期」完整内容
- 第 6 章「Tools 与 Function Calling」完整内容
- 9 个示例工程（Python + TypeScript 双版本）
- Mermaid 图索引和架构图索引
- 完整术语表（Glossary）
- 常见问题汇总（FAQ）
- 参考文献索引
- 10 阶段学习路线
- CI/CD 流水线配置（Markdown Lint、Mermaid 校验、链接检查、Python 测试、构建检查）
- MkDocs Material 文档站点配置

### 变更
- 整合 V1~V6 全部需求，形成统一规格

### 规划中
- 第 3-5、7-20 章完整内容撰写
- 更多 Mermaid 图（目标 40+ 张）
- 更多可运行代码示例（目标 30+ 个）
- 框架源码分析（GitHub Copilot、Claude Code、Cursor 等）
- 多平台构建验证（GitBook、mdBook、Docusaurus）

---

## 版本历史概要

| 版本 | 核心贡献 |
|------|---------|
| V1 | 核心概念速览、架构图、常见混淆澄清 |
| V2~V3 | 章节规划、术语规范、工程化基础 |
| V4 | 历史演进、框架源码分析、设计模式、学习路线、最佳实践与反模式、事实验证 |
| V5 | 项目工程化、发布部署 |
| V6 | 开源项目结构、CI/CD、配套文档、示例工程、多平台支持 |
| V7（历史） | 整合 V1~V6 的需求基线；现行规范已迁移到 `specs/book/` |
