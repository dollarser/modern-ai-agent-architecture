"""
MCP Client - MCP 客户端示例
=============================
展示 MCP Client 如何发现和调用 MCP Server 提供的 Tool

运行环境：Python 3.10+
依赖：无（模拟实现）
"""

import json
from dataclasses import dataclass, field


@dataclass
class MCPServerInfo:
    """MCP Server 信息"""
    name: str
    version: str
    tools: list[dict] = field(default_factory=list)


class MCPClient:
    """MCP 客户端（简化模拟实现）"""

    def __init__(self):
        self.servers: dict[str, MCPServerInfo] = {}
        self.connected: set[str] = set()

    def connect(self, server_name: str, server_info: MCPServerInfo):
        """连接到 MCP Server"""
        self.servers[server_name] = server_info
        self.connected.add(server_name)

    def disconnect(self, server_name: str):
        """断开 MCP Server"""
        self.connected.discard(server_name)

    def list_servers(self) -> list[str]:
        """列出已连接的 Server"""
        return list(self.connected)

    def list_tools(self, server_name: str | None = None) -> list[dict]:
        """列出 Tool"""
        if server_name:
            if server_name in self.servers:
                return self.servers[server_name].tools
            return []

        all_tools = []
        for name in self.connected:
            all_tools.extend(self.servers[name].tools)
        return all_tools

    def call_tool(self, server_name: str, tool_name: str,
                  arguments: dict) -> dict:
        """调用 Tool"""
        if server_name not in self.connected:
            return {"success": False, "error": f"Server '{server_name}' 未连接"}

        # 模拟 Tool 调用
        return {
            "success": True,
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
            "result": f"Tool '{tool_name}' 执行成功"
        }


def main():
    client = MCPClient()

    # 模拟 MCP Server
    filesystem_server = MCPServerInfo(
        name="filesystem",
        version="1.0.0",
        tools=[
            {"name": "read_file", "description": "读取文件", "parameters": {"path": "string"}},
            {"name": "write_file", "description": "写入文件", "parameters": {"path": "string", "content": "string"}},
        ]
    )

    database_server = MCPServerInfo(
        name="database",
        version="1.0.0",
        tools=[
            {"name": "query", "description": "执行 SQL 查询", "parameters": {"sql": "string"}},
            {"name": "list_tables", "description": "列出所有表", "parameters": {}},
        ]
    )

    # 连接 Server
    client.connect("filesystem", filesystem_server)
    client.connect("database", database_server)

    print("=" * 60)
    print("  MCP Client 示例")
    print("=" * 60)

    print(f"\n  已连接 Server: {client.list_servers()}")

    print(f"\n  所有可用 Tool:")
    for tool in client.list_tools():
        print(f"    [{tool['name']}] {tool['description']}")

    print(f"\n  调用 Tool:")
    result = client.call_tool("filesystem", "read_file", {"path": "/tmp/test.txt"})
    print(f"    {json.dumps(result, ensure_ascii=False)}")

    result = client.call_tool("database", "query", {"sql": "SELECT * FROM users"})
    print(f"    {json.dumps(result, ensure_ascii=False)}")

    # 断开连接
    client.disconnect("database")
    print(f"\n  断开 database 后: {client.list_servers()}")

    print("=" * 60)


if __name__ == "__main__":
    main()
