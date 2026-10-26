"""Observer Event Bus 与 Subagent Handoff 协调。"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol, TypeVar, Union

from runtime_state import ToolResult


__all__ = [
    "AgentRunner",
    "EventBus",
    "EventBusPort",
    "HandoffCoordinator",
    "HandoffRequest",
    "HookKind",
    "ReviewSubagent",
]


T = TypeVar("T")


async def _await_if_needed(value: Union[T, Awaitable[T]]) -> T:
    return await value if inspect.isawaitable(value) else value


class HookKind(str, Enum):
    GUARD = "guard"
    OBSERVER = "observer"


class EventBusPort(Protocol):
    def publish(
        self, topic: str, payload: dict[str, Any]
    ) -> Awaitable[None]: ...


class EventBus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._subscribers: dict[
            str, list[tuple[
                HookKind, str,
                Callable[[dict[str, Any]], Union[None, Awaitable[None]]],
            ]]
        ] = {}

    def subscribe(
        self, topic: str,
        callback: Callable[[dict[str, Any]], Union[None, Awaitable[None]]], *,
        kind: HookKind = HookKind.OBSERVER, name: str = "anonymous",
    ) -> None:
        self._subscribers.setdefault(topic, []).append((kind, name, callback))

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        event = {"topic": topic, **payload}
        self.events.append(event)
        for kind, name, callback in self._subscribers.get(topic, []):
            try:
                await _await_if_needed(callback(event))
            except Exception as exc:
                if kind is HookKind.GUARD:
                    raise
                self.events.append({
                    "topic": "observer.error", "subscriber": name, "error": str(exc),
                })


@dataclass(frozen=True)
class HandoffRequest:
    task: str
    parent_run_id: str
    parent_trace_id: str
    parent_span_id: str
    depth: int = 1


class AgentRunner(Protocol):
    def run_task(self, request: HandoffRequest) -> ToolResult | Awaitable[ToolResult]: ...


class ReviewSubagent:
    def run_task(self, request: HandoffRequest) -> ToolResult:
        return {
            "success": True,
            "review": "子 Agent 已验证候选路径与变更说明",
            "parent_trace_id": request.parent_trace_id,
            "parent_span_id": request.parent_span_id,
        }


class HandoffCoordinator:
    def __init__(self, runner: AgentRunner, events: EventBusPort, max_depth: int = 2) -> None:
        self.runner, self.events, self.max_depth = runner, events, max_depth

    async def handoff(self, request: HandoffRequest) -> ToolResult:
        if request.depth > self.max_depth:
            return {"success": False, "error": "Handoff 超过最大深度"}
        await self.events.publish(
            "handoff.created",
            {"run_id": request.parent_run_id, "trace_id": request.parent_trace_id},
        )
        result = await _await_if_needed(self.runner.run_task(request))
        await self.events.publish(
            "handoff.completed",
            {"run_id": request.parent_run_id, "success": result.get("success")},
        )
        return result
