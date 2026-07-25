import { createHash } from "node:crypto"

export type Status = "submitted" | "working" | "completed" | "cancel_requested"
export type AgentCard = { name: string; skills: string[]; authScheme: string }
export type ArtifactRef = {
  artifactId: string; taskId: string; tenantId: string; owner: string
  mediaType: string; checksum: string; size: number; content: Buffer
}
export type Task = {
  taskId: string; contextId: string; tenantId: string; owner: string
  status: Status; events: Array<Record<string, unknown>>; artifacts: ArtifactRef[]
}

export class ArtifactStore {
  private readonly items = new Map<string, ArtifactRef>()
  put(task: Task, content: Buffer, mediaType: string): ArtifactRef {
    const artifactId = `artifact-${this.items.size + 1}`
    const ref = { artifactId, taskId: task.taskId, tenantId: task.tenantId, owner: task.owner,
      mediaType, checksum: createHash("sha256").update(content).digest("hex"),
      size: content.length, content }
    this.items.set(artifactId, ref)
    return ref
  }
  get(artifactId: string, tenantId: string, owner: string): Buffer {
    const ref = this.items.get(artifactId)
    if (!ref) throw new Error("artifact not found")
    if (ref.tenantId !== tenantId || ref.owner !== owner) throw new Error("artifact scope mismatch")
    return ref.content
  }
}

export class InMemoryA2A {
  readonly card: AgentCard = { name: "report-agent", skills: ["report"], authScheme: "bearer" }
  readonly artifacts = new ArtifactStore()
  readonly tasks = new Map<string, Task>()
  private readonly idempotency = new Map<string, string>()

  submit(taskId: string, idempotencyKey: string, tenantId: string, owner: string): Task {
    const existing = this.idempotency.get(idempotencyKey)
    if (existing) return this.tasks.get(existing)!
    const task: Task = { taskId, contextId: `ctx-${taskId}`, tenantId, owner,
      status: "submitted", events: [], artifacts: [] }
    this.tasks.set(taskId, task); this.idempotency.set(idempotencyKey, taskId); this.emit(task, "submitted")
    return task
  }

  work(taskId: string, payload: unknown): Task {
    const task = this.tasks.get(taskId)!; this.emit(task, "working")
    const ref = this.artifacts.put(task, Buffer.from(JSON.stringify(payload)), "application/json")
    task.artifacts.push(ref); this.emit(task, "completed"); return task
  }

  cancel(taskId: string): Task { const task = this.tasks.get(taskId)!; this.emit(task, "cancel_requested"); return task }
  private emit(task: Task, status: Status): void {
    task.status = status
    task.events.push({ taskId: task.taskId, status, sequence: task.events.length + 1, timestamp: new Date().toISOString() })
  }
}
