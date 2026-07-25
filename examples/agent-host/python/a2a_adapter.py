"""A2A/Artifact 进入 AgentHost 的最小适配层。

该模块只负责把远程 Task 的身份和事件绑定到 Host 的 run_id；远程传输、认证
和真正的 Artifact 持久化仍由注入的 Client/Store 实现。
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RemoteTaskRequest:
    run_id: str
    task_id: str
    tenant_id: str
    owner: str
    idempotency_key: str
    message: str


class RemoteTaskClient(Protocol):
    async def submit(self, request: RemoteTaskRequest) -> dict[str, Any]: ...

    async def get_task(self, task_id: str, tenant_id: str, owner: str) -> dict[str, Any]: ...

    async def get_artifact(self, artifact_id: str, tenant_id: str, owner: str) -> bytes: ...


class HostA2AAdapter:
    def __init__(self, host: Any, client: RemoteTaskClient) -> None:
        self.host = host
        self.client = client
        self._run_tasks: dict[str, str] = {}

    async def submit(self, request: RemoteTaskRequest) -> dict[str, Any]:
        bound = self._run_tasks.get(request.run_id)
        if bound and bound != request.task_id:
            return {"success": False, "error_code": "checkpoint_mismatch",
                    "error_message": "一个 run_id 不能绑定多个远程 task", "retryable": False}
        self._run_tasks[request.run_id] = request.task_id
        result = await self.client.submit(request)
        await self.host.events.publish("a2a.task.submitted", {
            "run_id": request.run_id, "task_id": request.task_id,
            "tenant_id": request.tenant_id, "status": result.get("status", "submitted"),
        })
        return result

    async def get_task(self, run_id: str, task_id: str, tenant_id: str, owner: str) -> dict[str, Any]:
        bound = self._run_tasks.get(run_id)
        if bound != task_id:
            return {"success": False, "error_code": "checkpoint_mismatch",
                    "error_message": "run_id 与远程 task_id 不匹配", "retryable": False}
        return await self.client.get_task(task_id, tenant_id, owner)

    async def get_artifact(self, run_id: str, artifact_id: str, tenant_id: str, owner: str) -> bytes:
        if run_id not in self._run_tasks:
            raise ValueError("run_id 尚未绑定远程 task")
        return await self.client.get_artifact(artifact_id, tenant_id, owner)
