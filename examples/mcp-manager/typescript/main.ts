import { existsSync } from "node:fs"
import { mkdir, readFile, rename, writeFile } from "node:fs/promises"
import path from "node:path"

export interface MCPServerConfig {
  name: string; transport: "stdio" | "streamable-http"; command?: string[]
  url?: string; env?: Record<string, string>; enabled?: boolean
}
export interface MCPConnection {
  listTools(): Promise<Record<string, unknown>[]>
  callTool(name: string, arguments_: Record<string, unknown>): Promise<Record<string, unknown>>
  close(): Promise<void>
}
export interface MCPTransportFactory { connect(config: MCPServerConfig): Promise<MCPConnection> }

function validate(config: MCPServerConfig): void {
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(config.name)) throw new Error("Server name 格式非法")
  if (config.transport === "stdio" && !config.command?.length) throw new Error("stdio Server 必须配置 command")
  if (config.transport === "streamable-http" &&
      !(config.url?.startsWith("https://") || config.url?.startsWith("http://localhost"))) {
    throw new Error("远程 MCP 必须使用 HTTPS（localhost 可使用 HTTP）")
  }
}

export class FakeConnection implements MCPConnection {
  closed = false
  constructor(readonly name: string) {}
  async listTools(): Promise<Record<string, unknown>[]> {
    return [{ name: `${this.name}_search`, description: "fake tool" }]
  }
  async callTool(name: string, arguments_: Record<string, unknown>): Promise<Record<string, unknown>> {
    return name === `${this.name}_search`
      ? { success: true, query: arguments_.query ?? "", server: this.name }
      : { success: false, error: `未知 Tool: ${name}` }
  }
  async close(): Promise<void> { this.closed = true }
}
export class FakeTransportFactory implements MCPTransportFactory {
  readonly connections: FakeConnection[] = []
  async connect(config: MCPServerConfig): Promise<FakeConnection> {
    const connection = new FakeConnection(config.name); this.connections.push(connection); return connection
  }
}

export class MCPServerManager {
  private configs = new Map<string, MCPServerConfig>()
  private connections = new Map<string, MCPConnection>()
  private tools = new Map<string, Record<string, unknown>[]>()
  private constructor(readonly configPath: string, readonly factory: MCPTransportFactory) {}
  static async create(configPath: string, factory: MCPTransportFactory): Promise<MCPServerManager> {
    const manager = new MCPServerManager(configPath, factory); await manager.load(); return manager
  }
  async add(input: MCPServerConfig, replace = false): Promise<void> {
    const config = { ...input, enabled: input.enabled ?? true }; validate(config)
    if (this.configs.has(config.name) && !replace) throw new Error(`MCP Server 已存在: ${config.name}`)
    const old = this.configs.get(config.name); this.configs.set(config.name, config)
    try { await this.save() } catch (error) {
      old ? this.configs.set(config.name, old) : this.configs.delete(config.name); throw error
    }
  }
  async remove(name: string): Promise<void> {
    await this.stop(name); const old = this.require(name); this.configs.delete(name)
    try { await this.save() } catch (error) { this.configs.set(name, old); throw error }
  }
  async setEnabled(name: string, enabled: boolean): Promise<void> {
    const current = this.require(name); if (!enabled) await this.stop(name)
    this.configs.set(name, { ...current, enabled }); await this.save()
  }
  list(redactEnv = true): Record<string, unknown>[] {
    return [...this.configs.values()].sort((a, b) => a.name.localeCompare(b.name)).map((config) => ({
      ...config, env: redactEnv ? Object.fromEntries(Object.keys(config.env ?? {}).map((key) => [key, "***"])) : config.env,
      connected: this.connections.has(config.name),
    }))
  }
  async startEnabled(): Promise<Map<string, Record<string, unknown>[]>> {
    for (const config of this.configs.values()) if (config.enabled) await this.start(config.name)
    return new Map(this.tools)
  }
  async connectEnabled(): Promise<Array<[string, MCPConnection]>> {
    await this.startEnabled()
    return [...this.connections.entries()].sort(([left], [right]) => left.localeCompare(right))
  }
  async start(name: string): Promise<Record<string, unknown>[]> {
    const config = this.require(name); if (!config.enabled) throw new Error(`MCP Server 已禁用: ${name}`)
    if (this.connections.has(name)) return this.tools.get(name)!
    const connection = await this.factory.connect(config)
    try {
      const tools = await connection.listTools(); this.connections.set(name, connection); this.tools.set(name, tools); return tools
    } catch (error) { await connection.close(); throw error }
  }
  async refresh(name: string): Promise<Record<string, unknown>[]> {
    const connection = this.connections.get(name); if (!connection) return this.start(name)
    const tools = await connection.listTools(); this.tools.set(name, tools); return tools
  }
  async stop(name: string): Promise<void> {
    const connection = this.connections.get(name); this.connections.delete(name); this.tools.delete(name)
    if (connection) await connection.close()
  }
  async close(): Promise<void> { for (const name of [...this.connections.keys()]) await this.stop(name) }
  private require(name: string): MCPServerConfig {
    const config = this.configs.get(name); if (!config) throw new Error(`MCP Server 不存在: ${name}`); return config
  }
  private async load(): Promise<void> {
    if (!existsSync(this.configPath)) return
    const value = JSON.parse(await readFile(this.configPath, "utf8")) as { servers: MCPServerConfig[] }
    for (const config of value.servers ?? []) { validate(config); this.configs.set(config.name, config) }
  }
  private async save(): Promise<void> {
    await mkdir(path.dirname(this.configPath), { recursive: true })
    const temporary = `${this.configPath}.${process.pid}.tmp`
    await writeFile(temporary, JSON.stringify({ version: 1, servers: [...this.configs.values()] }, null, 2))
    await rename(temporary, this.configPath)
  }
}
