"""
Tool Registry - 工具注册与调度示例
=====================================
展示动态 Tool 注册、发现和路由

运行环境：Python 3.10+
依赖：无
"""

import json
import ast
import math
import operator
from dataclasses import dataclass, field
from typing import Any, Callable


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_calculate(expression: str) -> int | float:
    """使用 AST 白名单计算基础算术表达式。"""
    if len(expression) > 128:
        raise ValueError("表达式过长")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 32:
        raise ValueError("表达式过于复杂")

    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("只允许数字常量")
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return _UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("指数绝对值不能超过 10")
            result = _BINARY_OPERATORS[type(node.op)](left, right)
            if not math.isfinite(result) or abs(result) > 1e15:
                raise ValueError("计算结果超出允许范围")
            return result
        raise ValueError(f"不允许的表达式节点: {type(node).__name__}")

    return evaluate(tree)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"


class DynamicToolRegistry:
    """动态 Tool 注册中心"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_all(self) -> list[str]:
        return list(self._tools.keys())

    def find_by_tag(self, tag: str) -> list[Tool]:
        return [t for t in self._tools.values() if tag in t.tags]

    def search(self, keyword: str) -> list[Tool]:
        """按关键词搜索 Tool"""
        keyword = keyword.lower()
        return [
            t for t in self._tools.values()
            if keyword in t.name.lower() or keyword in t.description.lower()
        ]

    def get_definitions(self, tags: list[str] | None = None) -> list[dict]:
        """获取 OpenAI 格式的 Tool 定义，可按标签过滤"""
        tools = self._tools.values()
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]

        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in tools
        ]

    def execute(self, name: str, arguments: dict) -> dict:
        tool = self.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' 不存在"}

        try:
            return tool.handler(**arguments)
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    registry = DynamicToolRegistry()

    # 注册 Tool
    registry.register(Tool(
        name="search_web",
        description="搜索互联网",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        handler=lambda query: {"success": True, "results": [f"结果: {query}"]},
        tags=["search", "web"]
    ))

    registry.register(Tool(
        name="read_file",
        description="读取文件内容",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        handler=lambda path: {"success": True, "path": path},
        tags=["file", "io"]
    ))

    registry.register(Tool(
        name="search_files",
        description="搜索文件系统中的文件",
        parameters={"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]},
        handler=lambda pattern: {"success": True, "matches": [f"file_{pattern}.py"]},
        tags=["search", "file"]
    ))

    registry.register(Tool(
        name="calculate",
        description="执行数学计算",
        parameters={"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]},
        handler=lambda expr: {"success": True, "result": safe_calculate(expr)},
        tags=["math", "utility"]
    ))

    print("=" * 60)
    print("  Tool Registry 示例")
    print("=" * 60)

    # 列出所有 Tool
    print(f"\n  已注册 Tool: {', '.join(registry.list_all())}")

    # 按标签搜索
    for tag in ["search", "file", "math"]:
        tools = registry.find_by_tag(tag)
        print(f"  [{tag}] -> {[t.name for t in tools]}")

    # 关键词搜索
    results = registry.search("搜索")
    print(f"\n  搜索 '搜索': {[t.name for t in results]}")

    print(f"  安全计算: {registry.execute('calculate', {'expr': '(2 + 3) * 4'})}")
    print(f"  拒绝代码: {registry.execute('calculate', {'expr': '__import__(\"os\")'})}")

    # 动态注销
    print(f"\n  注销 'calculate'...")
    registry.unregister("calculate")
    print(f"  已注册 Tool: {', '.join(registry.list_all())}")

    # 获取过滤后的定义
    print(f"\n  [web] 标签的 Tool 定义:")
    for d in registry.get_definitions(tags=["web"]):
        print(f"    - {d['function']['name']}")

    print("=" * 60)


if __name__ == "__main__":
    main()
