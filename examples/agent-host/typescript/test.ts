import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import {
  DeterministicLLMAdapter,
  ConfigScope,
  DefaultPolicyEngine,
  AutoApproveGate,
  AgentHost,
  DatabaseReviewAgent,
  EventBus,
  MCPToolAdapter,
  FakeMCPClient,
  HookKind,
  HookPipeline,
  InMemoryMemoryBackend,
  RunState,
  PolicyDecision,
  ScriptedApprovalGate,
  ToolSource,
  ToolState,
  type Tool,
  type ToolResult,
  type ExecutionContext,
  type MCPClient,
  type Plugin,
  type Skill,
} from "./main.js"
import { CodingAgent, Workspace } from "./coding-scenario.js"
import { ConversationApplication, JsonSessionStore } from "./application.js"
import { CatalogPluginProvider, CatalogSkillProvider, ManagerMCPProvider } from "./installed-adapters.js"

const withCheckpoint = async (test: (path: string) => Promise<void>): Promise<void> => {
  const directory = mkdtempSync(join(tmpdir(), "agent-host-test-"))
  try { await test(join(directory, "cp.json")) }
  finally { rmSync(directory, { recursive: true, force: true }) }
}

await withCheckpoint(async (checkpoint) => {
  const host = new AgentHost(checkpoint)
  assert.equal(host.skills.contains("config-review"), false)
  assert.equal(host.tools.contains("inspect_candidate"), false)
  assert.equal(host.initialMemory, undefined)
  await host.mcp.registerTools(host.tools)
  assert.equal(host.tools.get("search_catalog").name, "catalog-server.search_catalog")
  assert.equal(host.tools.listAliases().search_catalog, "catalog-server.search_catalog")
  await new MCPToolAdapter(new FakeMCPClient(), "other-server").registerTools(host.tools)
  assert.equal(host.tools.contains("other-server.search_catalog"), true)
  assert.equal(host.tools.get("search_catalog").name, "catalog-server.search_catalog")
})

await withCheckpoint(async (checkpoint) => {
  const llm = new DeterministicLLMAdapter()
  const memory = new InMemoryMemoryBackend()
  const mcp = new FakeMCPClient()
  const approval = new ScriptedApprovalGate({ propose_change: true })
  const events = new EventBus()
  const agent = new DatabaseReviewAgent(
    checkpoint, {}, { llm, memory, mcpClient: mcp, approval, eventBus: events },
  )
  const result = await agent.run(
    "查找数据库配置并给出变更建议", "complete",
    ["user: 上一轮已经确认只读检查"],
  )
  assert.equal(result.success, true)
  assert.equal(result.steps, 6)
  assert.equal(result.attempts, 6)
  assert.match(result.final, /src\/config\.ts/)
  assert.deepEqual(mcp.calls, ["search_catalog"])
  assert.equal(agent.tools.get("search_catalog").source, ToolSource.MCP)
  assert.equal(agent.tools.get("propose_change").source, ToolSource.Plugin)
  assert.equal(approval.requests.length, 1)
  assert.ok(events.events.some((event) => event.topic === "handoff.created"))
  assert.ok(llm.lastContext.some((item) => item.includes("先检索候选路径")))
  assert.ok(llm.lastContext.some((item) => item.includes("必须给出文件路径")))
  assert.ok(llm.lastContext.includes("user: 上一轮已经确认只读检查"))
  assert.ok(memory.recent("complete").some((entry) => entry.role === "tool"))
  const replay = await agent.run("查找数据库配置并给出变更建议", "complete")
  assert.equal(replay.success, true)
  assert.equal(replay.resumed, false)
  assert.equal(replay.replayed, true)
})

