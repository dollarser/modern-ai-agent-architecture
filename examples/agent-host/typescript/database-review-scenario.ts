/** 数据库配置审查 Demo；业务能力与通用 AgentHost 分离。 */

import {
  AgentHost, type AgentConfig, type AgentDependencies,
} from "./assembly.js"

export const installDatabaseReview = (host: AgentHost): void => {
  host.initialMemory = {
    role: "preference", content: "数据库 配置 变更必须给出文件路径并经过审查",
  }
  host.skills.register({
    name: "config-review", keywords: ["配置", "config"],
    instructions: "先检索候选路径，再生成变更并交给子 Agent 复核。",
  })
  host.tools.register({
    name: "inspect_candidate", description: "检查首个候选", tags: ["read"],
    handler: (_arguments, context) => ({
      success: true, path: (context.results["1"].matches as string[])[0],
      finding: "发现数据库连接配置入口",
    }),
  })
  host.tools.register({
    name: "delegate_review", description: "Handoff 给审查子 Agent",
    tags: ["orchestration"],
    handler: (_arguments, context) => host.handoffs.handoff({
      task: "审查变更建议", parentRunId: context.runId,
      parentTraceId: context.traceId, parentSpanId: context.spanId, depth: 1,
    }),
  })
  host.tools.register({
    name: "compose_report", description: "组合最终报告", tags: ["output"],
    handler: (_arguments, context) => ({
      success: true,
      report: `${String(context.results["4"].proposal)}；${String(context.results["5"].review)}。`,
    }),
  })
  host.plugins.load({
    manifest: { name: "review-pack", version: "1.0.0", permissions: ["tools:register"] },
    tools: [
      {
        name: "summarize_matches", description: "汇总 MCP 候选", tags: ["analysis"],
        handler: (_arguments, context) => ({
          success: true, count: (context.results["1"].matches as string[]).length,
          summary: "找到 2 个候选文件",
        }),
      },
      {
        name: "propose_change", description: "生成配置变更建议", tags: ["write"],
        requiresApproval: true,
        prepare: (_arguments, context) => ({
          resolvedIntent: `建议更新 ${String(context.results["2"].path)}` +
            `（${String(context.results["3"].summary)}）`,
        }),
        handler: (_arguments, context) => ({
          success: true,
          proposal: `建议更新 ${String(context.results["2"].path)}` +
            `（${String(context.results["3"].summary)}）`,
        }),
      },
    ],
  })
}

export class DatabaseReviewAgent extends AgentHost {
  constructor(
    checkpointPath: string,
    config: Partial<AgentConfig> = {},
    dependencies: AgentDependencies = {},
  ) {
    super(checkpointPath, config, dependencies)
    installDatabaseReview(this)
  }
}
