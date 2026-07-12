/** 第 16 章最终组装：可插拔端口与离线最小适配器。 */

import { dirname } from "node:path"
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import {
  DefaultPolicyEngine, PolicyDecision, type CapabilitySnapshot,
  type PolicyEngine, sha256Text, withSnapshotHash,
} from "./governance.js"
export * from "./governance.js"

export type ToolResult = {
  success: boolean
  error?: string
  capabilitySnapshot?: CapabilitySnapshot
  retryable?: boolean
  attempts?: number
  skipped?: boolean
  [key: string]: unknown
}

export type PlanStep = {
  id: number
  description: string
  tool: string
  arguments: Record<string, unknown>
  dependsOn: number[]
}

export type MemoryEntry = { role: string; content: string }
export type TraceEntry = { event: string; stepId?: number; [key: string]: unknown }

type StoredState = {
  runId: string
  task: string
  plan: PlanStep[]
  results: Record<string, ToolResult>
  memory: MemoryEntry[]
  trace: TraceEntry[]
  approvals: Record<string, boolean>
  stepCount: number
  attemptCount: number
  status: string
  error?: string
  capabilitySnapshot?: CapabilitySnapshot
}

export class RunState implements StoredState {
  results: Record<string, ToolResult> = {}
  memory: MemoryEntry[] = []
  trace: TraceEntry[] = []
  approvals: Record<string, boolean> = {}
  stepCount = 0
  attemptCount = 0
  status = "pending"
  error?: string
  capabilitySnapshot?: CapabilitySnapshot

  constructor(
    public readonly runId: string,
    public readonly task: string,
    public plan: PlanStep[],
  ) {}

  static restore(data: StoredState): RunState {
    const state = new RunState(data.runId, data.task, data.plan)
    state.results = data.results
    state.memory = data.memory
    state.trace = data.trace
    state.approvals = data.approvals ?? {}
    state.stepCount = data.stepCount
    state.attemptCount = data.attemptCount
    state.status = data.status
    state.error = data.error
    state.capabilitySnapshot = data.capabilitySnapshot
    return state
  }
}

// Memory port
export interface MemoryBackend {
  append(runId: string, entry: MemoryEntry): void | Promise<void>
  recent(runId: string, limit?: number): MemoryEntry[] | Promise<MemoryEntry[]>
  remember(namespace: string, entry: MemoryEntry): void | Promise<void>
  search(namespace: string, query: string, limit?: number): MemoryEntry[] | Promise<MemoryEntry[]>
}

export class InMemoryMemoryBackend implements MemoryBackend {
  readonly shortTerm = new Map<string, MemoryEntry[]>()
  readonly longTerm = new Map<string, MemoryEntry[]>()

  append(runId: string, entry: MemoryEntry): void {
    const entries = this.shortTerm.get(runId) ?? []
    entries.push(entry)
    this.shortTerm.set(runId, entries)
  }

  recent(runId: string, limit = 12): MemoryEntry[] {
    return [...(this.shortTerm.get(runId) ?? []).slice(-limit)]
  }

  remember(namespace: string, entry: MemoryEntry): void {
    const entries = this.longTerm.get(namespace) ?? []
    if (!entries.some((item) => item.role === entry.role && item.content === entry.content)) {
      entries.push(entry)
    }
    this.longTerm.set(namespace, entries)
  }

  search(namespace: string, query: string, limit = 5): MemoryEntry[] {
    const normalized = query.toLowerCase().replaceAll("，", " ")
    const terms = [
      ...normalized.split(/\s+/).filter(Boolean),
      ...Array.from({ length: Math.max(0, normalized.length - 1) }, (_, index) =>
        normalized.slice(index, index + 2)),
    ]
    return (this.longTerm.get(namespace) ?? [])
      .map((entry, index) => ({
        entry,
        index,
        score: terms.filter((term) => entry.content.toLowerCase().includes(term)).length,
      }))
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score || left.index - right.index)
      .slice(0, limit)
      .map((item) => item.entry)
  }
}

// Lifecycle hooks
export enum HookKind { Guard = "guard", Observer = "observer" }
export type HookCallback = (
  event: string,
  payload: Record<string, unknown>,
  state: RunState,
) => void | Promise<void>
export type HookDefinition = {
  callback: HookCallback
  kind?: HookKind
  priority?: number
  name?: string
  owner?: string
}

export class HookPipeline {
  private readonly hooks = new Map<string, Required<HookDefinition>[]>()

  register(event: string, definition: HookDefinition): void {
    const normalized: Required<HookDefinition> = {
      callback: definition.callback,
      kind: definition.kind ?? HookKind.Observer,
      priority: definition.priority ?? 100,
      name: definition.name ?? "anonymous",
      owner: definition.owner ?? "core",
    }
    const hooks = this.hooks.get(event) ?? []
    hooks.push(normalized)
    hooks.sort((left, right) => left.priority - right.priority)
    this.hooks.set(event, hooks)
  }

  unregisterOwner(owner: string): void {
    for (const [event, hooks] of this.hooks) {
      this.hooks.set(event, hooks.filter((hook) => hook.owner !== owner))
    }
  }
  async emit(event: string, payload: Record<string, unknown>, state: RunState): Promise<void> {
    state.trace.push({ event, stepId: Number(payload.stepId) || undefined })
    for (const hook of this.hooks.get(event) ?? []) {
      try {
        await hook.callback(event, payload, state)
      } catch (error) {
        if (hook.kind === HookKind.Guard) throw error
        state.trace.push({ event: "observer_error", hook: hook.name, error: String(error) })
      }
    }
  }
}

