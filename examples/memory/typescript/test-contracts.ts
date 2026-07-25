import { ArtifactView, buildContext, GovernedMemory, MemoryRecord } from "./contracts.js"

const assert = (condition: boolean, message: string): void => { if (!condition) throw new Error(message) }
const throws = (fn: () => void): void => {
  let failed = false
  try { fn() } catch { failed = true }
  assert(failed, "expected an exception")
}

const memory = new GovernedMemory()
const preference: MemoryRecord = { key: "preference/theme", content: "dark", tenantId: "t1", subjectId: "u1", provenance: "user_input", trust: "user_confirmed", consent: false }
throws(() => memory.put(preference))
memory.put({ ...preference, consent: true })
assert(memory.get("preference/theme", "t2", "u1") === undefined, "tenant isolation failed")
assert(memory.get("preference/theme", "t1", "u1")?.content === "dark", "memory lookup failed")
memory.put({ key: "temporary", content: "old", tenantId: "t1", subjectId: "u1", provenance: "tool_result", trust: "verified", consent: false, retentionUntil: Date.now() / 1000 - 1 })
assert(memory.get("temporary", "t1", "u1") === undefined, "retention failed")
const context = buildContext("rules", ["old history", "latest history"], [{ artifactId: "a1", summary: "report", mediaType: "text/plain", checksum: "abc" } as ArtifactView], 30)
assert(JSON.stringify(context.slice(0, 2)) === JSON.stringify(["rules", "[artifact:a1 text/plain sha256=abc] report"]), "artifact view failed")
assert(context.at(-1) === "latest history", "history selection failed")
console.log("memory/context contract tests: OK")
