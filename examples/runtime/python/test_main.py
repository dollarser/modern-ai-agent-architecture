import asyncio
import time
import unittest

from main import AgentRuntime, RunStatus, RuntimeConfig


class AgentRuntimeTest(unittest.TestCase):
    def test_only_done_result_is_finished(self) -> None:
        async def execute(step: str):
            return {"done": step == "verify"}

        result = asyncio.run(
            AgentRuntime().run(["search", "verify"], execute)
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status, RunStatus.FINISHED)

    def test_max_steps_is_exhausted_not_finished(self) -> None:
        async def execute(_step: str):
            return {"done": False}

        result = asyncio.run(
            AgentRuntime(RuntimeConfig(max_steps=1)).run(["one", "two"], execute)
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, RunStatus.EXHAUSTED)

    def test_timeout_returns_control(self) -> None:
        async def slow(_step: str):
            await asyncio.sleep(0.2)
            return {"done": True}

        started = time.monotonic()
        result = asyncio.run(
            AgentRuntime(RuntimeConfig(step_timeout=0.02)).run(["slow"], slow)
        )
        self.assertEqual(result.status, RunStatus.ERROR)
        self.assertLess(time.monotonic() - started, 0.15)

    def test_cancelled_state_is_preserved(self) -> None:
        runtime = AgentRuntime()

        async def cancel(_step: str):
            runtime.cancel()
            return {"done": True}

        result = asyncio.run(runtime.run(["cancel"], cancel))
        self.assertFalse(result.success)
        self.assertEqual(result.status, RunStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
