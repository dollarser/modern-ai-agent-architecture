/**
 * MCP Server - MCP 服务端示例
 * ==============================
 * 展示如何实现一个 MCP Server，暴露 Tool
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  handler: (args: Record<string, unknown>) => Record<string, unknown>;
}

interface MCPToolListResult {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

interface MCPToolCallResult {
  isError?: boolean;
  content: Array<{ type: string; text: string }>;
}

interface MCPServerInfo {
  name: string;
  version: string;
  protocolVersion: string;
}

class MCPServer {
  private name: string;
  private version: string;
  private tools: Map<string, MCPTool> = new Map();

  constructor(name: string, version: string = "1.0.0") {
    this.name = name;
    this.version = version;
  }

  /** 注册 Tool */
  registerTool(tool: MCPTool): void {
    this.tools.set(tool.name, tool);
  }

  /** 列出所有 Tool（MCP 协议格式） */
  listTools(): MCPToolListResult[] {
    return Array.from(this.tools.values()).map((t) => ({
      name: t.name,
      description: t.description,
      inputSchema: t.inputSchema,
    }));
  }

  /** 调用 Tool */
  callTool(name: string, args: Record<string, unknown>): MCPToolCallResult {
    const tool = this.tools.get(name);
    if (!tool) {
      return {
        isError: true,
        content: [{ type: "text", text: `Tool not found: ${name}` }],
      };
    }

    try {
      const result = tool.handler(args);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
      };
    } catch (e) {
      return {
        isError: true,
        content: [{ type: "text", text: String(e) }],
      };
    }
  }

  /** 获取 Server 信息 */
  getServerInfo(): MCPServerInfo {
    return {
      name: this.name,
      version: this.version,
      protocolVersion: "2024-11-05",
    };
  }
}

// ── Main ───────────────────────────────────────

function main(): void {
  // 创建 MCP Server
  const server = new MCPServer("weather-server", "1.0.0");

  // 注册 Tool
  server.registerTool({
    name: "get_weather",
    description: "获取指定城市的天气信息",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "城市名称" },
        unit: { type: "string", enum: ["celsius", "fahrenheit"], default: "celsius" },
      },
      required: ["city"],
    },
    handler: (args) => ({
      city: args.city,
      temperature: 22,
      unit: (args.unit as string) || "celsius",
      condition: "晴天",
    }),
  });

  server.registerTool({
    name: "get_forecast",
    description: "获取未来天气预报",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "城市名称" },
        days: { type: "integer", minimum: 1, maximum: 7, default: 3 },
      },
      required: ["city"],
    },
    handler: (args) => ({
      city: args.city,
      forecast: Array.from(
        { length: (args.days as number) || 3 },
        (_, i) => ({
          day: `第${i + 1}天`,
          high: 22 + i + 1,
          low: 15 + i + 1,
        })
      ),
    }),
  });

  console.log("=".repeat(60));
  console.log("  MCP Server 示例");
  console.log("=".repeat(60));

  // 打印 Server 信息
  const info = server.getServerInfo();
  console.log(`\n  Server: ${info.name} v${info.version}`);
  console.log(`  协议版本: ${info.protocolVersion}`);

  // 列出 Tool
  console.log("\n  可用 Tool:");
  for (const tool of server.listTools()) {
    console.log(`    • ${tool.name}: ${tool.description}`);
  }

  // 调用 Tool
  console.log("\n  调用 Tool:");
  let result = server.callTool("get_weather", { city: "北京" });
  console.log(`    get_weather: ${JSON.stringify(result)}`);

  result = server.callTool("get_forecast", { city: "上海", days: 3 });
  console.log(`    get_forecast: ${JSON.stringify(result)}`);

  console.log("=".repeat(60));
}

main();
