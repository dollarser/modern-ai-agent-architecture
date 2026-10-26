import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync, mkdirSync, chmodSync, statSync, readdirSync } from "node:fs"
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
import { HostA2AAdapter, type RemoteTaskRequest } from "./a2a-adapter.js"
import { SandboxProfile } from "./sandbox-profile.js"

const withCheckpoint = async (test: (path: string) => Promise<void>): Promise<void> => {
  const directory = mkdtempSync(join(tmpdir(), "agent-host-test-"))
  try { await test(join(directory, "cp.json")) }
  finally { rmSync(directory, { recursive: true, force: true }) }
}

await withCheckpoint(async (checkpoint) => {
  const profile = new SandboxProfile({ workspaceRoots: ["/workspace"], processAllowlist: ["python"], networkAllowlist: ["pypi.org"], secretNames: ["API_TOKEN"], maxRuntimeSeconds: 10 })
  profile.validate()
  assert.equal(profile.allowsProcess("/usr/bin/python"), true)
  assert.equal(profile.allowsProcess("bash"), false)
  assert.equal(profile.allowsNetwork("example.com"), false)
  assert.equal(profile.mayLogSecret("API_TOKEN"), false)
})

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
  assert.ok(result.trace.some((item) => item.event === "on_approval_rejected"))
  assert.ok(!result.trace.some((item) => item.event === "on_tool_error"))
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
  assert.match(denied.error ?? "", /Tool 调用管线失败/)
  assert.equal(denied.attempts, 0)
  assert.ok(denied.trace.some((item) => item.event === "on_tool_error"))
  assert.ok(denied.trace.some((item) => item.event === "after_tool"))
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

await withCheckpoint(async (checkpoint) => {
  const host = new AgentHost(checkpoint)
  const client = {
    submit: async (request: RemoteTaskRequest) => ({ success: true, status: "submitted", taskId: request.taskId }),
    getTask: async (taskId: string, tenantId: string, owner: string) => ({ success: true, taskId, tenantId, owner, status: "working" }),
    getArtifact: async (artifactId: string, tenantId: string, owner: string) => Buffer.from(`${tenantId}:${owner}:${artifactId}`),
  }
  const adapter = new HostA2AAdapter(host, client)
  const request: RemoteTaskRequest = {
    runId: "run-1", taskId: "task-1", tenantId: "tenant-a", owner: "alice",
    idempotencyKey: "idem-1", message: "生成报告",
  }
  const result = await adapter.submit(request)
  assert.equal(result.success, true)
  assert.equal((host.events as EventBus).events.at(-1)?.topic, "a2a.task.submitted")
  assert.equal((await adapter.getTask("run-1", "task-1", "tenant-a", "alice")).status, "working")
  assert.equal((await adapter.getArtifact("run-1", "artifact-1", "tenant-a", "alice")).toString(), "tenant-a:alice:artifact-1")
  const mismatch = await adapter.submit({ ...request, taskId: "task-2", idempotencyKey: "idem-2" })
  assert.equal(mismatch.error_code, "checkpoint_mismatch")
})



// 安全回归：与 Python 的失败形状逐项对应。
const planFor = (steps: import("./assembly.js").PlanStep[]) => ({
  createPlan: async () => steps,
  finalAnswer: async () => "done",
})
const single = (tool = "action", arguments_: Record<string, unknown> = {}) =>
  [{ id: 1, description: "probe", tool, arguments: arguments_, dependsOn: [] }]
const securityHost = (checkpoint: string, tool: Tool, dependencies: import("./assembly.js").AgentDependencies = {},
  config: Partial<import("./assembly.js").AgentConfig> = {}) => {
  const host = new AgentHost(checkpoint, { allowedTools: new Set(["action"]), ...config }, {
    llm: planFor(single()), ...dependencies,
  })
  host.tools.register(tool)
  return host
}

await withCheckpoint(async (checkpoint) => {
  const root = join(checkpoint, ".."), workspace = join(root, "workspace")
  mkdirSync(workspace)
  const target = join(workspace, "calculator.js"), outside = join(root, "outside")
  writeFileSync(target, "old"); chmodSync(target, 0o640)
  writeFileSync(outside, "protected")
  symlinkSync(outside, `${target}.tmp`)
  const host = new CodingAgent(checkpoint, workspace, {}, {
    approval: new AutoApproveGate(),
    llm: planFor(single("apply_patch", { path: "calculator.js", old: "old", new: "new" })),
  })
  assert.equal((await host.run("task", "patch")).success, true)
  assert.equal(readFileSync(outside, "utf8"), "protected")
  assert.equal(readFileSync(target, "utf8"), "new")
  assert.equal(statSync(target).mode & 0o777, 0o640)
  assert.equal(readdirSync(workspace).some((name) => name.startsWith(".agent-write-")), false)
})

