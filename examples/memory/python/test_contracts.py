import time
import unittest

from contracts import ArtifactView, GovernedMemory, MemoryRecord, build_context


class MemoryContextContractTest(unittest.TestCase):
    def test_memory_is_scoped_and_consent_gated(self):
        memory = GovernedMemory()
        with self.assertRaises(PermissionError):
            memory.put(MemoryRecord("preference/theme", "dark", "t1", "u1", "user_input", "user_confirmed", False))
        memory.put(MemoryRecord("preference/theme", "dark", "t1", "u1", "user_input", "user_confirmed", True))
        self.assertIsNone(memory.get("preference/theme", tenant_id="t2", subject_id="u1"))
        self.assertEqual(memory.get("preference/theme", tenant_id="t1", subject_id="u1").content, "dark")

    def test_retention_forget_and_context_budget_are_deterministic(self):
        memory = GovernedMemory()
        memory.put(MemoryRecord("temporary", "old", "t1", "u1", "tool_result", "verified", False, time.time() - 1))
        self.assertIsNone(memory.get("temporary", tenant_id="t1", subject_id="u1"))
        self.assertTrue(memory.forget("missing", tenant_id="t1", subject_id="u1") is False)
        context = build_context("rules", ["old history", "latest history"], [ArtifactView("a1", "report", "text/plain", "abc")], token_budget=30)
        self.assertEqual(context[:2], ["rules", "[artifact:a1 text/plain sha256=abc] report"])
        self.assertEqual(context[-1], "latest history")


if __name__ == "__main__":
    unittest.main()
