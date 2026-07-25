import type { AgentHost } from "./assembly.js"

export type RemoteTaskRequest = {
  runId: string; taskId: string; tenantId: string; owner: string
  idempotencyKey: string; message: string
}

export interface RemoteTaskClient {
  submit(request: RemoteTaskRequest): Promise<Record<string, unknown>>
  getTask(taskId: string, tenantId: string, owner: string): Promise<Record<string, unknown>>
  getArtifact(artifactId: string, tenantId: string, owner: string): Promise<Buffer>
}

export class HostA2AAdapter {
  private readonly runTasks = new Map<string, string>()
  constructor(private readonly host: AgentHost, private readonly client: RemoteTaskClient) {}

  async submit(request: RemoteTaskRequest): Promise<Record<string, unknown>> {
    const bound = this.runTasks.get(request.runId)
    if (bound && bound !== request.taskId) {
      return { success: false, error_code: "checkpoint_mismatch",
        error_message: "一个 run_id 不能绑定多个远程 task", retryable: false }
    }
    this.runTasks.set(request.runId, request.taskId)
    const result = await this.client.submit(request)
    await this.host.events.publish("a2a.task.submitted", {
      runId: request.runId, taskId: request.taskId, tenantId: request.tenantId,
      status: result.status ?? "submitted",
    })
    return result
  }

  async getTask(runId: string, taskId: string, tenantId: string, owner: string): Promise<Record<string, unknown>> {
    if (this.runTasks.get(runId) !== taskId) {
      return { success: false, error_code: "checkpoint_mismatch",
        error_message: "run_id 与远程 task_id 不匹配", retryable: false }
    }
    return this.client.getTask(taskId, tenantId, owner)
  }

  async getArtifact(runId: string, artifactId: string, tenantId: string, owner: string): Promise<Buffer> {
    if (!this.runTasks.has(runId)) throw new Error("run_id 尚未绑定远程 task")
    return this.client.getArtifact(artifactId, tenantId, owner)
  }
}
