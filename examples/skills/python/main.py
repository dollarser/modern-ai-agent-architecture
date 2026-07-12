"""本地 Skill 安装、发现与卸载的零依赖参考实现。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str
    description: str
    keywords: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()

    @classmethod
    def parse(cls, path: Path) -> "SkillManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"name", "version", "description"}
        missing = required.difference(data)
        if missing:
            raise ValueError(f"skill.json 缺少字段: {sorted(missing)}")
        if not NAME_PATTERN.fullmatch(data["name"]):
            raise ValueError("Skill name 只能包含小写字母、数字和连字符")
        return cls(
            name=data["name"], version=data["version"],
            description=data["description"],
            keywords=tuple(data.get("keywords", [])),
            dependencies=tuple(data.get("dependencies", [])),
            permissions=tuple(data.get("permissions", [])),
        )


@dataclass(frozen=True)
class InstalledSkill:
    manifest: SkillManifest
    instructions: str
    path: Path
    source: str
    checksum: str


class SkillCatalog:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self) -> list[InstalledSkill]:
        return [self._load(path) for path in sorted(self.root.glob("*/skill.json"))]

    def get(self, name: str) -> InstalledSkill:
        path = self.root / name / "skill.json"
        if not path.exists():
            raise KeyError(f"Skill 未安装: {name}")
        return self._load(path)

    def match(self, task: str) -> list[InstalledSkill]:
        lowered = task.lower()
        return [
            skill for skill in self.list()
            if any(keyword.lower() in lowered for keyword in skill.manifest.keywords)
        ]

    def _load(self, manifest_path: Path) -> InstalledSkill:
        directory = manifest_path.parent
        manifest = SkillManifest.parse(manifest_path)
        instructions_path = directory / "SKILL.md"
        if not instructions_path.is_file():
            raise ValueError(f"Skill 缺少 SKILL.md: {manifest.name}")
        metadata = json.loads((directory / ".installed.json").read_text(encoding="utf-8"))
        instructions = instructions_path.read_text(encoding="utf-8")
        return InstalledSkill(
            manifest, instructions, directory, metadata["source"], metadata["checksum"]
        )


class SkillInstaller:
    def __init__(self, root: Path, allowed_permissions: set[str] | None = None) -> None:
        self.root = root
        self.allowed_permissions = allowed_permissions or set()
        self.catalog = SkillCatalog(root)
        root.mkdir(parents=True, exist_ok=True)

    def install(self, source: Path, *, replace: bool = False) -> InstalledSkill:
        source = source.resolve()
        manifest = SkillManifest.parse(source / "skill.json")
        if not (source / "SKILL.md").is_file():
            raise ValueError("Skill 源目录缺少 SKILL.md")
        denied = set(manifest.permissions).difference(self.allowed_permissions)
        if denied:
            raise PermissionError(f"Skill 权限未获授权: {sorted(denied)}")
        installed = {item.manifest.name for item in self.catalog.list()}
        missing = set(manifest.dependencies).difference(installed)
        if missing:
            raise ValueError(f"Skill 依赖未安装: {sorted(missing)}")
        target = self.root / manifest.name
        if target.exists() and not replace:
            raise ValueError(f"Skill 已安装: {manifest.name}")

        checksum = self._checksum(source)
        staging = Path(tempfile.mkdtemp(prefix=f".{manifest.name}-", dir=self.root))
        backup = self.root / f".{manifest.name}.backup"
        try:
            shutil.copytree(source, staging, dirs_exist_ok=True)
            (staging / ".installed.json").write_text(json.dumps({
                "source": str(source), "checksum": checksum,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            if target.exists():
                os.replace(target, backup)
            os.replace(staging, target)
            if backup.exists():
                shutil.rmtree(backup)
        except Exception:
            if target.exists() and backup.exists():
                shutil.rmtree(target)
            if backup.exists():
                os.replace(backup, target)
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return self.catalog.get(manifest.name)

    def remove(self, name: str) -> None:
        target = self.root / name
        if not target.is_dir():
            raise KeyError(f"Skill 未安装: {name}")
        dependents = [
            item.manifest.name for item in self.catalog.list()
            if name in item.manifest.dependencies
        ]
        if dependents:
            raise ValueError(f"Skill 仍被依赖: {dependents}")
        shutil.rmtree(target)

    @staticmethod
    def _checksum(source: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            digest.update(path.relative_to(source).as_posix().encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(".agent/skills"))
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("source", type=Path)
    install.add_argument("--replace", action="store_true")
    update = sub.add_parser("update")
    update.add_argument("source", type=Path)
    sub.add_parser("list")
    remove = sub.add_parser("remove")
    remove.add_argument("name")
    args = parser.parse_args()
    installer = SkillInstaller(args.root)
    if args.command in {"install", "update"}:
        replace = args.command == "update" or args.replace
        print(installer.install(args.source, replace=replace).manifest.name)
    elif args.command == "remove":
        installer.remove(args.name)
    else:
        for skill in installer.catalog.list():
            print(f"{skill.manifest.name}\t{skill.manifest.version}\t{skill.source}")


if __name__ == "__main__":
    main()
