# Coverage Matrix

覆盖矩阵用于发现缺口，而不是要求每个概念都同时拥有图、代码和 FAQ。维护时至少记录下列追溯关系：

| 对象 | 必须映射到 |
|------|------------|
| 核心概念 | 主章节、Glossary 条目、至少一个来源或明确的推导标签 |
| 实现概念 | 可运行示例或明确标记的教学片段 |
| 协议 / 产品事实 | 版本或核查日期、直接官方来源 |
| Mermaid 图 | 所属章节和解释它的正文小节 |
| FAQ | 对应主章节，避免与正文漂移 |

核心概念至少包括 Prompt、Instructions、Context、Reasoning、Planning、Memory、Tool、Function Calling、Skill、Hook、Plugin、MCP、Connector、Agent/Subagent、ExpertProfile、AgentHost、Runtime、Tool Registry，以及 Task/Run/Session/Checkpoint/Trace。产品分析还必须单独维护“公开事实 / 推导 / 观点”的证据状态。

工程实践覆盖 Prompt、Context、Tool、Workflow、Harness、Loop 与 Agentic Engineering。它们是正交且逐步扩大的关注面，不得写成互相淘汰的严格演进阶段；新兴术语必须标明成熟度。
