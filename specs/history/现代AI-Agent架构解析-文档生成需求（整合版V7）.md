# 《现代 AI Agent 架构解析》文档生成需求（整合版 V7）

> **状态：已废止，仅作历史记录。** 当前维护规范见 [`../book/README.md`](../book/README.md)，当前章节目录见 [`../../docs/SUMMARY.md`](../../docs/SUMMARY.md)。本文中的章节建议、目录结构、示例列表、数量指标和 MVP → Enhanced → Production 路线不得作为当前验收依据。

> **定位：** 开源技术图书项目规范（Book + Documentation Project Specification）
>
> **目标：** 指导 AI 生成一本可长期维护、可持续演进、可发布到 GitHub Pages 的现代 AI Agent 技术参考书，定位出版级品质，而不仅是一篇 Markdown 文档。
---

# 一、核心概念速览

> 本节从 Agent 运行流程出发，建立全书的概念地图。所有后续章节均围绕此框架展开。

## 1.1 整体架构

```text
User
 │
Prompt
 │
Instructions
 │
Agent
 ├── Reasoning
 ├── Planning
 ├── Memory
 └── Tool Calling
      ├── Built-in Tools
      └── MCP Tools
           │
      Observation
           │
         Hooks
           │
      下一轮 Reasoning
```

## 1.2 Agent 主循环

```text
Prompt
 ↓
Reasoning
 ↓
Planning
 ↓
(按需读取 Skills)
 ↓
Tool Calling
 ↓
Observation
 ↓
Reasoning ...
```

## 1.3 概念速查表

| 概念 | 本质 | 读取/调用时机 |
|------|------|--------------|
| Prompt | 当前任务目标 | 任务开始时读取 |
| Instructions | 全局长期规则 | Session 初始化，始终在上下文 |
| Skills | 可复用工作流模板 | Agent 判断匹配时读取，不真正调用 |
| Tools | 可执行的执行接口 | Planning 完成后调用 |
| Built-in Tool | Agent 自带能力 | 无需安装，直接调用 |
| MCP | 连接 LLM 应用与外部上下文和能力的开放协议 | 需要接入 Tool、Resource、Prompt 等外部能力时使用 |
| Hooks | 生命周期事件 | 特定事件前后触发 |

## 1.4 常见混淆澄清

| 对比 | 区别 |
|------|------|
| Prompt vs Instructions | Prompt 是任务目标，Instructions 是长期规则 |
| Skill vs Tool | Skill 告诉 Agent 怎么做（工作流），Tool 真正去做（执行） |
| Tool vs MCP | Tool 是可执行能力，MCP 是连接外部 Tool、Resource、Prompt 等能力的协议 |
| Tool vs Function Calling | Tool 是能力，Function Calling 是调用方式/协议 |

---

# 二、项目定位与总体目标

## 2.1 定位

最终交付物不是单个 Markdown，而是一个完整的开源文档工程，具备：

- 电子书（Book）
- 文档网站（Documentation）
- 可运行示例（Examples）
- 图表资源（Assets）
- 自动化校验（CI）
- 持续维护能力（Maintenance）

## 2.2 覆盖范围

文档应覆盖：

- AI Agent 基础原理
- Prompt、Instructions、Reasoning、Planning、Memory
- Tools、Function Calling、Observation
- MCP、Plugin、Hooks、Skills
- Runtime、Tool Registry
- GitHub Copilot、Claude Code、Cursor 等主流 Coding Agent 架构
- Agent 设计模式
- Agent MVP 与增强版实现
- 工程实践、最佳实践、反模式
- 历史演进与未来趋势

## 2.3 目标读者

- 初学者：希望系统理解 AI Agent 架构
- AI 应用开发者：需要集成 Agent 能力
- Agent Framework 开发者：需要设计或扩展框架
- IDE 插件开发者：需要理解 Coding Agent 内部机制
- 企业平台开发者：需要评估和选型 Agent 方案

---

# 三、历史演进要求

> 要求以时间线说明架构为什么演进为今天的形态，而不仅介绍最终结果。

## 3.1 演进路径

```
LLM → Prompt Engineering → Function Calling → OpenAI Plugins
  → ReAct → Tool Calling → Agent Runtime → Memory → MCP → Modern Coding Agent
```

## 3.2 每个阶段必须回答

