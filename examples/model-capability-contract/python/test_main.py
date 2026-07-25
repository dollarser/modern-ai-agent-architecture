import unittest
from main import FakeProvider, ModelCapabilities


class ModelCapabilityTest(unittest.TestCase):
    def test_full_provider_contract(self):
        provider = FakeProvider()
        result = provider.complete("hello", tools=[{"name": "search"}], schema={"type": "object"})
        self.assertTrue(result["success"])
        self.assertIn("usage", result)
        self.assertEqual(list(provider.stream("hello world")), ["hello", "world"])
        provider.cancel()
        self.assertTrue(provider.cancelled)

    def test_unsupported_capability_fails_closed(self):
        provider = FakeProvider(ModelCapabilities(tool_calling=False, streaming=False))
        self.assertEqual(provider.complete("hello", tools=[{"name": "search"}])["error_code"], "capability_unsupported")
        with self.assertRaisesRegex(RuntimeError, "capability_unsupported"):
            list(provider.stream("hello"))


if __name__ == "__main__":
    unittest.main()
