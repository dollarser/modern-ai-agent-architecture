import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from main import (
    AgentConfig,
    AgentHost,
    AutoApproveGate,
    ConfigScope,
    DefaultPolicyEngine,
    DeterministicLLMAdapter,
    DatabaseReviewAgent,
    EventBus,
    ExecutionContext,
    FakeMCPClient,
    HookKind,
    HookDefinition,
    HookPipeline,
    InMemoryMemoryBackend,
    MCPToolAdapter,
    MCPToolDefinition,
    Plugin,
    PluginManifest,
    PolicyDecision,
    PolicyLayer,
    PolicyRequest,
    RunState,
    ScriptedApprovalGate,
    Skill,
    Tool,
    ToolSource,
    ToolState,
)
from coding_scenario import CodingAgent, Workspace
from application import ConversationApplication, JsonSessionStore
from installed_adapters import CatalogPluginProvider, CatalogSkillProvider, ManagerMCPProvider


class DatabaseReviewAgentTest(unittest.TestCase):
    def run_agent(self, agent: DatabaseReviewAgent, task: str, run_id: str) -> dict:
        return asyncio.run(agent.run(task, run_id))

    def test_final_assembly_runs_every_extension_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            llm = DeterministicLLMAdapter()
            memory = InMemoryMemoryBackend()
            mcp = FakeMCPClient()
            approval = ScriptedApprovalGate({"propose_change": True})
            events = EventBus()
            agent = DatabaseReviewAgent(
                Path(directory) / "cp.json",
                llm=llm,
                memory=memory,
                mcp_client=mcp,
                approval=approval,
                event_bus=events,
            )
            result = asyncio.run(agent.run(
                "查找数据库配置并给出变更建议", "complete",
                ["user: 上一轮已经确认只读检查"],
            ))

            self.assertTrue(result["success"])
            self.assertEqual(result["steps"], 6)
            self.assertEqual(result["attempts"], 6)
            self.assertIn("src/config.ts", result["final"])
            self.assertEqual(mcp.calls, ["search_catalog"])
            self.assertEqual(agent.tools.get("search_catalog").source, ToolSource.MCP)
            self.assertEqual(agent.tools.get("propose_change").source, ToolSource.PLUGIN)
            self.assertEqual(len(approval.requests), 1)
            self.assertTrue(any("子 Agent" in str(item) for item in result["results"].values()))
            self.assertIn("handoff.created", [event["topic"] for event in events.events])
            self.assertTrue(any("先检索候选路径" in item for item in llm.last_context))
            self.assertTrue(any("必须给出文件路径" in item for item in llm.last_context))
            self.assertIn("user: 上一轮已经确认只读检查", llm.last_context)
            self.assertTrue(any(entry.role == "tool" for entry in memory.recent("complete")))
            replay = self.run_agent(agent, "查找数据库配置并给出变更建议", "complete")
            self.assertTrue(replay["success"])
            self.assertFalse(replay["resumed"])
            self.assertTrue(replay["replayed"])

    def test_generic_host_has_no_demo_capabilities_and_mcp_uses_canonical_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            host = AgentHost(Path(directory) / "host.json")
            self.assertFalse(host.skills.contains("config-review"))
            self.assertFalse(host.tools.contains("inspect_candidate"))
            self.assertIsNone(host.initial_memory)

            asyncio.run(host.mcp.register_tools(host.tools))
            canonical = host.tools.get("search_catalog")
            self.assertEqual(canonical.name, "catalog-server.search_catalog")
            self.assertEqual(
                host.tools.aliases()["search_catalog"],
                "catalog-server.search_catalog",
            )
            second = MCPToolAdapter(FakeMCPClient(), "other-server")
            asyncio.run(second.register_tools(host.tools))
            self.assertTrue(host.tools.contains("other-server.search_catalog"))
            self.assertEqual(
                host.tools.get("search_catalog").name,
                "catalog-server.search_catalog",
            )

    def test_checkpoint_restores_approval_without_repeating_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "cp.json"
            gate = ScriptedApprovalGate({"propose_change": True})
            task = "查找数据库配置并给出变更建议"
            first = self.run_agent(
                DatabaseReviewAgent(
                    checkpoint,
                    AgentConfig(interrupt_after_steps=4),
                    approval=gate,
                ),
                task,
                "resume",
            )
            second = self.run_agent(
                DatabaseReviewAgent(checkpoint, approval=gate), task, "resume"
            )

            self.assertEqual(first["status"], "interrupted")
            self.assertTrue(second["success"])
            self.assertTrue(second["resumed"])
            self.assertEqual(second["steps"], 6)
            self.assertEqual(len(gate.requests), 1)

    def test_rejected_approval_never_calls_handler(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = 0
            gate = ScriptedApprovalGate({"propose_change": False})
            agent = DatabaseReviewAgent(Path(directory) / "cp.json", approval=gate)

            def forbidden(_args, _context):
                nonlocal calls
                calls += 1
                return {"success": True, "proposal": "不应出现"}

            agent.tools.register(
                Tool(
                    "propose_change",
                    "高风险变更",
                    forbidden,
                    source=ToolSource.PLUGIN,
                    source_name="review-pack",
                    requires_approval=True,
                ),
                replace=True,
            )
            result = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "reject"
            )

            self.assertFalse(result["success"])
            self.assertEqual(calls, 0)
            self.assertIn("审批拒绝", result["error"])
            events = [item["event"] for item in result["trace"]]
            self.assertIn("before_approval", events)
            self.assertIn("after_approval", events)
            self.assertIn("on_tool_error", events)

    def test_observer_failure_isolated_but_guard_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hooks = HookPipeline()
            hooks.register(
                "after_plan",
                lambda *_args: (_ for _ in ()).throw(RuntimeError("metrics down")),
                name="metrics",
            )
            agent = DatabaseReviewAgent(
                Path(directory) / "observer.json", hooks=hooks, approval=AutoApproveGate()
            )
            result = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "observer"
            )
            self.assertTrue(result["success"])
            self.assertIn("observer_error", [item["event"] for item in result["trace"]])

            guarded = HookPipeline()
            guarded.register(
                "before_tool",
                lambda *_args: (_ for _ in ()).throw(PermissionError("policy denied")),
                kind=HookKind.GUARD,
                priority=1,
                name="policy",
            )
            denied = self.run_agent(
                DatabaseReviewAgent(Path(directory) / "guard.json", hooks=guarded),
                "查找数据库配置并给出变更建议",
                "guard",
            )
            self.assertFalse(denied["success"])
            self.assertIn("Guardrail", denied["error"])
            self.assertEqual(denied["attempts"], 0)

    def test_router_filters_state_and_plugin_unload_removes_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = DatabaseReviewAgent(Path(directory) / "cp.json")
            agent.tools.register(
                Tool("disabled", "disabled", lambda *_: {"success": True}, state=ToolState.DISABLED)
            )
            self.assertNotIn("disabled", [tool.name for tool in agent.router.available()])
            with self.assertRaises(PermissionError):
                agent.router.resolve("disabled")

            hook_calls = 0

            def plugin_hook(*_args):
                nonlocal hook_calls
                hook_calls += 1

            agent.plugins.load(Plugin(
                PluginManifest("temporary", "1.0.0", ("skills:register", "hooks:register")),
                skills=[Skill("temporary-skill", ("临时",), "临时指令")],
                hooks=[("custom", HookDefinition(100, plugin_hook))],
            ))
            probe = RunState("probe", "临时任务", [])
            asyncio.run(agent.hooks.emit("custom", {}, probe))
            self.assertEqual(hook_calls, 1)
            self.assertEqual(len(agent.skills.match("临时任务")), 1)
            agent.plugins.unload("temporary")
            asyncio.run(agent.hooks.emit("custom", {}, probe))
            self.assertEqual(hook_calls, 1)
            self.assertEqual(agent.skills.match("临时任务"), [])

            agent.plugins.unload("review-pack")
            self.assertNotIn("propose_change", [tool.name for tool in agent.tools.list()])

    def test_plugin_preflight_is_atomic_and_enforces_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = DatabaseReviewAgent(Path(directory) / "cp.json")
            with self.assertRaises(PermissionError):
                agent.plugins.load(Plugin(
                    PluginManifest("underprivileged", "1.0.0"),
                    tools=[Tool("extra", "extra", lambda *_: {"success": True})],
                ))
            self.assertFalse(agent.tools.contains("extra"))

            with self.assertRaises(ValueError):
                agent.plugins.load(Plugin(
                    PluginManifest("conflicting", "1.0.0", ("tools:register",)),
                    tools=[
                        Tool("new-before-conflict", "new", lambda *_: {"success": True}),
                        Tool("inspect_candidate", "conflict", lambda *_: {"success": True}),
                    ],
                ))
            self.assertFalse(agent.tools.contains("new-before-conflict"))

    def test_schema_event_isolation_namespace_and_trace_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = DatabaseReviewAgent(
                Path(directory) / "cp.json", approval=AutoApproveGate()
            )
            agent.tools.register(Tool(
                "validated", "validated", lambda args, _ctx: {
                    "success": True, "value": args["value"],
                }, parameters={
                    "type": "object",
                    "required": ["value"],
                    "properties": {"value": {"type": "string"}},
                    "additionalProperties": False,
                },
            ))
            context = ExecutionContext("task", {}, "run", "trace-run", "step-1")
            with self.assertRaises(ValueError):
                asyncio.run(agent.router.execute("validated", {}, context))
            with self.assertRaises(TypeError):
                asyncio.run(agent.router.execute("validated", {"value": 1}, context))

            asyncio.run(agent.mcp.register_tools(agent.tools))
            asyncio.run(MCPToolAdapter(
                FakeMCPClient(), "other-server"
            ).register_tools(agent.tools))
            self.assertTrue(agent.tools.contains("other-server.search_catalog"))

            events = EventBus()
            events.subscribe(
                "topic", lambda _event: (_ for _ in ()).throw(RuntimeError("down")),
                name="metrics",
            )
            asyncio.run(events.publish("topic", {}))
            self.assertEqual(events.events[-1]["topic"], "observer.error")

            result = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "trace-context"
            )
            self.assertEqual(result["results"][5]["parent_trace_id"], "trace-trace-context")
            self.assertEqual(result["results"][5]["parent_span_id"], "step-5")

    def test_async_ports_are_directly_injectable(self) -> None:
        class AsyncMCP:
            async def list_tools(self):
                await asyncio.sleep(0)
                return [MCPToolDefinition("search_catalog", "async search")]

            async def call_tool(self, _name, arguments):
                await asyncio.sleep(0)
                return {
                    "success": True, "query": arguments.get("query"),
                    "matches": ["src/config.ts", "src/db.ts"],
                }

        class AsyncApproval:
            async def decide(self, _request):
                await asyncio.sleep(0)
                return True

        class AsyncRunner:
            async def run_task(self, request):
                await asyncio.sleep(0)
                return {
                    "success": True, "review": "异步子 Agent 已审查",
                    "parent_trace_id": request.parent_trace_id,
                    "parent_span_id": request.parent_span_id,
                }

        class AsyncMemory:
            def __init__(self):
                self.inner = InMemoryMemoryBackend()

            async def append(self, run_id, entry):
                self.inner.append(run_id, entry)

            async def recent(self, run_id, limit=12):
                return self.inner.recent(run_id, limit)

            async def remember(self, namespace, entry):
                self.inner.remember(namespace, entry)

            async def search(self, namespace, query, limit=5):
                return self.inner.search(namespace, query, limit)

        class AsyncCheckpoint:
            def __init__(self):
                self.states = {}

            async def save(self, state):
                self.states[state.run_id] = RunState.from_dict(state.to_dict())

            async def load(self, run_id):
                return self.states.get(run_id)

        with tempfile.TemporaryDirectory() as directory:
            hooks = HookPipeline()
            observed = []
            event_bus = EventBus()
            event_topics = []

            async def async_hook(event, _payload, _state):
                await asyncio.sleep(0)
                observed.append(event)

            hooks.register("before_run", async_hook)
            async def async_subscriber(event):
                await asyncio.sleep(0)
                event_topics.append(event["topic"])

            event_bus.subscribe("task.started", async_subscriber)
            result = self.run_agent(DatabaseReviewAgent(
                Path(directory) / "cp.json", hooks=hooks,
                approval=AsyncApproval(), mcp_client=AsyncMCP(), subagent=AsyncRunner(),
                memory=AsyncMemory(), event_bus=event_bus,
                checkpoint_store=AsyncCheckpoint(),
            ), "查找数据库配置并给出变更建议", "async-ports")
            self.assertTrue(result["success"])
            self.assertEqual(observed, ["before_run"])
            self.assertEqual(event_topics, ["task.started"])
            self.assertIn("异步子 Agent", result["results"][5]["review"])

    def test_run_task_mismatch_is_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "cp.json"
            agent = DatabaseReviewAgent(checkpoint, approval=AutoApproveGate())
            self.assertTrue(self.run_agent(agent, "原任务", "same-run")["success"])

            mismatch = self.run_agent(agent, "另一任务", "same-run")

            self.assertFalse(mismatch["success"])
            self.assertEqual(mismatch["status"], "failed")
            self.assertEqual(mismatch["error"], "run_task_mismatch")

    def test_top_level_failure_returns_failed_and_emits_on_error(self) -> None:
        class BrokenLLM(DeterministicLLMAdapter):
            async def create_plan(self, *_args):
                raise RuntimeError("planner unavailable")

        with tempfile.TemporaryDirectory() as directory:
            result = self.run_agent(
                DatabaseReviewAgent(Path(directory) / "cp.json", llm=BrokenLLM()),
                "任意任务",
                "runtime-error",
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "failed")
            self.assertIn("runtime_error", result["error"])
            self.assertIn("on_error", [item["event"] for item in result["trace"]])

    def test_default_approval_denies_and_request_contains_resolved_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            default_result = self.run_agent(
                DatabaseReviewAgent(Path(directory) / "deny.json"),
                "查找数据库配置并给出变更建议",
                "deny-by-default",
            )
            self.assertFalse(default_result["success"])
            self.assertIn("审批拒绝", default_result["error"])

            gate = ScriptedApprovalGate({"propose_change": True})
            approved = self.run_agent(
                DatabaseReviewAgent(Path(directory) / "approve.json", approval=gate),
                "查找数据库配置并给出变更建议",
                "preview",
            )
            self.assertTrue(approved["success"])
            request = gate.requests[0]
            self.assertEqual(request.risk, "high")
            self.assertEqual(request.idempotency_key, request.id)
            self.assertEqual(request.preview["dependency_results"]["2"]["path"], "src/config.ts")
            self.assertIn("src/config.ts", request.preview["resolved_intent"])

    def test_retry_count_and_terminal_failure_remain_honest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = 0

            def flaky(_args, _context):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return {"success": False, "error": "temporary", "retryable": True}
                return {"success": True, "matches": ["src/config.ts", "src/db.ts"]}

            agent = DatabaseReviewAgent(
                Path(directory) / "retry.json", approval=AutoApproveGate()
            )
            agent.tools.register(Tool("search_catalog", "flaky", flaky), replace=True)
            recovered = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "retry"
            )
            self.assertTrue(recovered["success"])
            self.assertEqual(recovered["attempts"], 7)
            self.assertEqual(recovered["results"][1]["attempts"], 2)

            failed = DatabaseReviewAgent(Path(directory) / "failed.json")
            failed.tools.register(
                Tool("search_catalog", "denied", lambda *_: {"success": False, "error": "denied"}),
                replace=True,
            )
            result = self.run_agent(
                failed, "查找数据库配置并给出变更建议", "failed"
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "denied")

    def test_installed_skills_and_managed_mcp_are_composed_at_startup(self) -> None:
        class Installed:
            def load_skills(self):
                return [Skill("installed-review", ("数据库",), "来自安装目录的审查规则", "installed")]

        class Client:
            def list_tools(self):
                return [MCPToolDefinition("managed_lookup", "managed")]
            def call_tool(self, name, arguments):
                return {"success": True, "name": name, **arguments}

        class Servers:
            closed = False
            def connect_enabled(self):
                return [("managed", Client())]
            def close(self):
                self.closed = True

        class InstalledPlugins:
            def load_plugins(self):
                return [Plugin(
                    PluginManifest("installed-pack", "1.0.0", ("tools:register",)),
                    tools=[Tool("installed_tool", "installed", lambda *_: {"success": True})],
                )]

        with tempfile.TemporaryDirectory() as directory:
            servers = Servers()
            agent = DatabaseReviewAgent(
                Path(directory) / "managed.json", approval=AutoApproveGate(),
                installed_skills=Installed(), mcp_servers=servers,
                installed_plugins=InstalledPlugins(),
            )
            result = self.run_agent(agent, "查找数据库配置并给出变更建议", "managed")
            self.assertTrue(result["success"])
            self.assertTrue(agent.skills.contains("installed-review"))
            self.assertTrue(agent.tools.contains("managed_lookup"))
            self.assertTrue(agent.tools.contains("installed_tool"))
            asyncio.run(agent.close_extensions())
            self.assertTrue(servers.closed)
            self.assertFalse(agent.tools.contains("managed_lookup"))
            self.assertFalse(agent.tools.contains("installed_tool"))

    def test_extension_initialization_rolls_back_and_can_retry(self) -> None:
        class Installed:
            def load_skills(self):
                return [Skill("transactional", ("数据库",), "transactional", "installed")]

        class Plugins:
            calls = 0
            def load_plugins(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("plugin catalog unavailable")
                return []

        with tempfile.TemporaryDirectory() as directory:
            agent = DatabaseReviewAgent(
                Path(directory) / "rollback.json", approval=AutoApproveGate(),
                installed_skills=Installed(), installed_plugins=Plugins(),
            )
            failed = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "rollback-first"
            )
            self.assertFalse(failed["success"])
            self.assertFalse(agent.skills.contains("transactional"))
            self.assertFalse(agent.tools.contains("search_catalog"))

            retried = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "rollback-second"
            )
            self.assertTrue(retried["success"])
            self.assertTrue(agent.skills.contains("transactional"))

    def test_capability_snapshot_rejects_incompatible_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "snapshot.json"
            task = "查找数据库配置并给出变更建议"
            first = self.run_agent(DatabaseReviewAgent(
                checkpoint, AgentConfig(interrupt_after_steps=2),
                approval=AutoApproveGate(),
            ), task, "snapshot")
            self.assertEqual(first["status"], "interrupted")

            changed = DatabaseReviewAgent(checkpoint, approval=AutoApproveGate())
            changed.tools.register(Tool(
                "new_capability", "new", lambda *_: {"success": True}
            ))
            resumed = self.run_agent(changed, task, "snapshot")
            self.assertFalse(resumed["success"])
            self.assertEqual(resumed["error"], "capability_snapshot_mismatch")

    def test_policy_scope_deny_wins_and_run_uses_frozen_tools(self) -> None:
        policy = DefaultPolicyEngine(
            frozenset({"read", "write"}),
            [
                PolicyLayer(ConfigScope.PROJECT, allow=frozenset({"write"})),
                PolicyLayer(ConfigScope.MANAGED, deny=frozenset({"write"})),
            ],
        )
        request = PolicyRequest(
            "agent", "write", {}, "write", "run", "builtin:core", "normal"
        )
        self.assertEqual(policy.evaluate(request), PolicyDecision.DENY)

        with tempfile.TemporaryDirectory() as directory:
            replacement_calls = 0
            agent = DatabaseReviewAgent(
                Path(directory) / "frozen.json", approval=AutoApproveGate()
            )

            def replacement(_args, _context):
                nonlocal replacement_calls
                replacement_calls += 1
                return {"success": True, "matches": []}

            def mutate_live_registry(_event, payload, _state):
                if payload["tool"] == "search_catalog":
                    agent.tools.register(Tool(
                        "search_catalog", "replacement", replacement,
                    ), replace=True)

            agent.hooks.register(
                "before_tool", mutate_live_registry,
                kind=HookKind.GUARD, priority=1, name="hot-reload",
            )
            result = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "frozen"
            )
            self.assertTrue(result["success"])
            self.assertEqual(replacement_calls, 0)


