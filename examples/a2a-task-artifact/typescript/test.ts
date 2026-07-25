import assert from "node:assert/strict"
import { InMemoryA2A } from "./main.js"

const server = new InMemoryA2A()
const task = server.submit("task-1", "idem-1", "tenant-a", "alice")
assert.equal(server.submit("task-2", "idem-1", "tenant-a", "alice"), task)
server.work(task.taskId, { answer: "完成" })
assert.equal(task.status, "completed")
assert.equal(server.artifacts.get(task.artifacts[0].artifactId, "tenant-a", "alice").toString(), '{"answer":"完成"}')
assert.throws(() => server.artifacts.get(task.artifacts[0].artifactId, "tenant-b", "alice"), /scope mismatch/)
server.cancel(task.taskId)
assert.equal(task.status, "cancel_requested")
console.log("A2A task/artifact TypeScript tests: OK")