- **出现原因：** 为什么需要这个阶段
- **解决了什么问题：** 核心突破是什么
- **为什么继续演进：** 局限性在哪里
- **对现代 Agent 的影响：** 留下了什么遗产

---

# 四、历史版本的继承原则

V1~V6 是设计素材与决策记录，而不是必须逐条实现的合同。维护时应保留以下稳定目标：

- 文档目标与章节规划
- 生命周期分析
- 历史演进
- 事实准确性
- 引用规范
- FAQ
- 最佳实践与反模式
- Mermaid 图规范
- 示例规范
- 术语规范
- 版本管理
- 学习路线
- 框架对比
- 源码分析
- 设计模式
- 可维护性要求

遇到旧版本与当前协议、官方文档或 `BookSpec-1.0` 冲突时，按以下优先级处理：当前官方规范 > `BookSpec-1.0` > 本 V7 > 更早历史版本。冲突内容应更新或加注历史范围，不能为了“继承”而保留已失效的产品能力或协议细节。

---

# 五、章节规划

## 5.1 推荐章节（15~20 章）

1. AI Agent 简介与历史演进
2. 总体架构与生命周期
3. Prompt 与 Instructions
4. Context 管理
5. Reasoning 与 Planning
6. Tools 与 Function Calling
7. Skills：可复用工作流
8. Hooks：生命周期事件
9. MCP：模型上下文协议
10. Plugin 体系
11. Memory：状态与记忆管理
12. Runtime：Agent 运行时
13. Tool Registry：工具注册与调度
14. Agent MVP：从零实现
15. 主流框架架构分析
16. Agent 设计模式
17. 增强版 Agent 实现
18. 工程实践与生产部署
19. 最佳实践与反模式汇总
20. FAQ 与延伸阅读

## 5.2 每章统一结构

每章应根据章节类型包含以下要素。学习目标、背景/核心概念、参考资料与 Checklist 为必备项；实现章节必须有可运行示例；历史、比较和理论章节可用可复核的图表、伪代码或案例替代可运行代码，并明确标注。

1. **学习目标：** 本章要掌握什么
2. **前置知识：** 需要先阅读哪些章节
3. **难度等级：** ⭐ ~ ⭐⭐⭐⭐⭐
4. **背景：** 为什么需要这个概念
5. **核心概念：** What / Why / How / When / Relationship
6. **生命周期位置：** 在 Agent 主循环中的位置
7. **架构图：** 在结构、时序或状态难以用文字表达时提供 Mermaid 图
8. **示例或案例：** 实现章节提供最小可运行示例并注明环境、依赖、输出；非实现章节提供可复核案例、图表或伪代码
9. **最佳实践：** 适用时给出推荐做法
10. **反模式：** 适用时说明常见错误与风险
11. **FAQ：** 容易产生歧义时给出问答，或链接到汇总 FAQ
12. **官方参考：** 官方文档、源码、RFC、论文
13. **延伸阅读：** 推荐进一步学习材料
14. **本章 Checklist：** 自查清单

## 5.3 每章标注

- **难度等级：** ⭐（入门）~ ⭐⭐⭐⭐⭐（专家）
- **来源可信度：** 官方规范 / 源码 / 论文 / 推导 / 观点

---

# 六、写作规范

## 6.1 写作原则

每个知识点必须说明：

```
Why → What → How → When → Trade-off
```

即：为什么需要 → 是什么 → 怎么做 → 什么时候用 → 有什么取舍。

## 6.2 术语规范

- 统一中英文术语对照
- 首次出现标注英文原文
- 全书术语保持一致
- 建立完整术语表（Glossary）

## 6.3 引用规范

优先级从高到低：

1. 官方文档
2. 官方源码
3. RFC / 规范
4. 学术论文
5. 官方博客
6. 社区共识

禁止无依据推断。

## 6.4 AI 生成约束

**必须区分四类信息：**

| 类型 | 标识 | 说明 |
|------|------|------|
| Fact | 事实 | 可被官方文档/源码验证 |
| Inference | 推导 | 基于已知事实的逻辑推断，必须说明依据 |
| Opinion | 作者观点 | 主观判断，需标注 |
| To Be Verified | 待验证 | 信息存疑，需后续确认 |

**严格禁止编造：**

- API 接口
- 协议字段
- 官方实现细节
- 产品能力

对于推导必须说明推导依据和逻辑链。

---

# 七、图示与代码规范

