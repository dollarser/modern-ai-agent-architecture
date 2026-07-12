import json
import tempfile
import unittest
from pathlib import Path

from main import PluginInstaller


class PluginInstallerTest(unittest.TestCase):
    def make_plugin(self, root: Path, name: str, **extra) -> Path:
        source = root / f"src-{name}"; source.mkdir()
        (source / "plugin.json").write_text(json.dumps({
            "name": name, "version": "1.0.0", "description": name,
            "entrypoint": f"{name}-factory", **extra,
        }), encoding="utf-8")
        (source / "README.md").write_text(name, encoding="utf-8")
        return source

    def test_install_update_enable_disable_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); installer = PluginInstaller(root / "installed")
            source = self.make_plugin(root, "review")
            item = installer.install(source)
            self.assertTrue(item.enabled); self.assertEqual(item.source, str(source.resolve()))
            self.assertFalse(installer.set_enabled("review", False).enabled)
            (source / "README.md").write_text("updated", encoding="utf-8")
            self.assertFalse(installer.install(source, replace=True).enabled)
            installer.remove("review"); self.assertEqual(installer.catalog.list(), [])

    def test_permissions_and_dependencies_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); installer = PluginInstaller(root / "installed")
            protected = self.make_plugin(root, "protected", permissions=["shell"])
            with self.assertRaises(PermissionError): installer.install(protected)
            incompatible = self.make_plugin(root, "future", min_agent_version="2.0.0")
            with self.assertRaises(ValueError): installer.install(incompatible)
            dependent = self.make_plugin(root, "dependent", dependencies=["base"])
            with self.assertRaises(ValueError): installer.install(dependent)
            base = self.make_plugin(root, "base"); installer.install(base); installer.install(dependent)
            with self.assertRaises(ValueError): installer.set_enabled("base", False)
            with self.assertRaises(ValueError): installer.remove("base")


if __name__ == "__main__": unittest.main()
