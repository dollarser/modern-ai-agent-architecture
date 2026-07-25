import unittest

from main import DynamicToolRegistry, Tool, ToolRegistryError, safe_calculate


def string_tool(name: str = "echo") -> Tool:
    return Tool(
        name=name,
        description="回显文本",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        handler=lambda value: {"success": True, "value": value},
        tags=["test"],
    )


class ToolRegistryTest(unittest.TestCase):
    def test_register_execute_discover_and_unregister(self) -> None:
        registry = DynamicToolRegistry()
        registry.register(string_tool())
        self.assertEqual(registry.list_all(), ["echo"])
        self.assertEqual(registry.find_by_tag("test")[0].name, "echo")
        self.assertEqual(registry.execute("echo", {"value": "ok"}), {"success": True, "value": "ok"})
        self.assertTrue(registry.unregister("echo"))

    def test_duplicate_and_schema_errors_fail_closed(self) -> None:
        registry = DynamicToolRegistry()
        registry.register(string_tool())
        with self.assertRaises(ToolRegistryError):
            registry.register(string_tool())
        self.assertEqual(registry.execute("echo", {} )["error_code"], "invalid_arguments")
        self.assertEqual(registry.execute("echo", {"value": 1})["error_code"], "invalid_arguments")
        self.assertEqual(registry.execute("echo", {"value": "ok", "extra": True})["error_code"], "invalid_arguments")

    def test_calculator_rejects_code_and_bounds(self) -> None:
        self.assertEqual(safe_calculate("(2 + 3) * 4"), 20)
        with self.assertRaises(ValueError):
            safe_calculate('__import__("os")')
        with self.assertRaises(ValueError):
            safe_calculate("2 ** 11")


if __name__ == "__main__":
    unittest.main()
