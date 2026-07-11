"""第 9 章：可测试的最小 Agent Runtime 状态机。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class RunStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FINISHED = "finished"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True)
class RuntimeConfig:
    max_steps: int = 4
    step_timeout: float = 1.0


@dataclass
class RunResult:
    status: RunStatus
    step_count: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == RunStatus.FINISHED


Executor = Callable[[str], Awaitable[dict[str, Any]]]


class AgentRuntime:
    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.result = RunResult(status=RunStatus.IDLE)

    def cancel(self) -> None:
        if self.result.status == RunStatus.RUNNING:
            self.result.status = RunStatus.CANCELLED

    async def run(self, plan: list[str], executor: Executor) -> RunResult:
        self.result = RunResult(status=RunStatus.RUNNING)

        for step in plan:
            if self.result.status == RunStatus.CANCELLED:
                return self.result
            if self.result.step_count >= self.config.max_steps:
                self.result.status = RunStatus.EXHAUSTED
                self.result.error = f"达到最大 Tool 步数: {self.config.max_steps}"
                return self.result

            try:
                observation = await asyncio.wait_for(
                    executor(step), timeout=self.config.step_timeout
                )
            except asyncio.TimeoutError:
                self.result.status = RunStatus.ERROR
                self.result.error = f"步骤超时: {step}"
                return self.result
            except Exception as error:
                self.result.status = RunStatus.ERROR
                self.result.error = str(error)
                return self.result

            self.result.step_count += 1
            self.result.observations.append(observation)
            if self.result.status == RunStatus.CANCELLED:
                return self.result
            if observation.get("done") is True:
                self.result.status = RunStatus.FINISHED
                return self.result

        self.result.status = RunStatus.EXHAUSTED
        self.result.error = "计划已执行完，但未满足完成条件"
        return self.result


async def demo() -> None:
    async def execute(step: str) -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return {"step": step, "done": step == "verify"}

    result = await AgentRuntime().run(["search", "inspect", "verify"], execute)
    print({
        "success": result.success,
        "status": result.status.value,
        "steps": result.step_count,
        "error": result.error,
    })


if __name__ == "__main__":
    asyncio.run(demo())
