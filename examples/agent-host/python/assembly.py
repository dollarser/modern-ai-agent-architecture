"""第 16 章最终组装：可插拔端口与离线最小适配器。"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol, TypeVar, Union

from governance import (
    ConfigScope, DefaultPolicyEngine, PolicyDecision, PolicyEngine, PolicyLayer, PolicyRequest,
    sha256_text, with_snapshot_hash,
)


ToolResult = dict[str, Any]
ToolHandler = Callable[
    [dict[str, Any], "ExecutionContext"], Union[ToolResult, Awaitable[ToolResult]]
]
ToolPreparer = Callable[[dict[str, Any], "ExecutionContext"], dict[str, Any]]
HookCallback = Callable[
    [str, dict[str, Any], "RunState"], Union[None, Awaitable[None]]
]
T = TypeVar("T")


async def await_if_needed(value: Union[T, Awaitable[T]]) -> T:
    return await value if inspect.isawaitable(value) else value


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
    step_count: int = 0
    attempt_count: int = 0
    status: str = "pending"
    error: str | None = None
    capability_snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "plan": [asdict(step) for step in self.plan],
            "results": {str(key): value for key, value in self.results.items()},
            "memory": [asdict(entry) for entry in self.memory],
            "trace": self.trace,
            "approvals": self.approvals,
            "step_count": self.step_count,
            "attempt_count": self.attempt_count,
            "status": self.status,
            "error": self.error,
            "capability_snapshot": self.capability_snapshot,
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
            step_count=int(data.get("step_count", 0)),
            attempt_count=int(data.get("attempt_count", 0)),
            status=str(data.get("status", "pending")),
            error=data.get("error"),
            capability_snapshot=data.get("capability_snapshot"),
        )


# ── Memory port ──────────────────────────────────────────────────────────────

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
        # 二元片段让无空格的中文任务也能进行一个确定性的教学检索。
        terms = words | {normalized[index:index + 2] for index in range(len(normalized) - 1)}
        ranked: list[tuple[int, int, MemoryEntry]] = []
        for index, entry in enumerate(self.long_term.get(namespace, [])):
            content = entry.content.lower()
            score = sum(term in content for term in terms)
            if score:
                ranked.append((score, index, entry))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [entry for _, _, entry in ranked[:limit]]


# ── Lifecycle hooks ─────────────────────────────────────────────────────────

class HookKind(str, Enum):
    GUARD = "guard"
    OBSERVER = "observer"


@dataclass(order=True)
class HookDefinition:
    priority: int
    callback: HookCallback = field(compare=False)
    kind: HookKind = field(default=HookKind.OBSERVER, compare=False)
    name: str = field(default="anonymous", compare=False)
    owner: str = field(default="core", compare=False)


class HookPipeline:
    """Guard 失败关闭执行；Observer 失败隔离并写入 Trace。"""

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookDefinition]] = {}

    def register(
        self,
        event: str,
        callback: HookCallback,
        *,
        kind: HookKind = HookKind.OBSERVER,
        priority: int = 100,
        name: str = "anonymous",
        owner: str = "core",
    ) -> None:
        definition = HookDefinition(priority, callback, kind, name, owner)
        self._hooks.setdefault(event, []).append(definition)
        self._hooks[event].sort()

    def unregister_owner(self, owner: str) -> None:
        for event, hooks in list(self._hooks.items()):
            self._hooks[event] = [hook for hook in hooks if hook.owner != owner]

    async def emit(self, event: str, payload: dict[str, Any], state: RunState) -> None:
        state.trace.append({"event": event, "step": payload.get("step_id")})
        for hook in self._hooks.get(event, []):
            try:
                await await_if_needed(hook.callback(event, payload, state))
            except Exception as exc:
                if hook.kind is HookKind.GUARD:
                    raise
                state.trace.append(
                    {"event": "observer_error", "hook": hook.name, "error": str(exc)}
                )


# ── Tool registry / router ──────────────────────────────────────────────────

class ToolSource(str, Enum):
    BUILTIN = "builtin"
    MCP = "mcp"
    PLUGIN = "plugin"


class ToolState(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: ToolHandler
    parameters: dict[str, Any] = field(default_factory=dict)
    prepare: ToolPreparer | None = None
    source: ToolSource = ToolSource.BUILTIN
    source_name: str = "core"
    state: ToolState = ToolState.ACTIVE
    tags: tuple[str, ...] = ()
    requires_approval: bool = False


@dataclass
class ExecutionContext:
    task: str
    results: dict[int, ToolResult]
    run_id: str
    trace_id: str
    span_id: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._aliases: dict[str, str] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        if tool.name in self._tools and not replace:
            raise ValueError(f"Tool 已存在: {tool.name}")
        self._tools[tool.name] = tool

    def unregister_by_source(self, source: ToolSource, source_name: str) -> int:
        names = [
            name for name, tool in self._tools.items()
            if tool.source is source and tool.source_name == source_name
        ]
        for name in names:
            del self._tools[name]
        for alias, target in list(self._aliases.items()):
            if target in names:
                del self._aliases[alias]
        return len(names)

    def register_alias(self, alias: str, canonical_name: str) -> None:
        if alias in self._tools or alias in self._aliases:
            raise ValueError(f"Tool Alias 已存在: {alias}")
        if canonical_name not in self._tools:
            raise LookupError(f"Tool 未注册: {canonical_name}")
        self._aliases[alias] = canonical_name

    def get(self, name: str) -> Tool:
        tool = self._tools.get(self._aliases.get(name, name))
        if tool is None:
            raise LookupError(f"Tool 未注册: {name}")
        return tool

    def contains(self, name: str) -> bool:
        return name in self._tools or name in self._aliases

    def list(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda tool: tool.name)

    def snapshot(self) -> "ToolRegistry":
        frozen = ToolRegistry()
        for tool in self.list():
            frozen.register(tool)
        for alias, target in self._aliases.items():
            frozen.register_alias(alias, target)
        return frozen

    def aliases(self) -> dict[str, str]:
        return dict(sorted(self._aliases.items()))


class ToolRouter:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def available(self, *, tag: str | None = None) -> list[Tool]:
        return [
            tool for tool in self.registry.list()
            if tool.state is ToolState.ACTIVE and (tag is None or tag in tool.tags)
        ]

    def available_names(self) -> list[str]:
        canonical = [tool.name for tool in self.available()]
        aliases = [
            alias for alias, target in self.registry.aliases().items()
            if target in canonical
        ]
        return sorted([*canonical, *aliases])

    def resolve(self, name: str) -> Tool:
        tool = self.registry.get(name)
        if tool.state is not ToolState.ACTIVE:
            raise PermissionError(f"Tool 不可用: {name} ({tool.state.value})")
        return tool

    async def execute(
        self, name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult:
        tool = self.resolve(name)
        self._validate_arguments(tool.parameters, arguments)
        if inspect.iscoroutinefunction(tool.handler):
            return await tool.handler(arguments, context)
        result = await asyncio.to_thread(tool.handler, arguments, context)
        return await await_if_needed(result)

    @staticmethod
    def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
        if not schema:
            return
        for name in schema.get("required", []):
            if name not in arguments:
                raise ValueError(f"Tool 参数缺少必填字段: {name}")
        properties = schema.get("properties", {})
        expected_types = {
            "string": str, "number": (int, float), "integer": int,
            "boolean": bool, "object": dict, "array": list,
        }
        for name, value in arguments.items():
            definition = properties.get(name)
            if definition is None:
                if schema.get("additionalProperties") is False:
                    raise ValueError(f"Tool 参数包含未知字段: {name}")
                continue
            expected = expected_types.get(definition.get("type"))
            if expected and (not isinstance(value, expected) or (
                definition.get("type") in {"number", "integer"} and isinstance(value, bool)
            )):
                raise TypeError(f"Tool 参数类型错误: {name}")
            if "enum" in definition and value not in definition["enum"]:
                raise ValueError(f"Tool 参数不在允许值中: {name}")


# ── Skills, MCP and Plugins ─────────────────────────────────────────────────

@dataclass(frozen=True)
class Skill:
    name: str
    keywords: tuple[str, ...]
    instructions: str
    owner: str = "core"


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    keywords: tuple[str, ...]
    owner: str


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill, *, replace: bool = False) -> None:
        if skill.name in self._skills and not replace:
            raise ValueError(f"Skill 已存在: {skill.name}")
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def contains(self, name: str) -> bool:
        return name in self._skills

    def unregister_owner(self, owner: str) -> None:
        for name in [name for name, skill in self._skills.items() if skill.owner == owner]:
            del self._skills[name]

    def match(self, task: str) -> list[Skill]:
        return self.load([item.name for item in self.discover(task)])

    def discover(self, task: str) -> list[SkillMetadata]:
        lowered = task.lower()
        return [
            SkillMetadata(skill.name, skill.keywords, skill.owner)
            for skill in self._skills.values()
            if any(keyword.lower() in lowered for keyword in skill.keywords)
        ]

    def load(self, names: list[str]) -> list[Skill]:
        return [self._skills[name] for name in names if name in self._skills]


class InstalledSkillProvider(Protocol):
    def load_skills(self) -> list[Skill] | Awaitable[list[Skill]]: ...


@dataclass(frozen=True)
class MCPToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient(Protocol):
    def list_tools(self) -> list[MCPToolDefinition] | Awaitable[list[MCPToolDefinition]]: ...
    def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult | Awaitable[ToolResult]: ...


class MCPServerProvider(Protocol):
    def connect_enabled(
        self,
    ) -> list[tuple[str, MCPClient]] | Awaitable[list[tuple[str, MCPClient]]]: ...
    def close(self) -> None | Awaitable[None]: ...


class FakeMCPClient:
    """离线 MCP Client；Adapter 与真实 Client 使用相同契约。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_tools(self) -> list[MCPToolDefinition]:
        return [MCPToolDefinition("search_catalog", "从 MCP 目录查找候选文件")]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append(name)
        if name != "search_catalog":
            return {"success": False, "error": f"未知 MCP Tool: {name}"}
        return {
            "success": True,
            "query": str(arguments.get("query", "")),
            "matches": ["src/config.ts", "src/db.ts"],
        }


