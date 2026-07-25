import { FakeProvider } from "./main.js"

const provider = new FakeProvider()
const result = provider.complete("hello", { tools: [{ name: "search" }], schema: { type: "object" } })
if (result.success !== true || !(result.usage as Record<string, unknown>)) throw new Error("full capability contract failed")
if (JSON.stringify([...provider.stream("hello world")]) !== JSON.stringify(["hello", "world"])) throw new Error("stream failed")
provider.cancel()
if (!provider.cancelled) throw new Error("cancel failed")
const limited = new FakeProvider({ toolCalling: false, structuredOutput: true, streaming: false, cancel: true })
if (limited.complete("hello", { tools: [{ name: "search" }] }).error_code !== "capability_unsupported") throw new Error("unsupported tool calling accepted")
try { [...limited.stream("hello")] ; throw new Error("unsupported streaming accepted") } catch (error) {
  if (!String(error).includes("capability_unsupported")) throw error
}
console.log("model capability TypeScript tests: OK")