await withCheckpoint(async (checkpoint) => {
  for (const [index, [allow, deny]] of [
    [["action", "alias"], ["action"]], [["alias"], []], [["action"], ["alias"]],
  ].entries()) {
    let calls = 0
    const policy = new DefaultPolicyEngine(new Set(allow), [{ scope: ConfigScope.Managed, deny: new Set(deny) }])
    const host = securityHost(checkpoint, { name: "action", description: "action", handler: () => {
      calls += 1; return { success: true }
    } }, { policy, llm: planFor(single("alias")) })
    host.tools.registerAlias("alias", "action")
    assert.equal((await host.run("task", String(index))).success, false)
    assert.equal(calls, 0)
  }
})

await withCheckpoint(async (checkpoint) => {
  const schema = { type: "object", properties: { items: { type: "array", maxItems: 1,
    items: { type: "object", required: ["n"], properties: { n: { type: "integer", maximum: 10 } }, additionalProperties: false } } } }
  for (const [index, arguments_] of [
    { items: [{ n: 999 }] }, { items: [{ n: true }] }, { items: [{}] }, { items: [{ n: 1 }, { n: 2 }] },
  ].entries()) {
    let calls = 0
    const approval = new ScriptedApprovalGate({ action: true })
    const host = securityHost(checkpoint, { name: "action", description: "action", parameters: schema,
      requiresApproval: true, handler: () => { calls += 1; return { success: true } },
    }, { approval, llm: planFor(single("action", arguments_)) })
    assert.equal((await host.run("task", String(index))).success, false)
    assert.equal(calls, 0)
    assert.equal(approval.requests.length, 0)
  }
  const { validate } = await import("./schema-validation.js")
  assert.throws(() => validate({ properties: { absent: { pattern: "x" } } }, {}))
  assert.throws(() => validate({ maximum: "10" }, {}))
  validate(schema, { items: [{ n: 10 }] })
})

await withCheckpoint(async (checkpoint) => {
  const tool: Tool = { name: "action", description: "action", requiresApproval: true, handler: () => ({ success: true }) }
  const base = securityHost(checkpoint, tool, {}, { interruptAfterSteps: 0 })
  assert.equal((await base.run("task", "r")).status, "interrupted")
  for (const changed of [
    { ...tool, handler: () => ({ success: false }) },
    { ...tool, implementationVersion: "2" }, { ...tool, requiresApproval: false },
  ]) {
    assert.equal((await securityHost(checkpoint, changed).run("task", "r")).error, "capability_snapshot_mismatch")
  }
  const policy = new DefaultPolicyEngine(new Set(["action"]), [{ scope: ConfigScope.Managed, deny: new Set(["action"]) }])
  assert.equal((await securityHost(checkpoint, tool, { policy }).run("task", "r")).error, "capability_snapshot_mismatch")
  const state = await base.checkpoints.load("r")
  assert.ok(state)
  state.capabilitySnapshot = undefined
  await base.checkpoints.save(state)
  assert.equal((await securityHost(checkpoint, tool).run("task", "r")).error, "capability_snapshot_mismatch")
})