class MCPToolAdapter:
    def __init__(self, client: MCPClient, server_name: str) -> None:
        self.client = client
        self.server_name = server_name
        self._registered = False

    async def register_tools(self, registry: ToolRegistry) -> int:
        if self._registered:
            return 0
        definitions = await await_if_needed(self.client.list_tools())
        for definition in definitions:
            name = f"{self.server_name}.{definition.name}"
            registry.register(
                Tool(
                    name=name,
                    description=definition.description,
                    parameters=definition.input_schema,
                    source=ToolSource.MCP,
                    source_name=self.server_name,
                    tags=("external",),
                    handler=self._handler(definition.name),
                )
            )
            if not registry.contains(definition.name):
                registry.register_alias(definition.name, name)
        self._registered = True
        return len(definitions)

    def _handler(self, remote_name: str) -> ToolHandler:
        async def call(arguments: dict[str, Any], _context: ExecutionContext) -> ToolResult:
            return await await_if_needed(self.client.call_tool(remote_name, arguments))
        return call

    def unregister_tools(self, registry: ToolRegistry) -> int:
        removed = registry.unregister_by_source(ToolSource.MCP, self.server_name)
        self._registered = False
        return removed


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    permissions: tuple[str, ...] = ()


@dataclass
class Plugin:
    manifest: PluginManifest
    tools: list[Tool] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    hooks: list[tuple[str, HookDefinition]] = field(default_factory=list)
    state: str = "registered"


