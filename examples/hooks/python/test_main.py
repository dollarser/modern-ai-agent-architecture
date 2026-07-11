import unittest

from main import AgentWithHooks


class HooksTest(unittest.TestCase):
    def test_guard_blocks_handler_path(self) -> None:
        agent = AgentWithHooks()

        def allowlist(tool_name: str):
            if tool_name != "read_file":
                raise PermissionError("denied")

        agent.register_custom_hook("before_tool_call", allowlist)
        self.assertIsNone(agent.run("危险任务", "delete_all"))

    def test_after_hook_transformation_is_returned(self) -> None:
        agent = AgentWithHooks()

        def mask(_tool_name: str, result: dict):
            result["content"] = result["content"].replace("sk-demo", "sk-***")

        agent.register_custom_hook("after_tool_call", mask)
        result = agent.run("读取", "read_file")
        self.assertIsNotNone(result)
        self.assertIn("sk-***", result["content"])
        self.assertNotIn("sk-demo", result["content"])

    def test_after_hook_failure_is_isolated(self) -> None:
        agent = AgentWithHooks()
        agent.register_custom_hook(
            "after_tool_call", lambda *_args: (_ for _ in ()).throw(RuntimeError("metrics down"))
        )
        result = agent.run("读取", "read_file")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