await withCheckpoint(async (checkpoint) => {
  const gate = new ScriptedApprovalGate({ propose_change: true })
  const task = "查找数据库配置并给出变更建议"
  const first = await new DatabaseReviewAgent(
    checkpoint, { interruptAfterSteps: 4 }, { approval: gate },
  ).run(task, "resume")
  const second = await new DatabaseReviewAgent(checkpoint, {}, { approval: gate }).run(task, "resume")
  assert.equal(first.status, "interrupted")
  assert.equal(second.success, true)
  assert.equal(second.resumed, true)
  assert.equal(second.steps, 6)
  assert.equal(gate.requests.length, 1)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const gate = new ScriptedApprovalGate({ propose_change: false })
  const agent = new DatabaseReviewAgent(checkpoint, {}, { approval: gate })
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
  const observed = await new DatabaseReviewAgent(
    checkpoint, {}, { hooks, approval: new AutoApproveGate() },
  )
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
  const denied = await new DatabaseReviewAgent(checkpoint, {}, { hooks })
    .run("查找数据库配置并给出变更建议", "guard")
  assert.equal(denied.success, false)
  assert.match(denied.error ?? "", /Guardrail/)
  assert.equal(denied.attempts, 0)
})

await withCheckpoint(async (checkpoint) => {
  const agent = new DatabaseReviewAgent(checkpoint)
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
    manifest: {
      name: "temporary",
      version: "1.0.0",
      permissions: ["skills:register", "hooks:register"],
    },
    skills: [{ name: "temporary-skill", keywords: ["临时"], instructions: "临时指令" }],
    hooks: [{
      event: "custom",
      definition: { callback: () => { hookCalls += 1 } },
    }],
  })
  const probe = new RunState("probe", "临时任务", [])
  await agent.hooks.emit("custom", {}, probe)
  assert.equal(hookCalls, 1)
  assert.equal(agent.skills.match("临时任务").length, 1)
  agent.plugins.unload("temporary")
  await agent.hooks.emit("custom", {}, probe)
  assert.equal(hookCalls, 1)
  assert.equal(agent.skills.match("临时任务").length, 0)

  agent.plugins.unload("review-pack")
  assert.equal(agent.tools.list().some((tool) => tool.name === "propose_change"), false)
  await agent.mcp.registerTools(agent.tools)
  assert.equal(agent.tools.get("search_catalog").source, ToolSource.MCP)
})

await withCheckpoint(async (checkpoint) => {
  const agent = new DatabaseReviewAgent(checkpoint)
  assert.throws(() => agent.plugins.load({
    manifest: { name: "underprivileged", version: "1.0.0" },
    tools: [{ name: "extra", description: "extra", handler: () => ({ success: true }) }],
  }), /权限不足/)
  assert.equal(agent.tools.contains("extra"), false)

  assert.throws(() => agent.plugins.load({
    manifest: { name: "conflicting", version: "1.0.0", permissions: ["tools:register"] },
    tools: [
      { name: "new-before-conflict", description: "new", handler: () => ({ success: true }) },
      { name: "inspect_candidate", description: "conflict", handler: () => ({ success: true }) },
    ],
  }), /资源冲突/)
  assert.equal(agent.tools.contains("new-before-conflict"), false)
})

await withCheckpoint(async (checkpoint) => {
  const agent = new DatabaseReviewAgent(checkpoint, {}, { approval: new AutoApproveGate() })
  agent.tools.register({
    name: "validated",
    description: "validated",
    parameters: {
      type: "object",
      required: ["value"],
      properties: { value: { type: "string" } },
      additionalProperties: false,
    },
    handler: (arguments_) => ({ success: true, value: arguments_.value }),
  })
  const context: ExecutionContext = {
    task: "task", results: {}, runId: "run", traceId: "trace-run", spanId: "step-1",
  }
  await assert.rejects(agent.router.execute("validated", {}, context), /缺少必填字段/)
  await assert.rejects(agent.router.execute("validated", { value: 1 }, context), /类型错误/)

  await agent.mcp.registerTools(agent.tools)
  await new MCPToolAdapter(new FakeMCPClient(), "other-server").registerTools(agent.tools)
  assert.equal(agent.tools.contains("other-server.search_catalog"), true)

  const events = new EventBus()
  events.subscribe("topic", () => { throw new Error("down") }, HookKind.Observer, "metrics")
  await events.publish("topic", {})
  assert.equal(events.events.at(-1)?.topic, "observer.error")

  const result = await agent.run("查找数据库配置并给出变更建议", "trace-context")
  assert.equal(result.results["5"].parentTraceId, "trace-trace-context")
  assert.equal(result.results["5"].parentSpanId, "step-5")
})

