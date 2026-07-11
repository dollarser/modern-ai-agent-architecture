import assert from "node:assert/strict"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import {
  DeterministicLLMAdapter,
  EnhancedAgent,
  FakeMCPClient,
  HookKind,
  HookPipeline,
  InMemoryMemoryBackend,
  RunState,
  ScriptedApprovalGate,
  ToolSource,
  ToolState,
  type Tool,
} from "./main.js"

const withCheckpoint = async (test: (path: string) => Promise<void>): Promise<void> => {
  const directory = mkdtempSync(join(tmpdir(), "enhanced-agent-test-"))
  try { await test(join(directory, "cp.json")) }
  finally { rmSync(directory, { recursive: true, force: true }) }
}

await withCheckpoint(async (checkpoint) => {
  const llm = new DeterministicLLMAdapter()
  const memory = new InMemoryMemoryBackend()
  const mcp = new FakeMCPClient()
  const approval = new ScriptedApprovalGate({ propose_change: true })
  const agent = new EnhancedAgent(checkpoint, {}, { llm, memory, mcpClient: mcp, approval })
  const result = await agent.run("查找数据库配置并给出变更建议", "complete")
  assert.equal(result.success, true)
  assert.equal(result.steps, 6)
  assert.equal(result.attempts, 6)
  assert.match(result.final, /src\/config\.ts/)
  assert.deepEqual(mcp.calls, ["search_catalog"])
  assert.equal(agent.tools.get("search_catalog").source, ToolSource.MCP)
  assert.equal(agent.tools.get("propose_change").source, ToolSource.Plugin)
  assert.equal(approval.requests.length, 1)
  assert.ok(agent.events.events.some((event) => event.topic === "handoff.created"))
  assert.ok(llm.lastContext.some((item) => item.includes("先检索候选路径")))
  assert.ok(llm.lastContext.some((item) => item.includes("必须给出文件路径")))
  assert.ok(memory.recent("complete").some((entry) => entry.role === "tool"))
})

await withCheckpoint(async (checkpoint) => {
  const gate = new ScriptedApprovalGate({ propose_change: true })
  const task = "查找数据库配置并给出变更建议"
  const first = await new EnhancedAgent(
    checkpoint, { interruptAfterSteps: 4 }, { approval: gate },
  ).run(task, "resume")
  const second = await new EnhancedAgent(checkpoint, {}, { approval: gate }).run(task, "resume")
  assert.equal(first.status, "interrupted")
  assert.equal(second.success, true)
  assert.equal(second.resumed, true)
  assert.equal(second.steps, 6)
  assert.equal(gate.requests.length, 1)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const gate = new ScriptedApprovalGate({ propose_change: false })
  const agent = new EnhancedAgent(checkpoint, {}, { approval: gate })
  agent.tools.register({
    name: "propose_change",
    description: "高风险变更",
    source: ToolSource.Plugin,
    sourceName: "review-pack",
    requiresApproval: true,
    handler: () => { calls += 1; return { success: true, proposal: "不应出现" } },
  }, true)
  const result = await agent.run("查找数据库配置并给出变更建议", "reject")
  assert.equal(result.success, false)
  assert.equal(calls, 0)
  assert.match(result.error ?? "", /审批拒绝/)
  assert.ok(result.trace.some((item) => item.event === "on_tool_error"))
})

await withCheckpoint(async (checkpoint) => {
  const hooks = new HookPipeline()
  hooks.register("after_plan", {
    name: "metrics",
    callback: () => { throw new Error("metrics down") },
  })
  const observed = await new EnhancedAgent(checkpoint, {}, { hooks })
    .run("查找数据库配置并给出变更建议", "observer")
  assert.equal(observed.success, true)
  assert.ok(observed.trace.some((item) => item.event === "observer_error"))
})

await withCheckpoint(async (checkpoint) => {
  const hooks = new HookPipeline()
  hooks.register("before_tool", {
    name: "policy",
    kind: HookKind.Guard,
    priority: 1,
    callback: () => { throw new Error("policy denied") },
  })
  const denied = await new EnhancedAgent(checkpoint, {}, { hooks })
    .run("查找数据库配置并给出变更建议", "guard")
  assert.equal(denied.success, false)
  assert.match(denied.error ?? "", /Guardrail/)
  assert.equal(denied.attempts, 0)
})

await withCheckpoint(async (checkpoint) => {
  const agent = new EnhancedAgent(checkpoint)
  agent.tools.register({
    name: "disabled",
    description: "disabled",
    state: ToolState.Disabled,
    handler: () => ({ success: true }),
  })
  assert.equal(agent.router.available().some((tool) => tool.name === "disabled"), false)
  assert.throws(() => agent.router.resolve("disabled"), /Tool 不可用/)

  let hookCalls = 0
  agent.plugins.load({
    manifest: { name: "temporary", version: "1.0.0" },
    skills: [{ name: "temporary-skill", keywords: ["临时"], instructions: "临时指令" }],
    hooks: [{
      event: "custom",
      definition: { callback: () => { hookCalls += 1 } },
    }],
  })
  const probe = new RunState("probe", "临时任务", [])
  agent.hooks.emit("custom", {}, probe)
  assert.equal(hookCalls, 1)
  assert.equal(agent.skills.match("临时任务").length, 1)
  agent.plugins.unload("temporary")
  agent.hooks.emit("custom", {}, probe)
  assert.equal(hookCalls, 1)
  assert.equal(agent.skills.match("临时任务").length, 0)

  agent.plugins.unload("review-pack")
  assert.equal(agent.tools.list().some((tool) => tool.name === "propose_change"), false)
  assert.equal(agent.tools.get("search_catalog").source, ToolSource.MCP)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const flaky: Tool = {
    name: "search_catalog",
    description: "flaky",
    handler: () => {
      calls += 1
      return calls === 1
        ? { success: false, error: "temporary", retryable: true }
        : { success: true, matches: ["src/config.ts", "src/db.ts"] }
    },
  }
  const agent = new EnhancedAgent(checkpoint)
  agent.tools.register(flaky, true)
  const result = await agent.run("查找数据库配置并给出变更建议", "retry")
  assert.equal(result.success, true)
  assert.equal(result.attempts, 7)
  assert.equal(result.results["1"].attempts, 2)
})

console.log("enhanced-agent TypeScript tests: OK")
