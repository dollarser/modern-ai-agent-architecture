"""
MCP Server - MCP 服务端示例
=============================
展示如何实现一个 MCP Server，暴露 Tool

运行环境：Python 3.10+
依赖：无（模拟实现）
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MCPTool:
    """MCP Tool 定义"""
    name: str
    description: str
    input_schema: dict
    handler: Callable


class MCPServer:
    """MCP Server 实现（简化模拟）"""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, MCPTool] = {}

    def register_tool(self, tool: MCPTool):
        """注册 Tool"""
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict]:
        """列出所有 Tool（MCP 协议格式）"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema
            }
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """调用 Tool"""
        tool = self._tools.get(name)
        if not tool:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool not found: {name}"}]
            }

        try:
            result = tool.handler(**arguments)
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
            }
        except Exception as e:
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}]
            }

    def get_server_info(self) -> dict:
        """获取 Server 信息"""
        return {
            "name": self.name,
            "version": self.version,
            "protocolVersion": "2024-11-05"
        }


def main():
    # 创建 MCP Server
    server = MCPServer("weather-server", "1.0.0")

    # 注册 Tool
    server.register_tool(MCPTool(
        name="get_weather",
        description="获取指定城市的天气信息",
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
            },
            "required": ["city"]
        },
        handler=lambda city, unit="celsius": {
            "city": city,
            "temperature": 22,
            "unit": unit,
            "condition": "晴天"
        }
    ))

    server.register_tool(MCPTool(
        name="get_forecast",
        description="获取未来天气预报",
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "days": {"type": "integer", "minimum": 1, "maximum": 7, "default": 3}
            },
            "required": ["city"]
        },
        handler=lambda city, days=3: {
            "city": city,
            "forecast": [
                {"day": f"第{i}天", "high": 22 + i, "low": 15 + i}
                for i in range(1, days + 1)
            ]
        }
    ))

    print("=" * 60)
    print("  MCP Server 示例")
    print("=" * 60)

    # 打印 Server 信息
    info = server.get_server_info()
    print(f"\n  Server: {info['name']} v{info['version']}")
    print(f"  协议版本: {info['protocolVersion']}")

    # 列出 Tool
    print(f"\n  可用 Tool:")
    for tool in server.list_tools():
        print(f"    • {tool['name']}: {tool['description']}")

    # 调用 Tool
    print(f"\n  调用 Tool:")
    result = server.call_tool("get_weather", {"city": "北京"})
    print(f"    get_weather: {json.dumps(result, ensure_ascii=False)}")

    result = server.call_tool("get_forecast", {"city": "上海", "days": 3})
    print(f"    get_forecast: {json.dumps(result, ensure_ascii=False)}")

    print("=" * 60)


if __name__ == "__main__":
    main()
