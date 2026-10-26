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
    PlanStep,
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

    # docs:start checkpoint-resume-contract
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
    # docs:end checkpoint-resume-contract

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
            self.assertIn("on_approval_rejected", events)
            self.assertNotIn("on_tool_error", events)

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
            self.assertIn("Tool 调用管线失败", denied["error"])
            self.assertEqual(denied["attempts"], 0)
            denied_events = [item["event"] for item in denied["trace"]]
            self.assertIn("on_tool_error", denied_events)
            self.assertIn("after_tool", denied_events)

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


class SecurityPlan:
    def __init__(self, steps):
        self.steps = steps

    async def create_plan(self, *_):
        return self.steps

    async def final_answer(self, *_):
        return "done"


class AgentHostSecurityTest(unittest.TestCase):
    def host(self, checkpoint, tools, steps=None, **kwargs):
        config = kwargs.pop("config", AgentConfig(allowed_tools=frozenset(tool.name for tool in tools)))
        agent = AgentHost(checkpoint, config, llm=SecurityPlan(steps or [
            PlanStep(1, "probe", tools[0].name)
        ]), **kwargs)
        for tool in tools:
            agent.tools.register(tool)
        return agent

    def test_temporary_symlink_cannot_overwrite_outside_file(self):
        from assembly import PlanStep
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            target = workspace / "calculator.py"
            target.write_text("old")
            target.chmod(0o640)
            outside = root / "outside"
            outside.write_text("protected")
            (workspace / "calculator.py.tmp").symlink_to(outside)
            agent = CodingAgent(root / "cp.json", workspace, approval=AutoApproveGate(),
                llm=SecurityPlan([PlanStep(1, "patch", "apply_patch", {
                    "path": "calculator.py", "old": "old", "new": "new",
                })]))
            result = asyncio.run(agent.run("task", "patch"))
            self.assertTrue(result["success"])
            self.assertEqual(outside.read_text(), "protected")
            self.assertEqual(target.read_text(), "new")
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            self.assertFalse(list(workspace.glob(".agent-write-*")))

    def test_alias_cannot_bypass_canonical_deny_or_grant(self):
        from assembly import PlanStep
        with tempfile.TemporaryDirectory() as directory:
            for denied, allowed in (({"action"}, {"action", "alias"}), (set(), {"alias"}), ({"alias"}, {"action"})):
                with self.subTest(denied=denied, allowed=allowed):
                    calls = []
                    policy = DefaultPolicyEngine(frozenset(allowed), [PolicyLayer(ConfigScope.MANAGED, deny=frozenset(denied))])
                    host = self.host(Path(directory) / "cp.json", [Tool("action", "action", lambda *_: calls.append(1) or {"success": True})],
                        [PlanStep(1, "alias", "alias")], policy=policy)
                    host.tools.register_alias("alias", "action")
                    result = asyncio.run(host.run("task", str(denied) + str(allowed)))
                    self.assertFalse(result["success"])
                    self.assertEqual(calls, [])

    def test_schema_constraints_rejected_before_approval_and_handler(self):
        from assembly import PlanStep
        with tempfile.TemporaryDirectory() as directory:
            schema = {"type": "object", "properties": {"items": {"type": "array", "maxItems": 1,
                "items": {"type": "object", "required": ["n"], "properties": {
                    "n": {"type": "integer", "maximum": 10}}, "additionalProperties": False}}}}
            for index, arguments in enumerate(({"items": [{"n": 999}]}, {"items": [{"n": True}]},
                    {"items": [{}]}, {"items": [{"n": 1}, {"n": 2}]})):
                calls, gate = [], ScriptedApprovalGate({"action": True})
                host = self.host(Path(directory) / "cp.json", [Tool("action", "action", lambda *_: calls.append(1) or {"success": True},
                    parameters=schema, requires_approval=True)], [PlanStep(1, "invalid", "action", arguments)], approval=gate)
                self.assertFalse(asyncio.run(host.run("task", str(index)))["success"])
                self.assertEqual(calls, [])
                self.assertEqual(gate.requests, [])
            from schema_validation import validate
            for unsupported in ({"properties": {"absent": {"pattern": "x"}}}, {"maximum": "10"}):
                with self.assertRaises(ValueError):
                    validate(unsupported, {})
            validate(schema, {"items": [{"n": 10}]})

    def test_implementation_risk_policy_changes_and_missing_snapshot_block_resume(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cp.json"
            original = Tool("action", "action", lambda *_: {"success": True}, requires_approval=True)
            base = self.host(path, [original], config=AgentConfig(allowed_tools=frozenset({"action"}), interrupt_after_steps=0))
            self.assertEqual(asyncio.run(base.run("task", "r"))["status"], "interrupted")
            alternatives = [replace(original, handler=lambda *_: {"success": False}),
                replace(original, implementation_version="2"), replace(original, requires_approval=False)]
            for tool in alternatives:
                changed = self.host(path, [tool])
                self.assertEqual(asyncio.run(changed.run("task", "r"))["error"], "capability_snapshot_mismatch")
            changed = self.host(path, [original], policy=DefaultPolicyEngine(frozenset({"action"}),
                [PolicyLayer(ConfigScope.MANAGED, deny=frozenset({"action"}))]))
            self.assertEqual(asyncio.run(changed.run("task", "r"))["error"], "capability_snapshot_mismatch")
            state = base.checkpoints.load("r")
            state.capability_snapshot = None
            base.checkpoints.save(state)
            self.assertEqual(asyncio.run(self.host(path, [original]).run("task", "r"))["error"], "capability_snapshot_mismatch")

    def test_prepared_target_change_invalidates_saved_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, target = [], ["first"]
            tool = Tool("action", "action", lambda *_: calls.append(1) or {"success": True},
                prepare=lambda *_: {"target": target[0]}, requires_approval=True)
            gate = ScriptedApprovalGate({"action": False})
            host = self.host(Path(directory) / "cp.json", [tool], approval=gate)
            asyncio.run(host.run("task", "r"))
            state = host.checkpoints.load("r")
            old_id = next(iter(state.approvals))
            state.approvals[old_id] = True
            state.results.clear()
            state.step_count = 0
            host.checkpoints.save(state)
            target[0] = "second"
            result = asyncio.run(host.run("task", "r"))
            self.assertFalse(result["success"])
            self.assertEqual(len(gate.requests), 2)
            self.assertNotEqual(gate.requests[0].id, gate.requests[1].id)
            self.assertEqual(calls, [])

    def test_parallel_cancel_preserves_sibling_result_and_blocks_unknown_replay(self):
        from assembly import PlanStep
        async def scenario(path):
            calls = []
            async def write(*_):
                calls.append(1)
                return {"success": True}
            async def cancel(*_):
                await asyncio.sleep(.02)
                raise asyncio.CancelledError()
            host = self.host(path, [Tool("write", "write", write), Tool("cancel", "cancel", cancel)],
                [PlanStep(1, "write", "write"), PlanStep(2, "cancel", "cancel")])
            with self.assertRaises(asyncio.CancelledError):
                await host.run("task", "r")
            state = host.checkpoints.load("r")
            self.assertTrue(state.results[1]["success"])
            self.assertIn("2", state.executions)
            result = await host.run("task", "r")
            self.assertEqual(result["status"], "reconciliation_required")
            self.assertEqual(calls, [1])
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "cp.json"))

    def test_timeout_side_effect_is_unknown_and_never_automatically_replayed(self):
        import time
        async def scenario(path):
            calls = []
            def slow(*_):
                time.sleep(.06)
                calls.append(1)
                return {"success": True}
            host = self.host(path, [Tool("action", "slow", slow)],
                config=AgentConfig(allowed_tools=frozenset({"action"}), step_timeout=.01))
            result = await host.run("task", "r")
            self.assertEqual(result["status"], "reconciliation_required")
            self.assertTrue(result["results"][1]["outcome_unknown"])
            await asyncio.sleep(.1)
            resumed = await host.run("task", "r")
            self.assertEqual(resumed["status"], "reconciliation_required")
            self.assertEqual(calls, [1])
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "cp.json"))

    def test_run_registry_schema_snapshot_is_independent(self):
        from assembly import ToolRegistry
        schema = {"properties": {"n": {"type": "integer", "maximum": 10}}}
        registry = ToolRegistry()
        registry.register(Tool("action", "action", lambda *_: {"success": True}, parameters=schema))
        frozen = registry.snapshot()
        schema["properties"]["n"]["maximum"] = 999
        self.assertEqual(frozen.get("action").parameters["properties"]["n"]["maximum"], 10)

    def test_checkpoint_and_session_ignore_precreated_temporary_symlinks(self):
        from assembly import JsonCheckpointStore
        from application import Session
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.write_text("protected")
            for filename in ("checkpoint.json", "session.json"):
                (root / (filename + ".tmp")).symlink_to(outside)
            checkpoint = JsonCheckpointStore(root / "checkpoint.json")
            checkpoint.save(RunState("r", "task", []))
            self.assertEqual(checkpoint.load("r").task, "task")
            session_store = JsonSessionStore(root / "session.json")
            session_store.save(Session("s"))
            self.assertEqual(session_store.load("s").session_id, "s")
            self.assertEqual(outside.read_text(), "protected")
            self.assertFalse(list(root.glob(".agent-write-*")))

    def test_parallel_async_checkpoint_saves_are_serialized(self):
        from assembly import JsonCheckpointStore
        class SlowStore(JsonCheckpointStore):
            active = 0
            peak = 0
            async def save(self, state):
                self.active += 1
                self.peak = max(self.peak, self.active)
                try:
                    await asyncio.sleep(.001)
                    super().save(state)
                finally:
                    self.active -= 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cp.json"
            store = SlowStore(path)
            async def success(*_):
                return {"success": True}
            host = self.host(path, [Tool("a", "a", success), Tool("b", "b", success)],
                [PlanStep(1, "a", "a"), PlanStep(2, "b", "b")], checkpoint_store=store)
            self.assertTrue(asyncio.run(host.run("task", "r"))["success"])
            self.assertEqual(store.peak, 1)
            self.assertEqual(len(store.load("r").results), 2)


