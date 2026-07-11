/**
 * Hooks - Agent 生命周期钩子示例
 * =================================
 * 展示 Before/After Hook 的注册和触发
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

declare const process: { argv: string[] };

type HookCallback = (...args: unknown[]) => void;
export type ToolResult = { success: boolean; content: string };

export class HookSystem {
  private hooks: Map<string, HookCallback[]> = new Map();

  /** 注册 Hook */
  register(event: string, callback: HookCallback): void {
    if (!this.hooks.has(event)) {
      this.hooks.set(event, []);
    }
    this.hooks.get(event)!.push(callback);
  }

  /** 触发 Hook */
  trigger(event: string, ...args: unknown[]): void {
    const callbacks = this.hooks.get(event);
    if (!callbacks) return;

    for (const hook of callbacks) {
      try {
        hook(...args);
      } catch (e) {
        if (event.startsWith("before_")) throw e;
        console.log(`  [Hook Error] ${event}: ${e}`);
      }
    }
  }
}

export class AgentWithHooks {
  private hooks: HookSystem;
  private static readonly LIFECYCLE_EVENTS = [
    "before_load",
    "after_load",
    "before_reasoning",
    "after_reasoning",
    "before_tool_call",
    "after_tool_call",
    "before_finish",
    "after_finish",
  ] as const;

  constructor() {
    this.hooks = new HookSystem();
    this.setupDefaultHooks();
  }

  private setupDefaultHooks(): void {
    for (const event of AgentWithHooks.LIFECYCLE_EVENTS) {
      this.hooks.register(event, (...args: unknown[]) => {
        const argStr = args.length > 0 ? String(args) : "no args";
        console.log(`  [LOG] ${event}: ${argStr}`);
      });
    }
  }

  /** 注册自定义 Hook */
  registerCustomHook(event: string, callback: HookCallback): void {
    this.hooks.register(event, callback);
  }

  /** 运行 Agent 生命周期 */
  run(task: string = "demo", toolName: string = "search_web"): ToolResult | null {
    this.hooks.trigger("before_load", task);
    this.hooks.trigger("after_load", task);
    this.hooks.trigger("before_reasoning", task);
    this.hooks.trigger("after_reasoning", "分析完成");

    try {
      this.hooks.trigger("before_tool_call", toolName);
    } catch (error) {
      console.log(`  [BLOCKED] ${error}`);
      return null;
    }

    const result: ToolResult = {
      success: true,
      content: `${toolName} 执行完成；token=sk-demo`,
    };
    this.hooks.trigger("after_tool_call", toolName, result);
    this.hooks.trigger("before_finish");
    this.hooks.trigger("after_finish");
    return result;
  }
}

// ── Main ───────────────────────────────────────

function main(): void {
  console.log("=".repeat(60));
  console.log("  Agent Hooks 系统示例");
  console.log("=".repeat(60));

  const agent = new AgentWithHooks();

  // 注册权限检查 Hook
  const permissionCheck = (toolName: unknown) => {
    const allowed = ["search_web", "read_file", "calculate"];
    const name = String(toolName);
    if (!allowed.includes(name)) {
      throw new Error(`拒绝 Tool: ${name}`);
    }
    console.log(`  [PERMISSION] ✅ 允许 Tool: ${name}`);
  };
  agent.registerCustomHook("before_tool_call", permissionCheck);

  agent.registerCustomHook("after_tool_call", (_toolName: unknown, value: unknown) => {
    const result = value as ToolResult;
    result.content = result.content.replace("sk-demo", "sk-***");
  });

  // 注册计时 Hook
  const timingHook = () => {
    const now = new Date().toTimeString().slice(0, 8);
    console.log(`  [TIMING] ${now}`);
  };
  agent.registerCustomHook("before_reasoning", timingHook);
  agent.registerCustomHook("before_finish", timingHook);

  console.log("\n  运行 Agent 生命周期:");
  console.log("  " + "-".repeat(40));
  agent.run("搜索 AI 新闻");
  agent.run("尝试危险操作", "delete_all");
  console.log("  " + "-".repeat(40));
  console.log("=".repeat(60));
}

const entry = process.argv[1];
if (entry && decodeURIComponent(new URL(import.meta.url).pathname) === entry) {
  main();
}
