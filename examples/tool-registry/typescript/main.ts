/**
 * Tool Registry - 工具注册与调度示例
 * =====================================
 * 展示动态 Tool 注册、发现和路由
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

export interface ToolParameters {
  type: string;
  properties: Record<string, { type: string; description?: string }>;
  required: string[];
}

export interface ToolResult {
  success: boolean;
  error?: string;
  [key: string]: unknown;
}

export function safeCalculate(expression: string): number {
  if (expression.length > 128) throw new Error("表达式过长");
  const compact = expression.replace(/\s/g, "");
  const tokens = compact.match(/\d+(?:\.\d+)?|\*\*|[()+\-*/%]/g) ?? [];
  if (tokens.join("") !== compact || tokens.length > 32) {
    throw new Error("表达式包含不允许的字符或过于复杂");
  }

  let index = 0;
  const peek = () => tokens[index];
  const take = () => tokens[index++];

  const parsePrimary = (): number => {
    if (peek() === "(") {
      take();
      const value = parseExpression();
      if (take() !== ")") throw new Error("括号不匹配");
      return value;
    }
    const token = take();
    if (!token || !/^\d+(?:\.\d+)?$/.test(token)) throw new Error("需要数字");
    return Number(token);
  };

  const parsePower = (): number => {
    const left = parsePrimary();
    if (peek() !== "**") return left;
    take();
    const exponent = parseUnary();
    if (Math.abs(exponent) > 10) throw new Error("指数绝对值不能超过 10");
    return left ** exponent;
  };

  const parseUnary = (): number => {
    if (peek() === "+") { take(); return parseUnary(); }
    if (peek() === "-") { take(); return -parseUnary(); }
    return parsePower();
  };

  const parseTerm = (): number => {
    let value = parseUnary();
    while (["*", "/", "%"].includes(peek())) {
      const operator = take();
      const right = parseUnary();
      if (operator === "*") value *= right;
      else if (operator === "/") value /= right;
      else value %= right;
    }
    return value;
  };

  const parseExpression = (): number => {
    let value = parseTerm();
    while (["+", "-"].includes(peek())) {
      const operator = take();
      const right = parseTerm();
      value = operator === "+" ? value + right : value - right;
    }
    return value;
  };

  const result = parseExpression();
  if (index !== tokens.length) throw new Error("表达式未完整解析");
  if (!Number.isFinite(result) || Math.abs(result) > 1e15) {
    throw new Error("计算结果超出允许范围");
  }
  return result;
}

type ToolHandler = (args: Record<string, unknown>) => ToolResult;

export interface Tool {
  name: string;
  description: string;
  parameters: ToolParameters;
  handler: ToolHandler;
  tags: string[];
  version: string;
}

export class ToolRegistryError extends Error {}

export class DynamicToolRegistry {
  private tools: Map<string, Tool> = new Map();

  register(tool: Tool, options: { replace?: boolean } = {}): void {
    if (!tool.name.trim()) throw new ToolRegistryError("Tool 名称不能为空");
    if (typeof tool.handler !== "function") throw new ToolRegistryError(`Tool '${tool.name}' 缺少可调用 Handler`);
    this.validateSchema(tool.parameters);
    if (this.tools.has(tool.name) && !options.replace) {
      throw new ToolRegistryError(`Tool '${tool.name}' 已注册；显式 replace=true 才能替换`);
    }
    this.tools.set(tool.name, tool);
  }

  private validateSchema(schema: ToolParameters): void {
    if (schema.type !== "object" || !schema.properties || !Array.isArray(schema.required)) {
      throw new ToolRegistryError("Tool 参数必须是 object JSON Schema");
    }
    if (schema.required.some((name) => !(name in schema.properties))) {
      throw new ToolRegistryError("required 必须引用已声明的 properties");
    }
  }

  private validateArguments(schema: ToolParameters, args: Record<string, unknown>): void {
    if (!args || typeof args !== "object" || Array.isArray(args)) throw new ToolRegistryError("Tool 参数必须是对象");
    const missing = schema.required.filter((name) => !(name in args));
    if (missing.length) throw new ToolRegistryError(`缺少必填参数: ${missing.join(", ")}`);
    const unknown = Object.keys(args).filter((name) => !(name in schema.properties));
    if (unknown.length) throw new ToolRegistryError(`存在未声明参数: ${unknown.join(", ")}`);
    for (const [name, value] of Object.entries(args)) {
      const expected = schema.properties[name].type;
      const valid = expected === "string" ? typeof value === "string"
        : expected === "number" ? typeof value === "number" && Number.isFinite(value)
        : expected === "boolean" ? typeof value === "boolean"
        : expected === "object" ? typeof value === "object" && value !== null && !Array.isArray(value)
        : expected === "array" ? Array.isArray(value)
        : false;
      if (!valid) throw new ToolRegistryError(`参数 '${name}' 类型错误，期望 ${expected}`);
    }
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
      return { success: false, error_code: "tool_not_found", error: `Tool '${name}' 不存在` };
    }

    try {
      this.validateArguments(tool.parameters, args);
      return tool.handler(args);
    } catch (e) {
      if (e instanceof ToolRegistryError) {
        return { success: false, error_code: "invalid_arguments", error: e.message };
      }
      return { success: false, error_code: "handler_error", error: String(e) };
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
        const result = safeCalculate(String(args.expr));
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

  console.log(`  安全计算: ${JSON.stringify(registry.execute("calculate", { expr: "(2 + 3) * 4" }))}`);
  console.log(`  拒绝代码: ${JSON.stringify(registry.execute("calculate", { expr: "globalThis.process.exit()" }))}`);

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

export { main };