// Tool registry / router
export enum ToolSource { Builtin = "builtin", MCP = "mcp", Plugin = "plugin" }
export enum ToolState { Active = "active", Disabled = "disabled", Deprecated = "deprecated", Error = "error" }
export type ExecutionContext = {
  task: string
  results: Record<string, ToolResult>
  runId: string
  traceId: string
  spanId: string
}
export type Tool = {
  name: string
  description: string
  handler: (
    arguments_: Record<string, unknown>,
    context: ExecutionContext,
  ) => ToolResult | Promise<ToolResult>
  prepare?: (
    arguments_: Record<string, unknown>,
    context: ExecutionContext,
  ) => Record<string, unknown>
  parameters?: Record<string, unknown>
  source?: ToolSource
  sourceName?: string
  state?: ToolState
  tags?: string[]
  requiresApproval?: boolean
}

export class ToolRegistry {
  private readonly tools = new Map<string, Tool>()
  private readonly aliases = new Map<string, string>()

  register(tool: Tool, replace = false): void {
    if (this.tools.has(tool.name) && !replace) throw new Error(`Tool 已存在: ${tool.name}`)
    this.tools.set(tool.name, {
      parameters: {},
      source: ToolSource.Builtin,
      sourceName: "core",
      state: ToolState.Active,
      tags: [],
      requiresApproval: false,
      ...tool,
    })
  }

  get(name: string): Tool {
    const tool = this.tools.get(this.aliases.get(name) ?? name)
    if (!tool) throw new Error(`Tool 未注册: ${name}`)
    return tool
  }

  contains(name: string): boolean { return this.tools.has(name) || this.aliases.has(name) }

  registerAlias(alias: string, canonicalName: string): void {
    if (this.contains(alias)) throw new Error(`Tool Alias 已存在: ${alias}`)
    if (!this.tools.has(canonicalName)) throw new Error(`Tool 未注册: ${canonicalName}`)
    this.aliases.set(alias, canonicalName)
  }

  listAliases(): Record<string, string> {
    return Object.fromEntries([...this.aliases.entries()].sort(([a], [b]) => a.localeCompare(b)))
  }

  list(): Tool[] {
    return [...this.tools.values()].sort((left, right) => left.name.localeCompare(right.name))
  }

  unregisterBySource(source: ToolSource, sourceName: string): number {
    const names = this.list()
      .filter((tool) => tool.source === source && tool.sourceName === sourceName)
      .map((tool) => tool.name)
    names.forEach((name) => this.tools.delete(name))
    for (const [alias, target] of this.aliases) if (names.includes(target)) this.aliases.delete(alias)
    return names.length
  }
  snapshot(): ToolRegistry {
    const frozen = new ToolRegistry()
    this.list().forEach((tool) => frozen.register(tool))
    for (const [alias, target] of this.aliases) frozen.registerAlias(alias, target)
    return frozen
  }
}

export class ToolRouter {
  constructor(readonly registry: ToolRegistry) {}

  available(tag?: string): Tool[] {
    return this.registry.list().filter(
      (tool) => tool.state === ToolState.Active && (!tag || tool.tags?.includes(tag)),
    )
  }

  availableNames(): string[] {
    const canonical = this.available().map((tool) => tool.name)
    const aliases = Object.entries(this.registry.listAliases())
      .filter(([, target]) => canonical.includes(target)).map(([alias]) => alias)
    return [...canonical, ...aliases].sort()
  }

  resolve(name: string): Tool {
    const tool = this.registry.get(name)
    if (tool.state !== ToolState.Active) throw new Error(`Tool 不可用: ${name} (${tool.state})`)
    return tool
  }

  async execute(
    name: string,
    arguments_: Record<string, unknown>,
    context: ExecutionContext,
  ): Promise<ToolResult> {
    const tool = this.resolve(name)
    this.validateArguments(tool.parameters ?? {}, arguments_)
    return await tool.handler(arguments_, context)
  }

  private validateArguments(
    schema: Record<string, unknown>,
    arguments_: Record<string, unknown>,
  ): void {
    if (!Object.keys(schema).length) return
    const required = (schema.required as string[] | undefined) ?? []
    for (const name of required) {
      if (!(name in arguments_)) throw new Error(`Tool 参数缺少必填字段: ${name}`)
    }
    const properties = (schema.properties as Record<string, Record<string, unknown>> | undefined) ?? {}
    for (const [name, value] of Object.entries(arguments_)) {
      const definition = properties[name]
      if (!definition) {
        if (schema.additionalProperties === false) throw new Error(`Tool 参数包含未知字段: ${name}`)
        continue
      }
      const expected = definition.type
      const valid = expected === undefined ||
        (expected === "string" && typeof value === "string") ||
        (expected === "number" && typeof value === "number") ||
        (expected === "integer" && typeof value === "number" && Number.isInteger(value)) ||
        (expected === "boolean" && typeof value === "boolean") ||
        (expected === "object" && typeof value === "object" && value !== null && !Array.isArray(value)) ||
        (expected === "array" && Array.isArray(value))
      if (!valid) throw new Error(`Tool 参数类型错误: ${name}`)
      if (Array.isArray(definition.enum) && !definition.enum.includes(value)) {
        throw new Error(`Tool 参数不在允许值中: ${name}`)
      }
    }
  }
}