class CodingAgentTest(unittest.TestCase):
    @staticmethod
    def make_project(root: Path) -> None:
        (root / "calculator.py").write_text(
            "def add(a, b):\n    return a - b\n", encoding="utf-8"
        )
        (root / "test_calculator.py").write_text(
            "import unittest\nfrom calculator import add\n\n"
            "class CalculatorTest(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(-2, 5), 3)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n",
            encoding="utf-8",
        )

    def test_coding_slice_patches_workspace_and_runs_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_project(root)
            agent = CodingAgent(
                root / ".checkpoints.json", root,
                approval=ScriptedApprovalGate({"apply_patch": True, "run_check": True}),
            )
            result = asyncio.run(agent.run("修复 add 并运行测试", "coding-success"))
            self.assertTrue(result["success"])
            self.assertIn("return a + b", (root / "calculator.py").read_text("utf-8"))
            self.assertEqual(result["results"][5]["exit_code"], 0)

    def test_coding_slice_denied_write_has_no_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_project(root)
            original = (root / "calculator.py").read_text("utf-8")
            agent = CodingAgent(root / ".checkpoints.json", root)
            result = asyncio.run(agent.run("修复 add", "coding-denied"))
            self.assertFalse(result["success"])
            self.assertEqual((root / "calculator.py").read_text("utf-8"), original)

    def test_workspace_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            workspace = Workspace(directory)
            with self.assertRaises(PermissionError):
                workspace.resolve("../outside.txt")
            target = Path(outside) / "secret.txt"
            target.write_text("secret", encoding="utf-8")
            os.symlink(target, Path(directory) / "link.txt")
            with self.assertRaises(PermissionError):
                workspace.resolve("link.txt")


