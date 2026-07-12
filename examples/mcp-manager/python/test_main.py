import tempfile
import unittest
from pathlib import Path

from main import FakeTransportFactory, MCPServerConfig, MCPServerManager


class MCPServerManagerTest(unittest.TestCase):
    def test_persistence_lifecycle_refresh_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "mcp.json"; factory = FakeTransportFactory()
            manager = MCPServerManager(config, factory)
            manager.add(MCPServerConfig("catalog", "stdio", ("catalog-server",), env={"TOKEN": "secret"}))
            self.assertEqual(manager.list()[0]["env"], {"TOKEN": "***"})
            self.assertEqual(manager.start_enabled()["catalog"][0]["name"], "catalog_search")
            name, connection = manager.connect_enabled()[0]
            self.assertEqual(name, "catalog")
            self.assertTrue(connection.call_tool("catalog_search", {"query": "db"})["success"])
            self.assertEqual(manager.refresh("catalog")[0]["name"], "catalog_search")
            manager.set_enabled("catalog", False)
            self.assertTrue(factory.connections[0].closed)
            restored = MCPServerManager(config, FakeTransportFactory())
            self.assertFalse(restored.list()[0]["enabled"])
            restored.remove("catalog")
            self.assertEqual(restored.list(), [])

    def test_validation_and_failed_discovery_do_not_connect(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = MCPServerManager(Path(directory) / "mcp.json", FakeTransportFactory())
            with self.assertRaises(ValueError):
                manager.add(MCPServerConfig("bad", "streamable-http", url="http://remote.test"))
            manager.add(MCPServerConfig("ok", "stdio", ("server",)))
            with self.assertRaises(ValueError):
                manager.add(MCPServerConfig("ok", "stdio", ("server",)))


if __name__ == "__main__": unittest.main()