class PluginLoader:
    def __init__(
        self, tools: ToolRegistry, skills: SkillRegistry, hooks: HookPipeline
    ) -> None:
        self.tools, self.skills, self.hooks = tools, skills, hooks
        self._plugins: dict[str, Plugin] = {}

    def load(self, plugin: Plugin) -> None:
        name = plugin.manifest.name
        if name in self._plugins:
            raise ValueError(f"Plugin 已加载: {name}")
        required_permissions = {
            permission
            for permission, resources in (
                ("tools:register", plugin.tools),
                ("skills:register", plugin.skills),
                ("hooks:register", plugin.hooks),
            )
            if resources
        }
        missing = required_permissions.difference(plugin.manifest.permissions)
        if missing:
            raise PermissionError(f"Plugin 权限不足: {sorted(missing)}")
        conflicts = [tool.name for tool in plugin.tools if self.tools.contains(tool.name)]
        conflicts.extend(
            skill.name for skill in plugin.skills if self.skills.contains(skill.name)
        )
        if conflicts:
            raise ValueError(f"Plugin 资源冲突: {sorted(conflicts)}")
        try:
            for tool in plugin.tools:
                self.tools.register(Tool(**{
                    **tool.__dict__, "source": ToolSource.PLUGIN, "source_name": name,
                }))
            for skill in plugin.skills:
                self.skills.register(Skill(**{**skill.__dict__, "owner": name}))
            for event, definition in plugin.hooks:
                self.hooks.register(
                    event, definition.callback, kind=definition.kind,
                    priority=definition.priority, name=definition.name, owner=name,
                )
        except Exception:
            self.tools.unregister_by_source(ToolSource.PLUGIN, name)
            self.skills.unregister_owner(name)
            self.hooks.unregister_owner(name)
            raise
        plugin.state = "active"
        self._plugins[name] = plugin

    def unload(self, name: str) -> None:
        plugin = self._plugins.pop(name)
        self.tools.unregister_by_source(ToolSource.PLUGIN, name)
        self.skills.unregister_owner(name)
        self.hooks.unregister_owner(name)
        plugin.state = "unloaded"