class ConversationApplicationTest(unittest.TestCase):
    def test_session_aggregates_multiple_task_run_pairs_and_context(self) -> None:
        class Runner:
            def __init__(self, calls: list[dict]) -> None:
                self.calls = calls

            async def run(self, task, run_id, conversation_context=None):
                self.calls.append({
                    "task": task, "run_id": run_id,
                    "context": list(conversation_context or []),
                })
                return {
                    "success": True, "status": "completed", "run_id": run_id,
                    "final": f"完成：{task}", "error": None,
                }

        with tempfile.TemporaryDirectory() as directory:
            calls: list[dict] = []
            ids = iter(["t1", "r1", "t2", "r2"])
            app = ConversationApplication(
                JsonSessionStore(Path(directory) / "sessions.json"),
                lambda _session_id, _task_id, _run_id: Runner(calls),
                id_factory=lambda: next(ids),
            )
            async def converse():
                first_result = await app.send("conversation-1", "先检查项目")
                second_result = await app.send("conversation-1", "继续修复问题")
                return first_result, second_result

            first, second = asyncio.run(converse())
            session = app.get_session("conversation-1")

            self.assertEqual(first["task_id"], "task-t1")
            self.assertEqual(first["run_id"], "run-r1")
            self.assertEqual(second["task_id"], "task-t2")
            self.assertEqual(second["run_id"], "run-r2")
            self.assertEqual(len(session.tasks), 2)
            self.assertEqual(len(session.messages), 4)
            self.assertEqual(calls[0]["context"], [])
            self.assertEqual(
                calls[1]["context"],
                ["user: 先检查项目", "assistant: 完成：先检查项目"],
            )
            self.assertNotEqual(session.session_id, first["run_id"])


