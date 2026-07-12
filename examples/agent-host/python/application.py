"""AgentHost 之上的 Application Session 与多轮消息层。"""

from __future__ import annotations

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
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        temporary.replace(self.path)


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
        self.max_context_messages = max_context_messages
        self._lock = asyncio.Lock()

    async def send(self, session_id: str, content: str) -> dict[str, Any]:
        if not session_id.strip() or not content.strip():
            raise ValueError("session_id 与消息内容不能为空")
        async with self._lock:
            session = self.store.load(session_id) or Session(session_id)
            prior = session.messages[-self.max_context_messages:]
            task_id, run_id = f"task-{self.id_factory()}", f"run-{self.id_factory()}"
            record = TaskRecord(task_id, run_id, content)
            session.tasks.append(record)
            session.messages.append(Message("user", content, task_id, run_id))
            self.store.save(session)  # 调用 Runtime 前先持久化用户意图与执行身份。

            context = [f"{message.role}: {message.content}" for message in prior]
            agent = self.agent_factory(session_id, task_id, run_id)
            result = await agent.run(content, run_id, context)
            record.status = str(result.get("status", "failed"))
            answer = str(result.get("final") or result.get("error") or "任务未完成")
            session.messages.append(Message("assistant", answer, task_id, run_id))
            self.store.save(session)
            return {
                "session_id": session_id,
                "task_id": task_id,
                "run_id": run_id,
                "answer": answer,
                "run": result,
            }

    def get_session(self, session_id: str) -> Session | None:
        return self.store.load(session_id)