class ReleaseReliabilityTest(unittest.TestCase):
    host = AgentHostSecurityTest.host

    def test_shared_store_same_run_executes_and_finalizes_once(self):
        async def scenario(path):
            calls, finals = [], []
            async def action(*_):
                calls.append(1)
                await asyncio.sleep(.01)
                return {"success": True}
            class Planner(SecurityPlan):
                async def final_answer(self, *_):
                    finals.append(1)
                    return f"answer-{len(finals)}"
            tool = Tool("action", "action", action)
            a, b = self.host(path, [tool]), self.host(path, [tool])
            a.llm = b.llm = Planner([PlanStep(1, "action", "action")])
            first, second = await asyncio.gather(a.run("task", "r"), b.run("task", "r"))
            self.assertTrue(first["success"] and second["success"])
            self.assertEqual(calls, [1])
            self.assertEqual(finals, [1])
            self.assertEqual(first["final"], second["final"])
            self.assertTrue(second["replayed"])
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "cp.json"))

    def test_finalization_failure_never_reexecutes_tool(self):
        class Planner(SecurityPlan):
            attempts = 0
            async def final_answer(self, *_):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("model unavailable")
                return "persisted answer"
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            host = self.host(Path(directory) / "cp.json", [Tool("action", "action", lambda *_: calls.append(1) or {"success": True})])
            host.llm = Planner([PlanStep(1, "action", "action")])
            first = asyncio.run(host.run("task", "r"))
            self.assertEqual(first["error_code"], "runtime_error")
            self.assertTrue(asyncio.run(host.run("task", "r"))["success"])
            self.assertEqual(asyncio.run(host.run("task", "r"))["final"], "persisted answer")
            self.assertEqual(calls, [1])
            self.assertEqual(host.llm.attempts, 2)

    def test_message_idempotency_survives_application_restart(self):
        async def scenario(path):
            calls = []
            class Agent:
                async def run(self, task, run_id, context):
                    calls.append((run_id, context))
                    return {"success": True, "status": "completed", "final": "answer"}
            app = ConversationApplication(JsonSessionStore(path), lambda *_: Agent(), max_context_messages=0)
            a, b = await asyncio.gather(app.send("s", "hello", idempotency_key="m1"), app.send("s", "hello", idempotency_key="m1"))
            restarted = ConversationApplication(JsonSessionStore(path), lambda *_: Agent())
            c = await restarted.send("s", "hello", idempotency_key="m1")
            self.assertEqual(a, b)
            self.assertEqual(a, c)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1], [])
            with self.assertRaisesRegex(ValueError, "idempotency_key_conflict"):
                await restarted.send("s", "changed", idempotency_key="m1")
            self.assertEqual(len(restarted.get_session("s").messages), 2)
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "s.json"))

    def test_cancelled_message_is_persisted_and_explicitly_resumed(self):
        async def scenario(path):
            runs = []
            class Agent:
                async def run(self, task, run_id, context):
                    runs.append(run_id)
                    if len(runs) == 1:
                        raise asyncio.CancelledError()
                    return {"success": True, "status": "completed", "final": "answer"}
            app = ConversationApplication(JsonSessionStore(path), lambda *_: Agent())
            with self.assertRaises(asyncio.CancelledError):
                await app.send("s", "hello", idempotency_key="m")
            record = app.get_session("s").tasks[0]
            self.assertEqual(record.status, "cancelled")
            with self.assertRaisesRegex(ValueError, "resume_required"):
                await app.send("s", "hello", idempotency_key="m")
            result = await app.resume("s", record.task_id)
            self.assertEqual(result["run_id"], record.run_id)
            self.assertEqual(runs, [record.run_id, record.run_id])
            self.assertEqual(len(app.get_session("s").messages), 2)
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "s.json"))

    def test_unrelated_sessions_run_concurrently(self):
        async def scenario(path):
            entered, both = [], asyncio.Event()
            class Agent:
                async def run(self, task, run_id, context):
                    entered.append(run_id)
                    if len(entered) == 2:
                        both.set()
                    await asyncio.wait_for(both.wait(), .2)
                    return {"success": True, "status": "completed", "final": "done"}
            app = ConversationApplication(JsonSessionStore(path), lambda *_: Agent())
            await asyncio.gather(app.send("s1", "a"), app.send("s2", "b"))
            self.assertEqual(len(entered), 2)
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "s.json"))

    def test_reconciliation_blocks_live_execution_and_requires_receipt(self):
        async def scenario(path):
            calls = []
            async def slow(*_):
                await asyncio.sleep(.05)
                calls.append(1)
                return {"success": True}
            host = self.host(path, [Tool("action", "slow", slow)],
                config=AgentConfig(allowed_tools=frozenset({"action"}), step_timeout=.005))
            self.assertEqual((await host.run("task", "r"))["error_code"], "unknown_side_effect")
            def verified(*_):
                return {"evidence": "test-downstream-receipt-1", "result": {"success": True, "remote_id": "1"}}
            with self.assertRaisesRegex(RuntimeError, "execution_still_active"):
                await host.reconcile("r", 1, verified)
            await asyncio.sleep(.08)
            with self.assertRaisesRegex(ValueError, "invalid_reconciliation_receipt"):
                await host.reconcile("r", 1, lambda *_: {"result": {"success": True}})
            state = await host.reconcile("r", 1, verified)
            self.assertEqual(state.trace[-1]["event"], "execution_reconciled")
            self.assertTrue((await host.run("task", "r"))["success"])
            self.assertEqual(calls, [1])
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(Path(directory) / "cp.json"))

    def test_error_codes_are_stable_and_completed_delivery_failure_is_replayable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cp.json"
            denied = self.host(path, [Tool("action", "action", lambda *_: {"success": True})],
                policy=DefaultPolicyEngine(frozenset()))
            self.assertEqual(asyncio.run(denied.run("task", "denied"))["error_code"], "policy_denied")
            invalid = self.host(path, [Tool("action", "action", lambda *_: {"success": True},
                parameters={"required": ["missing"]})])
            self.assertEqual(asyncio.run(invalid.run("task", "invalid"))["error_code"], "invalid_arguments")
            approval = self.host(path, [Tool("action", "action", lambda *_: {"success": True}, requires_approval=True)])
            self.assertEqual(asyncio.run(approval.run("task", "approval"))["error_code"], "approval_denied")
            completed = self.host(path, [Tool("action", "action", lambda *_: {"success": True})])
            def fail(*_):
                raise RuntimeError("delivery down")
            completed.hooks.register("after_run", fail, kind=HookKind.GUARD)
            self.assertTrue(asyncio.run(completed.run("task", "completed"))["success"])
            self.assertTrue(asyncio.run(completed.run("task", "completed"))["replayed"])