class InstalledAdapterTest(unittest.TestCase):
    def test_catalogs_and_manager_feed_agent_host_ports(self) -> None:
        skill_record = SimpleNamespace(
            manifest=SimpleNamespace(name="installed-review", keywords=("数据库",)),
            instructions="先读取再审查",
        )
        skill_catalog = SimpleNamespace(list=lambda: [skill_record])

        class Connection:
            closed = False
            def list_tools(self):
                return [{"name": "lookup", "description": "lookup"}]
            def call_tool(self, name, arguments):
                return {"success": name == "lookup", "query": arguments.get("query")}

        connection = Connection()
        manager = SimpleNamespace(
            connect_enabled=lambda: [("managed", connection)],
            close=lambda: setattr(connection, "closed", True),
        )

        base = SimpleNamespace(
            manifest=SimpleNamespace(
                name="base", version="1.0.0", entrypoint="base-factory", dependencies=(),
            )
        )
        addon = SimpleNamespace(
            manifest=SimpleNamespace(
                name="addon", version="1.0.0", entrypoint="addon-factory", dependencies=("base",),
            )
        )
        plugin_catalog = SimpleNamespace(list=lambda enabled_only=False: [addon, base])
        factories = {
            "base-factory": lambda record: Plugin(PluginManifest(record.manifest.name, record.manifest.version, ())),
            "addon-factory": lambda record: Plugin(PluginManifest(record.manifest.name, record.manifest.version, ())),
        }
        plugin_provider = CatalogPluginProvider(plugin_catalog, factories)
        self.assertEqual(
            [plugin.manifest.name for plugin in plugin_provider.load_plugins()],
            ["base", "addon"],
        )

        with tempfile.TemporaryDirectory() as directory:
            agent = DatabaseReviewAgent(
                Path(directory) / "adapters.json",
                approval=AutoApproveGate(),
                installed_skills=CatalogSkillProvider(skill_catalog),
                mcp_servers=ManagerMCPProvider(manager),
                installed_plugins=plugin_provider,
            )
            result = asyncio.run(agent.run("查找数据库配置并给出变更建议", "adapters"))
            self.assertTrue(result["success"])
            self.assertTrue(agent.skills.contains("installed-review"))
            self.assertTrue(agent.tools.contains("managed.lookup"))
            asyncio.run(agent.close_extensions())
            self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
