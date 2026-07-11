import unittest

from main import MinimalAgent, TaskState, ToolCall, ToolDispatcher


class MinimalAgentTest(unittest.TestCase):
    def test_completes_the_two_tool_plan(self) -> None:
        state = MinimalAgent().run("查找数据库连接配置")

        self.assertTrue(state.finished)
        self.assertIsNone(state.error)
        self.assertEqual(state.step_count, 2)
        self.assertEqual(len(state.observations), 2)

    def test_step_limit_is_not_reported_as_success(self) -> None:
        state = MinimalAgent(max_steps=1).run("查找数据库连接配置")

        self.assertFalse(state.finished)
        self.assertEqual(state.error, "达到最大步数: 1")
        self.assertEqual(state.step_count, 1)

    def test_unknown_tool_returns_structured_failure(self) -> None:
        result = ToolDispatcher().execute(
            ToolCall("missing_tool", {}), TaskState(task="test")
        )

        self.assertFalse(result["ok"])
        self.assertIn("unknown tool", result["error"])

    def test_instructions_participate_in_reasoning(self) -> None:
        agent = MinimalAgent(instructions="始终输出可核查的文件路径")

        reason = agent.planner.reason("查找配置", agent.instructions)

        self.assertIn("始终输出可核查的文件路径", reason)


if __name__ == "__main__":
    unittest.main()