await withCheckpoint(async (checkpoint) => {
  let target = "first", calls = 0
  const approval = new ScriptedApprovalGate({ action: false })
  const host = securityHost(checkpoint, { name: "action", description: "action", requiresApproval: true,
    prepare: () => ({ target }), handler: () => { calls += 1; return { success: true } },
  }, { approval })
  await host.run("task", "r")
  const state = await host.checkpoints.load("r")
  assert.ok(state)
  state.approvals[Object.keys(state.approvals)[0]] = true
  state.results = {}; state.stepCount = 0
  await host.checkpoints.save(state)
  target = "second"
  assert.equal((await host.run("task", "r")).success, false)
  assert.equal(approval.requests.length, 2)
  assert.notEqual(approval.requests[0].id, approval.requests[1].id)
  assert.equal(calls, 0)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const host = new AgentHost(checkpoint, { allowedTools: new Set(["write", "cancel"]) }, {
    llm: planFor([...single("write"), { ...single("cancel")[0], id: 2 }]),
  })
  host.tools.register({ name: "write", description: "write", handler: () => { calls += 1; return { success: true } } })
  host.tools.register({ name: "cancel", description: "cancel", handler: async () => {
    await new Promise((resolve) => setTimeout(resolve, 20))
    const error = new Error("cancelled"); error.name = "AbortError"; throw error
  } })
  await assert.rejects(host.run("task", "r"), { name: "AbortError" })
  const state = await host.checkpoints.load("r")
  assert.ok(state?.results["1"].success)
  assert.equal(state?.executions["2"], "started")
  assert.equal((await host.run("task", "r")).status, "reconciliation_required")
  assert.equal(calls, 1)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const host = securityHost(checkpoint, { name: "action", description: "slow", handler: async () => {
    await new Promise((resolve) => setTimeout(resolve, 60)); calls += 1; return { success: true }
  } }, {}, { stepTimeoutMs: 10 })
  const result = await host.run("task", "r")
  assert.equal(result.status, "reconciliation_required")
  assert.equal(result.results["1"].outcome_unknown, true)
  await new Promise((resolve) => setTimeout(resolve, 100))
  assert.equal((await host.run("task", "r")).status, "reconciliation_required")
  assert.equal(calls, 1)
})

await withCheckpoint(async (checkpoint) => {
  const host = securityHost(checkpoint, { name: "action", description: "schema", parameters: {
    properties: { n: { type: "integer", maximum: 10 } },
  }, handler: () => ({ success: true }) })
  const frozen = host.tools.snapshot()
  const properties = host.tools.get("action").parameters?.properties as Record<string, { maximum: number }>
  properties.n.maximum = 999
  assert.equal((frozen.get("action").parameters?.properties as typeof properties).n.maximum, 10)
})



await withCheckpoint(async (checkpoint) => {
  const outside = join(checkpoint, "..", "outside")
  writeFileSync(outside, "protected")
  symlinkSync(outside, `${checkpoint}.tmp`)
  const { JsonCheckpointStore } = await import("./assembly.js")
  const store = new JsonCheckpointStore(checkpoint)
  store.save(new RunState("r", "task", []))
  assert.equal(store.load("r")?.task, "task")
  const sessionPath = join(checkpoint, "..", "sessions.json")
  symlinkSync(outside, `${sessionPath}.tmp`)
  const sessions = new JsonSessionStore(sessionPath)
  sessions.save({ sessionId: "s", messages: [], tasks: [] })
  assert.equal(sessions.load("s")?.sessionId, "s")
  assert.equal(readFileSync(outside, "utf8"), "protected")
})

await withCheckpoint(async (checkpoint) => {
  const { JsonCheckpointStore } = await import("./assembly.js")
  const backing = new JsonCheckpointStore(checkpoint)
  let active = 0, peak = 0
  const store = {
    load: (runId: string) => backing.load(runId),
    save: async (state: RunState) => {
      active += 1; peak = Math.max(peak, active)
      try {
        await new Promise((resolve) => setTimeout(resolve, 1))
        backing.save(state)
      } finally { active -= 1 }
    },
  }
  const host = new AgentHost(checkpoint, { allowedTools: new Set(["a", "b"]) }, {
    checkpointStore: store, llm: planFor([...single("a"), { ...single("b")[0], id: 2 }]),
  })
  for (const name of ["a", "b"]) host.tools.register({ name, description: name, handler: async () => ({ success: true }) })
  assert.equal((await host.run("task", "r")).success, true)
  assert.equal(peak, 1)
  assert.equal(Object.keys(backing.load("r")?.results ?? {}).length, 2)
})



