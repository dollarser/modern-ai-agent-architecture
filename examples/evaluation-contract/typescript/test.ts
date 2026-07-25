import { runCase } from "./main.js"

const c = { caseId: "case-1", allowedTools: ["orders.search"], forbiddenTools: ["orders.update"], expectedStatus: "completed", maxToolCalls: 2, versions: { agent: "a1" } }
const good = runCase(c, [{ event: "tool_call", tool: "orders.search" }, { status: "completed" }])
if (good.passed !== true) throw new Error("valid trace was rejected")
const bad = runCase(c, [
  { event: "tool_call", tool: "orders.update" },
  { event: "tool_call", tool: "orders.search" },
  { event: "tool_call", tool: "orders.search" },
  { status: "completed" },
])
if (bad.passed !== false || JSON.stringify(bad.forbiddenTools) !== JSON.stringify(["orders.update"])) throw new Error("invalid trace was accepted")
console.log("evaluation contract TypeScript tests: OK")
