import assert from "node:assert/strict"
import { mkdtemp, mkdir, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { SkillInstaller } from "./main.js"

async function makeSkill(root: string, name: string, extra: object = {}): Promise<string> {
  const source = path.join(root, `src-${name}`); await mkdir(source)
  await writeFile(path.join(source, "skill.json"), JSON.stringify({
    name, version: "1.0.0", description: name, keywords: [name], ...extra,
  }))
  await writeFile(path.join(source, "SKILL.md"), `# ${name}`); return source
}

const root = await mkdtemp(path.join(os.tmpdir(), "skill-installer-"))
const installer = new SkillInstaller(path.join(root, "installed"))
const source = await makeSkill(root, "review")
await installer.install(source)
assert.equal((await installer.catalog.match("review code"))[0].manifest.name, "review")
await assert.rejects(installer.install(source))
await writeFile(path.join(source, "SKILL.md"), "updated")
assert.equal((await installer.install(source, true)).instructions, "updated")
const protectedSkill = await makeSkill(root, "protected", { permissions: ["shell"] })
await assert.rejects(installer.install(protectedSkill))
const dependent = await makeSkill(root, "dependent", { dependencies: ["missing"] })
await assert.rejects(installer.install(dependent))
await installer.remove("review")
assert.equal((await installer.catalog.list()).length, 0)
console.log("skill installer TypeScript tests: OK")
