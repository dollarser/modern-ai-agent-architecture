/**
 * Tool Calling - Tool Abstraction and Function Calling Example
 * ============================================================
 * Demonstrates Tool definition, registration, execution, and error handling
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

interface ToolParameters {
  type: string;
  properties: Record<string, { type: string; description: string; default?: unknown }>;
  required: string[];
}

interface ToolResult {
  success: boolean;
  error?: string;
  [key: string]: unknown;
}

type ToolHandler = (...args: any[]) => ToolResult;

interface Tool {
  name: string;
  description: string;
  parameters: ToolParameters;
  handler: ToolHandler;
}

class ToolRegistry {
  private tools: Map<string, Tool> = new Map();

  register(tool: Tool): void {
    this.tools.set(tool.name, tool);
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  listTools(): string[] {
    return Array.from(this.tools.keys());
  }

  getDefinitions(): object[] {
    return Array.from(this.tools.values()).map((t) => ({
      type: "function",
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters,
      },
    }));
  }

  execute(name: string, args: Record<string, unknown>): ToolResult {
    const tool = this.get(name);
    if (!tool) {
      return { success: false, error: `Tool '${name}' 不存在` };
    }

    try {
      return tool.handler(args);
    } catch (e) {
      return { success: false, error: String(e) };
    }
  }
}

// ── Tool Handlers ──────────────────────────────

function searchWebHandler(args: { query: string; max_results?: number }): ToolResult {
  const maxResults = args.max_results ?? 5;
  return {
    success: true,
    query: args.query,
    results: Array.from({ length: Math.min(maxResults, 3) }, (_, i) => ({
      title: `搜索结果 ${i + 1}: ${args.query}`,
      url: `https://example.com/r/${i + 1}`,
    })),
  };
}

function calculateHandler(args: { expression: string }): ToolResult {
  try {
    // Safe evaluation for demo purposes
    const result = Function(`"use strict"; return (${args.expression})`)();
    return { success: true, expression: args.expression, result };
  } catch (e) {
    return { success: false, expression: args.expression, error: String(e) };
  }
}

// ── Main ───────────────────────────────────────

function main(): void {
  const registry = new ToolRegistry();

  registry.register({
    name: "search_web",
    description: "搜索互联网获取最新信息。当需要实时数据或用户询问最新消息时使用。",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string", description: "搜索关键词" },
        max_results: { type: "integer", description: "最大结果数", default: 5 },
      },
      required: ["query"],
    },
    handler: searchWebHandler,
  });

  registry.register({
    name: "calculate",
    description: "执行数学计算。支持基本运算表达式。",
    parameters: {
      type: "object",
      properties: {
        expression: { type: "string", description: "数学表达式" },
      },
      required: ["expression"],
    },
    handler: calculateHandler,
  });

  console.log("=".repeat(60));
  console.log("  已注册的 Tool:");
  console.log("=".repeat(60));
  for (const name of registry.listTools()) {
    const tool = registry.get(name)!;
    console.log(`  • ${name}: ${tool.description}`);
  }
  console.log();

  console.log("=".repeat(60));
  console.log("  模拟 Function Calling 流程");
  console.log("=".repeat(60));

  const testCases = [
    { name: "search_web", args: { query: "AI Agent 架构 2026", max_results: 3 } },
    { name: "calculate", args: { expression: "2 ** 10 + 3 * 5" } },
    { name: "unknown_tool", args: {} },
  ];

  for (const [i, tc] of testCases.entries()) {
    console.log(`\n  [${i + 1}] 调用 Tool: ${tc.name}`);
    console.log(`      参数: ${JSON.stringify(tc.args)}`);
    const result = registry.execute(tc.name, tc.args);
    const status = result.success ? "✓" : "✗";
    console.log(`      结果: ${status} ${JSON.stringify(result).slice(0, 120)}`);
  }

  console.log("\n" + "=".repeat(60));
}

main();