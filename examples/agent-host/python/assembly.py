"""第 16 章最终组装：可插拔端口与离线最小适配器。"""

from __future__ import annotations

import asyncio
import inspect
from copy import deepcopy
from types import CodeType
import json
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol, TypeVar, Union

from coordination import *  # noqa: F401,F403 - 公共协调契约由 assembly 统一重导出
from governance import (
    ConfigScope, DefaultPolicyEngine, PolicyDecision, PolicyEngine, PolicyLayer, PolicyRequest,
    sha256_text, with_snapshot_hash,
)
from safe_io import atomic_write_text
from keyed_lock import keyed_lock, store_scope, track_execution, has_active_execution
from runtime_state import *  # noqa: F401,F403 - 公共状态契约由 assembly 统一重导出


ToolHandler = Callable[
    [dict[str, Any], "ExecutionContext"], Union[ToolResult, Awaitable[ToolResult]]
]
ToolPreparer = Callable[[dict[str, Any], "ExecutionContext"], dict[str, Any]]
HookCallback = Callable[
    [str, dict[str, Any], "RunState"], Union[None, Awaitable[None]]
]
T = TypeVar("T")
ERROR_CODES = frozenset({"tool_not_found", "invalid_arguments", "policy_denied", "approval_denied",
    "approval_required", "approval_expired", "handler_error", "provider_timeout", "cancelled",
    "checkpoint_mismatch", "capability_unsupported", "budget_exceeded", "unknown_side_effect",
    "runtime_error", "interrupted"})


async def await_if_needed(value: Union[T, Awaitable[T]]) -> T:
    return await value if inspect.isawaitable(value) else value


# ── Lifecycle hooks ─────────────────────────────────────────────────────────

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
    implementation_version: str = "1"


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
            frozen.register(replace(tool, parameters=deepcopy(tool.parameters)))
        for alias, target in self._aliases.items():
            frozen.register_alias(alias, target)
        return frozen

    def aliases(self) -> dict[str, str]:
        return dict(sorted(self._aliases.items()))