await withCheckpoint(async (checkpoint) => {
  const hooks = new HookPipeline()
  const observed: string[] = []
  const eventBus = new EventBus()
  const eventTopics: string[] = []
  eventBus.subscribe("task.started", async (event) => {
    await Promise.resolve()
    eventTopics.push(String(event.topic))
  })
  const memoryDelegate = new InMemoryMemoryBackend()
  const asyncMemory = {
    append: async (runId: string, entry: { role: string; content: string }) =>
      memoryDelegate.append(runId, entry),
    recent: async (runId: string, limit?: number) =>
      memoryDelegate.recent(runId, limit),
    remember: async (namespace: string, entry: { role: string; content: string }) =>
      memoryDelegate.remember(namespace, entry),
    search: async (namespace: string, query: string, limit?: number) =>
      memoryDelegate.search(namespace, query, limit),
  }
  const states = new Map<string, RunState>()
  const asyncCheckpoint = {
    save: async (state: RunState) => {
      states.set(state.runId, RunState.restore(JSON.parse(JSON.stringify(state))))
    },
    load: async (runId: string) => states.get(runId),
  }
  hooks.register("before_run", {
    callback: async (event) => { await Promise.resolve(); observed.push(event) },
  })
  const agent = new DatabaseReviewAgent(checkpoint, {}, {
    hooks, memory: asyncMemory, eventBus, checkpointStore: asyncCheckpoint,
    approval: { decide: async () => true },
    mcpClient: {
      listTools: async () => [{ name: "search_catalog", description: "async search" }],
      callTool: async (_name, arguments_) => ({
        success: true,
        query: arguments_.query,
        matches: ["src/config.ts", "src/db.ts"],
      }),
    },
    subagent: {
      runTask: async (request) => ({
        success: true,
        review: "异步子 Agent 已审查",
        parentTraceId: request.parentTraceId,
        parentSpanId: request.parentSpanId,
      }),
    },
  })
  const result = await agent.run("查找数据库配置并给出变更建议", "async-ports")
  assert.equal(result.success, true)
  assert.deepEqual(observed, ["before_run"])
  assert.deepEqual(eventTopics, ["task.started"])
  assert.match(String(result.results["5"].review), /异步子 Agent/)
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
  const agent = new DatabaseReviewAgent(checkpoint, {}, { approval: new AutoApproveGate() })
  agent.tools.register(flaky, true)
  const result = await agent.run("查找数据库配置并给出变更建议", "retry")
  assert.equal(result.success, true)
  assert.equal(result.attempts, 7)
  assert.equal(result.results["1"].attempts, 2)
})

await withCheckpoint(async (checkpoint) => {
  const task = "原任务"
  const agent = new DatabaseReviewAgent(checkpoint, {}, { approval: new AutoApproveGate() })
  assert.equal((await agent.run(task, "same-run")).success, true)
  const mismatch = await agent.run("另一任务", "same-run")
  assert.equal(mismatch.success, false)
  assert.equal(mismatch.status, "failed")
  assert.equal(mismatch.error, "run_task_mismatch")
})

