"""数据库配置审查 Demo；业务能力与通用 AgentHost 分离。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from assembly import (
    AgentConfig, AgentHost, ExecutionContext, HandoffRequest, MemoryEntry,
    Plugin, PluginManifest, Skill, Tool, ToolResult,
)


def install_database_review(host: AgentHost) -> None:
    host.initial_memory = MemoryEntry(
        "preference", "数据库 配置 变更必须给出文件路径并经过审查"
    )
    host.skills.register(Skill(
        "config-review", ("配置", "config"),
        "先检索候选路径，再生成变更并交给子 Agent 复核。",
    ))
    host.tools.register(Tool(
        "inspect_candidate", "检查首个候选", lambda _args, ctx: {
            "success": True, "path": ctx.results[1]["matches"][0],
            "finding": "发现数据库连接配置入口",
        }, tags=("read",),
    ))

    async def delegate(_arguments: dict[str, Any], context: ExecutionContext) -> ToolResult:
        return await host.handoffs.handoff(HandoffRequest(
            task="审查变更建议", parent_run_id=context.run_id,
            parent_trace_id=context.trace_id, parent_span_id=context.span_id,
        ))

    host.tools.register(Tool(
        "delegate_review", "Handoff 给审查子 Agent", delegate,
        tags=("orchestration",),
    ))
    host.tools.register(Tool(
        "compose_report", "组合最终报告", lambda _args, ctx: {
            "success": True,
            "report": f"{ctx.results[4]['proposal']}；{ctx.results[5]['review']}。",
        }, tags=("output",),
    ))
    host.plugins.load(Plugin(
        PluginManifest("review-pack", "1.0.0", ("tools:register",)),
        tools=[
            Tool("summarize_matches", "汇总 MCP 候选", lambda _args, ctx: {
                "success": True, "count": len(ctx.results[1]["matches"]),
                "summary": "找到 2 个候选文件",
            }, tags=("analysis",)),
            Tool("propose_change", "生成配置变更建议", lambda _args, ctx: {
                "success": True,
                "proposal": f"建议更新 {ctx.results[2]['path']}（{ctx.results[3]['summary']}）",
            }, prepare=lambda _args, ctx: {
                "resolved_intent": (
                    f"建议更新 {ctx.results[2]['path']}（{ctx.results[3]['summary']}）"
                )
            }, tags=("write",), requires_approval=True),
        ],
    ))


class DatabaseReviewAgent(AgentHost):
    """数据库配置审查应用：通用 Host + 显式场景安装。"""

    def __init__(self, checkpoint_path: str | Path, config: AgentConfig | None = None, **kwargs: Any) -> None:
        super().__init__(checkpoint_path, config, **kwargs)
        install_database_review(self)
