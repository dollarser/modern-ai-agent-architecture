from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AgentCard:
    name: str
    skills: tuple[str, ...]
    auth_scheme: str


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    task_id: str
    tenant_id: str
    owner: str
    media_type: str
    checksum: str
    size: int
    content: bytes = field(repr=False)


@dataclass
class Task:
    task_id: str
    context_id: str
    tenant_id: str
    owner: str
    status: str = "submitted"
    events: list[dict] = field(default_factory=list)
    artifacts: list[ArtifactRef] = field(default_factory=list)


class ArtifactStore:
    def __init__(self) -> None:
        self._items: dict[str, ArtifactRef] = {}

    def put(self, task: Task, content: bytes, media_type: str) -> ArtifactRef:
        artifact_id = f"artifact-{len(self._items) + 1}"
        ref = ArtifactRef(
            artifact_id, task.task_id, task.tenant_id, task.owner, media_type,
            sha256(content).hexdigest(), len(content), content,
        )
        self._items[artifact_id] = ref
        return ref

    def get(self, artifact_id: str, tenant_id: str, owner: str) -> bytes:
        ref = self._items[artifact_id]
        if (ref.tenant_id, ref.owner) != (tenant_id, owner):
            raise PermissionError("artifact scope mismatch")
        return ref.content


class InMemoryA2A:
    def __init__(self) -> None:
        self.card = AgentCard("report-agent", ("report",), "bearer")
        self.artifacts = ArtifactStore()
        self.tasks: dict[str, Task] = {}
        self._idempotency: dict[str, str] = {}

    def submit(self, task_id: str, idempotency_key: str, tenant_id: str, owner: str) -> Task:
        if idempotency_key in self._idempotency:
            return self.tasks[self._idempotency[idempotency_key]]
        task = Task(task_id, f"ctx-{task_id}", tenant_id, owner)
        self.tasks[task_id] = task
        self._idempotency[idempotency_key] = task_id
        self._emit(task, "submitted")
        return task

    def work(self, task_id: str, payload: dict) -> Task:
        task = self.tasks[task_id]
        self._emit(task, "working")
        body = json.dumps(payload, ensure_ascii=False).encode()
        task.artifacts.append(self.artifacts.put(task, body, "application/json"))
        self._emit(task, "completed")
        return task

    def cancel(self, task_id: str) -> Task:
        task = self.tasks[task_id]
        # This means cancellation was accepted locally; it does not assert
        # that an already-started external side effect was rolled back.
        self._emit(task, "cancel_requested")
        return task

    @staticmethod
    def _emit(task: Task, status: str) -> None:
        task.status = status
        task.events.append({"task_id": task.task_id, "status": status,
                            "sequence": len(task.events) + 1, "timestamp": now()})


class ContractTest(unittest.TestCase):
    def test_idempotency_and_artifact_scope(self) -> None:
        server = InMemoryA2A()
        first = server.submit("task-1", "idem-1", "tenant-a", "alice")
        again = server.submit("task-2", "idem-1", "tenant-a", "alice")
        self.assertIs(first, again)
        server.work("task-1", {"answer": "完成"})
        self.assertEqual(first.status, "completed")
        self.assertEqual(server.artifacts.get(first.artifacts[0].artifact_id, "tenant-a", "alice").decode(), '{"answer": "完成"}')
        with self.assertRaises(PermissionError):
            server.artifacts.get(first.artifacts[0].artifact_id, "tenant-b", "alice")

    def test_cancel_is_not_rollback(self) -> None:
        server = InMemoryA2A()
        task = server.submit("task-1", "idem-1", "tenant-a", "alice")
        server.cancel(task.task_id)
        self.assertEqual(task.status, "cancel_requested")


if __name__ == "__main__":
    unittest.main()