await withCheckpoint(async (checkpoint) => {
  let calls = 0, finals = 0
  const tool: Tool = { name: "action", description: "action", handler: async () => {
    calls += 1; await new Promise((resolve) => setTimeout(resolve, 10)); return { success: true }
  } }
  const llm = { ...planFor(single()), finalAnswer: async () => `answer-${++finals}` }
  const a = securityHost(checkpoint, tool, { llm }), b = securityHost(checkpoint, tool, { llm })
  const [first, second] = await Promise.all([a.run("task", "r"), b.run("task", "r")])
  assert.equal(first.success && second.success, true)
  assert.equal(calls, 1); assert.equal(finals, 1)
  assert.equal(first.final, second.final); assert.equal(second.replayed, true)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0, finals = 0
  const llm = { ...planFor(single()), finalAnswer: async () => {
    if (++finals === 1) throw new Error("model unavailable")
    return "persisted answer"
  } }
  const host = securityHost(checkpoint, { name: "action", description: "action", handler: () => {
    calls += 1; return { success: true }
  } }, { llm })
  assert.equal((await host.run("task", "r")).error_code, "runtime_error")
  assert.equal((await host.run("task", "r")).success, true)
  assert.equal((await host.run("task", "r")).final, "persisted answer")
  assert.equal(calls, 1); assert.equal(finals, 2)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const factory = () => ({ run: async (_task: string, runId: string, context: string[] = []) => {
    calls += 1; assert.deepEqual(context, [])
    return { success: true, status: "completed", runId, final: "answer" } as import("./assembly.js").AgentResult
  } })
  const app = new ConversationApplication(new JsonSessionStore(checkpoint), factory, undefined, 0)
  const [a, b] = await Promise.all([app.send("s", "hello", "m"), app.send("s", "hello", "m")])
  const restarted = new ConversationApplication(new JsonSessionStore(checkpoint), factory)
  assert.deepEqual(a, b); assert.deepEqual(a, await restarted.send("s", "hello", "m"))
  assert.equal(calls, 1)
  await assert.rejects(restarted.send("s", "changed", "m"), /idempotency_key_conflict/)
  assert.equal(restarted.getSession("s")?.messages.length, 2)
})

await withCheckpoint(async (checkpoint) => {
  const runs: string[] = []
  const app = new ConversationApplication(new JsonSessionStore(checkpoint), () => ({
    run: async (_task, runId) => {
      runs.push(runId)
      if (runs.length === 1) { const error = new Error("cancel"); error.name = "AbortError"; throw error }
      return { success: true, status: "completed", runId, final: "done" } as import("./assembly.js").AgentResult
    },
  }))
  await assert.rejects(app.send("s", "hello", "m"), { name: "AbortError" })
  const record = app.getSession("s")!.tasks[0]
  assert.equal(record.status, "cancelled")
  await assert.rejects(app.send("s", "hello", "m"), /resume_required/)
  assert.equal((await app.resume("s", record.taskId)).runId, record.runId)
  assert.deepEqual(runs, [record.runId, record.runId])
  assert.equal(app.getSession("s")?.messages.length, 2)
})

await withCheckpoint(async (checkpoint) => {
  let entered = 0, release!: () => void
  const both = new Promise<void>((resolve) => { release = resolve })
  const app = new ConversationApplication(new JsonSessionStore(checkpoint), () => ({
    run: async (_task, runId) => {
      if (++entered === 2) release()
      let timer: ReturnType<typeof setTimeout>
      await Promise.race([both, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error("sessions serialized")), 200) })])
        .finally(() => clearTimeout(timer))
      return { success: true, status: "completed", runId, final: "done" } as import("./assembly.js").AgentResult
    },
  }))
  await Promise.all([app.send("s1", "a"), app.send("s2", "b")])
  assert.equal(entered, 2)
})

await withCheckpoint(async (checkpoint) => {
  let calls = 0
  const host = securityHost(checkpoint, { name: "action", description: "slow", handler: async () => {
    await new Promise((resolve) => setTimeout(resolve, 50)); calls += 1; return { success: true }
  } }, {}, { stepTimeoutMs: 5 })
  assert.equal((await host.run("task", "r")).error_code, "unknown_side_effect")
  const verify = async () => ({ evidence: "test-downstream-receipt-1", result: { success: true, remoteId: "1" } })
  await assert.rejects(host.reconcile("r", 1, verify), /execution_still_active/)
  await new Promise((resolve) => setTimeout(resolve, 80))
  await assert.rejects(host.reconcile("r", 1, () => ({ evidence: "", result: { success: true } })), /invalid_reconciliation_receipt/)
  const state = await host.reconcile("r", 1, verify)
  assert.equal(state.trace.at(-1)?.event, "execution_reconciled")
  assert.equal((await host.run("task", "r")).success, true)
  assert.equal(calls, 1)
})

console.log("agent-host TypeScript tests: OK (security and reliability regressions)")
