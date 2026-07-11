/**
 * MCP Client - MCP 客户端示例
 * ==============================
 * 展示 MCP Client 如何发现和调用 MCP Server 提供的 Tool
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

interface MCPToolDef {
  name: string;
  description: string;
  parameters: Record<string, string>;
}

interface MCPServerInfo {
  name: string;
  version: string;
  tools: MCPToolDef[];
}

interface ToolCallResult {
  success: boolean;
  server?: string;
  tool?: string;
  arguments?: Record<string, unknown>;
  result?: string;
  error?: string;
}

class MCPClient {
  private servers: Map<string, MCPServerInfo> = new Map();
  private connected: Set<string> = new Set();

  /** 连接到 MCP Server */
  connect(serverName: string, serverInfo: MCPServerInfo): void {
    this.servers.set(serverName, serverInfo);
    this.connected.add(serverName);
  }

  /** 断开 MCP Server */
  disconnect(serverName: string): void {
    this.connected.delete(serverName);
  }

  /** 列出已连接的 Server */
  listServers(): string[] {
    return Array.from(this.connected);
  }

  /** 列出 Tool */
  listTools(serverName?: string): MCPToolDef[] {
    if (serverName) {
      const server = this.servers.get(serverName);
      return server ? server.tools : [];
    }

    const allTools: MCPToolDef[] = [];
    for (const name of this.connected) {
      const server = this.servers.get(name);
      if (server) {
        allTools.push(...server.tools);
      }
    }
    return allTools;
  }

  /** 调用 Tool */
  callTool(
    serverName: string,
    toolName: string,
    args: Record<string, unknown>
  ): ToolCallResult {
    if (!this.connected.has(serverName)) {
      return { success: false, error: `Server '${serverName}' 未连接` };
    }

    // 模拟 Tool 调用
    return {
      success: true,
      server: serverName,
      tool: toolName,
      arguments: args,
      result: `Tool '${toolName}' 执行成功`,
    };
  }
}

// ── Main ───────────────────────────────────────

function main(): void {
  const client = new MCPClient();

  // 模拟 MCP Server
  const filesystemServer: MCPServerInfo = {
    name: "filesystem",
    version: "1.0.0",
    tools: [
      { name: "read_file", description: "读取文件", parameters: { path: "string" } },
      { name: "write_file", description: "写入文件", parameters: { path: "string", content: "string" } },
    ],
  };

  const databaseServer: MCPServerInfo = {
    name: "database",
    version: "1.0.0",
    tools: [
      { name: "query", description: "执行 SQL 查询", parameters: { sql: "string" } },
      { name: "list_tables", description: "列出所有表", parameters: {} },
    ],
  };

  // 连接 Server
  client.connect("filesystem", filesystemServer);
  client.connect("database", databaseServer);

  console.log("=".repeat(60));
  console.log("  MCP Client 示例");
  console.log("=".repeat(60));

  console.log(`\n  已连接 Server: ${JSON.stringify(client.listServers())}`);

  console.log("\n  所有可用 Tool:");
  for (const tool of client.listTools()) {
    console.log(`    [${tool.name}] ${tool.description}`);
  }

  console.log("\n  调用 Tool:");
  let result = client.callTool("filesystem", "read_file", { path: "/tmp/test.txt" });
  console.log(`    ${JSON.stringify(result)}`);

  result = client.callTool("database", "query", { sql: "SELECT * FROM users" });
  console.log(`    ${JSON.stringify(result)}`);

  // 断开连接
  client.disconnect("database");
  console.log(`\n  断开 database 后: ${JSON.stringify(client.listServers())}`);

  console.log("=".repeat(60));
}

main();
