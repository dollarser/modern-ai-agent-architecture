"""第 7 章：可运行的最小 Agent 纵向切片。"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class TaskState:
    task: str
    step_count: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)
    finished: bool = False


class RulePlanner:
    """用确定性规则展示“推理后生成计划”的位置。"""

    def reason(self, task: str) -> str:
        return f"任务需要先查找相关信息，再整理可读结论：{task}"

    def plan(self, task: str) -> list[ToolCall]:
        return [
            ToolCall("search_catalog", {"query": task}),
            ToolCall("summarize_observation", {}),
        ]


class ToolDispatcher:
    """少量内置 Tool 的静态分发，不是动态 Tool Registry。"""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any], TaskState], dict[str, Any]]] = {
            "search_catalog": self._search_catalog,
            "summarize_observation": self._summarize_observation,
        }

    def execute(self, call: ToolCall, state: TaskState) -> dict[str, Any]:
        handler = self._handlers.get(call.name)
        if handler is None:
            return {"ok": False, "error": f"unknown tool: {call.name}"}
        return handler(call.arguments, state)

    @staticmethod
    def _search_catalog(arguments: dict[str, Any], _: TaskState) -> dict[str, Any]:
        query = str(arguments["query"])
        return {
            "ok": True,
            "matches": [
                {"path": "src/config.ts", "snippet": f"connection settings for: {query}"},
                {"path": "src/db.ts", "snippet": "createConnection(config)"},
            ],
        }

    @staticmethod
    def _summarize_observation(_: dict[str, Any], state: TaskState) -> dict[str, Any]:
        previous = state.observations[-1] if state.observations else {"matches": []}
        count = len(previous.get("matches", []))
        return {"ok": True, "summary": f"找到 {count} 条候选信息，等待用户确认下一步。"}


class MinimalAgent:
    def __init__(self, max_steps: int = 4) -> None:
        self.max_steps = max_steps
        self.planner = RulePlanner()
        self.tools = ToolDispatcher()

    def run(self, task: str) -> TaskState:
        state = TaskState(task=task)
        print(f"task: {task}")

        thought = self.planner.reason(task)
        print(f"reason: {thought}")

        plan = self.planner.plan(task)
        print(f"plan: {[call.name for call in plan]}")

        for call in plan:
            if state.step_count >= self.max_steps:
                break
            state.step_count += 1
            print(f"execute: {call.name}")
            observation = self.tools.execute(call, state)
            state.observations.append(observation)
            print(f"observe: {observation}")
            if not observation["ok"]:
                break

        state.finished = True
        print(f"finish: steps={state.step_count}, finished={state.finished}")
        return state


if __name__ == "__main__":
    MinimalAgent().run("查找数据库连接配置")
