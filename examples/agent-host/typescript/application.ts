/** AgentHost 之上的 Application Session 与多轮消息层。 */

import { storeScope, withKeyLock } from "./keyed-lock.js"
import { randomUUID } from "node:crypto"
import { atomicWriteText } from "./safe-io.js"
import { existsSync, mkdirSync, readFileSync } from "node:fs"
import { dirname } from "node:path"
import type { AgentResult } from "./assembly.js"

export type Message = {
  role: "user" | "assistant"
  content: string
  taskId?: string
  runId?: string
}
export type TaskRecord = {
  taskId: string
  runId: string
  request: string
  status: string
  idempotencyKey?: string
  context?: string[]
  result?: AgentResult
  answer?: string
  error?: string
}
export type Session = {
  sessionId: string
  messages: Message[]
  tasks: TaskRecord[]
}
export interface SessionStore {
  load(sessionId: string): Session | undefined
  save(session: Session): void
}

export class JsonSessionStore implements SessionStore {
  constructor(readonly path: string) { mkdirSync(dirname(path), { recursive: true }) }
  private read(): Record<string, Session> {
    return existsSync(this.path)
      ? JSON.parse(readFileSync(this.path, "utf8")) as Record<string, Session>
      : {}
  }
  load(sessionId: string): Session | undefined { return this.read()[sessionId] }
  save(session: Session): void {
    const data = this.read()
    data[session.sessionId] = session
    atomicWriteText(this.path, JSON.stringify(data, null, 2))
  }
}

export interface RunScopedAgent {
  run(task: string, runId: string, conversationContext?: string[]): Promise<AgentResult>
}
export type AgentFactory = (
  sessionId: string, taskId: string, runId: string,
) => RunScopedAgent

export class ConversationApplication {
  constructor(
    readonly store: SessionStore,
    readonly agentFactory: AgentFactory,
    readonly idFactory: () => string = () => randomUUID().replaceAll("-", ""),
    readonly maxContextMessages = 12,
  ) {
    if (maxContextMessages < 0 || !Number.isInteger(maxContextMessages)) throw new Error("maxContextMessages 必须是非负整数")
  }

  send(sessionId: string, content: string, idempotencyKey?: string): Promise<ApplicationResult> {
    return withKeyLock(storeScope(this.store), sessionId, async () => {
      if (!sessionId.trim() || !content.trim() || idempotencyKey === "") throw new Error("身份、消息与显式幂等键不能为空")
      const session = this.store.load(sessionId) ?? { sessionId, messages: [], tasks: [] }
      if (idempotencyKey !== undefined) {
        const existing = session.tasks.find((item) => item.idempotencyKey === idempotencyKey)
        if (existing) {
          if (existing.request !== content) throw new Error("idempotency_key_conflict")
          if (!existing.result) throw new Error("resume_required: 使用原 taskId 显式恢复")
          return this.response(sessionId, existing)
        }
      }
      const prior = this.maxContextMessages ? session.messages.slice(-this.maxContextMessages) : []
      const taskId = `task-${this.idFactory()}`, runId = `run-${this.idFactory()}`
      const record: TaskRecord = { taskId, runId, request: content, status: "pending", idempotencyKey,
        context: prior.map((message) => `${message.role}: ${message.content}`) }
      session.tasks.push(record)
      session.messages.push({ role: "user", content, taskId, runId })
      this.store.save(session)
      return this.execute(session, record)
    })
  }

  resume(sessionId: string, taskId: string): Promise<ApplicationResult> {
    return withKeyLock(storeScope(this.store), sessionId, async () => {
      const session = this.store.load(sessionId)
      const record = session?.tasks.find((item) => item.taskId === taskId)
      if (!session || !record) throw new Error("Session / Task 不存在")
      return record.result && record.status === "completed" ? this.response(sessionId, record) : this.execute(session, record)
    })
  }

  private async execute(session: Session, record: TaskRecord): Promise<ApplicationResult> {
    record.status = "running"; record.error = undefined
    this.store.save(session)
    let run: AgentResult
    try {
      run = await this.agentFactory(session.sessionId, record.taskId, record.runId)
        .run(record.request, record.runId, [...(record.context ?? [])])
    } catch (error) {
      record.status = error instanceof Error && error.name === "AbortError" ? "cancelled" : "failed"
      record.error = String(error)
      this.store.save(session)
      throw error
    }
    record.result = structuredClone(run)
    record.status = run.status
    record.answer = String(run.final || run.error || "任务未完成")
    const message: Message = { role: "assistant", content: record.answer, taskId: record.taskId, runId: record.runId }
    const index = session.messages.findIndex((item) => item.role === "assistant" && item.runId === record.runId)
    if (index < 0) session.messages.push(message)
    else session.messages[index] = message
    this.store.save(session)
    return this.response(session.sessionId, record)
  }

  private response(sessionId: string, record: TaskRecord): ApplicationResult {
    if (!record.result) throw new Error("Task 尚无结果")
    return { sessionId, taskId: record.taskId, runId: record.runId,
      answer: record.answer ?? "", run: structuredClone(record.result) }
  }

  getSession(sessionId: string): Session | undefined { return this.store.load(sessionId) }
}

export type ApplicationResult = { sessionId: string; taskId: string; runId: string; answer: string; run: AgentResult }
