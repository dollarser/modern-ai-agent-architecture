import { createHash } from "node:crypto"
import { existsSync } from "node:fs"
import { cp, mkdir, readFile, readdir, rename, rm, stat, writeFile } from "node:fs/promises"
import path from "node:path"

export interface SkillManifest {
  name: string; version: string; description: string
  keywords?: string[]; dependencies?: string[]; permissions?: string[]
}
export interface InstalledSkill {
  manifest: SkillManifest; instructions: string; path: string; source: string; checksum: string
}

const validName = /^[a-z0-9][a-z0-9-]{0,63}$/

async function manifestAt(directory: string): Promise<SkillManifest> {
  const value = JSON.parse(await readFile(path.join(directory, "skill.json"), "utf8")) as SkillManifest
  if (!value.name || !value.version || !value.description) throw new Error("skill.json 缺少必填字段")
  if (!validName.test(value.name)) throw new Error("Skill name 格式非法")
  return value
}

export class SkillCatalog {
  constructor(readonly root: string) {}
  async list(): Promise<InstalledSkill[]> {
    await mkdir(this.root, { recursive: true })
    const entries = (await readdir(this.root, { withFileTypes: true }))
      .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
      .map((entry) => entry.name).sort()
    return Promise.all(entries.map((name) => this.get(name)))
  }
  async get(name: string): Promise<InstalledSkill> {
    const directory = path.join(this.root, name)
    if (!existsSync(path.join(directory, "skill.json"))) throw new Error(`Skill 未安装: ${name}`)
    const manifest = await manifestAt(directory)
    const instructions = await readFile(path.join(directory, "SKILL.md"), "utf8")
    const metadata = JSON.parse(await readFile(path.join(directory, ".installed.json"), "utf8"))
    return { manifest, instructions, path: directory, source: metadata.source, checksum: metadata.checksum }
  }
  async match(task: string): Promise<InstalledSkill[]> {
    const lowered = task.toLowerCase()
    return (await this.list()).filter((skill) =>
      (skill.manifest.keywords ?? []).some((word) => lowered.includes(word.toLowerCase())))
  }
}

export class SkillInstaller {
  readonly catalog: SkillCatalog
  constructor(readonly root: string, readonly allowedPermissions = new Set<string>()) {
    this.catalog = new SkillCatalog(root)
  }
  async install(sourceInput: string, replace = false): Promise<InstalledSkill> {
    const source = path.resolve(sourceInput)
    const manifest = await manifestAt(source)
    if (!existsSync(path.join(source, "SKILL.md"))) throw new Error("Skill 源目录缺少 SKILL.md")
    const denied = (manifest.permissions ?? []).filter((item) => !this.allowedPermissions.has(item))
    if (denied.length) throw new Error(`Skill 权限未获授权: ${denied.sort()}`)
    const installed = new Set((await this.catalog.list()).map((item) => item.manifest.name))
    const missing = (manifest.dependencies ?? []).filter((item) => !installed.has(item))
    if (missing.length) throw new Error(`Skill 依赖未安装: ${missing.sort()}`)
    const target = path.join(this.root, manifest.name)
    if (existsSync(target) && !replace) throw new Error(`Skill 已安装: ${manifest.name}`)
    await mkdir(this.root, { recursive: true })
    const staging = path.join(this.root, `.${manifest.name}-${Date.now()}-${process.pid}`)
    const backup = path.join(this.root, `.${manifest.name}.backup`)
    await cp(source, staging, { recursive: true })
    await writeFile(path.join(staging, ".installed.json"), JSON.stringify({
      source, checksum: await this.checksum(source),
    }, null, 2))
    try {
      if (existsSync(target)) await rename(target, backup)
      await rename(staging, target)
      if (existsSync(backup)) await rm(backup, { recursive: true })
    } catch (error) {
      if (existsSync(target) && existsSync(backup)) await rm(target, { recursive: true })
      if (existsSync(backup)) await rename(backup, target)
      if (existsSync(staging)) await rm(staging, { recursive: true })
      throw error
    }
    return this.catalog.get(manifest.name)
  }
  async remove(name: string): Promise<void> {
    const target = path.join(this.root, name)
    if (!existsSync(target)) throw new Error(`Skill 未安装: ${name}`)
    const dependents = (await this.catalog.list()).filter((item) =>
      (item.manifest.dependencies ?? []).includes(name)).map((item) => item.manifest.name)
    if (dependents.length) throw new Error(`Skill 仍被依赖: ${dependents}`)
    await rm(target, { recursive: true })
  }
  private async checksum(root: string): Promise<string> {
    const digest = createHash("sha256")
    const walk = async (directory: string): Promise<void> => {
      for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
        const full = path.join(directory, entry.name)
        if (entry.isDirectory()) await walk(full)
        else { digest.update(path.relative(root, full)); digest.update(await readFile(full)) }
      }
    }
    await walk(root); return digest.digest("hex")
  }
}
