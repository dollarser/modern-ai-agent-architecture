/** Run 状态与 Memory Port；保持执行状态模型独立于 Host 组装。 */

import type { CapabilitySnapshot } from "./governance.js"

export type ToolResult = {
  success: boolean
  error?: string
  capabilitySnapshot?: CapabilitySnapshot
  finalAnswer?: string
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

export type StoredState = {
  runId: string
  task: string
  plan: PlanStep[]
  results: Record<string, ToolResult>
  memory: MemoryEntry[]
  trace: TraceEntry[]
  approvals: Record<string, boolean>
  executions?: Record<string, string>
  stepCount: number
  attemptCount: number
  status: string
  error?: string
  capabilitySnapshot?: CapabilitySnapshot
  finalAnswer?: string
}

export class RunState implements StoredState {
  results: Record<string, ToolResult> = {}
  memory: MemoryEntry[] = []
  trace: TraceEntry[] = []
  approvals: Record<string, boolean> = {}
  executions: Record<string, string> = {}
  stepCount = 0
  attemptCount = 0
  status = "pending"
  error?: string
  capabilitySnapshot?: CapabilitySnapshot
  finalAnswer?: string

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
    state.executions = data.executions ?? {}
    state.stepCount = data.stepCount
    state.attemptCount = data.attemptCount
    state.status = data.status
    state.error = data.error
    state.finalAnswer = data.finalAnswer
    state.capabilitySnapshot = data.capabilitySnapshot
    return state
  }
}

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