// Skills, MCP and Plugins
export type Skill = { name: string; keywords: string[]; instructions: string; owner?: string }
export type SkillMetadata = { name: string; keywords: string[]; owner?: string }
export interface InstalledSkillProvider {
  loadSkills(): Skill[] | Promise<Skill[]>
}
export class SkillRegistry {
  private readonly skills = new Map<string, Skill>()
  register(skill: Skill, replace = false): void {
    if (this.skills.has(skill.name) && !replace) throw new Error(`Skill 已存在: ${skill.name}`)
    this.skills.set(skill.name, skill)
  }
  unregister(name: string): void { this.skills.delete(name) }
  contains(name: string): boolean { return this.skills.has(name) }
  unregisterOwner(owner: string): void {
    for (const [name, skill] of this.skills) if (skill.owner === owner) this.skills.delete(name)
  }
  list(): Skill[] { return [...this.skills.values()].sort((a, b) => a.name.localeCompare(b.name)) }
  match(task: string): Skill[] {
    return this.load(this.discover(task).map((skill) => skill.name))
  }
  discover(task: string): SkillMetadata[] {
    const lowered = task.toLowerCase()
    return [...this.skills.values()].filter(
      (skill) => skill.keywords.some((keyword) => lowered.includes(keyword.toLowerCase())),
    ).map(({ name, keywords, owner }) => ({ name, keywords, owner }))
  }
  load(names: string[]): Skill[] { return names.flatMap((name) => this.skills.get(name) ?? []) }
}

export type MCPToolDefinition = {
  name: string
  description: string
  inputSchema?: Record<string, unknown>
}
export interface MCPClient {
  listTools(): MCPToolDefinition[] | Promise<MCPToolDefinition[]>
  callTool(name: string, arguments_: Record<string, unknown>): ToolResult | Promise<ToolResult>
}
export interface MCPServerProvider {
  connectEnabled(): Array<[string, MCPClient]> | Promise<Array<[string, MCPClient]>>
  close(): void | Promise<void>
}

export class FakeMCPClient implements MCPClient {
  readonly calls: string[] = []
  listTools(): MCPToolDefinition[] {
    return [{ name: "search_catalog", description: "从 MCP 目录查找候选文件" }]
  }
  callTool(name: string, arguments_: Record<string, unknown>): ToolResult {
    this.calls.push(name)
    if (name !== "search_catalog") return { success: false, error: `未知 MCP Tool: ${name}` }
    return {
      success: true,
      query: String(arguments_.query ?? ""),
      matches: ["src/config.ts", "src/db.ts"],
    }
  }
}

export class MCPToolAdapter {
  private registered = false
  constructor(readonly client: MCPClient, readonly serverName: string) {}
  async registerTools(registry: ToolRegistry): Promise<number> {
    if (this.registered) return 0
    const definitions = await this.client.listTools()
    for (const definition of definitions) {
      const name = `${this.serverName}.${definition.name}`
      registry.register({
        name,
        description: definition.description,
        parameters: definition.inputSchema,
        source: ToolSource.MCP,
        sourceName: this.serverName,
        tags: ["external"],
        handler: (arguments_) => this.client.callTool(definition.name, arguments_),
      })
      if (!registry.contains(definition.name)) registry.registerAlias(definition.name, name)
    }
    this.registered = true
    return definitions.length
  }
  unregisterTools(registry: ToolRegistry): number {
    const removed = registry.unregisterBySource(ToolSource.MCP, this.serverName)
    this.registered = false
    return removed
  }
}

export type PluginManifest = { name: string; version: string; permissions?: string[] }
export type Plugin = {
  manifest: PluginManifest
  tools?: Tool[]
  skills?: Skill[]
  hooks?: Array<{ event: string; definition: HookDefinition }>
  state?: "registered" | "active" | "unloaded"
}

export class PluginLoader {
  private readonly plugins = new Map<string, Plugin>()
  constructor(
    readonly tools: ToolRegistry,
    readonly skills: SkillRegistry,
    readonly hooks: HookPipeline,
  ) {}

