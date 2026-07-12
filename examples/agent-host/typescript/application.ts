/** AgentHost 之上的 Application Session 与多轮消息层。 */

import { randomUUID } from "node:crypto"
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
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
    const temporary = `${this.path}.tmp`
    writeFileSync(temporary, JSON.stringify(data, null, 2), "utf8")
    renameSync(temporary, this.path)
  }
}

export interface RunScopedAgent {
  run(task: string, runId: string, conversationContext?: string[]): Promise<AgentResult>
}
export type AgentFactory = (
  sessionId: string, taskId: string, runId: string,
) => RunScopedAgent

export class ConversationApplication {
  private queue: Promise<unknown> = Promise.resolve()
  constructor(
    readonly store: SessionStore,
    readonly agentFactory: AgentFactory,
    readonly idFactory: () => string = () => randomUUID().replaceAll("-", ""),
    readonly maxContextMessages = 12,
  ) {}

  send(sessionId: string, content: string): Promise<{
    sessionId: string
    taskId: string
    runId: string
    answer: string
    run: AgentResult
  }> {
    const execute = async () => {
      if (!sessionId.trim() || !content.trim()) throw new Error("sessionId 与消息内容不能为空")
      const session = this.store.load(sessionId) ?? { sessionId, messages: [], tasks: [] }
      const prior = session.messages.slice(-this.maxContextMessages)
      const taskId = `task-${this.idFactory()}`, runId = `run-${this.idFactory()}`
      const record = { taskId, runId, request: content, status: "pending" }
      session.tasks.push(record)
      session.messages.push({ role: "user", content, taskId, runId })
      this.store.save(session)

      const context = prior.map((message) => `${message.role}: ${message.content}`)
      const run = await this.agentFactory(sessionId, taskId, runId)
        .run(content, runId, context)
      record.status = run.status
      const answer = String(run.final || run.error || "任务未完成")
      session.messages.push({ role: "assistant", content: answer, taskId, runId })
      this.store.save(session)
      return { sessionId, taskId, runId, answer, run }
    }
    const result = this.queue.then(execute, execute)
    this.queue = result.then(() => undefined, () => undefined)
    return result
  }

  getSession(sessionId: string): Session | undefined { return this.store.load(sessionId) }
}
