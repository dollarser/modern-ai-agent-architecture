/**
 * Coding Agent - Cross-component Preview (Not the Final Architecture)
 * ====================================================================
 * Combines lightweight Prompt, Instructions, Planner, Memory,
 * Tool mapping and callbacks. It does not implement an MCP Client.
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

// ── State ──────────────────────────────────────

enum AgentState {
  LOAD = "LOAD",
  READ = "READ",
  REASONING = "REASONING",
  PLANNING = "PLANNING",
  EXECUTING = "EXECUTING",
  OBSERVING = "OBSERVING",
  FINISHED = "FINISHED",
}

// ── Types ──────────────────────────────────────

interface ToolResult {
  success: boolean;
  error?: string;
  [key: string]: unknown;
}

type ToolHandler = (...args: any[]) => ToolResult;

interface Tool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  handler: ToolHandler;
  tags: string[];
}

interface MemoryEntry {
  role: string;
  content: string;
}

type HookCallback = (...args: any[]) => void;

// ── Memory ────────────────────────────────────

class Memory {
  private shortTerm: MemoryEntry[] = [];
  private longTerm: Map<string, unknown> = new Map();
  private maxShortTerm: number;

  constructor(maxShortTerm: number = 20) {
    this.maxShortTerm = maxShortTerm;
  }

  add(role: string, content: string): void {
    this.shortTerm.push({ role, content });
    if (this.shortTerm.length > this.maxShortTerm) {
      this.shortTerm.shift();
    }
  }

  save(key: string, value: unknown): void {
    this.longTerm.set(key, value);
  }

  recall(key: string): unknown {
    return this.longTerm.get(key);
  }

  getContext(): string {
    return this.shortTerm
      .map((m) => `[${m.role}] ${m.content.slice(0, 100)}`)
      .join("\n");
  }

  get size(): number {
    return this.shortTerm.length;
  }
}

// ── Planner ───────────────────────────────────

class Planner {
  createPlan(task: string, tools: string[]): string[] {
    return [
      `分析任务: ${task}`,
      `选择工具: ${tools.slice(0, 3).join(", ")}`,
      "执行操作",
      "验证结果",
    ];
  }
}

// ── Tool Registry ──────────────────────────────

class ToolRegistry {
  private tools: Map<string, Tool> = new Map();

  register(tool: Tool): void {
    this.tools.set(tool.name, tool);
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  listAll(): string[] {
    return Array.from(this.tools.keys());
  }

  execute(name: string, args: Record<string, unknown>): ToolResult {
    const tool = this.get(name);
    if (!tool) {
      return { success: false, error: `Tool not found: ${name}` };
    }
    try {
      return tool.handler(args);
    } catch (e) {
      return { success: false, error: String(e) };
    }
  }
}

// ── Hooks ─────────────────────────────────────

class HookSystem {
  private hooks: Map<string, HookCallback[]> = new Map();

  on(event: string, callback: HookCallback): void {
    const callbacks = this.hooks.get(event) || [];
    callbacks.push(callback);
    this.hooks.set(event, callbacks);
  }

  trigger(event: string, ...args: unknown[]): void {
    const callbacks = this.hooks.get(event) || [];
    for (const cb of callbacks) {
      cb(...args);
    }
  }
}

// ── Coding Agent ───────────────────────────────

interface AgentConfig {
  instructions: string;
  maxSteps: number;
}

class CodingAgent {
  private config: AgentConfig;
  state: AgentState = AgentState.LOAD;
  memory: Memory;
  planner: Planner;
  toolRegistry: ToolRegistry;
  hooks: HookSystem;
  private stepCount: number = 0;

  constructor(config: AgentConfig) {
    this.config = config;
    this.memory = new Memory();
    this.planner = new Planner();
    this.toolRegistry = new ToolRegistry();
    this.hooks = new HookSystem();
  }

  setup(): void {
    this.toolRegistry.register({
      name: "read_file",
      description: "读取文件内容",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } },
        required: ["path"],
      },
      handler: (args: any) => ({
        success: true,
        content: `<文件内容: ${args.path}>`,
      }),
      tags: ["file"],
    });

    this.toolRegistry.register({
      name: "write_file",
      description: "写入文件",
      parameters: {
        type: "object",
        properties: {
          path: { type: "string" },
          content: { type: "string" },
        },
        required: ["path", "content"],
      },
      handler: (args: any) => ({ success: true, path: args.path }),
      tags: ["file"],
    });

    this.toolRegistry.register({
      name: "search_code",
      description: "搜索代码库",
      parameters: {
        type: "object",
        properties: { query: { type: "string" } },
        required: ["query"],
      },
      handler: (args: any) => ({
        success: true,
        results: [`match_${args.query}`],
      }),
      tags: ["search"],
    });

    this.hooks.on("before_tool_call", (name: any, args: any) =>
      console.log(`  [Hook] 调用 Tool: ${name}`)
    );
    this.hooks.on("after_tool_call", (name: any, result: any) =>
      console.log(`  [Hook] Tool 完成: ${name}`)
    );

    this.state = AgentState.LOAD;
    this.memory.add("system", `Instructions: ${this.config.instructions}`);
  }

  run(prompt: string): string {
    this.state = AgentState.READ;
    this.memory.add("user", prompt);

    console.log(`\n${"=".repeat(60)}`);
    console.log(`  Coding Agent MVP`);
    console.log(`${"=".repeat(60)}`);
    console.log(`  任务: ${prompt}`);
    console.log(`  可用 Tool: ${this.toolRegistry.listAll()}`);
    console.log(`  ${"-".repeat(40)}`);

    // Reasoning
    this.state = AgentState.REASONING;
    this.hooks.trigger("before_reasoning", prompt);
    const thought = `分析任务: ${prompt}`;
    this.memory.add("assistant", thought);
    this.hooks.trigger("after_reasoning", thought);

    // Planning
    this.state = AgentState.PLANNING;
    const plan = this.planner.createPlan(prompt, this.toolRegistry.listAll());
    this.memory.add("assistant", `计划: ${plan}`);

    // Execute
    this.state = AgentState.EXECUTING;
    let result: ToolResult;
    if (prompt.includes("文件") || prompt.includes("代码")) {
      this.hooks.trigger("before_tool_call", "read_file", { path: "main.py" });
      result = this.toolRegistry.execute("read_file", { path: "main.py" });
      this.hooks.trigger("after_tool_call", "read_file", result);
    } else if (prompt.includes("搜索")) {
      this.hooks.trigger("before_tool_call", "search_code", { query: prompt });
      result = this.toolRegistry.execute("search_code", { query: prompt });
      this.hooks.trigger("after_tool_call", "search_code", result);
    } else {
      result = { success: true, message: "任务分析完成" };
    }

    // Observe
    this.state = AgentState.OBSERVING;
    this.memory.add("tool", JSON.stringify(result));

    this.state = AgentState.FINISHED;
    this.hooks.trigger("before_finish");
    this.memory.add("assistant", "任务完成");

    console.log(`  ${"-".repeat(40)}`);
    console.log(`  执行步数: ${this.stepCount}`);
    console.log(`  最终状态: ${this.state}`);
    console.log(`  记忆条目: ${this.memory.size}`);
    console.log(`${"=".repeat(60)}`);

    return "任务完成";
  }
}

// ── Main ───────────────────────────────────────

function main(): void {
  const config: AgentConfig = {
    instructions: "你是一个 Coding Agent，帮助用户完成编程任务。始终使用中文回复。",
    maxSteps: 10,
  };

  const agent = new CodingAgent(config);
  agent.setup();

  agent.run("搜索数据库连接相关的代码");
  agent.run("读取 main.py 文件");
}

main();
