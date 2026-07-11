"""
Tool Calling - Tool 抽象与调用示例
====================================
展示 Tool 定义、注册、Function Calling 和错误处理

运行环境：Python 3.10+
依赖：无
"""

import json
import ast
import math
import operator
from dataclasses import dataclass
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
    """只计算数字、括号和基础算术运算，不执行名称、调用或属性访问。"""
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
    """Tool 标准定义"""
    name: str
    description: str
    parameters: dict
    handler: Callable


class ToolRegistry:
    """Tool 注册中心"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_definitions(self) -> list[dict]:
        """获取 OpenAI 格式的 Tool 定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict) -> dict:
        """执行 Tool，带错误处理"""
        tool = self.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' 不存在"}

        try:
            result = tool.handler(**arguments)
            return result
        except TypeError as e:
            return {"success": False, "error": f"参数错误: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Tool 定义 ──────────────────────────────────

def search_web_handler(query: str, max_results: int = 5) -> dict:
    """搜索互联网（模拟实现）"""
    return {
        "success": True,
        "query": query,
        "results": [
            {"title": f"搜索结果 {i}: {query}", "url": f"https://example.com/r/{i}"}
            for i in range(1, min(max_results, 4) + 1)
        ]
    }


def calculate_handler(expression: str) -> dict:
    """执行数学计算"""
    try:
        result = safe_calculate(expression)
        return {"success": True, "expression": expression, "result": result}
    except Exception as e:
        return {"success": False, "expression": expression, "error": str(e)}


def read_file_handler(path: str) -> dict:
    """读取文件"""
    try:
        with open(path, "r") as f:
            content = f.read()
        return {"success": True, "path": path, "content": content[:500]}
    except FileNotFoundError:
        return {"success": False, "error": f"文件不存在: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 主流程 ─────────────────────────────────────

def main():
    # 创建 Tool Registry
    registry = ToolRegistry()

    # 注册 Tool
    registry.register(Tool(
        name="search_web",
        description="搜索互联网获取最新信息。当需要实时数据或用户询问最新消息时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最大结果数", "default": 5}
            },
            "required": ["query"]
        },
        handler=search_web_handler
    ))

    registry.register(Tool(
        name="calculate",
        description="执行数学计算。支持基本运算表达式。",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"]
        },
        handler=calculate_handler
    ))

    registry.register(Tool(
        name="read_file",
        description="读取文件内容。当需要查看文件内容时使用。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        },
        handler=read_file_handler
    ))

    # 打印已注册的 Tool
    print("=" * 60)
    print("  已注册的 Tool:")
    print("=" * 60)
    for name in registry.list_tools():
        tool = registry.get(name)
        print(f"  • {name}: {tool.description}")
    print()

    # 模拟 Function Calling 流程
    print("=" * 60)
    print("  模拟 Function Calling 流程")
    print("=" * 60)

    test_cases = [
        {
            "name": "search_web",
            "arguments": {"query": "AI Agent 架构 2026", "max_results": 3}
        },
        {
            "name": "calculate",
            "arguments": {"expression": "2 ** 10 + 3 * 5"}
        },
        {
            "name": "calculate",
            "arguments": {"expression": "__import__('os').getcwd()"}
        },
        {
            "name": "search_web",
            "arguments": {"query": "Python"}  # 缺少 max_results，使用默认值
        },
        {
            "name": "unknown_tool",
            "arguments": {}
        }
    ]

    for i, tc in enumerate(test_cases, 1):
        name = tc["name"]
        args = tc["arguments"]
        print(f"\n  [{i}] 调用 Tool: {name}")
        print(f"      参数: {json.dumps(args, ensure_ascii=False)}")
        result = registry.execute(name, args)
        status = "✓" if result.get("success") else "✗"
        print(f"      结果: {status} {json.dumps(result, ensure_ascii=False)[:120]}")

    print("\n" + "=" * 60)

    # 打印 Tool 定义（OpenAI 格式）
    print("\n  OpenAI 格式 Tool 定义:")
    print("=" * 60)
    for td in registry.get_definitions():
        print(f"  {json.dumps(td, ensure_ascii=False, indent=2)[:300]}")
        print("  ...")
    print("=" * 60)


if __name__ == "__main__":
    main()