## 7.1 Mermaid 图规范

- 统一使用 Mermaid 格式
- 图编号：`图 X-Y`（X=章节号，Y=图序号）
- 每张图包含标题和说明
- 覆盖类型：架构图、流程图、时序图、状态图、类图
- 目标：全书 40+ 张 Mermaid 图

## 7.2 代码规范

- 语言：Python 为主
- 示例按风险分级：示例工程必须可运行；章节内为说明而截取的代码必须标明依赖或链接到完整工程；伪代码不得伪装成可运行代码
- 每个示例注明：
  - 运行环境
  - 依赖版本
  - 预期输出
- 目标：示例工程覆盖核心实现路径；现行基线与验收规则见 `BookSpec-1.0/08-acceptance-criteria.md`

---

# 八、事实验证机制

## 8.1 来源标注

每个重要结论标注来源类型：

- 官方文档
- 官方源码
- RFC / 规范
- 学术论文
- 推导分析
- 作者观点

## 8.2 争议处理

存在争议时给出不同观点，不强行统一。

---

# 九、Agent 设计模式

## 9.1 需覆盖的设计模式

系统介绍以下模式：

| 模式 | 核心思想 |
|------|---------|
| ReAct | Reasoning + Acting 交替 |
| Plan-and-Execute | 先规划再执行 |
| Reflection | 自我反思与修正 |
| Multi-Agent | 多 Agent 协作 |
| Tool Router | 智能路由到合适 Tool |
| Tool Registry | 统一 Tool 注册与发现 |
| Plugin Registry | 插件化扩展 |
| Event Bus | 事件驱动架构 |
| Hook Pipeline | 生命周期拦截链 |
| Workflow Orchestration | 工作流编排 |

## 9.2 每种模式包含

- 原理
- 优缺点
- 适用场景
- 最小实现（可运行代码）

---

# 十、主流框架架构分析

## 10.1 需分析的框架

至少分析以下框架：

- GitHub Copilot
- Claude Code
- OpenAI Agents SDK
- LangGraph
- Continue
- Roo Code（如适用）

## 10.2 重点分析维度

每个框架分析以下维度：

- Runtime
- Planner
- Tool Registry
- Memory
- MCP Client
- Hooks
- Skills
- Context 管理

## 10.3 来源标注

注明哪些来源于官方实现，哪些属于推导分析。

---

# 十一、实现路线图

## 11.1 从零学习路线

提供从零学习 Agent 的实践路线：

| 阶段 | 主题 | 学习目标 | 推荐实践 |
|------|------|---------|---------|
| 1 | Prompt | 理解 Prompt 结构 | 编写有效 Prompt |
| 2 | Function Calling | 理解模型调用函数 | 实现 Function Call |
| 3 | Tool | 理解 Tool 抽象 | 封装 Tool |
| 4 | Memory | 理解状态管理 | 实现 Memory 层 |
| 5 | Planning | 理解任务规划 | 实现 Planner |
| 6 | Runtime | 理解运行时 | 实现 Agent Loop |
| 7 | MCP | 理解协议扩展 | 实现 MCP Client/Server |
| 8 | Hooks | 理解生命周期 | 实现 Hook 系统 |
| 9 | Skills | 理解工作流复用 | 实现 Skill 加载 |
| 10 | 完整 Agent | 整合所有组件 | 实现 Coding Agent MVP |

## 11.2 每阶段说明

- 学习目标
- 推荐资料（官方文档、论文、博客）
- 推荐实践（动手项目）
- 推荐项目（参考开源实现）

---

# 十二、最佳实践与反模式

## 12.1 按适用性提供

实现和工程章节应给出最佳实践与反模式；纯历史、索引或 FAQ 章节可通过链接到权威章节避免重复。

### Best Practices（最佳实践）

推荐做法及理由。

### Anti Patterns（反模式）

常见错误及风险说明。

## 12.2 典型反模式示例

| 反模式 | 风险 | 推荐方案 |
|--------|------|---------|
| Prompt 承担 Instructions 职责 | 上下文膨胀，不可维护 | 分离 Prompt 和 Instructions |
| Tool 数量失控 | 模型选择困难，延迟增加 | 合理分组，动态注册 |
| Memory 无限增长 | 上下文溢出 | 分级存储，定期清理 |
| 将 Skill 当 Tool | 架构混淆 | 明确 Skill 是工作流，Tool 是执行 |
| 将 MCP 当 Agent | 职责不清 | MCP 提供外部上下文和能力的互操作，Agent 负责推理与编排 |
| Hook 承担业务逻辑 | 耦合严重 | Hook 只做横切关注点 |

