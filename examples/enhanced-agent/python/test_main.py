import asyncio
import tempfile
import unittest
from pathlib import Path

from main import (
    AgentConfig,
    DeterministicLLMAdapter,
    EnhancedAgent,
    FakeMCPClient,
    HookKind,
    HookDefinition,
    HookPipeline,
    InMemoryMemoryBackend,
    Plugin,
    PluginManifest,
    RunState,
    ScriptedApprovalGate,
    Skill,
    Tool,
    ToolSource,
    ToolState,
)


class EnhancedAgentTest(unittest.TestCase):
    def run_agent(self, agent: EnhancedAgent, task: str, session: str) -> dict:
        return asyncio.run(agent.run(task, session))

    def test_final_assembly_runs_every_extension_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            llm = DeterministicLLMAdapter()
            memory = InMemoryMemoryBackend()
            mcp = FakeMCPClient()
            approval = ScriptedApprovalGate({"propose_change": True})
            agent = EnhancedAgent(
                Path(directory) / "cp.json",
                llm=llm,
                memory=memory,
                mcp_client=mcp,
                approval=approval,
            )
            result = self.run_agent(agent, "查找数据库配置并给出变更建议", "complete")

            self.assertTrue(result["success"])
            self.assertEqual(result["steps"], 6)
            self.assertEqual(result["attempts"], 6)
            self.assertIn("src/config.ts", result["final"])
            self.assertEqual(mcp.calls, ["search_catalog"])
            self.assertEqual(agent.tools.get("search_catalog").source, ToolSource.MCP)
            self.assertEqual(agent.tools.get("propose_change").source, ToolSource.PLUGIN)
            self.assertEqual(len(approval.requests), 1)
            self.assertTrue(any("子 Agent" in str(item) for item in result["results"].values()))
            self.assertIn("handoff.created", [event["topic"] for event in agent.events.events])
            self.assertTrue(any("先检索候选路径" in item for item in llm.last_context))
            self.assertTrue(any("必须给出文件路径" in item for item in llm.last_context))
            self.assertTrue(any(entry.role == "tool" for entry in memory.recent("complete")))

    def test_checkpoint_restores_approval_without_repeating_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "cp.json"
            gate = ScriptedApprovalGate({"propose_change": True})
            task = "查找数据库配置并给出变更建议"
            first = self.run_agent(
                EnhancedAgent(
                    checkpoint,
                    AgentConfig(interrupt_after_steps=4),
                    approval=gate,
                ),
                task,
                "resume",
            )
            second = self.run_agent(
                EnhancedAgent(checkpoint, approval=gate), task, "resume"
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
            agent = EnhancedAgent(Path(directory) / "cp.json", approval=gate)

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
            agent = EnhancedAgent(Path(directory) / "observer.json", hooks=hooks)
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
                EnhancedAgent(Path(directory) / "guard.json", hooks=guarded),
                "查找数据库配置并给出变更建议",
                "guard",
            )
            self.assertFalse(denied["success"])
            self.assertIn("Guardrail", denied["error"])
            self.assertEqual(denied["attempts"], 0)

    def test_router_filters_state_and_plugin_unload_removes_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = EnhancedAgent(Path(directory) / "cp.json")
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
                PluginManifest("temporary", "1.0.0"),
                skills=[Skill("temporary-skill", ("临时",), "临时指令")],
                hooks=[("custom", HookDefinition(100, plugin_hook))],
            ))
            probe = RunState("probe", "临时任务", [])
            agent.hooks.emit("custom", {}, probe)
            self.assertEqual(hook_calls, 1)
            self.assertEqual(len(agent.skills.match("临时任务")), 1)
            agent.plugins.unload("temporary")
            agent.hooks.emit("custom", {}, probe)
            self.assertEqual(hook_calls, 1)
            self.assertEqual(agent.skills.match("临时任务"), [])

            agent.plugins.unload("review-pack")
            self.assertNotIn("propose_change", [tool.name for tool in agent.tools.list()])
            self.assertEqual(agent.tools.get("search_catalog").source, ToolSource.MCP)

    def test_retry_count_and_terminal_failure_remain_honest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = 0

            def flaky(_args, _context):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return {"success": False, "error": "temporary", "retryable": True}
                return {"success": True, "matches": ["src/config.ts", "src/db.ts"]}

            agent = EnhancedAgent(Path(directory) / "retry.json")
            agent.tools.register(Tool("search_catalog", "flaky", flaky), replace=True)
            recovered = self.run_agent(
                agent, "查找数据库配置并给出变更建议", "retry"
            )
            self.assertTrue(recovered["success"])
            self.assertEqual(recovered["attempts"], 7)
            self.assertEqual(recovered["results"][1]["attempts"], 2)

            failed = EnhancedAgent(Path(directory) / "failed.json")
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


if __name__ == "__main__":
    unittest.main()
