"""Run 状态与 Memory Port；保持执行状态模型独立于 Host 组装。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Protocol, Union


__all__ = [
    "InMemoryMemoryBackend",
    "MemoryBackend",
    "MemoryEntry",
    "PlanStep",
    "RunState",
    "ToolResult",
]


ToolResult = dict[str, Any]


@dataclass(frozen=True)
class PlanStep:
    id: int
    description: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)


@dataclass
class MemoryEntry:
    role: str
    content: str


@dataclass
class RunState:
    run_id: str
    task: str
    plan: list[PlanStep]
    results: dict[int, ToolResult] = field(default_factory=dict)
    memory: list[MemoryEntry] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    approvals: dict[str, bool] = field(default_factory=dict)
    executions: dict[str, str] = field(default_factory=dict)
    step_count: int = 0
    attempt_count: int = 0
    status: str = "pending"
    error: str | None = None
    capability_snapshot: dict[str, Any] | None = None
    final_answer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "plan": [asdict(step) for step in self.plan],
            "results": {str(key): value for key, value in self.results.items()},
            "memory": [asdict(entry) for entry in self.memory],
            "trace": self.trace,
            "approvals": self.approvals,
            "executions": self.executions,
            "step_count": self.step_count,
            "attempt_count": self.attempt_count,
            "status": self.status,
            "error": self.error,
            "capability_snapshot": self.capability_snapshot,
            "final_answer": self.final_answer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        return cls(
            run_id=str(data["run_id"]),
            task=str(data["task"]),
            plan=[PlanStep(**step) for step in data.get("plan", [])],
            results={int(key): value for key, value in data.get("results", {}).items()},
            memory=[MemoryEntry(**entry) for entry in data.get("memory", [])],
            trace=list(data.get("trace", [])),
            approvals=dict(data.get("approvals", {})),
            executions=dict(data.get("executions", {})),
            step_count=int(data.get("step_count", 0)),
            attempt_count=int(data.get("attempt_count", 0)),
            status=str(data.get("status", "pending")),
            error=data.get("error"),
            capability_snapshot=data.get("capability_snapshot"),
            final_answer=data.get("final_answer"),
        )


class MemoryBackend(Protocol):
    def append(
        self, run_id: str, entry: MemoryEntry
    ) -> Union[None, Awaitable[None]]: ...

    def recent(
        self, run_id: str, limit: int = 12
    ) -> Union[list[MemoryEntry], Awaitable[list[MemoryEntry]]]: ...

    def remember(
        self, namespace: str, entry: MemoryEntry
    ) -> Union[None, Awaitable[None]]: ...

    def search(
        self, namespace: str, query: str, limit: int = 5
    ) -> Union[list[MemoryEntry], Awaitable[list[MemoryEntry]]]: ...


class InMemoryMemoryBackend:
    """短期按 Run 隔离；长期按 Namespace 隔离；检索使用确定性词项评分。"""

    def __init__(self) -> None:
        self.short_term: dict[str, list[MemoryEntry]] = {}
        self.long_term: dict[str, list[MemoryEntry]] = {}

    def append(self, run_id: str, entry: MemoryEntry) -> None:
        self.short_term.setdefault(run_id, []).append(entry)

    def recent(self, run_id: str, limit: int = 12) -> list[MemoryEntry]:
        return list(self.short_term.get(run_id, [])[-limit:])

    def remember(self, namespace: str, entry: MemoryEntry) -> None:
        entries = self.long_term.setdefault(namespace, [])
        if entry not in entries:
            entries.append(entry)

    def search(self, namespace: str, query: str, limit: int = 5) -> list[MemoryEntry]:
        normalized = query.lower().replace("，", " ")
        words = {item for item in normalized.split() if item}
        terms = words | {
            normalized[index:index + 2] for index in range(len(normalized) - 1)
        }
        ranked: list[tuple[int, int, MemoryEntry]] = []
        for index, entry in enumerate(self.long_term.get(namespace, [])):
            content = entry.content.lower()
            score = sum(term in content for term in terms)
            if score:
                ranked.append((score, index, entry))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [entry for _, _, entry in ranked[:limit]]