  load(plugin: Plugin): void {
    const name = plugin.manifest.name
    if (this.plugins.has(name)) throw new Error(`Plugin 已加载: ${name}`)
    const permissions = new Set(plugin.manifest.permissions ?? [])
    const missing = [
      (plugin.tools?.length ?? 0) > 0 && !permissions.has("tools:register")
        ? "tools:register" : undefined,
      (plugin.skills?.length ?? 0) > 0 && !permissions.has("skills:register")
        ? "skills:register" : undefined,
      (plugin.hooks?.length ?? 0) > 0 && !permissions.has("hooks:register")
        ? "hooks:register" : undefined,
    ].filter((item): item is string => item !== undefined)
    if (missing.length) throw new Error(`Plugin 权限不足: ${missing.sort().join(", ")}`)
    const conflicts = [
      ...(plugin.tools ?? []).filter((tool) => this.tools.contains(tool.name)).map((tool) => tool.name),
      ...(plugin.skills ?? []).filter((skill) => this.skills.contains(skill.name))
        .map((skill) => skill.name),
    ]
    if (conflicts.length) throw new Error(`Plugin 资源冲突: ${conflicts.sort().join(", ")}`)
    try {
      for (const tool of plugin.tools ?? []) {
        this.tools.register({ ...tool, source: ToolSource.Plugin, sourceName: name })
      }
      for (const skill of plugin.skills ?? []) this.skills.register({ ...skill, owner: name })
      for (const hook of plugin.hooks ?? []) {
        this.hooks.register(hook.event, { ...hook.definition, owner: name })
      }
    } catch (error) {
      this.tools.unregisterBySource(ToolSource.Plugin, name)
      this.skills.unregisterOwner(name)
      this.hooks.unregisterOwner(name)
      throw error
    }
    plugin.state = "active"
    this.plugins.set(name, plugin)
  }

  unload(name: string): void {
    const plugin = this.plugins.get(name)
    if (!plugin) throw new Error(`Plugin 未加载: ${name}`)
    this.plugins.delete(name)
    this.tools.unregisterBySource(ToolSource.Plugin, name)
    this.skills.unregisterOwner(name)
    this.hooks.unregisterOwner(name)
    plugin.state = "unloaded"
  }
}

export interface InstalledPluginProvider {
  loadPlugins(): Plugin[] | Promise<Plugin[]>
}

// Approval and orchestration
export type ApprovalRequest = {
  id: string
  runId: string
  tool: string
  arguments: Record<string, unknown>
  reason: string
  preview: Record<string, unknown>
  risk: "high"
  idempotencyKey: string
}
export interface ApprovalGate { decide(request: ApprovalRequest): boolean | Promise<boolean> }
export class AutoApproveGate implements ApprovalGate { decide(): boolean { return true } }
export class DenyApprovalGate implements ApprovalGate { decide(): boolean { return false } }
export class ScriptedApprovalGate implements ApprovalGate {
  readonly requests: ApprovalRequest[] = []
  constructor(readonly decisions: Record<string, boolean>) {}
  decide(request: ApprovalRequest): boolean {
    this.requests.push(request)
    return this.decisions[request.tool] ?? false
  }
}

export interface EventBusPort {
  publish(topic: string, payload: Record<string, unknown>): Promise<void>
}

export class EventBus implements EventBusPort {
  readonly events: Array<Record<string, unknown>> = []
  private readonly subscribers = new Map<string, Array<{
    callback: (event: Record<string, unknown>) => void | Promise<void>
    kind: HookKind
    name: string
  }>>()
  subscribe(
    topic: string,
    callback: (event: Record<string, unknown>) => void | Promise<void>,
    kind = HookKind.Observer,
    name = "anonymous",
  ): void {
    const callbacks = this.subscribers.get(topic) ?? []
    callbacks.push({ callback, kind, name })
    this.subscribers.set(topic, callbacks)
  }
  async publish(topic: string, payload: Record<string, unknown>): Promise<void> {
    const event = { topic, ...payload }
    this.events.push(event)
    for (const subscriber of this.subscribers.get(topic) ?? []) {
      try { await subscriber.callback(event) } catch (error) {
        if (subscriber.kind === HookKind.Guard) throw error
        this.events.push({
          topic: "observer.error", subscriber: subscriber.name, error: String(error),
        })
      }
    }
  }
}

export type HandoffRequest = {
  task: string
  parentRunId: string
  parentTraceId: string
  parentSpanId: string
  depth: number
}
export interface AgentRunner { runTask(request: HandoffRequest): ToolResult | Promise<ToolResult> }
export class ReviewSubagent implements AgentRunner {
  runTask(request: HandoffRequest): ToolResult {
    return {
      success: true,
      review: "子 Agent 已验证候选路径与变更说明",
      parentTraceId: request.parentTraceId,
      parentSpanId: request.parentSpanId,
    }
  }
}
export class HandoffCoordinator {
  constructor(
    readonly runner: AgentRunner,
    readonly events: EventBusPort,
    readonly maxDepth = 2,
  ) {}
  async handoff(request: HandoffRequest): Promise<ToolResult> {
    if (request.depth > this.maxDepth) return { success: false, error: "Handoff 超过最大深度" }
    await this.events.publish("handoff.created", {
      runId: request.parentRunId,
      traceId: request.parentTraceId,
    })
    const result = await this.runner.runTask(request)
    await this.events.publish("handoff.completed", {
      runId: request.parentRunId,
      success: result.success,
    })
    return result
  }
}