class ToolRouter:
    def __init__(self, registry: ToolRegistry, execution_scope: str = "") -> None:
        self.registry = registry
        self.execution_scope = execution_scope
        self.active_executions: set[asyncio.Task] = set()

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
        from schema_validation import validate
        validate(schema, arguments)


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
            "search_catalog", "catalog-server.search_catalog", "inspect_candidate", "summarize_matches",
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
        atomic_write_text(self.path, json.dumps(data, ensure_ascii=False, indent=2))

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
            "search_catalog", "catalog-server.search_catalog", "inspect_candidate", "summarize_matches",
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
            async def execute_and_record(step: PlanStep) -> None:
                result = await self._execute_step(step, state, checkpoint)
                state.results[step.id] = result
                state.executions.pop(str(step.id), None)
                state.step_count += 1
                entry = MemoryEntry("tool", json.dumps(
                    {"step_id": step.id, "tool": step.tool, "result": result},
                    ensure_ascii=False,
                ))
                state.memory.append(entry)
                # 保存结果先于外部 Memory I/O，避免兄弟步骤取消丢失已完成结果。
                await await_if_needed(checkpoint())
                await await_if_needed(self.memory.append(state.run_id, entry))

            tasks = [asyncio.create_task(execute_and_record(step)) for step in batch]
            try:
                await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise

        failure = next(
            (result for result in state.results.values() if not result.get("success", False)),
            None,
        )
        if failure:
            state.status = "reconciliation_required" if any(
                result.get("outcome_unknown") for result in state.results.values()
            ) else "failed"
            state.error = ("execution_outcome_unknown" if state.status == "reconciliation_required"
                           else str(failure.get("error", "Tool 执行失败")))
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
            arguments = deepcopy(step.arguments)
            tool = self.router.resolve(step.tool)
            self.router._validate_arguments(tool.parameters, arguments)
            decision = self.policy.evaluate(PolicyRequest(
                subject="agent", capability=tool.name, arguments=deepcopy(arguments),
                resource=tool.name, invoked_as=step.tool, run_id=state.run_id,
                source=f"{tool.source.value}:{tool.source_name}",
                risk="high" if tool.requires_approval else "normal",
            ))
            state.trace.append({
                "event": "policy_decision", "tool": step.tool,
                "decision": decision.value, "policy_version": self.policy.version,
            })
            if decision is PolicyDecision.DENY:
                return {"success": False, "error": f"Policy 拒绝 Tool: {step.tool}", "error_code": "policy_denied"}
            if decision is PolicyDecision.ASK:
                dependency_results = {
                    str(dependency): state.results[dependency]
                    for dependency in step.depends_on
                }
                preview = {
                    "task": state.task, "tool": tool.name,
                    "arguments": deepcopy(arguments),
                    "dependency_results": dependency_results,
                }
                if tool.prepare is not None:
                    preview.update(tool.prepare(deepcopy(arguments), context))
                intent_hash = with_snapshot_hash({"arguments": arguments, "preview": preview})["snapshot_hash"]
                approval_id = f"{state.run_id}:{step.id}:{tool.name}:{self.snapshot_hash}:{intent_hash}"
                if approval_id not in state.approvals:
                    request = ApprovalRequest(
                        approval_id, state.run_id, tool.name, deepcopy(arguments),
                        "Policy 请求审批", deepcopy(preview), "high", approval_id,
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
                    result = {"success": False, "error": f"审批拒绝执行: {step.tool}", "error_code": "approval_denied"}
                    await self.hooks.emit(
                        "on_approval_rejected", {**payload, "result": result}, state
                    )
                    return result
        except Exception as exc:
            result = {"success": False, "error": f"Tool 调用管线失败: {exc}",
                      "error_code": "invalid_arguments" if isinstance(exc, (ValueError, TypeError))
                      else "tool_not_found" if isinstance(exc, LookupError) else "runtime_error"}
            await self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
            await self.hooks.emit("after_tool", {**payload, "result": result}, state)
            return result

        state.executions[str(step.id)] = "started"
        await await_if_needed(checkpoint())
        last_error = "Tool 执行失败"
        attempt = 0
        for attempt in range(1, self.config.max_retries + 2):
            state.attempt_count += 1
            try:
                execution = asyncio.create_task(
                    self.router.execute(step.tool, deepcopy(arguments), context)
                )
                self.router.active_executions.add(execution)
                track_execution(self.router.execution_scope, state.run_id, execution)
                def finished(task: asyncio.Task) -> None:
                    self.router.active_executions.discard(task)
                    if not task.cancelled():
                        task.exception()
                execution.add_done_callback(finished)
                result = await asyncio.wait_for(
                    asyncio.shield(execution),
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
                # 超时不等于停止；后台任务保留到完成，但不允许自动重放。
                result = {"success": False, "error": "execution_outcome_unknown",
                          "outcome_unknown": True, "retryable": False, "attempts": attempt}
                await self.hooks.emit("on_tool_error", {**payload, "result": result}, state)
                await self.hooks.emit("after_tool", {**payload, "result": result}, state)
                return result
            except asyncio.CancelledError:
                raise
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
        self.lock_scope = store_scope(self.checkpoints)
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
        async with keyed_lock(self.lock_scope, run_id):
            return await self._run_guarded(task, run_id, conversation_context)

    async def reconcile(
        self, run_id: str, step_id: int,
        verify: Callable[[RunState, PlanStep], Union[dict[str, Any], Awaitable[dict[str, Any]]]],
    ) -> RunState:
        """可信 Adapter 核对下游回执；不是面向模型的 Tool，也不派发业务操作。"""
        async with keyed_lock(self.lock_scope, run_id):
            if has_active_execution(self.lock_scope, run_id):
                raise RuntimeError("execution_still_active")
            state = await await_if_needed(self.checkpoints.load(run_id))
            if state is None:
                raise LookupError("Run 不存在")
            if str(step_id) not in state.executions and not state.results.get(step_id, {}).get("outcome_unknown"):
                raise ValueError("step_not_unknown")
            step = next(item for item in state.plan if item.id == step_id)
            receipt = await await_if_needed(verify(deepcopy(state), deepcopy(step)))
            evidence, result = receipt.get("evidence"), receipt.get("result")
            if (not isinstance(evidence, str) or not evidence.strip()
                or not isinstance(result, dict) or not isinstance(result.get("success"), bool)
                or result.get("outcome_unknown") or result.get("retryable")):
                raise ValueError("invalid_reconciliation_receipt")
            # 对账只补录确定结果，不把步骤重置为可重试。
            if step_id not in state.results:
                state.step_count += 1
            state.results[step_id] = {**deepcopy(result), "retryable": False}
            state.executions.pop(str(step_id), None)
            state.trace.append({"event": "execution_reconciled", "step": step_id, "evidence": evidence})
            state.status, state.error = "interrupted", None
            await await_if_needed(self.checkpoints.save(state))
            return state

    async def _run_guarded(
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
            if state.status == "completed" and state.final_answer is not None:
                state.trace.append({"event": "delivery_error", "error": str(exc)})
                return self._result(state, state.final_answer, False, started)
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

    @staticmethod
    def _implementation_digest(handler: Any) -> str:
        def code_identity(code: CodeType) -> tuple:
            # 使用稳定字节码/常量标识，不依赖运行时对象地址与集合排列。
            def constant(item: Any) -> Any:
                if isinstance(item, CodeType):
                    return code_identity(item)
                if isinstance(item, tuple):
                    return tuple(constant(value) for value in item)
                if isinstance(item, frozenset):
                    return ("frozenset", tuple(sorted(repr(constant(value)) for value in item)))
                return repr(item)
            return (code.co_code.hex(), code.co_names, code.co_varnames,
                    code.co_freevars, code.co_cellvars, code.co_argcount,
                    code.co_kwonlyargcount, code.co_flags,
                    tuple(constant(item) for item in code.co_consts))
        code = getattr(handler, "__code__", None)
        return sha256_text(repr(code_identity(code)) if code else type(handler).__qualname__)

    def _capability_snapshot(self) -> dict[str, Any]:
        payload = {
            "tools": [{
                "name": tool.name, "schema": tool.parameters,
                "source": tool.source.value, "source_name": tool.source_name,
                "implementation_version": tool.implementation_version,
                "handler_digest": self._implementation_digest(tool.handler),
                "prepare_digest": self._implementation_digest(tool.prepare),
                "requires_approval": tool.requires_approval, "state": tool.state.value,
            } for tool in self.tools.list()],
            "tool_aliases": self.tools.aliases(),
            "skills": [{
                "name": skill.name, "owner": skill.owner,
                "checksum": sha256_text(skill.instructions),
            } for skill in sorted(self.skills._skills.values(), key=lambda item: item.name)],
            "policy_version": self.policy.version,
            "policy": self.policy.snapshot() if isinstance(self.policy, DefaultPolicyEngine) else {},
            "config": {"allowed_tools": sorted(self.config.allowed_tools)},
        }
        return with_snapshot_hash(deepcopy(payload))

    async def _run(
        self, task: str, run_id: str, started: float, conversation_context: list[str]
    ) -> dict[str, Any]:
        await self._initialize_extensions()
        current_snapshot = self._capability_snapshot()
        run_router = ToolRouter(self.tools.snapshot(), self.lock_scope)
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
            restored and (restored.capability_snapshot or {}).get("snapshot_hash")
            != current_snapshot["snapshot_hash"]
        ):
            mismatch = RunState(run_id, task, [])
            mismatch.status = "failed"
            mismatch.error = "capability_snapshot_mismatch"
            mismatch.capability_snapshot = current_snapshot
            return self._result(mismatch, mismatch.error, False, started)

        if restored and (restored.executions or any(
            result.get("outcome_unknown") for result in restored.results.values()
        )):
            restored.status, restored.error = "reconciliation_required", "execution_outcome_unknown"
            return self._result(restored, "执行结果未知，核对副作用后再创建新 Run", True, started)

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
                if state.final_answer is None:
                    state.final_answer = await self.llm.final_answer(task, state.results)
                    await await_if_needed(self.checkpoints.save(state))
                return self._result(state, state.final_answer, False, started, replayed=True)
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
        checkpoint_lock = asyncio.Lock()
        async def checkpoint() -> None:
            async with checkpoint_lock:
                await await_if_needed(self.checkpoints.save(deepcopy(state)))
        await executor.run(state, checkpoint)
        if state.status == "completed":
            state.status = "finalizing"
            await checkpoint()
            final = await self.llm.final_answer(task, state.results)
            state.final_answer, state.status = final, "completed"
            await checkpoint()  # 先持久化可回放交付物，再执行观测/消息副作用。
        else:
            final = state.error or "任务未完成"

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
        success = state.status == "completed"
        normalized_code = None
        if not success:
            normalized_code = (
                "checkpoint_mismatch"
                if state.error in {"run_task_mismatch", "capability_snapshot_mismatch"}
                else "unknown_side_effect" if state.error == "execution_outcome_unknown"
                else next((str(result["error_code"]) for result in state.results.values()
                           if not result.get("success") and result.get("error_code") in ERROR_CODES), "runtime_error" if (state.error or "").startswith("runtime_error:")
                          else "budget_exceeded" if state.status == "max_steps"
                          else "interrupted" if state.status == "interrupted" else "handler_error")
            )
        return {
            "success": success,
            "status": state.status,
            "run_id": state.run_id,
            "resumed": resumed,
            "replayed": replayed,
            "steps": state.step_count,
            "attempts": state.attempt_count,
            "results": state.results,
            "final": final,
            "error_code": normalized_code,
            "error_message": None if success else final,
            "retryable": False,
            "details": {} if success else {"reason": state.error or normalized_code},
            # 兼容早期教学调用方；跨边界代码应读取 error_code/details。
            "error": state.error,
            "trace": state.trace,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
