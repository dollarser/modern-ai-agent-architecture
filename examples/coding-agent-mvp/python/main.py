"""
Coding Agent MVP - 完整组合版
====================================
组合轻量 Prompt、Instructions、Planner、Memory、
Tool 映射与回调。此示例不实现 MCP Client。

运行环境：Python 3.10+
依赖：无
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable
from collections import deque
from enum import Enum, auto


# ── 状态定义 ───────────────────────────────────

class AgentState(Enum):
    LOAD = auto()
    READ = auto()
    REASONING = auto()
    PLANNING = auto()
    EXECUTING = auto()
    OBSERVING = auto()
    FINISHED = auto()


# ── Tool ───────────────────────────────────────

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    tags: list[str] = field(default_factory=list)


# ── Memory ────────────────────────────────────

class Memory:
    def __init__(self, max_short_term: int = 20):
        self.short_term: deque = deque(maxlen=max_short_term)
        self.long_term: dict[str, Any] = {}

    def add(self, role: str, content: str):
        self.short_term.append({"role": role, "content": content})

    def save(self, key: str, value: Any):
        self.long_term[key] = value

    def recall(self, key: str) -> Any:
        return self.long_term.get(key)

    def get_context(self) -> str:
        return "\n".join(
            f"[{m['role']}] {m['content'][:100]}"
            for m in self.short_term
        )


# ── Planner ───────────────────────────────────

class Planner:
    def create_plan(self, task: str, tools: list[str]) -> list[str]:
        return [
            f"分析任务: {task}",
            f"选择工具: {', '.join(tools[:3])}",
            "执行操作",
            "验证结果",
        ]


# ── Tool Registry ──────────────────────────────

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_all(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, arguments: dict) -> dict:
        tool = self.get(name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {name}"}
        try:
            return tool.handler(**arguments)
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Hooks ─────────────────────────────────────

class HookSystem:
    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {}

    def on(self, event: str, callback: Callable):
        self._hooks.setdefault(event, []).append(callback)

    def trigger(self, event: str, *args):
        for hook in self._hooks.get(event, []):
            hook(*args)


# ── Coding Agent ───────────────────────────────

@dataclass
class AgentConfig:
    instructions: str
    max_steps: int = 10


class CodingAgent:
    """完整的 Coding Agent MVP"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = AgentState.LOAD
        self.memory = Memory()
        self.planner = Planner()
        self.tool_registry = ToolRegistry()
        self.hooks = HookSystem()
        self.step_count = 0

    def setup(self):
        """初始化 Agent"""
        # 注册内置 Tool
        self.tool_registry.register(Tool(
            name="read_file",
            description="读取文件内容",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=lambda path: {"success": True, "content": f"<文件内容: {path}>"},
            tags=["file"]
        ))
        self.tool_registry.register(Tool(
            name="write_file",
            description="写入文件",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
            handler=lambda path, content: {"success": True, "path": path},
            tags=["file"]
        ))
        self.tool_registry.register(Tool(
            name="search_code",
            description="搜索代码库",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            handler=lambda query: {"success": True, "results": [f"match_{query}"]},
            tags=["search"]
        ))
        self.tool_registry.register(Tool(
            name="execute_command",
            description="执行 Shell 命令",
            parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            handler=lambda command: {"success": True, "output": f"$ {command}\nOK"},
            tags=["shell"]
        ))

        # 注册默认 Hook
        self.hooks.on("before_tool_call", lambda name, args: print(f"  [Hook] 调用 Tool: {name}"))
        self.hooks.on("after_tool_call", lambda name, result: print(f"  [Hook] Tool 完成: {name}"))

        self.state = AgentState.LOAD
        self.memory.add("system", f"Instructions: {self.config.instructions}")

    def run(self, prompt: str) -> str:
        """Agent 主循环"""
        self.state = AgentState.READ
        self.memory.add("user", prompt)

        print(f"\n{'='*60}")
        print(f"  Coding Agent MVP")
        print(f"{'='*60}")
        print(f"  任务: {prompt}")
        print(f"  可用 Tool: {self.tool_registry.list_all()}")
        print(f"  {'-'*40}")

        while self.step_count < self.config.max_steps:
            self.step_count += 1

            # Reasoning
            self.state = AgentState.REASONING
            self.hooks.trigger("before_reasoning", prompt)
            thought = f"分析任务: {prompt}"
            self.memory.add("assistant", thought)
            self.hooks.trigger("after_reasoning", thought)

            # Planning
            self.state = AgentState.PLANNING
            tools = self.tool_registry.list_all()
            plan = self.planner.create_plan(prompt, tools)
            self.memory.add("assistant", f"计划: {plan}")

            # Execute
            self.state = AgentState.EXECUTING
            if "文件" in prompt or "代码" in prompt:
                self.hooks.trigger("before_tool_call", "read_file", {"path": "main.py"})
                result = self.tool_registry.execute("read_file", {"path": "main.py"})
                self.hooks.trigger("after_tool_call", "read_file", result)
            elif "搜索" in prompt:
                self.hooks.trigger("before_tool_call", "search_code", {"query": prompt})
                result = self.tool_registry.execute("search_code", {"query": prompt})
                self.hooks.trigger("after_tool_call", "search_code", result)
            else:
                result = {"success": True, "message": "任务分析完成"}

            # Observe
            self.state = AgentState.OBSERVING
            self.memory.add("tool", json.dumps(result, ensure_ascii=False))

            # 简化：执行一次就完成
            break

        self.state = AgentState.FINISHED
        self.hooks.trigger("before_finish")
        self.memory.add("assistant", "任务完成")

        print(f"  {'-'*40}")
        print(f"  执行步数: {self.step_count}")
        print(f"  最终状态: {self.state}")
        print(f"  记忆条目: {len(self.memory.short_term)}")
        print(f"{'='*60}")

        return "任务完成"


def main():
    config = AgentConfig(
        instructions="你是一个 Coding Agent，帮助用户完成编程任务。始终使用中文回复。",
        max_steps=10
    )

    agent = CodingAgent(config)
    agent.setup()

    # 测试不同任务
    agent.run("搜索数据库连接相关的代码")
    agent.run("读取 main.py 文件")


if __name__ == "__main__":
    main()