class InstalledPluginProvider(Protocol):
    def load_plugins(self) -> list[Plugin] | Awaitable[list[Plugin]]: ...


# ── Approval and orchestration ──────────────────────────────────────────────

@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    run_id: str
    tool: str
    arguments: dict[str, Any]
    reason: str
    preview: dict[str, Any] = field(default_factory=dict)
    risk: str = "high"
    idempotency_key: str = ""


class ApprovalGate(Protocol):
    def decide(self, request: ApprovalRequest) -> bool | Awaitable[bool]: ...


class AutoApproveGate:
    def decide(self, request: ApprovalRequest) -> bool:
        return True


class DenyApprovalGate:
    """安全默认值：未显式配置审批器时拒绝高风险操作。"""

    def decide(self, request: ApprovalRequest) -> bool:
        return False


class ScriptedApprovalGate:
    def __init__(self, decisions: dict[str, bool]) -> None:
        self.decisions = decisions
        self.requests: list[ApprovalRequest] = []

    def decide(self, request: ApprovalRequest) -> bool:
        self.requests.append(request)
        return self.decisions.get(request.tool, False)


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
                await await_if_needed(callback(event))
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
        result = await await_if_needed(self.runner.run_task(request))
        await self.events.publish(
            "handoff.completed",
            {"run_id": request.parent_run_id, "success": result.get("success")},
        )
        return result


# ── Runtime ports and execution ─────────────────────────────────────────────

class LLMAdapter(Protocol):
    async def create_plan(
        self, task: str, tool_names: list[str], context: list[str]
    ) -> list[PlanStep]: ...

    async def final_answer(self, task: str, results: dict[int, ToolResult]) -> str: ...


class DeterministicLLMAdapter:
    def __init__(self) -> None:
        self.last_context: list[str] = []

    async def create_plan(
        self, task: str, tool_names: list[str], context: list[str]
    ) -> list[PlanStep]:
        self.last_context = list(context)
        required = {
            "search_catalog", "inspect_candidate", "summarize_matches",
            "propose_change", "delegate_review", "compose_report",
        }
        missing = sorted(required.difference(tool_names))
        if missing:
            raise ValueError(f"计划所需 Tool 未注册: {missing}")
        return [
            PlanStep(1, "通过 MCP 查找候选", "search_catalog", {"query": task}),
            PlanStep(2, "检查首个候选", "inspect_candidate", depends_on=[1]),
            PlanStep(3, "通过 Plugin 汇总候选", "summarize_matches", depends_on=[1]),
            PlanStep(4, "生成需审批的变更建议", "propose_change", depends_on=[2, 3]),
            PlanStep(5, "移交子 Agent 审查", "delegate_review", depends_on=[4]),
            PlanStep(6, "组合最终报告", "compose_report", depends_on=[4, 5]),
        ]

    async def final_answer(self, task: str, results: dict[int, ToolResult]) -> str:
        return f"任务：{task}\n{results.get(6, {}).get('report', '未生成报告')}"


class CheckpointStore(Protocol):
    def save(self, state: RunState) -> Union[None, Awaitable[None]]: ...
    def load(
        self, run_id: str
    ) -> Union[RunState | None, Awaitable[RunState | None]]: ...


class JsonCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: RunState) -> None:
        data = self._read_all()
        data[state.run_id] = state.to_dict()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def load(self, run_id: str) -> RunState | None:
        item = self._read_all().get(run_id)
        return RunState.from_dict(item) if item else None


