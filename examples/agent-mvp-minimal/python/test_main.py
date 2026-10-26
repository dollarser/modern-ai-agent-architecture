import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from main import MinimalAgent, TaskState, ToolCall, ToolDispatcher


# docs:start agent-mvp-contract-tests
class MinimalAgentTest(unittest.TestCase):
    def test_completes_the_two_tool_plan(self) -> None:
        expected = json.loads(
            (Path(__file__).with_name("expected_transcript.json")).read_text()
        )
        output = io.StringIO()
        with redirect_stdout(output):
            state = MinimalAgent().run(expected["task"])

        self.assertTrue(state.finished)
        self.assertIsNone(state.error)
        self.assertEqual(state.step_count, expected["step_count"])
        self.assertEqual(state.observations, expected["observations"])
        for visible_line in expected["visible_lines"]:
            self.assertIn(visible_line, output.getvalue())

    def test_step_limit_is_not_reported_as_success(self) -> None:
        state = MinimalAgent(max_steps=1).run("查找数据库连接配置")

        self.assertFalse(state.finished)
        self.assertEqual(state.error, "达到最大步数: 1")
        self.assertEqual(state.step_count, 1)

    def test_unknown_tool_returns_structured_failure(self) -> None:
        result = ToolDispatcher().execute(
            ToolCall("missing_tool", {}), TaskState(task="test")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "tool_not_found")
        self.assertIn("unknown tool", result["error_message"])
        self.assertFalse(result["retryable"])

    def test_instructions_participate_in_reasoning(self) -> None:
        agent = MinimalAgent(instructions="始终输出可核查的文件路径")

        reason = agent.planner.reason("查找配置", agent.instructions)

        self.assertIn("始终输出可核查的文件路径", reason)
# docs:end agent-mvp-contract-tests


if __name__ == "__main__":
    unittest.main()
