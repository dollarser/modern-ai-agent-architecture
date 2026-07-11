import { AgentRuntime } from "./main.js"

const assert = (condition: boolean, message: string): void => {
  if (!condition) throw new Error(message)
}
const delay = (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

const completed = await new AgentRuntime().run(["search", "verify"], async (step) => ({
  done: step === "verify",
}))
assert(completed.status === "finished" && completed.success, "done result must finish")

const exhausted = await new AgentRuntime({ maxSteps: 1, stepTimeoutMs: 1_000 }).run(
  ["one", "two"],
  async () => ({ done: false }),
)
assert(exhausted.status === "exhausted" && !exhausted.success, "limit must exhaust")

const started = performance.now()
const timedOut = await new AgentRuntime({ maxSteps: 1, stepTimeoutMs: 20 }).run(
  ["slow"],
  async () => { await delay(200); return { done: true } },
)
assert(timedOut.status === "error", "timeout must be an error")
assert(performance.now() - started < 150, "timeout must return control promptly")

const runtime = new AgentRuntime()
const cancelled = await runtime.run(["cancel"], async () => {
  runtime.cancel()
  return { done: true }
})
assert(cancelled.status === "cancelled" && !cancelled.success, "cancel must be preserved")

console.log("runtime TypeScript tests: OK")
