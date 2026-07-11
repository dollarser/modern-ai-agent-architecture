"""第 16 章最终组装：可插拔端口与离线最小适配器。"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol


ToolResult = dict[str, Any]
ToolHandler = Callable[[dict[str, Any], "ExecutionContext"], ToolResult]
HookCallback = Callable[[str, dict[str, Any], "RunState"], None]


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
    session_id: str
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        return cls(
            session_id=str(data["session_id"]),
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
        )


# ── Memory port ──────────────────────────────────────────────────────────────

class MemoryBackend(Protocol):
    def append(self, session_id: str, entry: MemoryEntry) -> None: ...
    def recent(self, session_id: str, limit: int = 12) -> list[MemoryEntry]: ...
    def remember(self, namespace: str, entry: MemoryEntry) -> None: ...
    def search(self, namespace: str, query: str, limit: int = 5) -> list[MemoryEntry]: ...


class InMemoryMemoryBackend:
    """短期按 Session 隔离；长期按 Namespace 隔离；检索使用确定性词项评分。"""

    def __init__(self) -> None:
        self.short_term: dict[str, list[MemoryEntry]] = {}
        self.long_term: dict[str, list[MemoryEntry]] = {}

    def append(self, session_id: str, entry: MemoryEntry) -> None:
        self.short_term.setdefault(session_id, []).append(entry)

    def recent(self, session_id: str, limit: int = 12) -> list[MemoryEntry]:
        return list(self.short_term.get(session_id, [])[-limit:])

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

    def emit(self, event: str, payload: dict[str, Any], state: RunState) -> None:
        state.trace.append({"event": event, "step": payload.get("step_id")})
        for hook in self._hooks.get(event, []):
            try:
                hook.callback(event, payload, state)
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
    source: ToolSource = ToolSource.BUILTIN
    source_name: str = "core"
    state: ToolState = ToolState.ACTIVE
    tags: tuple[str, ...] = ()
    requires_approval: bool = False


@dataclass
class ExecutionContext:
    task: str
    results: dict[int, ToolResult]
    session_id: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

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
        return len(names)

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise LookupError(f"Tool 未注册: {name}")
        return tool

    def list(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda tool: tool.name)


class ToolRouter:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def available(self, *, tag: str | None = None) -> list[Tool]:
        return [
            tool for tool in self.registry.list()
            if tool.state is ToolState.ACTIVE and (tag is None or tag in tool.tags)
        ]

    def resolve(self, name: str) -> Tool:
        tool = self.registry.get(name)
        if tool.state is not ToolState.ACTIVE:
            raise PermissionError(f"Tool 不可用: {name} ({tool.state.value})")
        return tool

    def execute(
        self, name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult:
        return self.resolve(name).handler(arguments, context)


# ── Skills, MCP and Plugins ─────────────────────────────────────────────────

@dataclass(frozen=True)
class Skill:
    name: str
    keywords: tuple[str, ...]
    instructions: str


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def match(self, task: str) -> list[Skill]:
        lowered = task.lower()
        return [
            skill for skill in self._skills.values()
            if any(keyword.lower() in lowered for keyword in skill.keywords)
        ]


@dataclass(frozen=True)
class MCPToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient(Protocol):
    def list_tools(self) -> list[MCPToolDefinition]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult: ...


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

    def register_tools(self, registry: ToolRegistry) -> int:
        definitions = self.client.list_tools()
        for definition in definitions:
            name = definition.name
            registry.register(
                Tool(
                    name=name,
                    description=definition.description,
                    parameters=definition.input_schema,
                    source=ToolSource.MCP,
                    source_name=self.server_name,
                    tags=("external",),
                    handler=lambda arguments, _context, tool_name=name: self.client.call_tool(
                        tool_name, arguments
                    ),
                )
            )
        return len(definitions)


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
        for tool in plugin.tools:
            self.tools.register(
                Tool(
                    **{
                        **tool.__dict__,
                        "source": ToolSource.PLUGIN,
                        "source_name": name,
                    }
                )
            )
        for skill in plugin.skills:
            self.skills.register(skill)
        for event, definition in plugin.hooks:
            self.hooks.register(
                event,
                definition.callback,
                kind=definition.kind,
                priority=definition.priority,
                name=definition.name,
                owner=name,
            )
        plugin.state = "active"
        self._plugins[name] = plugin

    def unload(self, name: str) -> None:
        plugin = self._plugins.pop(name)
        self.tools.unregister_by_source(ToolSource.PLUGIN, name)
        for skill in plugin.skills:
            self.skills.unregister(skill.name)
        self.hooks.unregister_owner(name)
        plugin.state = "unloaded"


# ── Approval and orchestration ──────────────────────────────────────────────

@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    session_id: str
    tool: str
    arguments: dict[str, Any]
    reason: str


class ApprovalGate(Protocol):
    def decide(self, request: ApprovalRequest) -> bool: ...


class AutoApproveGate:
    def decide(self, request: ApprovalRequest) -> bool:
        return True


class ScriptedApprovalGate:
    def __init__(self, decisions: dict[str, bool]) -> None:
        self.decisions = decisions
        self.requests: list[ApprovalRequest] = []

    def decide(self, request: ApprovalRequest) -> bool:
        self.requests.append(request)
        return self.decisions.get(request.tool, False)


class EventBus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def subscribe(self, topic: str, callback: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.setdefault(topic, []).append(callback)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        event = {"topic": topic, **payload}
        self.events.append(event)
        for callback in self._subscribers.get(topic, []):
            callback(event)


@dataclass(frozen=True)
class HandoffRequest:
    task: str
    parent_session_id: str
    parent_trace_id: str
    depth: int = 1


class AgentRunner(Protocol):
    def run_task(self, request: HandoffRequest) -> ToolResult: ...


class ReviewSubagent:
    def run_task(self, request: HandoffRequest) -> ToolResult:
        return {
            "success": True,
            "review": "子 Agent 已验证候选路径与变更说明",
            "parent_trace_id": request.parent_trace_id,
        }


class HandoffCoordinator:
    def __init__(self, runner: AgentRunner, events: EventBus, max_depth: int = 2) -> None:
        self.runner, self.events, self.max_depth = runner, events, max_depth

    def handoff(self, request: HandoffRequest) -> ToolResult:
        if request.depth > self.max_depth:
            return {"success": False, "error": "Handoff 超过最大深度"}
        self.events.publish(
            "handoff.created",
            {"session_id": request.parent_session_id, "trace_id": request.parent_trace_id},
        )
        result = self.runner.run_task(request)
        self.events.publish(
            "handoff.completed",
            {"session_id": request.parent_session_id, "success": result.get("success")},
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
        data[state.session_id] = state.to_dict()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def load(self, session_id: str) -> RunState | None:
        item = self._read_all().get(session_id)
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
    ) -> None:
        self.router, self.hooks, self.approval, self.memory, self.config = (
            router, hooks, approval, memory, config
        )

    async def run(self, state: RunState, checkpoint: Callable[[], None]) -> None:
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
                checkpoint()
                return
            if state.step_count >= self.config.max_steps:
                state.status, state.error = "max_steps", f"达到最大 Tool 步数: {self.config.max_steps}"
                checkpoint()
                return
            if (
                self.config.interrupt_after_steps is not None
                and state.step_count - started_at >= self.config.interrupt_after_steps
            ):
                state.status, state.error = "interrupted", "按教学配置模拟中断，可恢复"
                checkpoint()
                return
            remaining = self.config.max_steps - state.step_count
            batch = ready[:remaining]
            if self.config.interrupt_after_steps is not None:
                batch = batch[: self.config.interrupt_after_steps - (state.step_count - started_at)]
            results = await asyncio.gather(*(self._execute_step(step, state) for step in batch))
            for step, result in zip(batch, results):
                state.results[step.id] = result
                state.step_count += 1
                state.memory.append(
                    entry := MemoryEntry("tool", json.dumps(
                        {"step_id": step.id, "tool": step.tool, "result": result},
                        ensure_ascii=False,
                    ))
                )
                self.memory.append(state.session_id, entry)
            checkpoint()

        failure = next(
            (result for result in state.results.values() if not result.get("success", False)),
            None,
        )
        if failure:
            state.status, state.error = "failed", str(failure.get("error", "Tool 执行失败"))
        else:
            state.status, state.error = "completed", None
        checkpoint()

    async def _execute_step(self, step: PlanStep, state: RunState) -> ToolResult:
        payload = {"step_id": step.id, "tool": step.tool, "arguments": step.arguments}
        try:
            self.hooks.emit("before_tool", payload, state)
            tool = self.router.resolve(step.tool)
            if tool.requires_approval:
                approval_id = f"{state.session_id}:{step.id}:{step.tool}"
                if approval_id not in state.approvals:
                    request = ApprovalRequest(
                        approval_id, state.session_id, step.tool, step.arguments,
                        "Tool 声明 requires_approval",
                    )
                    self.hooks.emit("before_approval", {**payload, "request": request.id}, state)
                    state.approvals[approval_id] = self.approval.decide(request)
                    self.hooks.emit(
                        "after_approval",
                        {**payload, "approved": state.approvals[approval_id]},
                        state,
                    )
                if not state.approvals[approval_id]:
                    result = {"success": False, "error": f"审批拒绝执行: {step.tool}"}
                    self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
                    self.hooks.emit("after_tool", {**payload, "result": result}, state)
                    return result
        except Exception as exc:
            result = {"success": False, "error": f"Guardrail 拒绝执行: {exc}"}
            self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
            self.hooks.emit("after_tool", {**payload, "result": result}, state)
            return result

        context = ExecutionContext(state.task, state.results, state.session_id)
        last_error = "Tool 执行失败"
        attempt = 0
        for attempt in range(1, self.config.max_retries + 2):
            state.attempt_count += 1
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self.router.execute, step.tool, step.arguments, context),
                    timeout=self.config.step_timeout,
                )
                result = {**result, "attempts": attempt}
                if result.get("success", False):
                    self.hooks.emit("after_tool", {**payload, "result": result}, state)
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
        self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
        self.hooks.emit("after_tool", {**payload, "result": result}, state)
        return result


class EnhancedAgent:
    """Composition Root：所有端口均可由构造函数替换。"""

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
        event_bus: EventBus | None = None,
        subagent: AgentRunner | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.llm = llm or DeterministicLLMAdapter()
        self.memory = memory or InMemoryMemoryBackend()
        self.hooks = hooks or HookPipeline()
        self.approval = approval or AutoApproveGate()
        self.events = event_bus or EventBus()
        self.tools = ToolRegistry()
        self.router = ToolRouter(self.tools)
        self.skills = SkillRegistry()
        self.plugins = PluginLoader(self.tools, self.skills, self.hooks)
        self.checkpoints = JsonCheckpointStore(checkpoint_path)
        self.mcp = MCPToolAdapter(mcp_client or FakeMCPClient(), "catalog-server")
        self.handoffs = HandoffCoordinator(subagent or ReviewSubagent(), self.events)
        self._assemble()

    def _assemble(self) -> None:
        self.skills.register(Skill(
            "config-review", ("配置", "config"), "先检索候选路径，再生成变更并交给子 Agent 复核。"
        ))
        self.memory.remember("default", MemoryEntry(
            "preference", "数据库 配置 变更必须给出文件路径并经过审查"
        ))
        self.mcp.register_tools(self.tools)
        self.tools.register(Tool(
            "inspect_candidate", "检查首个候选", lambda _args, ctx: {
                "success": True,
                "path": ctx.results[1]["matches"][0],
                "finding": "发现数据库连接配置入口",
            }, tags=("read",)
        ))
        self.tools.register(Tool(
            "delegate_review", "Handoff 给审查子 Agent",
            lambda _args, ctx: self.handoffs.handoff(HandoffRequest(
                task="审查变更建议", parent_session_id=ctx.session_id,
                parent_trace_id=f"step-{len(ctx.results) + 1}",
            )), tags=("orchestration",)
        ))
        self.tools.register(Tool(
            "compose_report", "组合最终报告", lambda _args, ctx: {
                "success": True,
                "report": f"{ctx.results[4]['proposal']}；{ctx.results[5]['review']}。",
            }, tags=("output",)
        ))
        plugin = Plugin(
            PluginManifest("review-pack", "1.0.0", ("tools:register",)),
            tools=[
                Tool(
                    "summarize_matches", "汇总 MCP 候选", lambda _args, ctx: {
                        "success": True,
                        "count": len(ctx.results[1]["matches"]),
                        "summary": "找到 2 个候选文件",
                    }, tags=("analysis",)
                ),
                Tool(
                    "propose_change", "生成配置变更建议", lambda _args, ctx: {
                        "success": True,
                        "proposal": f"建议更新 {ctx.results[2]['path']}（{ctx.results[3]['summary']}）",
                    }, tags=("write",), requires_approval=True
                ),
            ],
        )
        self.plugins.load(plugin)
        self.hooks.register(
            "before_tool", self._enforce_allowlist,
            kind=HookKind.GUARD, priority=10, name="tool-allowlist",
        )

    def _enforce_allowlist(
        self, _event: str, payload: dict[str, Any], _state: RunState
    ) -> None:
        if str(payload["tool"]) not in self.config.allowed_tools:
            raise PermissionError(f"Tool 不在允许列表中: {payload['tool']}")

    @staticmethod
    def _validate_plan(plan: list[PlanStep]) -> None:
        ids = [step.id for step in plan]
        if len(ids) != len(set(ids)):
            raise ValueError("计划步骤 id 必须唯一")
        known = set(ids)
        for step in plan:
            if step.id in step.depends_on or not set(step.depends_on).issubset(known):
                raise ValueError(f"步骤 {step.id} 包含无效依赖")

    def _record_memory(self, state: RunState, role: str, content: str) -> None:
        entry = MemoryEntry(role, content)
        state.memory.append(entry)
        self.memory.append(state.session_id, entry)

    async def run(self, task: str, session_id: str) -> dict[str, Any]:
        started = time.monotonic()
        restored = self.checkpoints.load(session_id)
        if restored and restored.task != task:
            return self._result(restored, "同一 session_id 不能恢复为不同任务", False, started)

        if restored:
            state = restored
            resumed = state.status != "completed"
            if state.status == "completed":
                final = await self.llm.final_answer(task, state.results)
                return self._result(state, final, True, started)
            self.hooks.emit("before_run", {"task": task, "resumed": True}, state)
            self.hooks.emit("on_resume", {"status": state.status}, state)
        else:
            state = RunState(session_id, task, [])
            self.events.publish("task.started", {"session_id": session_id})
            self.hooks.emit("before_run", {"task": task}, state)
            matched = self.skills.match(task)
            recalled = self.memory.search("default", task)
            context = [self.config.instructions]
            context.extend(skill.instructions for skill in matched)
            context.extend(entry.content for entry in recalled)
            self.hooks.emit("before_plan", {"context": context}, state)
            state.plan = await self.llm.create_plan(
                task, [tool.name for tool in self.router.available()], context
            )
            self._validate_plan(state.plan)
            self.hooks.emit("after_plan", {"steps": len(state.plan)}, state)
            self._record_memory(state, "system", self.config.instructions)
            for instruction in context[1:]:
                self._record_memory(state, "context", instruction)
            self._record_memory(state, "user", task)
            resumed = False
            self.checkpoints.save(state)

        executor = DependencyExecutor(
            self.router, self.hooks, self.approval, self.memory, self.config
        )
        await executor.run(state, lambda: self.checkpoints.save(state))
        final = (
            await self.llm.final_answer(task, state.results)
            if state.status == "completed" else state.error or "任务未完成"
        )
        self._record_memory(state, "assistant" if state.status == "completed" else "system", final)
        self.hooks.emit("after_run", {"status": state.status}, state)
        self.hooks.emit("on_finish", {"status": state.status}, state)
        self.events.publish("task.completed", {"session_id": session_id, "status": state.status})
        self.checkpoints.save(state)
        return self._result(state, final, resumed, started)

    @staticmethod
    def _result(
        state: RunState, final: str, resumed: bool, started: float
    ) -> dict[str, Any]:
        return {
            "success": state.status == "completed",
            "status": state.status,
            "session_id": state.session_id,
            "resumed": resumed,
            "steps": state.step_count,
            "attempts": state.attempt_count,
            "results": state.results,
            "final": final,
            "error": state.error,
            "trace": state.trace,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