@dataclass(frozen=True)
class AgentConfig:
    instructions: str = "只读取模拟数据，并输出可核查的路径"
    max_steps: int = 10
    max_retries: int = 1
    step_timeout: float = 2.0
    retry_delay: float = 0.01
    interrupt_after_steps: int | None = None
    allowed_tools: frozenset[str] = frozenset(
        {
            "search_catalog", "inspect_candidate", "summarize_matches",
            "propose_change", "delegate_review", "compose_report",
        }
    )


class DependencyExecutor:
    def __init__(
        self,
        router: ToolRouter,
        hooks: HookPipeline,
        approval: ApprovalGate,
        memory: MemoryBackend,
        config: AgentConfig,
        policy: PolicyEngine,
        snapshot_hash: str,
    ) -> None:
        self.router, self.hooks, self.approval, self.memory, self.config = (
            router, hooks, approval, memory, config
        )
        self.policy, self.snapshot_hash = policy, snapshot_hash

    async def run(
        self, state: RunState,
        checkpoint: Callable[[], Union[None, Awaitable[None]]],
    ) -> None:
        started_at = state.step_count
        state.status, state.error = "running", None
        while len(state.results) < len(state.plan):
            pending = [step for step in state.plan if step.id not in state.results]
            for step in pending:
                if any(
                    dependency in state.results
                    and not state.results[dependency].get("success", False)
                    for dependency in step.depends_on
                ):
                    state.results[step.id] = {
                        "success": False, "error": "依赖步骤失败，未执行 Tool", "skipped": True
                    }
            pending = [step for step in state.plan if step.id not in state.results]
            if not pending:
                break
            ready = [
                step for step in pending
                if all(dependency in state.results for dependency in step.depends_on)
            ]
            if not ready:
                state.status, state.error = "failed", "计划存在循环依赖或未知依赖"
                await await_if_needed(checkpoint())
                return
            if state.step_count >= self.config.max_steps:
                state.status, state.error = "max_steps", f"达到最大 Tool 步数: {self.config.max_steps}"
                await await_if_needed(checkpoint())
                return
            if (
                self.config.interrupt_after_steps is not None
                and state.step_count - started_at >= self.config.interrupt_after_steps
            ):
                state.status, state.error = "interrupted", "按教学配置模拟中断，可恢复"
                await await_if_needed(checkpoint())
                return
            remaining = self.config.max_steps - state.step_count
            batch = ready[:remaining]
            if self.config.interrupt_after_steps is not None:
                batch = batch[: self.config.interrupt_after_steps - (state.step_count - started_at)]
            results = await asyncio.gather(
                *(self._execute_step(step, state, checkpoint) for step in batch)
            )
            for step, result in zip(batch, results):
                state.results[step.id] = result
                state.step_count += 1
                state.memory.append(
                    entry := MemoryEntry("tool", json.dumps(
                        {"step_id": step.id, "tool": step.tool, "result": result},
                        ensure_ascii=False,
                    ))
                )
                await await_if_needed(self.memory.append(state.run_id, entry))
            await await_if_needed(checkpoint())

        failure = next(
            (result for result in state.results.values() if not result.get("success", False)),
            None,
        )
        if failure:
            state.status, state.error = "failed", str(failure.get("error", "Tool 执行失败"))
        else:
            state.status, state.error = "completed", None
        await await_if_needed(checkpoint())

    async def _execute_step(
        self, step: PlanStep, state: RunState,
        checkpoint: Callable[[], Union[None, Awaitable[None]]],
    ) -> ToolResult:
        payload = {"step_id": step.id, "tool": step.tool, "arguments": step.arguments}
        context = ExecutionContext(
            state.task, state.results, state.run_id,
            f"trace-{state.run_id}", f"step-{step.id}",
        )
        try:
            await self.hooks.emit("before_tool", payload, state)
            tool = self.router.resolve(step.tool)
            decision = self.policy.evaluate(PolicyRequest(
                subject="agent", capability=step.tool, arguments=step.arguments,
                resource=step.tool, run_id=state.run_id,
                source=f"{tool.source.value}:{tool.source_name}",
                risk="high" if tool.requires_approval else "normal",
            ))
            state.trace.append({
                "event": "policy_decision", "tool": step.tool,
                "decision": decision.value, "policy_version": self.policy.version,
            })
            if decision is PolicyDecision.DENY:
                raise PermissionError(f"Policy 拒绝 Tool: {step.tool}")
            if decision is PolicyDecision.ASK:
                approval_id = (
                    f"{state.run_id}:{step.id}:{step.tool}:{self.snapshot_hash}"
                )
                if approval_id not in state.approvals:
                    dependency_results = {
                        str(dependency): state.results[dependency]
                        for dependency in step.depends_on
                    }
                    preview = {
                        "task": state.task,
                        "tool": step.tool,
                        "arguments": step.arguments,
                        "dependency_results": dependency_results,
                    }
                    if tool.prepare is not None:
                        preview.update(tool.prepare(step.arguments, context))
                    request = ApprovalRequest(
                        approval_id, state.run_id, step.tool, step.arguments,
                        "Tool 声明 requires_approval", preview, "high", approval_id,
                    )
                    await self.hooks.emit(
                        "before_approval", {**payload, "request": request.id}, state
                    )
                    state.approvals[approval_id] = await await_if_needed(
                        self.approval.decide(request)
                    )
                    await self.hooks.emit(
                        "after_approval",
                        {**payload, "approved": state.approvals[approval_id]},
                        state,
                    )
                    # 审批决定必须先于有副作用的 Handler 持久化。
                    await await_if_needed(checkpoint())
                if not state.approvals[approval_id]:
                    result = {"success": False, "error": f"审批拒绝执行: {step.tool}"}
                    await self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
                    await self.hooks.emit("after_tool", {**payload, "result": result}, state)
                    return result
        except Exception as exc:
            result = {"success": False, "error": f"Guardrail 拒绝执行: {exc}"}
            await self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
            await self.hooks.emit("after_tool", {**payload, "result": result}, state)
            return result

        last_error = "Tool 执行失败"
        attempt = 0
        for attempt in range(1, self.config.max_retries + 2):
            state.attempt_count += 1
            try:
                result = await asyncio.wait_for(
                    self.router.execute(step.tool, step.arguments, context),
                    timeout=self.config.step_timeout,
                )
                result = {**result, "attempts": attempt}
                if result.get("success", False):
                    await self.hooks.emit("after_tool", {**payload, "result": result}, state)
                    return result
                last_error = str(result.get("error", last_error))
                if not result.get("retryable", False):
                    break
            except asyncio.TimeoutError:
                last_error = f"Tool '{step.tool}' 超时"
                break
            except Exception as exc:
                last_error = str(exc)
                break
            if attempt <= self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay * attempt)
        result = {"success": False, "error": last_error, "attempts": attempt}
        await self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
        await self.hooks.emit("after_tool", {**payload, "result": result}, state)
        return result


