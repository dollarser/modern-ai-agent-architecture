/**
 * Hooks - Agent 生命周期钩子示例
 * =================================
 * 展示 Before/After Hook 的注册和触发
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

type HookCallback = (...args: unknown[]) => void;

class HookSystem {
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
        console.log(`  [Hook Error] ${event}: ${e}`);
      }
    }
  }
}

class AgentWithHooks {
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
  run(task: string = "demo"): void {
    const events: Array<[string, ...unknown[]]> = [
      ["before_load", task],
      ["after_load", task],
      ["before_reasoning", task],
      ["after_reasoning", "分析完成"],
      ["before_tool_call", "search_web"],
      ["after_tool_call", "search_web", "搜索完成"],
      ["before_finish"],
      ["after_finish"],
    ];

    for (const [event, ...args] of events) {
      this.hooks.trigger(event, ...args);
    }
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
      console.log(`  [PERMISSION] ⛔ 拒绝 Tool: ${name}`);
    } else {
      console.log(`  [PERMISSION] ✅ 允许 Tool: ${name}`);
    }
  };
  agent.registerCustomHook("before_tool_call", permissionCheck);

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
  console.log("  " + "-".repeat(40));
  console.log("=".repeat(60));
}

main();
