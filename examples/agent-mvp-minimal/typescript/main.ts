type JsonObject = Record<string, unknown>

interface ToolCall {
  name: string
  arguments: JsonObject
}

interface TaskState {
  task: string
  stepCount: number
  observations: JsonObject[]
  finished: boolean
  error?: string
}

class RulePlanner {
  reason(task: string, instructions: string): string {
    return `遵循约束“${instructions}”，先查找相关信息，再整理可读结论：${task}`
  }

  plan(task: string): ToolCall[] {
    return [
      { name: "search_catalog", arguments: { query: task } },
      { name: "summarize_observation", arguments: {} },
    ]
  }
}

type ToolHandler = (arguments_: JsonObject, state: TaskState) => JsonObject

class ToolDispatcher {
  private readonly handlers: Map<string, ToolHandler>

  constructor() {
    this.handlers = new Map([
      ["search_catalog", this.searchCatalog],
      ["summarize_observation", this.summarizeObservation],
    ])
  }

  execute(call: ToolCall, state: TaskState): JsonObject {
    const handler = this.handlers.get(call.name)
    return handler ? handler(call.arguments, state) : { ok: false, error: `unknown tool: ${call.name}` }
  }

  private searchCatalog(arguments_: JsonObject): JsonObject {
    const query = String(arguments_.query)
    return {
      ok: true,
      matches: [
        { path: "src/config.ts", snippet: `connection settings for: ${query}` },
        { path: "src/db.ts", snippet: "createConnection(config)" },
      ],
    }
  }

  private summarizeObservation(_: JsonObject, state: TaskState): JsonObject {
    const previous = state.observations.at(-1) ?? { matches: [] }
    const matches = Array.isArray(previous.matches) ? previous.matches : []
    return { ok: true, summary: `找到 ${matches.length} 条候选信息，等待用户确认下一步。` }
  }
}

class MinimalAgent {
  private readonly planner = new RulePlanner()
  private readonly tools = new ToolDispatcher()

  constructor(
    private readonly instructions = "只读取信息，不执行有副作用的操作",
    private readonly maxSteps = 4,
  ) {
    if (maxSteps < 0) throw new Error("maxSteps must be non-negative")
  }

  run(task: string): TaskState {
    const state: TaskState = { task, stepCount: 0, observations: [], finished: false }
    console.log(`task: ${task}`)
    console.log(`instructions: ${this.instructions}`)
    console.log(`reason: ${this.planner.reason(task, this.instructions)}`)

    const plan = this.planner.plan(task)
    console.log(`plan: ${plan.map((call) => call.name).join(", ")}`)

    for (const call of plan) {
      if (state.stepCount >= this.maxSteps) {
        state.error = `达到最大步数: ${this.maxSteps}`
        break
      }
      state.stepCount += 1
      console.log(`execute: ${call.name}`)
      const observation = this.tools.execute(call, state)
      state.observations.push(observation)
      console.log(`observe: ${JSON.stringify(observation)}`)
      if (observation.ok !== true) {
        state.error = String(observation.error ?? "tool execution failed")
        break
      }
    }

    if (state.error === undefined) state.finished = true
    console.log(`finish: steps=${state.stepCount}, finished=${state.finished}, error=${state.error ?? "none"}`)
    return state
  }
}

new MinimalAgent().run("查找数据库连接配置")