class AgentHost:
    """通用 Agent Host：只负责组装端口、治理扩展和执行计划。"""

    def __init__(
        self,
        checkpoint_path: str | Path,
        config: AgentConfig | None = None,
        *,
        llm: LLMAdapter | None = None,
        memory: MemoryBackend | None = None,
        hooks: HookPipeline | None = None,
        approval: ApprovalGate | None = None,
        mcp_client: MCPClient | None = None,
        installed_skills: InstalledSkillProvider | None = None,
        mcp_servers: MCPServerProvider | None = None,
        installed_plugins: InstalledPluginProvider | None = None,
        event_bus: EventBusPort | None = None,
        subagent: AgentRunner | None = None,
        checkpoint_store: CheckpointStore | None = None,
        policy: PolicyEngine | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.llm = llm or DeterministicLLMAdapter()
        self.memory = memory or InMemoryMemoryBackend()
        self.hooks = hooks or HookPipeline()
        self.approval = approval or DenyApprovalGate()
        self.policy = policy or DefaultPolicyEngine(self.config.allowed_tools)
        self.events = event_bus or EventBus()
        self.tools = ToolRegistry()
        self.router = ToolRouter(self.tools)
        self.skills = SkillRegistry()
        self.plugins = PluginLoader(self.tools, self.skills, self.hooks)
        self.checkpoints = checkpoint_store or JsonCheckpointStore(checkpoint_path)
        self.mcp = MCPToolAdapter(mcp_client or FakeMCPClient(), "catalog-server")
        self.installed_skills = installed_skills
        self.mcp_servers = mcp_servers
        self.installed_plugins = installed_plugins
        self._managed_mcp: list[MCPToolAdapter] = []
        self._installed_plugin_names: list[str] = []
        self.handoffs = HandoffCoordinator(subagent or ReviewSubagent(), self.events)
        self._memory_initialized = False
        self._extensions_initialized = False
        self._extension_lock = asyncio.Lock()
        self._installed_skill_names: list[str] = []
        self.initial_memory: MemoryEntry | None = None

    @staticmethod
    def _validate_plan(plan: list[PlanStep]) -> None:
        ids = [step.id for step in plan]
        if len(ids) != len(set(ids)):
            raise ValueError("计划步骤 id 必须唯一")
        known = set(ids)
        for step in plan:
            if step.id in step.depends_on or not set(step.depends_on).issubset(known):
                raise ValueError(f"步骤 {step.id} 包含无效依赖")

    async def _record_memory(self, state: RunState, role: str, content: str) -> None:
        entry = MemoryEntry(role, content)
        state.memory.append(entry)
        await await_if_needed(self.memory.append(state.run_id, entry))

    async def run(
        self, task: str, run_id: str, conversation_context: list[str] | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        try:
            return await self._run(task, run_id, started, conversation_context or [])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                state = await await_if_needed(self.checkpoints.load(run_id))
                state = state or RunState(run_id, task, [])
            except Exception:
                state = RunState(run_id, task, [])
            state.status = "failed"
            state.error = f"runtime_error: {exc}"
            try:
                await self.hooks.emit("on_error", {"error": str(exc)}, state)
            except Exception as hook_error:
                state.trace.append({"event": "on_error_failed", "error": str(hook_error)})
            try:
                await self.events.publish(
                    "task.failed", {"run_id": run_id, "error": state.error}
                )
            except Exception:
                pass
            try:
                await await_if_needed(self.checkpoints.save(state))
            except Exception as checkpoint_error:
                state.trace.append(
                    {"event": "checkpoint_error", "error": str(checkpoint_error)}
                )
            return self._result(state, state.error, False, started)

    async def _initialize_extensions(self) -> None:
        async with self._extension_lock:
            if self._extensions_initialized:
                return
            try:
                if self.installed_skills:
                    for skill in await await_if_needed(self.installed_skills.load_skills()):
                        self.skills.register(skill)
                        self._installed_skill_names.append(skill.name)
                await self.mcp.register_tools(self.tools)
                if self.mcp_servers:
                    clients = await await_if_needed(self.mcp_servers.connect_enabled())
                    for server_name, client in clients:
                        adapter = MCPToolAdapter(client, server_name)
                        await adapter.register_tools(self.tools)
                        self._managed_mcp.append(adapter)
                if self.installed_plugins:
                    for plugin in await await_if_needed(self.installed_plugins.load_plugins()):
                        self.plugins.load(plugin)
                        self._installed_plugin_names.append(plugin.manifest.name)
                self._extensions_initialized = True
            except Exception:
                await self._rollback_extensions(close_provider=True)
                raise

    async def _rollback_extensions(self, *, close_provider: bool) -> list[str]:
        errors: list[str] = []
        for name in reversed(self._installed_plugin_names):
            try:
                self.plugins.unload(name)
            except Exception as exc:
                errors.append(f"plugin {name}: {exc}")
        self._installed_plugin_names.clear()
        for adapter in reversed(self._managed_mcp):
            adapter.unregister_tools(self.tools)
        self._managed_mcp.clear()
        self.mcp.unregister_tools(self.tools)
        for name in reversed(self._installed_skill_names):
            self.skills.unregister(name)
        self._installed_skill_names.clear()
        if close_provider and self.mcp_servers:
            try:
                await await_if_needed(self.mcp_servers.close())
            except Exception as exc:
                errors.append(f"mcp provider: {exc}")
        self._extensions_initialized = False
        return errors

    async def close_extensions(self) -> None:
        """关闭安装型扩展；由 Host 生命周期显式调用。"""
        async with self._extension_lock:
            errors = await self._rollback_extensions(close_provider=True)
        if errors:
            raise RuntimeError("扩展关闭存在错误: " + "; ".join(errors))

    def _capability_snapshot(self) -> dict[str, Any]:
        payload = {
            "tools": [{
                "name": tool.name, "schema": tool.parameters,
                "source": tool.source.value, "source_name": tool.source_name,
            } for tool in self.tools.list()],
            "tool_aliases": self.tools.aliases(),
            "skills": [{
                "name": skill.name, "owner": skill.owner,
                "checksum": sha256_text(skill.instructions),
            } for skill in sorted(self.skills._skills.values(), key=lambda item: item.name)],
            "policy_version": self.policy.version,
            "config": {"allowed_tools": sorted(self.config.allowed_tools)},
        }
        return with_snapshot_hash(payload)

    async def _run(
        self, task: str, run_id: str, started: float, conversation_context: list[str]
    ) -> dict[str, Any]:
        await self._initialize_extensions()
        current_snapshot = self._capability_snapshot()
        run_router = ToolRouter(self.tools.snapshot())
        if not self._memory_initialized and self.initial_memory is not None:
            await await_if_needed(self.memory.remember("default", self.initial_memory))
            self._memory_initialized = True
        restored = await await_if_needed(self.checkpoints.load(run_id))
        if restored and restored.task != task:
            mismatch = RunState(run_id, task, [])
            mismatch.status = "failed"
            mismatch.error = "run_task_mismatch"
            return self._result(
                mismatch, "同一 run_id 不能恢复为不同任务", False, started
            )
        if (
            restored and restored.capability_snapshot
            and restored.capability_snapshot.get("snapshot_hash")
            != current_snapshot["snapshot_hash"]
        ):
            mismatch = RunState(run_id, task, [])
            mismatch.status = "failed"
            mismatch.error = "capability_snapshot_mismatch"
            mismatch.capability_snapshot = current_snapshot
            return self._result(mismatch, mismatch.error, False, started)

        if restored:
            state = restored
            existing_memory = await await_if_needed(
                self.memory.recent(run_id, max(12, len(state.memory)))
            )
            for entry in state.memory:
                if entry not in existing_memory:
                    await await_if_needed(self.memory.append(run_id, entry))
                    existing_memory.append(entry)
            resumed = state.status != "completed"
            if state.status == "completed":
                final = await self.llm.final_answer(task, state.results)
                return self._result(state, final, False, started, replayed=True)
            await self.hooks.emit("before_run", {"task": task, "resumed": True}, state)
            await self.hooks.emit("on_resume", {"status": state.status}, state)
        else:
            state = RunState(run_id, task, [])
            state.capability_snapshot = current_snapshot
            await self.events.publish("task.started", {"run_id": run_id})
            await self.hooks.emit("before_run", {"task": task}, state)
            discovered = self.skills.discover(task)
            state.trace.append({
                "event": "skills_discovered", "skills": [item.name for item in discovered]
            })
            matched = self.skills.load([item.name for item in discovered])
            state.trace.append({
                "event": "skills_loaded", "skills": [item.name for item in matched]
            })
            recalled = await await_if_needed(self.memory.search("default", task))
            context = [self.config.instructions]
            context.extend(conversation_context)
            context.extend(skill.instructions for skill in matched)
            context.extend(entry.content for entry in recalled)
            await self.hooks.emit("before_plan", {"context": context}, state)
            state.plan = await self.llm.create_plan(
                task, run_router.available_names(), context
            )
            self._validate_plan(state.plan)
            await self.hooks.emit("after_plan", {"steps": len(state.plan)}, state)
            await self._record_memory(state, "system", self.config.instructions)
            for instruction in context[1:]:
                await self._record_memory(state, "context", instruction)
            await self._record_memory(state, "user", task)
            resumed = False
            await await_if_needed(self.checkpoints.save(state))

        executor = DependencyExecutor(
            run_router, self.hooks, self.approval, self.memory, self.config,
            self.policy, current_snapshot["snapshot_hash"],
        )
        await executor.run(state, lambda: self.checkpoints.save(state))
        final = (
            await self.llm.final_answer(task, state.results)
            if state.status == "completed" else state.error or "任务未完成"
        )
        await self._record_memory(
            state, "assistant" if state.status == "completed" else "system", final
        )
        await self.hooks.emit("after_run", {"status": state.status}, state)
        await self.hooks.emit("on_finish", {"status": state.status}, state)
        await self.events.publish(
            "task.completed", {"run_id": run_id, "status": state.status}
        )
        await await_if_needed(self.checkpoints.save(state))
        return self._result(state, final, resumed, started)

    @staticmethod
    def _result(
        state: RunState, final: str, resumed: bool, started: float, *, replayed: bool = False
    ) -> dict[str, Any]:
        return {
            "success": state.status == "completed",
            "status": state.status,
            "run_id": state.run_id,
            "resumed": resumed,
            "replayed": replayed,
            "steps": state.step_count,
            "attempts": state.attempt_count,
            "results": state.results,
            "final": final,
            "error": state.error,
            "trace": state.trace,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