// Runtime ports and execution
export interface LLMAdapter {
  createPlan(task: string, toolNames: string[], context: string[]): Promise<PlanStep[]>
  finalAnswer(task: string, results: Record<string, ToolResult>): Promise<string>
}
export class DeterministicLLMAdapter implements LLMAdapter {
  lastContext: string[] = []
  async createPlan(task: string, toolNames: string[], context: string[]): Promise<PlanStep[]> {
    this.lastContext = [...context]
    const required = [
      "search_catalog", "inspect_candidate", "summarize_matches",
      "propose_change", "delegate_review", "compose_report",
    ]
    const missing = required.filter((name) => !toolNames.includes(name))
    if (missing.length) throw new Error(`计划所需 Tool 未注册: ${missing.join(",")}`)
    return [
      { id: 1, description: "通过 MCP 查找候选", tool: "search_catalog", arguments: { query: task }, dependsOn: [] },
      { id: 2, description: "检查首个候选", tool: "inspect_candidate", arguments: {}, dependsOn: [1] },
      { id: 3, description: "通过 Plugin 汇总候选", tool: "summarize_matches", arguments: {}, dependsOn: [1] },
      { id: 4, description: "生成需审批的变更建议", tool: "propose_change", arguments: {}, dependsOn: [2, 3] },
      { id: 5, description: "移交子 Agent 审查", tool: "delegate_review", arguments: {}, dependsOn: [4] },
      { id: 6, description: "组合最终报告", tool: "compose_report", arguments: {}, dependsOn: [4, 5] },
    ]
  }
  async finalAnswer(task: string, results: Record<string, ToolResult>): Promise<string> {
    return `任务：${task}\n${String(results["6"]?.report ?? "未生成报告")}`
  }
}

export interface CheckpointStore {
  save(state: RunState): void | Promise<void>
  load(runId: string): RunState | undefined | Promise<RunState | undefined>
}

export class JsonCheckpointStore implements CheckpointStore {
  constructor(readonly path: string) { mkdirSync(dirname(path), { recursive: true }) }
  private readAll(): Record<string, StoredState> {
    if (!existsSync(this.path)) return {}
    return JSON.parse(readFileSync(this.path, "utf8")) as Record<string, StoredState>
  }
  save(state: RunState): void {
    const data = this.readAll()
    data[state.runId] = state
    const temporary = `${this.path}.tmp`
    writeFileSync(temporary, JSON.stringify(data, null, 2), "utf8")
    renameSync(temporary, this.path)
  }
  load(runId: string): RunState | undefined {
    const item = this.readAll()[runId]
    return item ? RunState.restore(item) : undefined
  }
}

