import json
import tempfile
import unittest
from pathlib import Path

from main import SkillInstaller


class SkillInstallerTest(unittest.TestCase):
    def make_skill(self, root: Path, name="review", **extra) -> Path:
        source = root / f"src-{name}"
        source.mkdir()
        manifest = {"name": name, "version": "1.0.0", "description": name,
                    "keywords": [name], **extra}
        (source / "skill.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "SKILL.md").write_text(f"# {name}\n\n执行 {name}", encoding="utf-8")
        return source

    def test_install_match_replace_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            installer = SkillInstaller(base / "installed")
            source = self.make_skill(base, "review")
            installed = installer.install(source)
            self.assertEqual(installed.manifest.name, "review")
            self.assertEqual(installer.catalog.match("请 review 代码")[0].source, str(source.resolve()))
            (source / "SKILL.md").write_text("updated", encoding="utf-8")
            updated = installer.install(source, replace=True)
            self.assertEqual(updated.instructions, "updated")
            installer.remove("review")
            self.assertEqual(installer.catalog.list(), [])

    def test_permissions_dependencies_and_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            installer = SkillInstaller(base / "installed")
            protected = self.make_skill(base, "protected", permissions=["shell"])
            with self.assertRaises(PermissionError):
                installer.install(protected)
            dependent = self.make_skill(base, "dependent", dependencies=["base"])
            with self.assertRaises(ValueError):
                installer.install(dependent)
            source = self.make_skill(base, "base")
            installer.install(source)
            with self.assertRaises(ValueError):
                installer.install(source)


if __name__ == "__main__":
    unittest.main()