await withCheckpoint(async (checkpoint) => {
  class BrokenLLM extends DeterministicLLMAdapter {
    override async createPlan(): Promise<never> { throw new Error("planner unavailable") }
  }
  const failed = await new DatabaseReviewAgent(checkpoint, {}, { llm: new BrokenLLM() })
    .run("任意任务", "runtime-error")
  assert.equal(failed.success, false)
  assert.equal(failed.status, "failed")
  assert.match(failed.error ?? "", /runtime_error/)
  assert.ok(failed.trace.some((entry) => entry.event === "on_error"))
})

await withCheckpoint(async (checkpoint) => {
  class CancelledLLM extends DeterministicLLMAdapter {
    override async createPlan(): Promise<never> {
      const error = new Error("cancelled")
      error.name = "AbortError"
      throw error
    }
  }
  await assert.rejects(
    new DatabaseReviewAgent(checkpoint, {}, { llm: new CancelledLLM() })
      .run("任意任务", "cancelled"),
    (error: Error) => error.name === "AbortError",
  )
})

await withCheckpoint(async (checkpoint) => {
  const denied = await new DatabaseReviewAgent(checkpoint)
    .run("查找数据库配置并给出变更建议", "deny-by-default")
  assert.equal(denied.success, false)
  assert.match(denied.error ?? "", /审批拒绝/)
})

await withCheckpoint(async (checkpoint) => {
  const gate = new ScriptedApprovalGate({ propose_change: true })
  const approved = await new DatabaseReviewAgent(checkpoint, {}, { approval: gate })
    .run("查找数据库配置并给出变更建议", "preview")
  assert.equal(approved.success, true)
  assert.equal(gate.requests[0].risk, "high")
  assert.equal(gate.requests[0].idempotencyKey, gate.requests[0].id)
  const dependencies = gate.requests[0].preview.dependencyResults as Record<string, ToolResult>
  assert.equal(dependencies["2"].path, "src/config.ts")
  assert.match(String(gate.requests[0].preview.resolvedIntent), /src\/config\.ts/)
})

await withCheckpoint(async (checkpoint) => {
  const installedSkills = {
    loadSkills: (): Skill[] => [{
      name: "installed-review", keywords: ["数据库"], instructions: "来自安装目录的审查规则", owner: "installed",
    }],
  }
  const client: MCPClient = {
    listTools: () => [{ name: "managed_lookup", description: "managed" }],
    callTool: (name, arguments_) => ({ success: true, name, ...arguments_ }),
  }
  const mcpServers = {
    closed: false,
    connectEnabled: () => [["managed", client]] as Array<[string, MCPClient]>,
    close() { this.closed = true },
  }
  const installedPlugins = {
    loadPlugins: (): Plugin[] => [{
      manifest: { name: "installed-pack", version: "1.0.0", permissions: ["tools:register"] },
      tools: [{ name: "installed_tool", description: "installed", handler: () => ({ success: true }) }],
    }],
  }
  const agent = new DatabaseReviewAgent(checkpoint, {}, {
    approval: new AutoApproveGate(), installedSkills, mcpServers, installedPlugins,
  })
  assert.equal((await agent.run("查找数据库配置并给出变更建议", "managed")).success, true)
  assert.equal(agent.skills.contains("installed-review"), true)
  assert.equal(agent.tools.contains("managed_lookup"), true)
  assert.equal(agent.tools.contains("installed_tool"), true)
  await agent.closeExtensions()
  assert.equal(mcpServers.closed, true)
  assert.equal(agent.tools.contains("managed_lookup"), false)
  assert.equal(agent.tools.contains("installed_tool"), false)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const agent = new DatabaseReviewAgent(checkpoint, {}, {
    approval: new AutoApproveGate(),
    installedSkills: { loadSkills: () => [{
      name: "transactional", keywords: ["数据库"], instructions: "transactional",
      owner: "installed",
    }] },
    installedPlugins: {
      loadPlugins: () => {
        calls += 1
        if (calls === 1) throw new Error("plugin catalog unavailable")
        return []
      },
    },
  })
  const failed = await agent.run("查找数据库配置并给出变更建议", "rollback-first")
  assert.equal(failed.success, false)
  assert.equal(agent.skills.contains("transactional"), false)
  assert.equal(agent.tools.contains("search_catalog"), false)
  const retried = await agent.run("查找数据库配置并给出变更建议", "rollback-second")
  assert.equal(retried.success, true)
  assert.equal(agent.skills.contains("transactional"), true)
})

