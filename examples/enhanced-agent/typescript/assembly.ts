/** 第 16 章最终组装：可插拔端口与离线最小适配器。 */

import { dirname } from "node:path"
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"

export type ToolResult = {
  success: boolean
  error?: string
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
  sessionId: string
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

  constructor(
    public readonly sessionId: string,
    public readonly task: string,
    public plan: PlanStep[],
  ) {}

  static restore(data: StoredState): RunState {
    const state = new RunState(data.sessionId, data.task, data.plan)
    state.results = data.results
    state.memory = data.memory
    state.trace = data.trace
    state.approvals = data.approvals ?? {}
    state.stepCount = data.stepCount
    state.attemptCount = data.attemptCount
    state.status = data.status
    state.error = data.error
    return state
  }
}

// Memory port
export interface MemoryBackend {
  append(sessionId: string, entry: MemoryEntry): void
  recent(sessionId: string, limit?: number): MemoryEntry[]
  remember(namespace: string, entry: MemoryEntry): void
  search(namespace: string, query: string, limit?: number): MemoryEntry[]
}

export class InMemoryMemoryBackend implements MemoryBackend {
  readonly shortTerm = new Map<string, MemoryEntry[]>()
  readonly longTerm = new Map<string, MemoryEntry[]>()

  append(sessionId: string, entry: MemoryEntry): void {
    const entries = this.shortTerm.get(sessionId) ?? []
    entries.push(entry)
    this.shortTerm.set(sessionId, entries)
  }

  recent(sessionId: string, limit = 12): MemoryEntry[] {
    return [...(this.shortTerm.get(sessionId) ?? []).slice(-limit)]
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
) => void
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

