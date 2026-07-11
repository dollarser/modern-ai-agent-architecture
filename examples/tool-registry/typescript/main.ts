/**
 * Tool Registry - 工具注册与调度示例
 * =====================================
 * 展示动态 Tool 注册、发现和路由
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

interface ToolParameters {
  type: string;
  properties: Record<string, { type: string; description?: string }>;
  required: string[];
}

interface ToolResult {
  success: boolean;
  error?: string;
  [key: string]: unknown;
}

type ToolHandler = (args: Record<string, unknown>) => ToolResult;

interface Tool {
  name: string;
  description: string;
  parameters: ToolParameters;
  handler: ToolHandler;
  tags: string[];
  version: string;
}

class DynamicToolRegistry {
  private tools: Map<string, Tool> = new Map();

  register(tool: Tool): void {
    this.tools.set(tool.name, tool);
  }

  unregister(name: string): boolean {
    return this.tools.delete(name);
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  listAll(): string[] {
    return Array.from(this.tools.keys());
  }

  findByTag(tag: string): Tool[] {
    return Array.from(this.tools.values()).filter((t) => t.tags.includes(tag));
  }

  /** 按关键词搜索 Tool */
  search(keyword: string): Tool[] {
    const kw = keyword.toLowerCase();
    return Array.from(this.tools.values()).filter(
      (t) =>
        t.name.toLowerCase().includes(kw) ||
        t.description.toLowerCase().includes(kw)
    );
  }

  /** 获取 OpenAI 格式的 Tool 定义，可按标签过滤 */
  getDefinitions(tags?: string[]): object[] {
    let tools = Array.from(this.tools.values());
    if (tags) {
      tools = tools.filter((t) => t.tags.some((tag) => tags.includes(tag)));
    }

    return tools.map((t) => ({
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

// ── Main ───────────────────────────────────────

function main(): void {
  const registry = new DynamicToolRegistry();

  // 注册 Tool
  registry.register({
    name: "search_web",
    description: "搜索互联网",
    parameters: {
      type: "object",
      properties: { query: { type: "string" } },
      required: ["query"],
    },
    handler: (args) => ({ success: true, results: [`结果: ${args.query}`] }),
    tags: ["search", "web"],
    version: "1.0.0",
  });

  registry.register({
    name: "read_file",
    description: "读取文件内容",
    parameters: {
      type: "object",
      properties: { path: { type: "string" } },
      required: ["path"],
    },
    handler: (args) => ({ success: true, path: args.path }),
    tags: ["file", "io"],
    version: "1.0.0",
  });

  registry.register({
    name: "search_files",
    description: "搜索文件系统中的文件",
    parameters: {
      type: "object",
      properties: { pattern: { type: "string" } },
      required: ["pattern"],
    },
    handler: (args) => ({ success: true, matches: [`file_${args.pattern}.py`] }),
    tags: ["search", "file"],
    version: "1.0.0",
  });

  registry.register({
    name: "calculate",
    description: "执行数学计算",
    parameters: {
      type: "object",
      properties: { expr: { type: "string" } },
      required: ["expr"],
    },
    handler: (args) => {
      try {
        const result = Function(`"use strict"; return (${args.expr})`)();
        return { success: true, result };
      } catch (e) {
        return { success: false, error: String(e) };
      }
    },
    tags: ["math", "utility"],
    version: "1.0.0",
  });

  console.log("=".repeat(60));
  console.log("  Tool Registry 示例");
  console.log("=".repeat(60));

  // 列出所有 Tool
  console.log(`\n  已注册 Tool: ${registry.listAll().join(", ")}`);

  // 按标签搜索
  for (const tag of ["search", "file", "math"]) {
    const tools = registry.findByTag(tag);
    console.log(`  [${tag}] -> [${tools.map((t) => t.name).join(", ")}]`);
  }

  // 关键词搜索
  const results = registry.search("搜索");
  console.log(`\n  搜索 '搜索': [${results.map((t) => t.name).join(", ")}]`);

  // 动态注销
  console.log("\n  注销 'calculate'...");
  registry.unregister("calculate");
  console.log(`  已注册 Tool: ${registry.listAll().join(", ")}`);

  // 获取过滤后的定义
  console.log("\n  [web] 标签的 Tool 定义:");
  for (const d of registry.getDefinitions(["web"]) as Array<{
    function: { name: string };
  }>) {
    console.log(`    - ${d.function.name}`);
  }

  console.log("=".repeat(60));
}

main();