---

# 十三、项目交付结构

## 13.1 目录结构

```text
book/
├── README.md
├── SUMMARY.md
├── PREFACE.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── glossary/
│   └── Glossary.md
├── faq/
│   └── FAQ.md
├── references/
│   └── References.md
├── roadmap/
│   └── Roadmap.md
├── chapters/
│   ├── 01-introduction/
│   ├── 02-architecture/
│   └── ...
├── examples/
│   ├── hello-agent/
│   ├── tool-calling/
│   ├── memory/
│   ├── planning/
│   ├── hooks/
│   ├── mcp-client/
│   ├── mcp-server/
│   ├── tool-registry/
│   └── coding-agent-mvp/
├── mermaid/
│   └── MermaidIndex.md
├── assets/
├── diagrams/
├── docs/
├── scripts/
├── tests/
└── .github/workflows/
    ├── markdown-lint.yml
    ├── mermaid-check.yml
    ├── link-check.yml
    ├── python-test.yml
    └── build-check.yml
```

## 13.2 支持平台

- MkDocs Material
- GitHub Pages

其他生成器可作为迁移目标，不作为每次发布的验收门槛；当前唯一受支持的构建链路是 MkDocs Material + GitHub Pages。

---

# 十四、示例工程

## 14.1 examples/ 目录内容

每个示例包含独立 README，说明：

- 学习目标
- 前置知识
- 运行方式
- 预期输出

## 14.2 推荐示例列表

| 示例 | 名称 | 覆盖概念 |
|------|------|---------|
| hello-agent | 最小 Agent | Prompt → Reasoning → Output |
| tool-calling | Tool 调用 | Function Calling, Tool 抽象 |
| memory | 记忆管理 | Memory 读写，上下文窗口 |
| planning | 任务规划 | Plan-and-Execute |
| hooks | 生命周期 | Before/After Hook |
| mcp-client | MCP 客户端 | MCP 协议，Tool 发现 |
| mcp-server | MCP 服务端 | Tool 暴露，协议实现 |
| tool-registry | Tool 注册中心 | 动态注册，路由 |
| coding-agent-mvp | 完整 Agent | 所有组件整合 |

---

# 十五、自动化校验

## 15.1 CI 流水线

.github/workflows 包含：

- **Markdown Lint：** 统一格式
- **Mermaid 校验：** 图语法正确
- **链接检查：** 无死链
- **Python 示例运行：** 所有示例可执行
- **文档构建检查：** MkDocs 构建通过

---

# 十六、配套文档

生成以下配套文档：

| 文档 | 内容 |
|------|------|
| Glossary.md | 完整术语表，中英文对照 |
| FAQ.md | 常见问题汇总 |
| References.md | 官方参考文献索引 |
| ArchitectureIndex.md | 架构图索引 |
| MermaidIndex.md | 所有 Mermaid 图索引 |
| CodeExamples.md | 所有代码示例索引 |
| Roadmap.md | 版本路线图 |

---

# 十七、发布要求

## 17.1 支持发布方式

- GitHub Pages
- MkDocs Material + GitHub Pages

## 17.2 交付物

- 电子书（多格式）
- 文档网站
- 可运行示例仓库
- 图表资源
- 自动化校验流水线

## 17.3 提供部署说明

每种发布方式提供完整部署步骤。

---

# 十八、维护要求

## 18.1 维护策略

- 版本矩阵：记录各框架/协议已验证版本
- Changelog：每次更新记录变更
- 更新策略：明确何时更新、如何更新
- 兼容性说明：版本间兼容性

## 18.2 可扩展性

支持未来新增：

- 新模型
- 新协议（如 MCP 后续版本）
- 新 Agent Framework

---

# 十九、覆盖矩阵

## 19.1 概念覆盖矩阵

所有核心概念必须映射到章节、示例、图表、FAQ、引用和代码：

```
Prompt、Instructions、Context、Reasoning、Planning、
Observation、Memory、Tool、Function Calling、Skill、
Hook、Plugin、MCP、Runtime、Tool Registry、Agent
```

## 19.2 生命周期覆盖矩阵

