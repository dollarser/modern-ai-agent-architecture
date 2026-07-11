/** 第 9 章：可测试的最小 Agent Runtime 状态机。 */

declare const process: { argv: string[] }

export type RunStatus = "idle" | "running" | "finished" | "exhausted" | "cancelled" | "error"
export type Observation = { done?: boolean; [key: string]: unknown }
export type Executor = (step: string) => Promise<Observation>

export type RuntimeConfig = {
  maxSteps: number
  stepTimeoutMs: number
}

export type RunResult = {
  status: RunStatus
  success: boolean
  stepCount: number
  observations: Observation[]
  error?: string
}

const defaultConfig: RuntimeConfig = { maxSteps: 4, stepTimeoutMs: 1_000 }

export class AgentRuntime {
  private result: RunResult = {
    status: "idle",
    success: false,
    stepCount: 0,
    observations: [],
  }

  constructor(private readonly config: RuntimeConfig = defaultConfig) {}

  cancel(): void {
    if (this.result.status === "running") this.result.status = "cancelled"
  }

  async run(plan: string[], executor: Executor): Promise<RunResult> {
    this.result = { status: "running", success: false, stepCount: 0, observations: [] }

    for (const step of plan) {
      if (this.isCancelled()) return this.result
      if (this.result.stepCount >= this.config.maxSteps) {
        this.result.status = "exhausted"
        this.result.error = `达到最大 Tool 步数: ${this.config.maxSteps}`
        return this.result
      }

      let observation: Observation
      try {
        observation = await this.withTimeout(executor(step), `步骤超时: ${step}`)
      } catch (error) {
        this.result.status = "error"
        this.result.error = String(error)
        return this.result
      }

      this.result.stepCount += 1
      this.result.observations.push(observation)
      if (this.isCancelled()) return this.result
      if (observation.done === true) {
        this.result.status = "finished"
        this.result.success = true
        return this.result
      }
    }

    this.result.status = "exhausted"
    this.result.error = "计划已执行完，但未满足完成条件"
    return this.result
  }

  private withTimeout<T>(work: Promise<T>, message: string): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(message)), this.config.stepTimeoutMs)
      work.then(
        (value) => { clearTimeout(timer); resolve(value) },
        (error: unknown) => { clearTimeout(timer); reject(error) },
      )
    })
  }

  private isCancelled(): boolean {
    return this.result.status === "cancelled"
  }
}

const delay = (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

async function demo(): Promise<void> {
  const runtime = new AgentRuntime()
  const result = await runtime.run(["search", "inspect", "verify"], async (step) => {
    await delay(10)
    return { step, done: step === "verify" }
  })
  console.log(result)
}

const entry = process.argv[1]
if (entry && decodeURIComponent(new URL(import.meta.url).pathname) === entry) {
  await demo()
}
