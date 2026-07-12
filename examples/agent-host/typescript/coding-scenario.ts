/** 受限工作区 Coding Agent 教学场景。 */

import { execFile } from "node:child_process"
import {
  readFileSync, readdirSync, realpathSync, renameSync, statSync, writeFileSync,
} from "node:fs"
import { relative, resolve, sep } from "node:path"
import {
  AgentHost, type AgentConfig, type AgentDependencies, type ExecutionContext,
  type LLMAdapter, type PlanStep, type ToolResult,
} from "./assembly.js"

export class CodingPlanAdapter implements LLMAdapter {
  async createPlan(_task: string, toolNames: string[], _context: string[]): Promise<PlanStep[]> {
    const required = ["list_files", "read_file", "search_code", "apply_patch", "run_check", "report_change"]
    const missing = required.filter((name) => !toolNames.includes(name))
    if (missing.length) throw new Error(`编码计划所需 Tool 未注册: ${missing.join(",")}`)
    return [
      { id: 1, description: "列出工作区文件", tool: "list_files", arguments: {}, dependsOn: [] },
      { id: 2, description: "读取目标文件", tool: "read_file", arguments: { path: "calculator.js" }, dependsOn: [1] },
      { id: 3, description: "搜索待修改符号", tool: "search_code", arguments: { query: "export const add" }, dependsOn: [1] },
      {
        id: 4, description: "应用最小补丁", tool: "apply_patch",
        arguments: {
          path: "calculator.js",
          old: "export const add = (a, b) => a - b\n",
          new: "export const add = (a, b) => a + b\n",
        }, dependsOn: [2, 3],
      },
      { id: 5, description: "运行白名单测试", tool: "run_check", arguments: { check: "unit" }, dependsOn: [4] },
      { id: 6, description: "汇报变更与验证结果", tool: "report_change", arguments: {}, dependsOn: [4, 5] },
    ]
  }
  async finalAnswer(task: string, results: Record<string, ToolResult>): Promise<string> {
    return String(results["6"]?.report ?? `任务未完成：${task}`)
  }
}

export class Workspace {
  readonly root: string
  constructor(root: string) {
    this.root = realpathSync(root)
    if (!statSync(this.root).isDirectory()) throw new Error("工作区必须是目录")
  }
  resolve(relativePath: string): string {
    const candidate = resolve(this.root, relativePath)
    if (candidate === this.root || !candidate.startsWith(`${this.root}${sep}`)) {
      throw new Error(`路径越过工作区: ${relativePath}`)
    }
    try {
      const actual = realpathSync(candidate)
      if (!actual.startsWith(`${this.root}${sep}`)) throw new Error(`符号链接越过工作区: ${relativePath}`)
      return actual
    } catch (error) {
      if (error instanceof Error && error.message.includes("符号链接越过")) throw error
      return candidate
    }
  }
  listFiles(directory = this.root): string[] {
    const files: string[] = []
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name)
      if (entry.isSymbolicLink()) continue
      if (entry.isDirectory()) files.push(...this.listFiles(path))
      else if (entry.isFile()) files.push(relative(this.root, path).split(sep).join("/"))
    }
    return files.sort()
  }
}

const runUnitCheck = (workspace: Workspace): Promise<ToolResult> => new Promise((done) => {
  execFile(process.execPath, ["--test"], { cwd: workspace.root, timeout: 1_500 },
    (error, stdout, stderr) => done({
      success: !error,
      exitCode: typeof error?.code === "number" ? error.code : error ? 1 : 0,
      stdout, stderr,
      ...(error?.killed ? { error: "检查超时" } : {}),
    }),
  )
})

export const installCodingTools = (host: AgentHost, workspace: Workspace): void => {
  host.tools.register({
    name: "list_files", description: "列出工作区文件", tags: ["read"],
    handler: () => ({ success: true, files: workspace.listFiles() }),
  })
  host.tools.register({
    name: "read_file", description: "读取 UTF-8 文件", tags: ["read"],
    handler: (arguments_) => {
      const path = workspace.resolve(String(arguments_.path))
      return { success: true, path: relative(workspace.root, path), content: readFileSync(path, "utf8") }
    },
  })
  host.tools.register({
    name: "search_code", description: "搜索代码文本", tags: ["read"],
    handler: (arguments_) => {
      const query = String(arguments_.query)
      const matches: Array<{ path: string; line: number }> = []
      for (const item of workspace.listFiles()) {
        readFileSync(workspace.resolve(item), "utf8").split(/\r?\n/u).forEach((line, index) => {
          if (line.includes(query)) matches.push({ path: item, line: index + 1 })
        })
      }
      return { success: true, matches }
    },
  })
  host.tools.register({
    name: "apply_patch", description: "精确替换一次文本", tags: ["write"], requiresApproval: true,
    handler: (arguments_) => {
      const path = workspace.resolve(String(arguments_.path))
      const oldText = String(arguments_.old), newText = String(arguments_.new)
      const content = readFileSync(path, "utf8")
      if (content.split(oldText).length !== 2) return { success: false, error: "补丁旧文本必须且只能匹配一次" }
      const temporary = `${path}.tmp`
      writeFileSync(temporary, content.replace(oldText, newText), "utf8")
      renameSync(temporary, path)
      return { success: true, path: String(arguments_.path), changed: true }
    },
  })
  host.tools.register({
    name: "run_check", description: "运行预注册检查", tags: ["execute"], requiresApproval: true,
    handler: (arguments_) => arguments_.check === "unit"
      ? runUnitCheck(workspace)
      : { success: false, error: "检查命令不在白名单" },
  })
  host.tools.register({
    name: "report_change", description: "汇总修改", tags: ["output"],
    handler: (_arguments: Record<string, unknown>, context: ExecutionContext) => ({
      success: true,
      report: `已修改 ${String(context.results["4"].path)}；测试退出码 ${String(context.results["5"].exitCode)}。`,
    }),
  })
}

export class CodingAgent extends AgentHost {
  readonly workspace: Workspace
  constructor(
    checkpointPath: string,
    workspacePath: string,
    config: Partial<AgentConfig> = {},
    dependencies: AgentDependencies = {},
  ) {
    const allowedTools = new Set(["list_files", "read_file", "search_code", "apply_patch", "run_check", "report_change"])
    super(checkpointPath, {
      instructions: "只在受限工作区内修改文件并运行预注册检查", allowedTools, ...config,
    }, { ...dependencies, llm: dependencies.llm ?? new CodingPlanAdapter() })
    this.workspace = new Workspace(workspacePath)
    installCodingTools(this, this.workspace)
  }
}
