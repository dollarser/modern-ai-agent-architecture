import assert from "node:assert/strict"
import { mkdtemp } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { FakeTransportFactory, MCPServerManager } from "./main.js"

const root = await mkdtemp(path.join(os.tmpdir(), "mcp-manager-")); const config = path.join(root, "mcp.json")
const factory = new FakeTransportFactory(); const manager = await MCPServerManager.create(config, factory)
await manager.add({ name: "catalog", transport: "stdio", command: ["server"], env: { TOKEN: "secret" } })
assert.deepEqual(manager.list()[0].env, { TOKEN: "***" })
assert.equal((await manager.startEnabled()).get("catalog")?.[0].name, "catalog_search")
const [serverName, connection] = (await manager.connectEnabled())[0]
assert.equal(serverName, "catalog")
assert.equal((await connection.callTool("catalog_search", { query: "db" })).success, true)
assert.equal((await manager.refresh("catalog"))[0].name, "catalog_search")
await manager.setEnabled("catalog", false); assert.equal(factory.connections[0].closed, true)
const restored = await MCPServerManager.create(config, new FakeTransportFactory())
assert.equal(restored.list()[0].enabled, false); await restored.remove("catalog"); assert.equal(restored.list().length, 0)
await assert.rejects(manager.add({ name: "remote", transport: "streamable-http", url: "http://remote.test" }))
console.log("mcp manager TypeScript tests: OK")