export type AgentConfig = {
  instructions: string
  maxSteps: number
  maxRetries: number
  stepTimeoutMs: number
  retryDelayMs: number
  interruptAfterSteps?: number
  allowedTools: Set<string>
}
const defaultConfig = (): AgentConfig => ({
  instructions: "只读取模拟数据，并输出可核查的路径",
  maxSteps: 10,
  maxRetries: 1,
  stepTimeoutMs: 2_000,
  retryDelayMs: 10,
  allowedTools: new Set([
    "search_catalog", "inspect_candidate", "summarize_matches",
    "propose_change", "delegate_review", "compose_report",
  ]),
})
const delay = (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

class DependencyExecutor {
  constructor(
    readonly router: ToolRouter,
    readonly hooks: HookPipeline,
    readonly approval: ApprovalGate,
    readonly memory: MemoryBackend,
    readonly config: AgentConfig,
    readonly policy: PolicyEngine,
    readonly snapshotHash: string,
  ) {}

  async run(state: RunState, checkpoint: () => void | Promise<void>): Promise<void> {
    const startedAt = state.stepCount
    state.status = "running"
    state.error = undefined
    while (Object.keys(state.results).length < state.plan.length) {
      let pending = state.plan.filter((step) => state.results[String(step.id)] === undefined)
      for (const step of pending) {
        const failed = step.dependsOn.some((id) => state.results[String(id)]?.success === false)
        if (failed) state.results[String(step.id)] = {
          success: false, error: "依赖步骤失败，未执行 Tool", skipped: true,
        }
      }
      pending = state.plan.filter((step) => state.results[String(step.id)] === undefined)
      if (!pending.length) break
      const ready = pending.filter((step) =>
        step.dependsOn.every((id) => state.results[String(id)] !== undefined),
      )
      if (!ready.length) {
        state.status = "failed"
        state.error = "计划存在循环依赖或未知依赖"
        await checkpoint()
        return
      }
      if (state.stepCount >= this.config.maxSteps) {
        state.status = "max_steps"
        state.error = `达到最大 Tool 步数: ${this.config.maxSteps}`
        await checkpoint()
        return
      }
      if (
        this.config.interruptAfterSteps !== undefined &&
        state.stepCount - startedAt >= this.config.interruptAfterSteps
      ) {
        state.status = "interrupted"
        state.error = "按教学配置模拟中断，可恢复"
        await checkpoint()
        return
      }
      let batch = ready.slice(0, this.config.maxSteps - state.stepCount)
      if (this.config.interruptAfterSteps !== undefined) {
        batch = batch.slice(0, this.config.interruptAfterSteps - (state.stepCount - startedAt))
      }
      const results = await Promise.all(
        batch.map((step) => this.executeStep(step, state, checkpoint)),
      )
      for (const [index, step] of batch.entries()) {
        state.results[String(step.id)] = results[index]
        state.stepCount += 1
        state.memory.push({
          role: "tool",
          content: JSON.stringify({ stepId: step.id, tool: step.tool, result: results[index] }),
        })
        await this.memory.append(state.runId, state.memory[state.memory.length - 1])
      }
      await checkpoint()
    }
    const failure = Object.values(state.results).find((result) => !result.success)
    state.status = failure ? "failed" : "completed"
    state.error = failure ? String(failure.error ?? "Tool 执行失败") : undefined
    await checkpoint()
  }

  private async executeStep(
    step: PlanStep,
    state: RunState,
    checkpoint: () => void | Promise<void>,
  ): Promise<ToolResult> {
    const payload = { stepId: step.id, tool: step.tool, arguments: step.arguments }
    const context: ExecutionContext = {
      task: state.task,
      results: state.results,
      runId: state.runId,
      traceId: `trace-${state.runId}`,
      spanId: `step-${step.id}`,
    }
    try {
      await this.hooks.emit("before_tool", payload, state)
      const tool = this.router.resolve(step.tool)
      const decision = this.policy.evaluate({
        subject: "agent", capability: step.tool, arguments: step.arguments,
        resource: step.tool, runId: state.runId,
        source: `${tool.source}:${tool.sourceName}`,
        risk: tool.requiresApproval ? "high" : "normal",
      })
      state.trace.push({
        event: "policy_decision", tool: step.tool,
        decision, policyVersion: this.policy.version,
      })
      if (decision === PolicyDecision.Deny) throw new Error(`Policy 拒绝 Tool: ${step.tool}`)
      if (decision === PolicyDecision.Ask) {
        const approvalId = `${state.runId}:${step.id}:${step.tool}:${this.snapshotHash}`
        if (state.approvals[approvalId] === undefined) {
          const request: ApprovalRequest = {
            id: approvalId,
            runId: state.runId,
            tool: step.tool,
            arguments: step.arguments,
            reason: "Tool 声明 requiresApproval",
            preview: {
              task: state.task,
              tool: step.tool,
              arguments: step.arguments,
              dependencyResults: Object.fromEntries(
                step.dependsOn.map((id) => [String(id), state.results[String(id)]]),
              ),
              ...(tool.prepare?.(step.arguments, context) ?? {}),
            },
            risk: "high",
            idempotencyKey: approvalId,
          }
          await this.hooks.emit("before_approval", { ...payload, request: request.id }, state)
          state.approvals[approvalId] = await this.approval.decide(request)
          await this.hooks.emit(
            "after_approval", { ...payload, approved: state.approvals[approvalId] }, state,
          )
          // 审批决定必须先于有副作用的 Handler 持久化。
          await checkpoint()
        }
        if (!state.approvals[approvalId]) {
          const result = { success: false, error: `审批拒绝执行: ${step.tool}` }
          await this.hooks.emit("on_tool_error", { ...payload, result }, state)
          await this.hooks.emit("after_tool", { ...payload, result }, state)
          return result
        }
      }
    } catch (error) {
      const result = { success: false, error: `Guardrail 拒绝执行: ${String(error)}` }
      await this.hooks.emit("on_tool_error", { ...payload, result }, state)
      await this.hooks.emit("after_tool", { ...payload, result }, state)
      return result
    }

    let lastError = "Tool 执行失败"
    let attempt = 0
    for (attempt = 1; attempt <= this.config.maxRetries + 1; attempt += 1) {
      state.attemptCount += 1
      try {
        const result = await this.withTimeout(
          this.router.execute(step.tool, step.arguments, context),
          `Tool '${step.tool}' 超时`,
        )
        const withAttempts = { ...result, attempts: attempt }
        if (withAttempts.success) {
          await this.hooks.emit("after_tool", { ...payload, result: withAttempts }, state)
          return withAttempts
        }
        lastError = String(withAttempts.error ?? lastError)
        if (!withAttempts.retryable) break
      } catch (error) {
        lastError = String(error)
        break
      }
      if (attempt <= this.config.maxRetries) await delay(this.config.retryDelayMs * attempt)
    }
    const result = { success: false, error: lastError, attempts: attempt }
    await this.hooks.emit("on_tool_error", { ...payload, result }, state)
    await this.hooks.emit("after_tool", { ...payload, result }, state)
    return result
  }

  private withTimeout<T>(promise: Promise<T>, message: string): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(message)), this.config.stepTimeoutMs)
      promise.then(
        (value) => { clearTimeout(timer); resolve(value) },
        (error: unknown) => { clearTimeout(timer); reject(error) },
      )
    })
  }
}

export type AgentDependencies = {
  llm?: LLMAdapter
  memory?: MemoryBackend
  hooks?: HookPipeline
  approval?: ApprovalGate
  mcpClient?: MCPClient
  installedSkills?: InstalledSkillProvider
  mcpServers?: MCPServerProvider
  installedPlugins?: InstalledPluginProvider
  eventBus?: EventBusPort
  subagent?: AgentRunner
  checkpointStore?: CheckpointStore
  policy?: PolicyEngine
}
export type AgentResult = {
  success: boolean
  status: string
  runId: string
  resumed: boolean
  replayed: boolean
  steps: number
  attempts: number
  results: Record<string, ToolResult>
  final: string
  error?: string
  trace: TraceEntry[]
  elapsedMs: number
}