await withCheckpoint(async (checkpoint) => {
  const task = "查找数据库配置并给出变更建议"
  const first = await new DatabaseReviewAgent(
    checkpoint, { interruptAfterSteps: 2 }, { approval: new AutoApproveGate() },
  ).run(task, "snapshot")
  assert.equal(first.status, "interrupted")
  const changed = new DatabaseReviewAgent(checkpoint, {}, { approval: new AutoApproveGate() })
  changed.tools.register({
    name: "new_capability", description: "new", handler: () => ({ success: true }),
  })
  const resumed = await changed.run(task, "snapshot")
  assert.equal(resumed.success, false)
  assert.equal(resumed.error, "capability_snapshot_mismatch")
})

await withCheckpoint(async (checkpoint) => {
  const policy = new DefaultPolicyEngine(new Set(["read", "write"]), [
    { scope: ConfigScope.Project, allow: new Set(["write"]) },
    { scope: ConfigScope.Managed, deny: new Set(["write"]) },
  ])
  assert.equal(policy.evaluate({
    subject: "agent", capability: "write", arguments: {}, resource: "write",
    runId: "run", source: "builtin:core", risk: "normal",
  }), PolicyDecision.Deny)

  let replacementCalls = 0
  const agent = new DatabaseReviewAgent(checkpoint, {}, { approval: new AutoApproveGate() })
  agent.hooks.register("before_tool", {
    kind: HookKind.Guard,
    priority: 1,
    name: "hot-reload",
    callback: (_event, payload) => {
      if (payload.tool === "search_catalog") agent.tools.register({
        name: "search_catalog", description: "replacement",
        handler: () => { replacementCalls += 1; return { success: true, matches: [] } },
      }, true)
    },
  })
  const result = await agent.run("查找数据库配置并给出变更建议", "frozen")
  assert.equal(result.success, true)
  assert.equal(replacementCalls, 0)
})

await withCheckpoint(async (checkpoint) => {
  const root = join(checkpoint, "..")
  writeFileSync(join(root, "package.json"), "{\"type\":\"module\"}\n", "utf8")
  writeFileSync(join(root, "calculator.js"), "export const add = (a, b) => a - b\n", "utf8")
  writeFileSync(join(root, "calculator.test.js"), [
    "import test from 'node:test'",
    "import assert from 'node:assert/strict'",
    "import { add } from './calculator.js'",
    "test('add supports negatives', () => assert.equal(add(-2, 5), 3))",
    "",
  ].join("\n"), "utf8")
  const agent = new CodingAgent(checkpoint, root, {}, {
    approval: new ScriptedApprovalGate({ apply_patch: true, run_check: true }),
  })
  const result = await agent.run("修复 add 并运行测试", "coding-success")
  assert.equal(result.success, true)
  assert.match(readFileSync(join(root, "calculator.js"), "utf8"), /a \+ b/u)
  assert.equal(result.results["5"].exitCode, 0)
})

await withCheckpoint(async (checkpoint) => {
  const root = join(checkpoint, "..")
  writeFileSync(join(root, "calculator.js"), "export const add = (a, b) => a - b\n", "utf8")
  writeFileSync(join(root, "calculator.test.js"), "", "utf8")
  const agent = new CodingAgent(checkpoint, root)
  const result = await agent.run("修复 add", "coding-denied")
  assert.equal(result.success, false)
  assert.match(readFileSync(join(root, "calculator.js"), "utf8"), /a - b/u)
  const workspace = new Workspace(root)
  assert.throws(() => workspace.resolve("../outside.txt"), /路径越过工作区/u)
  const outside = mkdtempSync(join(tmpdir(), "agent-host-outside-"))
  try {
    writeFileSync(join(outside, "secret.txt"), "secret", "utf8")
    symlinkSync(join(outside, "secret.txt"), join(root, "link.txt"))
    assert.throws(() => workspace.resolve("link.txt"), /符号链接越过工作区/u)
  } finally { rmSync(outside, { recursive: true, force: true }) }
})

