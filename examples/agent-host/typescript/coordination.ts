/** Observer Event Bus 与 Subagent Handoff 协调。 */

import type { ToolResult } from "./runtime-state.js"

export enum HookKind { Guard = "guard", Observer = "observer" }

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
      try {
        await subscriber.callback(event)
      } catch (error) {
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

export interface AgentRunner {
  runTask(request: HandoffRequest): ToolResult | Promise<ToolResult>
}

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
    if (request.depth > this.maxDepth) {
      return { success: false, error: "Handoff 超过最大深度" }
    }
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