```
Load → Read → Reasoning → Planning → Execute → Observe → Finish
```

## 19.3 框架覆盖矩阵

```
GitHub Copilot、Claude Code、Cursor、OpenAI Agents SDK、
LangGraph、Continue
```

## 19.4 实现覆盖矩阵

```
MVP → Enhanced → Production
```

## 19.5 证据覆盖矩阵

```
官方文档 → 官方源码 → RFC → 论文 → 社区 → 推导
```

## 19.6 需求追溯矩阵（RTM）

每个需求点可追溯到具体章节、示例和图表。

---

# 二十、验收标准

## 20.1 量化指标

| 指标 | 目标 |
|------|------|
| 规模 | 以结构完整、可导航、无明显重复和可维护为准；不再沿用短篇字数上限 |
| 章节数 | 15 ~ 20 章 |
| Mermaid 图 | 40+ 张 |
| 可运行代码示例 | 以独立工程的可运行性和覆盖价值为准；当前基线为 9 个主题、18 个双语言入口 |
| 对比表格 | 30+ 个 |
| 完整术语表 | 1 份 |
| FAQ | 覆盖所有核心概念 |
| 官方参考文献 | 每章至少一个可追溯来源；协议和产品事实应直接链接官方资料 |
| 历史演进 | 完整时间线 |
| 源码分析 | 6+ 框架 |
| 学习路线 | 10 阶段 |
| MVP 实现 | 完整可运行 |
| 增强版 Agent | 至少 1 个增强版 |
| 工程实践 | 覆盖 CI/CD、测试、部署 |

## 20.2 质量定位

> 一本可持续维护、工程化、事实可验证、可发布、可扩展的《现代 AI Agent 架构解析》开源技术参考书，而不是一篇介绍性博客。

---

# 二十一、Review Checklist

全书完成后必须通过以下检查：

- [ ] 覆盖所有核心概念（对照 Coverage Matrix）
- [ ] 需要图示的章节包含 Mermaid 图，图文一致
- [ ] 易混淆主题包含 FAQ 或链接到汇总 FAQ
- [ ] 每章包含至少一个可追溯来源；协议和产品事实使用直接官方来源
- [ ] 实现章节包含可运行代码示例；非实现章节提供可复核案例、图表或伪代码
- [ ] 术语全书统一
- [ ] 图文一致
- [ ] 无明显重复
- [ ] 无前后矛盾
- [ ] Coverage Matrix 完整（概念 / 生命周期 / 框架 / 实现 / 证据）
- [ ] 区分 Fact / Inference / Opinion / To Be Verified
- [ ] 所有代码示例可运行
- [ ] 无编造 API、协议字段或产品能力
- [ ] 所有链接有效
- [ ] MkDocs 构建通过，GitHub Pages 发布配置可用
- [ ] Changelog 已更新
- [ ] 术语表完整

---

# 二十二、最小 Agent MVP 参考

## 22.1 目录结构

```text
agent/
├── prompt.py          # Prompt 管理
├── instructions.py    # Instructions 管理
├── planner.py         # 规划器
├── memory.py          # 记忆管理
├── skill_loader.py    # Skill 加载
├── tool_registry.py   # Tool 注册中心
├── tools/             # Built-in Tools
├── mcp/               # MCP 集成
├── hooks/             # Hook 系统
└── runtime.py         # 主循环
```

## 22.2 执行流程

```text
Prompt
 ↓
Instructions
 ↓
Planner
 ↓
Skill Loader
 ↓
Tool Registry
 ↓
Built-in / MCP Tool
 ↓
Observation
 ↓
Hook
 ↓
Finish
```

---

# 二十三、版本历史

| 版本 | 核心贡献 |
|------|---------|
| V1 | 核心概念速览、架构图、常见混淆澄清 |
| V2~V3 | 章节规划、术语规范、工程化基础 |
| V4 | 历史演进、框架源码分析、设计模式、学习路线、最佳实践与反模式、事实验证 |
| V5 | 项目工程化、发布部署 |
| V6 | 开源项目结构、CI/CD、配套文档、示例工程、多平台支持 |
| V7（本版） | 整合 V1~V6 全部优点，融合 BookSpec-1.0 模块化规范框架，形成完整统一的需求规格 |

---

> **最终定位：** 一本可持续维护、工程化、事实可验证、可发布、可扩展的《现代 AI Agent 架构解析》开源技术参考书。
