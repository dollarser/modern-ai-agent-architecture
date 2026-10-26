"""AgentHost 之上的 Application Session 与多轮消息层。"""

from __future__ import annotations

from safe_io import atomic_write_text
from keyed_lock import keyed_lock, store_scope
from copy import deepcopy

import asyncio
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    task_id: str | None = None
    run_id: str | None = None


@dataclass
class TaskRecord:
    task_id: str
    run_id: str
    request: str
    status: str = "pending"
    idempotency_key: str | None = None
    context: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    answer: str | None = None
    error: str | None = None


@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    tasks: list[TaskRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            str(data["session_id"]),
            [Message(**item) for item in data.get("messages", [])],
            [TaskRecord(**item) for item in data.get("tasks", [])],
        )


class SessionStore(Protocol):
    def load(self, session_id: str) -> Session | None: ...
    def save(self, session: Session) -> None: ...


class JsonSessionStore:
    """教学存储：原子替换，但不提供多进程事务。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text("utf-8")) if self.path.exists() else {}

    def load(self, session_id: str) -> Session | None:
        item = self._read().get(session_id)
        return Session.from_dict(item) if item else None

    def save(self, session: Session) -> None:
        data = self._read()
        data[session.session_id] = asdict(session)
        atomic_write_text(self.path, json.dumps(data, ensure_ascii=False, indent=2))


class RunScopedAgent(Protocol):
    async def run(
        self, task: str, run_id: str, conversation_context: list[str] | None = None
    ) -> dict[str, Any]: ...


AgentFactory = Callable[[str, str, str], RunScopedAgent]


class ConversationApplication:
    """一个 Session 聚合多条 Message；每条用户消息创建新的 Task 与 Run。"""

    def __init__(
        self,
        store: SessionStore,
        agent_factory: AgentFactory,
        *,
        id_factory: Callable[[], str] | None = None,
        max_context_messages: int = 12,
    ) -> None:
        self.store, self.agent_factory = store, agent_factory
        self.id_factory = id_factory or (lambda: uuid4().hex)
        if max_context_messages < 0:
            raise ValueError("max_context_messages 不能为负数")
        self.max_context_messages = max_context_messages
        self.lock_scope = store_scope(store)

    async def send(
        self, session_id: str, content: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        if not session_id.strip() or not content.strip() or idempotency_key == "":
            raise ValueError("session_id、消息与显式幂等键不能为空")
        async with keyed_lock(self.lock_scope, session_id):
            session = self.store.load(session_id) or Session(session_id)
            if idempotency_key is not None:
                existing = next((item for item in session.tasks if item.idempotency_key == idempotency_key), None)
                if existing:
                    if existing.request != content:
                        raise ValueError("idempotency_key_conflict")
                    if existing.result is None:
                        raise ValueError("resume_required: 使用原 task_id 显式恢复")
                    return self._response(session_id, existing)
            prior = session.messages[-self.max_context_messages:] if self.max_context_messages else []
            task_id, run_id = f"task-{self.id_factory()}", f"run-{self.id_factory()}"
            record = TaskRecord(task_id, run_id, content,
                idempotency_key=idempotency_key,
                context=[f"{message.role}: {message.content}" for message in prior])
            session.tasks.append(record)
            session.messages.append(Message("user", content, task_id, run_id))
            self.store.save(session)
            return await self._execute(session, record)

    async def resume(self, session_id: str, task_id: str) -> dict[str, Any]:
        async with keyed_lock(self.lock_scope, session_id):
            session = self.store.load(session_id)
            if session is None:
                raise LookupError("Session 不存在")
            record = next((item for item in session.tasks if item.task_id == task_id), None)
            if record is None:
                raise LookupError("Task 不存在")
            if record.result is not None and record.status == "completed":
                return self._response(session_id, record)
            return await self._execute(session, record)

    async def _execute(self, session: Session, record: TaskRecord) -> dict[str, Any]:
        record.status, record.error = "running", None
        self.store.save(session)
        try:
            agent = self.agent_factory(session.session_id, record.task_id, record.run_id)
            result = await agent.run(record.request, record.run_id, deepcopy(record.context))
        except BaseException as exc:
            record.status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
            record.error = str(exc) or type(exc).__name__
            self.store.save(session)
            raise
        record.result = deepcopy(result)
        record.status = str(result.get("status", "failed"))
        record.answer = str(result.get("final") or result.get("error") or "任务未完成")
        message = Message("assistant", record.answer, record.task_id, record.run_id)
        existing = next((index for index, item in enumerate(session.messages)
                         if item.role == "assistant" and item.run_id == record.run_id), None)
        if existing is None:
            session.messages.append(message)
        else:
            session.messages[existing] = message
        self.store.save(session)
        return self._response(session.session_id, record)

    @staticmethod
    def _response(session_id: str, record: TaskRecord) -> dict[str, Any]:
        return {"session_id": session_id, "task_id": record.task_id, "run_id": record.run_id,
                "answer": record.answer, "run": deepcopy(record.result)}

    def get_session(self, session_id: str) -> Session | None:
        return self.store.load(session_id)
