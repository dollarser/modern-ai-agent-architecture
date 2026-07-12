import assert from "node:assert/strict"
import { mkdtemp, mkdir, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { PluginInstaller } from "./main.js"

async function makePlugin(root: string, name: string, extra: object = {}): Promise<string> {
  const source = path.join(root, `src-${name}`); await mkdir(source)
  await writeFile(path.join(source, "plugin.json"), JSON.stringify({
    name, version: "1.0.0", description: name, entrypoint: `${name}-factory`, ...extra,
  })); await writeFile(path.join(source, "README.md"), name); return source
}
const root = await mkdtemp(path.join(os.tmpdir(), "plugin-manager-")); const installer = new PluginInstaller(path.join(root, "installed"))
const review = await makePlugin(root, "review"); assert.equal((await installer.install(review)).enabled, true)
assert.equal((await installer.setEnabled("review", false)).enabled, false)
await writeFile(path.join(review, "README.md"), "updated"); assert.equal((await installer.install(review, true)).enabled, false)
const protectedPlugin = await makePlugin(root, "protected", { permissions: ["shell"] }); await assert.rejects(installer.install(protectedPlugin))
const future = await makePlugin(root, "future", { min_agent_version: "2.0.0" }); await assert.rejects(installer.install(future))
const dependent = await makePlugin(root, "dependent", { dependencies: ["review"] }); await installer.install(dependent)
await assert.rejects(installer.remove("review")); await installer.remove("dependent"); await installer.remove("review")
assert.equal((await installer.catalog.list()).length, 0)
console.log("plugin manager TypeScript tests: OK")
