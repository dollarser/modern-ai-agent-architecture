import { createHash } from "node:crypto"
import { existsSync } from "node:fs"
import { cp, mkdir, readFile, readdir, rename, rm, writeFile, lstat } from "node:fs/promises"
import path from "node:path"

export interface PluginManifest {
  name: string; version: string; description: string; entrypoint: string
  permissions?: string[]; dependencies?: string[]; min_agent_version?: string
}
export interface InstalledPlugin {
  manifest: PluginManifest; path: string; source: string; checksum: string; enabled: boolean
}
const namePattern = /^[a-z0-9][a-z0-9-]{0,63}$/
function versionTuple(value: string): number[] {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(value); if (!match) throw new Error(`示例仅支持 x.y.z 版本: ${value}`)
  return match.slice(1).map(Number)
}
function versionLess(left: string, right: string): boolean {
  const a = versionTuple(left), b = versionTuple(right)
  return a[0] !== b[0] ? a[0] < b[0] : a[1] !== b[1] ? a[1] < b[1] : a[2] < b[2]
}
async function manifestAt(directory: string): Promise<PluginManifest> {
  const value = JSON.parse(await readFile(path.join(directory, "plugin.json"), "utf8")) as PluginManifest
  if (!value.name || !value.version || !value.description || !value.entrypoint) throw new Error("plugin.json 缺少必填字段")
  if (!namePattern.test(value.name) || !namePattern.test(value.entrypoint)) throw new Error("Plugin name 或 entrypoint 格式非法")
  return value
}

export class PluginCatalog {
  constructor(readonly root: string) {}
  async list(enabledOnly = false): Promise<InstalledPlugin[]> {
    await mkdir(this.root, { recursive: true })
    const names = (await readdir(this.root, { withFileTypes: true }))
      .filter((entry) => entry.isDirectory() && !entry.name.startsWith(".")).map((entry) => entry.name).sort()
    const items = await Promise.all(names.map((name) => this.get(name)))
    return enabledOnly ? items.filter((item) => item.enabled) : items
  }
  async get(name: string): Promise<InstalledPlugin> {
    const directory = path.join(this.root, name)
    if (!existsSync(path.join(directory, "plugin.json"))) throw new Error(`Plugin 未安装: ${name}`)
    const manifest = await manifestAt(directory)
    const metadata = JSON.parse(await readFile(path.join(directory, ".installed.json"), "utf8"))
    return { manifest, path: directory, source: metadata.source, checksum: metadata.checksum, enabled: metadata.enabled }
  }
}

export class PluginInstaller {
  readonly catalog: PluginCatalog
  constructor(
    readonly root: string, readonly allowedPermissions = new Set<string>(), readonly agentVersion = "1.0.0",
  ) { this.catalog = new PluginCatalog(root) }
  async install(sourceInput: string, replace = false): Promise<InstalledPlugin> {
    const source = path.resolve(sourceInput); const manifest = await manifestAt(source)
    if (versionLess(this.agentVersion, manifest.min_agent_version ?? "1.0.0")) {
      throw new Error(`Plugin 需要 Agent >= ${manifest.min_agent_version}，当前 ${this.agentVersion}`)
    }
    const denied = (manifest.permissions ?? []).filter((item) => !this.allowedPermissions.has(item))
    if (denied.length) throw new Error(`Plugin 权限未获授权: ${denied.sort()}`)
    const installed = new Set((await this.catalog.list()).map((item) => item.manifest.name))
    const missing = (manifest.dependencies ?? []).filter((item) => !installed.has(item))
    if (missing.length) throw new Error(`Plugin 依赖未安装: ${missing.sort()}`)
    await this.rejectSymlinks(source)
    const target = path.join(this.root, manifest.name)
    if (existsSync(target) && !replace) throw new Error(`Plugin 已安装: ${manifest.name}`)
    const enabled = existsSync(target) ? (await this.catalog.get(manifest.name)).enabled : true
    const staging = path.join(this.root, `.${manifest.name}-${Date.now()}-${process.pid}`)
    const backup = path.join(this.root, `.${manifest.name}.backup`)
    await mkdir(this.root, { recursive: true }); await cp(source, staging, { recursive: true })
    await this.writeMetadata(staging, source, await this.checksum(source), enabled)
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
  async setEnabled(name: string, enabled: boolean): Promise<InstalledPlugin> {
    const item = await this.catalog.get(name)
    if (enabled) {
      const disabled = []
      for (const dependency of item.manifest.dependencies ?? []) if (!(await this.catalog.get(dependency)).enabled) disabled.push(dependency)
      if (disabled.length) throw new Error(`Plugin 依赖未启用: ${disabled}`)
    } else {
      const dependents = (await this.catalog.list(true)).filter((other) =>
        (other.manifest.dependencies ?? []).includes(name)).map((other) => other.manifest.name)
      if (dependents.length) throw new Error(`Plugin 仍被已启用插件依赖: ${dependents}`)
    }
    await this.writeMetadata(item.path, item.source, item.checksum, enabled); return this.catalog.get(name)
  }
  async remove(name: string): Promise<void> {
    const item = await this.catalog.get(name)
    const dependents = (await this.catalog.list()).filter((other) =>
      (other.manifest.dependencies ?? []).includes(name)).map((other) => other.manifest.name)
    if (dependents.length) throw new Error(`Plugin 仍被依赖: ${dependents}`)
    await rm(item.path, { recursive: true })
  }
  private async writeMetadata(directory: string, source: string, checksum: string, enabled: boolean): Promise<void> {
    const temporary = path.join(directory, ".installed.json.tmp")
    await writeFile(temporary, JSON.stringify({ source, checksum, enabled }, null, 2))
    await rename(temporary, path.join(directory, ".installed.json"))
  }
  private async rejectSymlinks(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name); if ((await lstat(full)).isSymbolicLink()) throw new Error("Plugin 包不允许包含符号链接")
      if (entry.isDirectory()) await this.rejectSymlinks(full)
    }
  }
  private async checksum(root: string): Promise<string> {
    const digest = createHash("sha256")
    const walk = async (directory: string): Promise<void> => {
      for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
        const full = path.join(directory, entry.name)
        if (entry.isDirectory()) await walk(full); else { digest.update(path.relative(root, full)); digest.update(await readFile(full)) }
      }
    }
    await walk(root); return digest.digest("hex")
  }
}