export class AgentHost {
  readonly config: AgentConfig
  readonly llm: LLMAdapter
  readonly memory: MemoryBackend
  readonly hooks: HookPipeline
  readonly approval: ApprovalGate
  readonly policy: PolicyEngine
  readonly events: EventBusPort
  readonly tools = new ToolRegistry()
  readonly router = new ToolRouter(this.tools)
  readonly skills = new SkillRegistry()
  readonly plugins: PluginLoader
  readonly checkpoints: CheckpointStore
  readonly mcp: MCPToolAdapter
  readonly installedSkills?: InstalledSkillProvider
  readonly mcpServers?: MCPServerProvider
  readonly installedPlugins?: InstalledPluginProvider
  private readonly managedMcp: MCPToolAdapter[] = []
  private readonly installedPluginNames: string[] = []
  readonly handoffs: HandoffCoordinator
  private memoryInitialized = false
  private extensionsInitialized = false
  private extensionInitialization?: Promise<void>
  private readonly installedSkillNames: string[] = []
  initialMemory?: MemoryEntry

  constructor(
    checkpointPath: string,
    config: Partial<AgentConfig> = {},
    dependencies: AgentDependencies = {},
  ) {
    this.config = { ...defaultConfig(), ...config }
    this.llm = dependencies.llm ?? new DeterministicLLMAdapter()
    this.memory = dependencies.memory ?? new InMemoryMemoryBackend()
    this.hooks = dependencies.hooks ?? new HookPipeline()
    this.approval = dependencies.approval ?? new DenyApprovalGate()
    this.policy = dependencies.policy ?? new DefaultPolicyEngine(this.config.allowedTools)
    this.events = dependencies.eventBus ?? new EventBus()
    this.plugins = new PluginLoader(this.tools, this.skills, this.hooks)
    this.checkpoints = dependencies.checkpointStore ?? new JsonCheckpointStore(checkpointPath)
    this.mcp = new MCPToolAdapter(dependencies.mcpClient ?? new FakeMCPClient(), "catalog-server")
    this.installedSkills = dependencies.installedSkills
    this.mcpServers = dependencies.mcpServers
    this.installedPlugins = dependencies.installedPlugins
    this.handoffs = new HandoffCoordinator(dependencies.subagent ?? new ReviewSubagent(), this.events)
  }

  private validatePlan(plan: PlanStep[]): void {
    const ids = plan.map((step) => step.id)
    if (new Set(ids).size !== ids.length) throw new Error("计划步骤 id 必须唯一")
    const known = new Set(ids)
    for (const step of plan) {
      if (step.dependsOn.includes(step.id) || step.dependsOn.some((id) => !known.has(id))) {
        throw new Error(`步骤 ${step.id} 包含无效依赖`)
      }
    }
  }

  private async recordMemory(state: RunState, role: string, content: string): Promise<void> {
    const entry = { role, content }
    state.memory.push(entry)
    await this.memory.append(state.runId, entry)
  }

  async run(task: string, runId: string, conversationContext: string[] = []): Promise<AgentResult> {
    const started = performance.now()
    try {
      return await this.runInternal(task, runId, started, conversationContext)
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error
      let state: RunState
      try {
        state = await this.checkpoints.load(runId) ?? new RunState(runId, task, [])
      } catch {
        state = new RunState(runId, task, [])
      }
      state.status = "failed"
      state.error = `runtime_error: ${String(error)}`
      try {
        await this.hooks.emit("on_error", { error: String(error) }, state)
      } catch (hookError) {
        state.trace.push({ event: "on_error_failed", error: String(hookError) })
      }
      try { await this.events.publish("task.failed", { runId, error: state.error }) } catch {}
      try { await this.checkpoints.save(state) } catch (checkpointError) {
        state.trace.push({ event: "checkpoint_error", error: String(checkpointError) })
      }
      return this.result(state, state.error, false, started)
    }
  }

  private async initializeExtensions(): Promise<void> {
    if (this.extensionsInitialized) return
    if (this.extensionInitialization) return this.extensionInitialization
    this.extensionInitialization = (async () => {
      try {
        for (const skill of await this.installedSkills?.loadSkills() ?? []) {
          this.skills.register(skill); this.installedSkillNames.push(skill.name)
        }
        await this.mcp.registerTools(this.tools)
        for (const [serverName, client] of await this.mcpServers?.connectEnabled() ?? []) {
          const adapter = new MCPToolAdapter(client, serverName)
          await adapter.registerTools(this.tools); this.managedMcp.push(adapter)
        }
        for (const plugin of await this.installedPlugins?.loadPlugins() ?? []) {
          this.plugins.load(plugin); this.installedPluginNames.push(plugin.manifest.name)
        }
        this.extensionsInitialized = true
      } catch (error) {
        await this.rollbackExtensions(true)
        throw error
      } finally {
        this.extensionInitialization = undefined
      }
    })()
    return this.extensionInitialization
  }

  async closeExtensions(): Promise<void> {
    await this.extensionInitialization
    const errors = await this.rollbackExtensions(true)
    if (errors.length) throw new Error(`扩展关闭存在错误: ${errors.join("; ")}`)
  }

  private async rollbackExtensions(closeProvider: boolean): Promise<string[]> {
    const errors: string[] = []
    for (const name of [...this.installedPluginNames].reverse()) {
      try { this.plugins.unload(name) } catch (error) {
        errors.push(`plugin ${name}: ${String(error)}`)
      }
    }
    this.installedPluginNames.length = 0
    for (const adapter of [...this.managedMcp].reverse()) adapter.unregisterTools(this.tools)
    this.managedMcp.length = 0
    this.mcp.unregisterTools(this.tools)
    for (const name of [...this.installedSkillNames].reverse()) this.skills.unregister(name)
    this.installedSkillNames.length = 0
    if (closeProvider) {
      try { await this.mcpServers?.close() } catch (error) {
        errors.push(`mcp provider: ${String(error)}`)
      }
    }
    this.extensionsInitialized = false
    return errors
  }

