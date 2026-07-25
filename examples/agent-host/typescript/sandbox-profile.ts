export type SandboxProfileConfig = {
  workspaceRoots: string[]; processAllowlist?: string[]; networkAllowlist?: string[]
  secretNames?: string[]; maxRuntimeSeconds?: number
}

export class SandboxProfile {
  readonly config: Required<SandboxProfileConfig>
  constructor(config: SandboxProfileConfig) {
    this.config = {
      workspaceRoots: config.workspaceRoots, processAllowlist: config.processAllowlist ?? [],
      networkAllowlist: config.networkAllowlist ?? [], secretNames: config.secretNames ?? [],
      maxRuntimeSeconds: config.maxRuntimeSeconds ?? 30,
    }
  }
  validate(): void {
    if (this.config.workspaceRoots.length === 0 || this.config.workspaceRoots.some((root) => !root.startsWith("/"))) throw new Error("Sandbox workspaceRoots 必须是非空绝对路径")
    if (this.config.processAllowlist.some((item) => /[\\/]/u.test(item))) throw new Error("processAllowlist 只能使用可执行文件名")
    if (this.config.networkAllowlist.some((item) => item === "*" || item.includes("://"))) throw new Error("networkAllowlist 不允许通配符或 URL")
    if (this.config.secretNames.some((item) => !item || /\n/u.test(item))) throw new Error("secretNames 非法")
    if (this.config.maxRuntimeSeconds <= 0) throw new Error("maxRuntimeSeconds 必须为正数")
  }
  allowsProcess(executable: string): boolean { return this.config.processAllowlist.includes(executable.split(/[\\/]/u).at(-1)!) }
  allowsNetwork(host: string): boolean { return this.config.networkAllowlist.includes(host) }
  mayLogSecret(_name: string): boolean { return false }
}