await withCheckpoint(async (checkpoint) => {
  const calls: Array<{ task: string; runId: string; context: string[] }> = []
  const ids = ["t1", "r1", "t2", "r2"]
  const app = new ConversationApplication(
    new JsonSessionStore(join(checkpoint, "..", "sessions.json")),
    () => ({
      run: async (task, runId, conversationContext = []) => {
        calls.push({ task, runId, context: [...conversationContext] })
        return {
          success: true, status: "completed", runId, resumed: false, replayed: false,
          steps: 0, attempts: 0, results: {}, final: `完成：${task}`, trace: [], elapsedMs: 0,
        }
      },
    }),
    () => {
      const id = ids.shift()
      if (!id) throw new Error("测试 ID 已耗尽")
      return id
    },
  )
  const first = await app.send("conversation-1", "先检查项目")
  const second = await app.send("conversation-1", "继续修复问题")
  const session = app.getSession("conversation-1")
  assert.equal(first.taskId, "task-t1")
  assert.equal(first.runId, "run-r1")
  assert.equal(second.taskId, "task-t2")
  assert.equal(second.runId, "run-r2")
  assert.equal(session?.tasks.length, 2)
  assert.equal(session?.messages.length, 4)
  assert.deepEqual(calls[0].context, [])
  assert.deepEqual(calls[1].context, ["user: 先检查项目", "assistant: 完成：先检查项目"])
  assert.notEqual(session?.sessionId, first.runId)
})

await withCheckpoint(async (checkpoint) => {
  const skillProvider = new CatalogSkillProvider({
    list: async () => [{
      manifest: { name: "installed-review", keywords: ["数据库"] },
      instructions: "先读取再审查",
    }],
  })
  let closed = false
  const connection = {
    listTools: async () => [{ name: "lookup", description: "lookup" }],
    callTool: async (name: string, arguments_: Record<string, unknown>) => ({
      success: name === "lookup", query: arguments_.query,
    }),
  }
  const mcpProvider = new ManagerMCPProvider({
    connectEnabled: async () => [["managed", connection]],
    close: async () => { closed = true },
  })
  const base = {
    manifest: { name: "base", version: "1.0.0", entrypoint: "base-factory", dependencies: [] },
  }
  const addon = {
    manifest: { name: "addon", version: "1.0.0", entrypoint: "addon-factory", dependencies: ["base"] },
  }
  const pluginProvider = new CatalogPluginProvider(
    { list: async () => [addon, base] },
    new Map([
      ["base-factory", (record) => ({ manifest: { name: record.manifest.name, version: record.manifest.version, permissions: [] } })],
      ["addon-factory", (record) => ({ manifest: { name: record.manifest.name, version: record.manifest.version, permissions: [] } })],
    ]),
  )
  assert.deepEqual((await pluginProvider.loadPlugins()).map((plugin) => plugin.manifest.name), ["base", "addon"])
  const agent = new DatabaseReviewAgent(checkpoint, {}, {
    approval: new AutoApproveGate(),
    installedSkills: skillProvider,
    mcpServers: mcpProvider,
    installedPlugins: pluginProvider,
  })
  const result = await agent.run("查找数据库配置并给出变更建议", "adapters")
  assert.equal(result.success, true)
  assert.equal(agent.skills.contains("installed-review"), true)
  assert.equal(agent.tools.contains("managed.lookup"), true)
  await agent.closeExtensions()
  assert.equal(closed, true)
})

console.log("agent-host TypeScript tests: OK")