  private capabilitySnapshot(): CapabilitySnapshot {
    const body = {
      tools: this.tools.list().map((tool) => ({
        name: tool.name, schema: tool.parameters,
        source: tool.source, sourceName: tool.sourceName,
      })),
      toolAliases: this.tools.listAliases(),
      skills: this.skills.list().map((skill) => ({
        name: skill.name, owner: skill.owner,
        checksum: sha256Text(skill.instructions),
      })),
      policyVersion: this.policy.version,
      config: { allowedTools: [...this.config.allowedTools].sort() },
    }
    return withSnapshotHash(body)
  }

  private async runInternal(
    task: string,
    runId: string,
    started: number,
    conversationContext: string[],
  ): Promise<AgentResult> {
    await this.initializeExtensions()
    const currentSnapshot = this.capabilitySnapshot()
    const runRouter = new ToolRouter(this.tools.snapshot())
    if (!this.memoryInitialized && this.initialMemory) {
      await this.memory.remember("default", this.initialMemory)
      this.memoryInitialized = true
    }
    const restored = await this.checkpoints.load(runId)
    if (restored && restored.task !== task) {
      const mismatch = new RunState(runId, task, [])
      mismatch.status = "failed"
      mismatch.error = "run_task_mismatch"
      return this.result(mismatch, "同一 runId 不能恢复为不同任务", false, started)
    }
    if (
      restored?.capabilitySnapshot &&
      restored.capabilitySnapshot.snapshotHash !== currentSnapshot.snapshotHash
    ) {
      const mismatch = new RunState(runId, task, [])
      mismatch.status = "failed"
      mismatch.error = "capability_snapshot_mismatch"
      mismatch.capabilitySnapshot = currentSnapshot
      return this.result(mismatch, mismatch.error, false, started)
    }
    let state: RunState
    let resumed = false
    if (restored) {
      state = restored
      const existingMemory = await this.memory.recent(
        runId, Math.max(12, state.memory.length),
      )
      for (const entry of state.memory) {
        if (!existingMemory.some(
          (item) => item.role === entry.role && item.content === entry.content,
        )) {
          await this.memory.append(runId, entry)
          existingMemory.push(entry)
        }
      }
      resumed = state.status !== "completed"
      if (state.status === "completed") {
        return this.result(
          state, await this.llm.finalAnswer(task, state.results), false, started, true,
        )
      }
      await this.hooks.emit("before_run", { task, resumed: true }, state)
      await this.hooks.emit("on_resume", { status: state.status }, state)
    } else {
      state = new RunState(runId, task, [])
      state.capabilitySnapshot = currentSnapshot
      await this.events.publish("task.started", { runId })
      await this.hooks.emit("before_run", { task }, state)
      const recalled = await this.memory.search("default", task)
      const discovered = this.skills.discover(task)
      state.trace.push({ event: "skills_discovered", skills: discovered.map((item) => item.name) })
      const loaded = this.skills.load(discovered.map((item) => item.name))
      state.trace.push({ event: "skills_loaded", skills: loaded.map((item) => item.name) })
      const context = [
        this.config.instructions,
        ...conversationContext,
        ...loaded.map((skill) => skill.instructions),
        ...recalled.map((entry) => entry.content),
      ]
      await this.hooks.emit("before_plan", { context }, state)
      state.plan = await this.llm.createPlan(
        task,
        runRouter.availableNames(),
        context,
      )
      this.validatePlan(state.plan)
      await this.hooks.emit("after_plan", { steps: state.plan.length }, state)
      await this.recordMemory(state, "system", this.config.instructions)
      for (const item of context.slice(1)) await this.recordMemory(state, "context", item)
      await this.recordMemory(state, "user", task)
      await this.checkpoints.save(state)
    }
    await new DependencyExecutor(
      runRouter, this.hooks, this.approval, this.memory, this.config,
      this.policy, currentSnapshot.snapshotHash,
    )
      .run(state, () => this.checkpoints.save(state))
    const final = state.status === "completed"
      ? await this.llm.finalAnswer(task, state.results)
      : state.error ?? "任务未完成"
    await this.recordMemory(
      state, state.status === "completed" ? "assistant" : "system", final,
    )
    await this.hooks.emit("after_run", { status: state.status }, state)
    await this.hooks.emit("on_finish", { status: state.status }, state)
    await this.events.publish("task.completed", { runId, status: state.status })
    await this.checkpoints.save(state)
    return this.result(state, final, resumed, started)
  }

  private result(
    state: RunState,
    final: string,
    resumed: boolean,
    started: number,
    replayed = false,
  ): AgentResult {
    return {
      success: state.status === "completed",
      status: state.status,
      runId: state.runId,
      resumed,
      replayed,
      steps: state.stepCount,
      attempts: state.attemptCount,
      results: state.results,
      final,
      error: state.error,
      trace: state.trace,
      elapsedMs: Math.round((performance.now() - started) * 100) / 100,
    }
  }
}
