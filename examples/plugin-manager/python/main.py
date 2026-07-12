"""本地 Plugin 包安装、启停与发现；不直接执行第三方代码。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(f"示例仅支持 x.y.z 版本: {value}")
    return tuple(map(int, match.groups()))


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    description: str
    entrypoint: str
    permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    min_agent_version: str = "1.0.0"

    @classmethod
    def parse(cls, path: Path) -> "PluginManifest":
        value = json.loads(path.read_text(encoding="utf-8"))
        missing = {"name", "version", "description", "entrypoint"}.difference(value)
        if missing:
            raise ValueError(f"plugin.json 缺少字段: {sorted(missing)}")
        if not NAME_PATTERN.fullmatch(value["name"]):
            raise ValueError("Plugin name 格式非法")
        if not NAME_PATTERN.fullmatch(value["entrypoint"]):
            raise ValueError("entrypoint 必须是 Host 注册的 Factory ID")
        return cls(
            value["name"], value["version"], value["description"], value["entrypoint"],
            tuple(value.get("permissions", [])), tuple(value.get("dependencies", [])),
            value.get("min_agent_version", "1.0.0"),
        )


@dataclass(frozen=True)
class InstalledPlugin:
    manifest: PluginManifest
    path: Path
    source: str
    checksum: str
    enabled: bool


class PluginCatalog:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self, *, enabled_only: bool = False) -> list[InstalledPlugin]:
        result = [self._load(path.parent) for path in sorted(self.root.glob("*/plugin.json"))]
        return [item for item in result if item.enabled or not enabled_only]

    def get(self, name: str) -> InstalledPlugin:
        directory = self.root / name
        if not (directory / "plugin.json").is_file():
            raise KeyError(f"Plugin 未安装: {name}")
        return self._load(directory)

    @staticmethod
    def _load(directory: Path) -> InstalledPlugin:
        manifest = PluginManifest.parse(directory / "plugin.json")
        metadata = json.loads((directory / ".installed.json").read_text(encoding="utf-8"))
        return InstalledPlugin(
            manifest, directory, metadata["source"], metadata["checksum"], metadata["enabled"]
        )


class PluginInstaller:
    def __init__(
        self, root: Path, allowed_permissions: set[str] | None = None,
        agent_version: str = "1.0.0",
    ) -> None:
        self.root = root
        self.allowed_permissions = allowed_permissions or set()
        self.agent_version = agent_version
        self.catalog = PluginCatalog(root)
        root.mkdir(parents=True, exist_ok=True)

    def install(self, source: Path, *, replace: bool = False) -> InstalledPlugin:
        source = source.resolve()
        manifest = PluginManifest.parse(source / "plugin.json")
        if version_tuple(self.agent_version) < version_tuple(manifest.min_agent_version):
            raise ValueError(
                f"Plugin 需要 Agent >= {manifest.min_agent_version}，当前 {self.agent_version}"
            )
        denied = set(manifest.permissions).difference(self.allowed_permissions)
        if denied:
            raise PermissionError(f"Plugin 权限未获授权: {sorted(denied)}")
        installed = {item.manifest.name for item in self.catalog.list()}
        missing = set(manifest.dependencies).difference(installed)
        if missing:
            raise ValueError(f"Plugin 依赖未安装: {sorted(missing)}")
        if any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError("Plugin 包不允许包含符号链接")
        target = self.root / manifest.name
        if target.exists() and not replace:
            raise ValueError(f"Plugin 已安装: {manifest.name}")
        previous_enabled = self.catalog.get(manifest.name).enabled if target.exists() else True
        checksum = self._checksum(source)
        staging = Path(tempfile.mkdtemp(prefix=f".{manifest.name}-", dir=self.root))
        backup = self.root / f".{manifest.name}.backup"
        try:
            shutil.copytree(source, staging, dirs_exist_ok=True)
            self._write_metadata(staging, str(source), checksum, previous_enabled)
            if target.exists(): os.replace(target, backup)
            os.replace(staging, target)
            if backup.exists(): shutil.rmtree(backup)
        except Exception:
            if target.exists() and backup.exists(): shutil.rmtree(target)
            if backup.exists(): os.replace(backup, target)
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return self.catalog.get(manifest.name)

    def set_enabled(self, name: str, enabled: bool) -> InstalledPlugin:
        item = self.catalog.get(name)
        if enabled:
            disabled_dependencies = [
                dep for dep in item.manifest.dependencies if not self.catalog.get(dep).enabled
            ]
            if disabled_dependencies:
                raise ValueError(f"Plugin 依赖未启用: {disabled_dependencies}")
        else:
            active_dependents = [
                other.manifest.name for other in self.catalog.list(enabled_only=True)
                if name in other.manifest.dependencies
            ]
            if active_dependents:
                raise ValueError(f"Plugin 仍被已启用插件依赖: {active_dependents}")
        self._write_metadata(item.path, item.source, item.checksum, enabled)
        return self.catalog.get(name)

    def remove(self, name: str) -> None:
        item = self.catalog.get(name)
        dependents = [
            other.manifest.name for other in self.catalog.list()
            if name in other.manifest.dependencies
        ]
        if dependents:
            raise ValueError(f"Plugin 仍被依赖: {dependents}")
        shutil.rmtree(item.path)

    @staticmethod
    def _write_metadata(directory: Path, source: str, checksum: str, enabled: bool) -> None:
        temporary = directory / ".installed.json.tmp"
        temporary.write_text(json.dumps({
            "source": source, "checksum": checksum, "enabled": enabled,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, directory / ".installed.json")

    @staticmethod
    def _checksum(source: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            digest.update(path.relative_to(source).as_posix().encode()); digest.update(path.read_bytes())
        return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path(".agent/plugins"))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "update"):
        action = sub.add_parser(command); action.add_argument("source", type=Path)
    sub.add_parser("list")
    for command in ("remove", "enable", "disable"):
        action = sub.add_parser(command); action.add_argument("name")
    args = parser.parse_args(); installer = PluginInstaller(args.root)
    if args.command in {"install", "update"}:
        print(installer.install(args.source, replace=args.command == "update").manifest.name)
    elif args.command == "remove": installer.remove(args.name)
    elif args.command in {"enable", "disable"}: installer.set_enabled(args.name, args.command == "enable")
    else:
        for item in installer.catalog.list():
            print(f"{item.manifest.name}\t{item.manifest.version}\t{'enabled' if item.enabled else 'disabled'}")


if __name__ == "__main__": main()
