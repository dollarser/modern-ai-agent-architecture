# 长期维护

## 更新触发条件

- MCP、模型 API、Agent SDK 或框架发生破坏性版本变更。
- 章节中的官方链接失效、产品能力发生变化，或读者报告事实错误。
- 示例无法运行，或输出不再与正文一致。

## 更新流程

1. 定位受影响主张和其来源；先确认是否为 Fact、Inference 或 Opinion。
2. 更新正文、版本范围、引用、示例和索引；不能确认时降级为历史说明或 To Be Verified。
3. 运行相关示例与 MkDocs 构建，按 Review Checklist 记录未运行项。
4. 在 `docs/CHANGELOG.md` 添加日期、范围和用户可感知的变化；涉及大范围审查时同步根目录审查记录。
5. 若章节、图、示例、测试、协议版本或能力闭环发生变化，同步 `11-current-baseline.md`；不要让 PRD 数量再次成为历史快照陷阱。

## 版本矩阵

对 MCP、A2A、ACP、OpenAI Agents SDK、Codex、Claude Code、Copilot、Cursor、LangGraph、Continue 及第 19 章快速变化的开源项目，至少记录“最后核查日期、官方来源、书中受影响章节”。不要把无法获得的内部版本号编造进矩阵。OpenTelemetry 只作为通用可观测性来源，不作为 Agent 项目或 Task/Run/Session 定义依据。

## 历史内容

旧 PRD、旧协议示例和产品快照可以保留，但必须标记其适用时间与替代来源。历史材料不得继续作为当前 API 或产品能力的唯一依据。
