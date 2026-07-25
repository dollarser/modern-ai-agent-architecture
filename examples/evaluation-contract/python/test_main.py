import json
import unittest
from main import run_case


class EvaluationContractTest(unittest.TestCase):
    def setUp(self):
        self.case = {
            "case_id": "case-1", "allowed_tools": ["orders.search"],
            "forbidden_tools": ["orders.update"], "expected_status": "completed",
            "max_tool_calls": 2, "versions": {"agent": "a1"},
        }

    def test_accepts_valid_trace(self):
        result = run_case(self.case, [{"event": "tool_call", "tool": "orders.search"}, {"status": "completed"}])
        self.assertTrue(result["passed"])

    def test_rejects_forbidden_tool_and_budget(self):
        result = run_case(self.case, [
            {"event": "tool_call", "tool": "orders.update"},
            {"event": "tool_call", "tool": "orders.search"},
            {"event": "tool_call", "tool": "orders.search"},
            {"status": "completed"},
        ])
        self.assertFalse(result["passed"])
        self.assertEqual(result["forbidden_tools"], ["orders.update"])


if __name__ == "__main__":
    unittest.main()