  emit(event: string, payload: Record<string, unknown>, state: RunState): void {
    state.trace.push({ event, stepId: Number(payload.stepId) || undefined })
    for (const hook of this.hooks.get(event) ?? []) {
      try {
        hook.callback(event, payload, state)
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
  sessionId: string
}
export type Tool = {
  name: string
  description: string
  handler: (
    arguments_: Record<string, unknown>,
    context: ExecutionContext,
  ) => ToolResult | Promise<ToolResult>
  parameters?: Record<string, unknown>
  source?: ToolSource
  sourceName?: string
  state?: ToolState
  tags?: string[]
  requiresApproval?: boolean
}

export class ToolRegistry {
  private readonly tools = new Map<string, Tool>()

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
    const tool = this.tools.get(name)
    if (!tool) throw new Error(`Tool 未注册: ${name}`)
    return tool
  }

  list(): Tool[] {
    return [...this.tools.values()].sort((left, right) => left.name.localeCompare(right.name))
  }

  unregisterBySource(source: ToolSource, sourceName: string): number {
    const names = this.list()
      .filter((tool) => tool.source === source && tool.sourceName === sourceName)
      .map((tool) => tool.name)
    names.forEach((name) => this.tools.delete(name))
    return names.length
  }
}

export class ToolRouter {
  constructor(readonly registry: ToolRegistry) {}

  available(tag?: string): Tool[] {
    return this.registry.list().filter(
      (tool) => tool.state === ToolState.Active && (!tag || tool.tags?.includes(tag)),
    )
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
    return await this.resolve(name).handler(arguments_, context)
  }
}

// Skills, MCP and Plugins
export type Skill = { name: string; keywords: string[]; instructions: string }
export class SkillRegistry {
  private readonly skills = new Map<string, Skill>()
  register(skill: Skill): void { this.skills.set(skill.name, skill) }
  unregister(name: string): void { this.skills.delete(name) }
  match(task: string): Skill[] {
    const lowered = task.toLowerCase()
    return [...this.skills.values()].filter(
      (skill) => skill.keywords.some((keyword) => lowered.includes(keyword.toLowerCase())),
    )
  }
}

export type MCPToolDefinition = {
  name: string
  description: string
  inputSchema?: Record<string, unknown>
}
export interface MCPClient {
  listTools(): MCPToolDefinition[]
  callTool(name: string, arguments_: Record<string, unknown>): ToolResult | Promise<ToolResult>
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
  constructor(readonly client: MCPClient, readonly serverName: string) {}
  registerTools(registry: ToolRegistry): number {
    const definitions = this.client.listTools()
    for (const definition of definitions) {
      const name = definition.name
      registry.register({
        name,
        description: definition.description,
        parameters: definition.inputSchema,
        source: ToolSource.MCP,
        sourceName: this.serverName,
        tags: ["external"],
        handler: (arguments_) => this.client.callTool(name, arguments_),
      })
    }
    return definitions.length
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
    for (const tool of plugin.tools ?? []) {
      this.tools.register({ ...tool, source: ToolSource.Plugin, sourceName: name })
    }
    for (const skill of plugin.skills ?? []) this.skills.register(skill)
    for (const hook of plugin.hooks ?? []) {
      this.hooks.register(hook.event, { ...hook.definition, owner: name })
    }
    plugin.state = "active"
    this.plugins.set(name, plugin)
  }

  unload(name: string): void {
    const plugin = this.plugins.get(name)
    if (!plugin) throw new Error(`Plugin 未加载: ${name}`)
    this.plugins.delete(name)
    this.tools.unregisterBySource(ToolSource.Plugin, name)
    for (const skill of plugin.skills ?? []) this.skills.unregister(skill.name)
    this.hooks.unregisterOwner(name)
    plugin.state = "unloaded"
  }
}

// Approval and orchestration
export type ApprovalRequest = {
  id: string
  sessionId: string
  tool: string
  arguments: Record<string, unknown>
  reason: string
}
export interface ApprovalGate { decide(request: ApprovalRequest): boolean }
export class AutoApproveGate implements ApprovalGate { decide(): boolean { return true } }
export class ScriptedApprovalGate implements ApprovalGate {
  readonly requests: ApprovalRequest[] = []
  constructor(readonly decisions: Record<string, boolean>) {}
  decide(request: ApprovalRequest): boolean {
    this.requests.push(request)
    return this.decisions[request.tool] ?? false
  }
}

export class EventBus {
  readonly events: Array<Record<string, unknown>> = []
  private readonly subscribers = new Map<string, Array<(event: Record<string, unknown>) => void>>()
  subscribe(topic: string, callback: (event: Record<string, unknown>) => void): void {
    const callbacks = this.subscribers.get(topic) ?? []
    callbacks.push(callback)
    this.subscribers.set(topic, callbacks)
  }
  publish(topic: string, payload: Record<string, unknown>): void {
    const event = { topic, ...payload }
    this.events.push(event)
    for (const callback of this.subscribers.get(topic) ?? []) callback(event)
  }
}

export type HandoffRequest = {
  task: string
  parentSessionId: string
  parentTraceId: string
  depth: number
}
export interface AgentRunner { runTask(request: HandoffRequest): ToolResult }
export class ReviewSubagent implements AgentRunner {
  runTask(request: HandoffRequest): ToolResult {
    return {
      success: true,
      review: "子 Agent 已验证候选路径与变更说明",
      parentTraceId: request.parentTraceId,
    }
  }
}
export class HandoffCoordinator {
  constructor(
    readonly runner: AgentRunner,
    readonly events: EventBus,
    readonly maxDepth = 2,
  ) {}
  handoff(request: HandoffRequest): ToolResult {
    if (request.depth > this.maxDepth) return { success: false, error: "Handoff 超过最大深度" }
    this.events.publish("handoff.created", {
      sessionId: request.parentSessionId,
      traceId: request.parentTraceId,
    })
    const result = this.runner.runTask(request)
    this.events.publish("handoff.completed", {
      sessionId: request.parentSessionId,
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

export class JsonCheckpointStore {
  constructor(readonly path: string) { mkdirSync(dirname(path), { recursive: true }) }
  private readAll(): Record<string, StoredState> {
    if (!existsSync(this.path)) return {}
    return JSON.parse(readFileSync(this.path, "utf8")) as Record<string, StoredState>
  }
  save(state: RunState): void {
    const data = this.readAll()
    data[state.sessionId] = state
    const temporary = `${this.path}.tmp`
    writeFileSync(temporary, JSON.stringify(data, null, 2), "utf8")
    renameSync(temporary, this.path)
  }
  load(sessionId: string): RunState | undefined {
    const item = this.readAll()[sessionId]
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
  ) {}

  async run(state: RunState, checkpoint: () => void): Promise<void> {
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
        checkpoint()
        return
      }
      if (state.stepCount >= this.config.maxSteps) {
        state.status = "max_steps"
        state.error = `达到最大 Tool 步数: ${this.config.maxSteps}`
        checkpoint()
        return
      }
      if (
        this.config.interruptAfterSteps !== undefined &&
        state.stepCount - startedAt >= this.config.interruptAfterSteps
      ) {
        state.status = "interrupted"
        state.error = "按教学配置模拟中断，可恢复"
        checkpoint()
        return
      }
      let batch = ready.slice(0, this.config.maxSteps - state.stepCount)
      if (this.config.interruptAfterSteps !== undefined) {
        batch = batch.slice(0, this.config.interruptAfterSteps - (state.stepCount - startedAt))
      }
      const results = await Promise.all(batch.map((step) => this.executeStep(step, state)))
      batch.forEach((step, index) => {
        state.results[String(step.id)] = results[index]
        state.stepCount += 1
        state.memory.push({
          role: "tool",
          content: JSON.stringify({ stepId: step.id, tool: step.tool, result: results[index] }),
        })
        this.memory.append(state.sessionId, state.memory[state.memory.length - 1])
      })
      checkpoint()
    }
    const failure = Object.values(state.results).find((result) => !result.success)
    state.status = failure ? "failed" : "completed"
    state.error = failure ? String(failure.error ?? "Tool 执行失败") : undefined
    checkpoint()
  }

  private async executeStep(step: PlanStep, state: RunState): Promise<ToolResult> {
    const payload = { stepId: step.id, tool: step.tool, arguments: step.arguments }
    try {
      this.hooks.emit("before_tool", payload, state)
      const tool = this.router.resolve(step.tool)
      if (tool.requiresApproval) {
        const approvalId = `${state.sessionId}:${step.id}:${step.tool}`
        if (state.approvals[approvalId] === undefined) {
          const request: ApprovalRequest = {
            id: approvalId,
            sessionId: state.sessionId,
            tool: step.tool,
            arguments: step.arguments,
            reason: "Tool 声明 requiresApproval",
          }
          this.hooks.emit("before_approval", { ...payload, request: request.id }, state)
          state.approvals[approvalId] = this.approval.decide(request)
          this.hooks.emit("after_approval", { ...payload, approved: state.approvals[approvalId] }, state)
        }
        if (!state.approvals[approvalId]) {
          const result = { success: false, error: `审批拒绝执行: ${step.tool}` }
          this.hooks.emit("on_tool_error", { ...payload, result }, state)
          this.hooks.emit("after_tool", { ...payload, result }, state)
          return result
        }
      }
    } catch (error) {
      const result = { success: false, error: `Guardrail 拒绝执行: ${String(error)}` }
      this.hooks.emit("on_tool_error", { ...payload, result }, state)
      this.hooks.emit("after_tool", { ...payload, result }, state)
      return result
    }

    const context: ExecutionContext = {
      task: state.task,
      results: state.results,
      sessionId: state.sessionId,
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
          this.hooks.emit("after_tool", { ...payload, result: withAttempts }, state)
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
    this.hooks.emit("on_tool_error", { ...payload, result }, state)
    this.hooks.emit("after_tool", { ...payload, result }, state)
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
  eventBus?: EventBus
  subagent?: AgentRunner
}
export type AgentResult = {
  success: boolean
  status: string
  sessionId: string
  resumed: boolean
  steps: number
  attempts: number
  results: Record<string, ToolResult>
  final: string
  error?: string
  trace: TraceEntry[]
  elapsedMs: number
}

export class EnhancedAgent {
  readonly config: AgentConfig
  readonly llm: LLMAdapter
  readonly memory: MemoryBackend
  readonly hooks: HookPipeline
  readonly approval: ApprovalGate
  readonly events: EventBus
  readonly tools = new ToolRegistry()
  readonly router = new ToolRouter(this.tools)
  readonly skills = new SkillRegistry()
  readonly plugins: PluginLoader
  readonly checkpoints: JsonCheckpointStore
  readonly mcp: MCPToolAdapter
  readonly handoffs: HandoffCoordinator

  constructor(
    checkpointPath: string,
    config: Partial<AgentConfig> = {},
    dependencies: AgentDependencies = {},
  ) {
    this.config = { ...defaultConfig(), ...config }
    this.llm = dependencies.llm ?? new DeterministicLLMAdapter()
    this.memory = dependencies.memory ?? new InMemoryMemoryBackend()
    this.hooks = dependencies.hooks ?? new HookPipeline()
    this.approval = dependencies.approval ?? new AutoApproveGate()
    this.events = dependencies.eventBus ?? new EventBus()
    this.plugins = new PluginLoader(this.tools, this.skills, this.hooks)
    this.checkpoints = new JsonCheckpointStore(checkpointPath)
    this.mcp = new MCPToolAdapter(dependencies.mcpClient ?? new FakeMCPClient(), "catalog-server")
    this.handoffs = new HandoffCoordinator(dependencies.subagent ?? new ReviewSubagent(), this.events)
    this.assemble()
  }

  private assemble(): void {
    this.skills.register({
      name: "config-review",
      keywords: ["配置", "config"],
      instructions: "先检索候选路径，再生成变更并交给子 Agent 复核。",
    })
    this.memory.remember("default", {
      role: "preference",
      content: "数据库 配置 变更必须给出文件路径并经过审查",
    })
    this.mcp.registerTools(this.tools)
    this.tools.register({
      name: "inspect_candidate",
      description: "检查首个候选",
      tags: ["read"],
      handler: (_arguments, context) => ({
        success: true,
        path: (context.results["1"].matches as string[])[0],
        finding: "发现数据库连接配置入口",
      }),
    })
    this.tools.register({
      name: "delegate_review",
      description: "Handoff 给审查子 Agent",
      tags: ["orchestration"],
      handler: (_arguments, context) => this.handoffs.handoff({
        task: "审查变更建议",
        parentSessionId: context.sessionId,
        parentTraceId: `step-${Object.keys(context.results).length + 1}`,
        depth: 1,
      }),
    })
    this.tools.register({
      name: "compose_report",
      description: "组合最终报告",
      tags: ["output"],
      handler: (_arguments, context) => ({
        success: true,
        report: `${String(context.results["4"].proposal)}；${String(context.results["5"].review)}。`,
      }),
    })
    this.plugins.load({
      manifest: { name: "review-pack", version: "1.0.0", permissions: ["tools:register"] },
      tools: [
        {
          name: "summarize_matches",
          description: "汇总 MCP 候选",
          tags: ["analysis"],
          handler: (_arguments, context) => ({
            success: true,
            count: (context.results["1"].matches as string[]).length,
            summary: "找到 2 个候选文件",
          }),
        },
        {
          name: "propose_change",
          description: "生成配置变更建议",
          tags: ["write"],
          requiresApproval: true,
          handler: (_arguments, context) => ({
            success: true,
            proposal: `建议更新 ${String(context.results["2"].path)}（${String(context.results["3"].summary)}）`,
          }),
        },
      ],
    })
    this.hooks.register("before_tool", {
      kind: HookKind.Guard,
      priority: 10,
      name: "tool-allowlist",
      callback: (_event, payload) => {
        const tool = String(payload.tool)
        if (!this.config.allowedTools.has(tool)) throw new Error(`Tool 不在允许列表中: ${tool}`)
      },
    })
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

  private recordMemory(state: RunState, role: string, content: string): void {
    const entry = { role, content }
    state.memory.push(entry)
    this.memory.append(state.sessionId, entry)
  }

  async run(task: string, sessionId: string): Promise<AgentResult> {
    const started = performance.now()
    const restored = this.checkpoints.load(sessionId)
    if (restored && restored.task !== task) {
      return this.result(restored, "同一 sessionId 不能恢复为不同任务", false, started)
    }
    let state: RunState
    let resumed = false
    if (restored) {
      state = restored
      resumed = state.status !== "completed"
      if (state.status === "completed") {
        return this.result(state, await this.llm.finalAnswer(task, state.results), true, started)
      }
      this.hooks.emit("before_run", { task, resumed: true }, state)
      this.hooks.emit("on_resume", { status: state.status }, state)
    } else {
      state = new RunState(sessionId, task, [])
      this.events.publish("task.started", { sessionId })
      this.hooks.emit("before_run", { task }, state)
      const context = [
        this.config.instructions,
        ...this.skills.match(task).map((skill) => skill.instructions),
        ...this.memory.search("default", task).map((entry) => entry.content),
      ]
      this.hooks.emit("before_plan", { context }, state)
      state.plan = await this.llm.createPlan(
        task,
        this.router.available().map((tool) => tool.name),
        context,
      )
      this.validatePlan(state.plan)
      this.hooks.emit("after_plan", { steps: state.plan.length }, state)
      this.recordMemory(state, "system", this.config.instructions)
      context.slice(1).forEach((item) => this.recordMemory(state, "context", item))
      this.recordMemory(state, "user", task)
      this.checkpoints.save(state)
    }
    await new DependencyExecutor(this.router, this.hooks, this.approval, this.memory, this.config)
      .run(state, () => this.checkpoints.save(state))
    const final = state.status === "completed"
      ? await this.llm.finalAnswer(task, state.results)
      : state.error ?? "任务未完成"
    this.recordMemory(state, state.status === "completed" ? "assistant" : "system", final)
    this.hooks.emit("after_run", { status: state.status }, state)
    this.hooks.emit("on_finish", { status: state.status }, state)
    this.events.publish("task.completed", { sessionId, status: state.status })
    this.checkpoints.save(state)
    return this.result(state, final, resumed, started)
  }

  private result(state: RunState, final: string, resumed: boolean, started: number): AgentResult {
    return {
      success: state.status === "completed",
      status: state.status,
      sessionId: state.sessionId,
      resumed,
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
