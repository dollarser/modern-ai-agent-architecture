/** 第 12～14 章安装/管理子系统到 AgentHost Provider Port 的适配器。 */

import type {
  MCPClient, MCPToolDefinition, Plugin, Skill, ToolResult,
} from "./assembly.js"

type InstalledSkillRecord = {
  manifest: { name: string; keywords?: string[] }
  instructions: string
}
export interface SkillCatalogPort { list(): InstalledSkillRecord[] | Promise<InstalledSkillRecord[]> }
export class CatalogSkillProvider {
  constructor(readonly catalog: SkillCatalogPort) {}
  async loadSkills(): Promise<Skill[]> {
    return (await this.catalog.list()).map((item) => ({
      name: item.manifest.name,
      keywords: item.manifest.keywords ?? [],
      instructions: item.instructions,
      owner: `installed-skill:${item.manifest.name}`,
    }))
  }
}

export interface ManagedConnectionPort {
  listTools(): Promise<Record<string, unknown>[]>
  callTool(name: string, arguments_: Record<string, unknown>): Promise<Record<string, unknown>>
}
export class ManagedMCPClient implements MCPClient {
  constructor(readonly connection: ManagedConnectionPort) {}
  async listTools(): Promise<MCPToolDefinition[]> {
    return (await this.connection.listTools()).map((item) => ({
      name: String(item.name),
      description: String(item.description ?? ""),
      inputSchema: (item.inputSchema ?? item.input_schema ?? {}) as Record<string, unknown>,
    }))
  }
  async callTool(name: string, arguments_: Record<string, unknown>): Promise<ToolResult> {
    return await this.connection.callTool(name, arguments_) as ToolResult
  }
}
export interface MCPManagerPort {
  connectEnabled(): Promise<Array<[string, ManagedConnectionPort]>>
  close(): Promise<void>
}
export class ManagerMCPProvider {
  constructor(readonly manager: MCPManagerPort) {}
  async connectEnabled(): Promise<Array<[string, ManagedMCPClient]>> {
    return (await this.manager.connectEnabled()).map(
      ([name, connection]) => [name, new ManagedMCPClient(connection)],
    )
  }
  close(): Promise<void> { return this.manager.close() }
}

export type InstalledPluginRecord = {
  manifest: {
    name: string
    version: string
    entrypoint: string
    dependencies?: string[]
  }
}
export interface PluginCatalogPort {
  list(enabledOnly?: boolean): InstalledPluginRecord[] | Promise<InstalledPluginRecord[]>
}
export type PluginFactory = (record: InstalledPluginRecord) => Plugin
export class CatalogPluginProvider {
  constructor(
    readonly catalog: PluginCatalogPort,
    readonly factories: ReadonlyMap<string, PluginFactory>,
  ) {}
  async loadPlugins(): Promise<Plugin[]> {
    const records = this.dependencyOrder(await this.catalog.list(true))
    return records.map((record) => {
      const factory = this.factories.get(record.manifest.entrypoint)
      if (!factory) throw new Error(`Plugin Factory 未注册: ${record.manifest.entrypoint}`)
      const plugin = factory(record)
      if (
        plugin.manifest.name !== record.manifest.name ||
        plugin.manifest.version !== record.manifest.version
      ) throw new Error(`Plugin Factory 身份不匹配: ${record.manifest.name}`)
      return plugin
    })
  }
  private dependencyOrder(records: InstalledPluginRecord[]): InstalledPluginRecord[] {
    const byName = new Map(records.map((item) => [item.manifest.name, item]))
    const ordered: InstalledPluginRecord[] = [], visiting = new Set<string>(), visited = new Set<string>()
    const visit = (name: string): void => {
      if (visited.has(name)) return
      if (visiting.has(name)) throw new Error(`Plugin 依赖存在循环: ${name}`)
      const item = byName.get(name)
      if (!item) throw new Error(`已启用 Plugin 缺少依赖: ${name}`)
      visiting.add(name)
      for (const dependency of item.manifest.dependencies ?? []) visit(dependency)
      visiting.delete(name); visited.add(name); ordered.push(item)
    }
    for (const item of records) visit(item.manifest.name)
    return ordered
  }
}
