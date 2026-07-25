import asyncio
import tempfile
import unittest
from pathlib import Path

from a2a_adapter import HostA2AAdapter, RemoteTaskRequest
from assembly import AgentHost


class FakeRemoteClient:
    async def submit(self, request):
        return {"success": True, "status": "submitted", "task_id": request.task_id}

    async def get_artifact(self, artifact_id, tenant_id, owner):
        return f"{tenant_id}:{owner}:{artifact_id}".encode()

    async def get_task(self, task_id, tenant_id, owner):
        return {"success": True, "task_id": task_id, "tenant_id": tenant_id, "owner": owner, "status": "working"}


class HostA2AAdapterTest(unittest.TestCase):
    def test_binds_remote_task_to_host_run_and_publishes_event(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as directory:
                host = AgentHost(Path(directory) / "checkpoint.json")
                adapter = HostA2AAdapter(host, FakeRemoteClient())
                request = RemoteTaskRequest("run-1", "task-1", "tenant-a", "alice", "idem-1", "生成报告")
                result = await adapter.submit(request)
                self.assertTrue(result["success"])
                self.assertEqual(host.events.events[-1]["topic"], "a2a.task.submitted")
                self.assertEqual((await adapter.get_task("run-1", "task-1", "tenant-a", "alice"))["status"], "working")
                self.assertEqual(await adapter.get_artifact("run-1", "artifact-1", "tenant-a", "alice"), b"tenant-a:alice:artifact-1")
                mismatch = await adapter.submit(RemoteTaskRequest("run-1", "task-2", "tenant-a", "alice", "idem-2", "继续"))
                self.assertEqual(mismatch["error_code"], "checkpoint_mismatch")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
