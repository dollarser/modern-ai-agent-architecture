"""MCP Server 配置、启停和 Tool 刷新的 Host 管理层。"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    transport: str
    command: tuple[str, ...] = ()
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def validate(self) -> None:
        if not NAME_PATTERN.fullmatch(self.name):
            raise ValueError("Server name 格式非法")
        if self.transport not in {"stdio", "streamable-http"}:
            raise ValueError("transport 必须是 stdio 或 streamable-http")
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio Server 必须配置 command")
        if self.transport == "streamable-http" and not self.url.startswith(("https://", "http://localhost")):
            raise ValueError("远程 MCP 必须使用 HTTPS（localhost 可使用 HTTP）")


class MCPConnection(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def close(self) -> None: ...


class MCPTransportFactory(Protocol):
    def connect(self, config: MCPServerConfig) -> MCPConnection: ...


class FakeConnection:
    def __init__(self, name: str) -> None:
        self.name, self.closed = name, False
    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": f"{self.name}_search", "description": "fake tool"}]
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name != f"{self.name}_search":
            return {"success": False, "error": f"未知 Tool: {name}"}
        return {"success": True, "query": arguments.get("query", ""), "server": self.name}
    def close(self) -> None:
        self.closed = True


class FakeTransportFactory:
    def __init__(self) -> None:
        self.connections: list[FakeConnection] = []
    def connect(self, config: MCPServerConfig) -> FakeConnection:
        connection = FakeConnection(config.name)
        self.connections.append(connection)
        return connection


class MCPServerManager:
    def __init__(self, config_path: Path, factory: MCPTransportFactory) -> None:
        self.config_path, self.factory = config_path, factory
        self._configs = self._load()
        self._connections: dict[str, MCPConnection] = {}
        self._tools: dict[str, list[dict[str, Any]]] = {}

    def add(self, config: MCPServerConfig, *, replace: bool = False) -> None:
        config.validate()
        if config.name in self._configs and not replace:
            raise ValueError(f"MCP Server 已存在: {config.name}")
        old = self._configs.get(config.name)
        self._configs[config.name] = config
        try:
            self._save()
        except Exception:
            if old is None:
                self._configs.pop(config.name, None)
            else:
                self._configs[config.name] = old
            raise

    def remove(self, name: str) -> None:
        self.stop(name)
        if name not in self._configs:
            raise KeyError(f"MCP Server 不存在: {name}")
        old = self._configs.pop(name)
        try:
            self._save()
        except Exception:
            self._configs[name] = old
            raise

    def set_enabled(self, name: str, enabled: bool) -> None:
        current = self._require(name)
        if not enabled:
            self.stop(name)
        self._configs[name] = MCPServerConfig(**{**asdict(current), "enabled": enabled})
        self._save()

    def list(self, *, redact_env: bool = True) -> list[dict[str, Any]]:
        result = []
        for config in sorted(self._configs.values(), key=lambda item: item.name):
            item = asdict(config)
            if redact_env:
                item["env"] = {key: "***" for key in config.env}
            item["connected"] = config.name in self._connections
            result.append(item)
        return result

    def start_enabled(self) -> dict[str, list[dict[str, Any]]]:
        for config in self._configs.values():
            if config.enabled:
                self.start(config.name)
        return dict(self._tools)

    def connect_enabled(self) -> list[tuple[str, MCPConnection]]:
        """连接已启用 Server，并暴露可直接适配为 AgentHost MCPClient 的会话。"""
        self.start_enabled()
        return sorted(self._connections.items())

    def start(self, name: str) -> list[dict[str, Any]]:
        config = self._require(name)
        if not config.enabled:
            raise ValueError(f"MCP Server 已禁用: {name}")
        if name in self._connections:
            return self._tools[name]
        connection = self.factory.connect(config)
        try:
            tools = connection.list_tools()
        except Exception:
            connection.close()
            raise
        self._connections[name], self._tools[name] = connection, tools
        return tools

    def refresh(self, name: str) -> list[dict[str, Any]]:
        connection = self._connections.get(name)
        if connection is None:
            return self.start(name)
        tools = connection.list_tools()
        self._tools[name] = tools
        return tools

    def stop(self, name: str) -> None:
        connection = self._connections.pop(name, None)
        self._tools.pop(name, None)
        if connection:
            connection.close()

    def close(self) -> None:
        for name in list(self._connections):
            self.stop(name)

    def _require(self, name: str) -> MCPServerConfig:
        if name not in self._configs:
            raise KeyError(f"MCP Server 不存在: {name}")
        return self._configs[name]

    def _load(self) -> dict[str, MCPServerConfig]:
        if not self.config_path.exists():
            return {}
        values = json.loads(self.config_path.read_text(encoding="utf-8"))
        configs = {}
        for value in values.get("servers", []):
            value["command"] = tuple(value.get("command", []))
            config = MCPServerConfig(**value); config.validate(); configs[config.name] = config
        return configs

    def _save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "servers": [asdict(value) for value in self._configs.values()]}
        fd, temporary = tempfile.mkstemp(prefix="mcp-", dir=self.config_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.config_path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(".agent/mcp.json"))
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add"); add.add_argument("name"); add.add_argument("command", nargs="+")
    sub.add_parser("list")
    for action in ("remove", "enable", "disable"):
        command = sub.add_parser(action); command.add_argument("name")
    args = parser.parse_args(); manager = MCPServerManager(args.config, FakeTransportFactory())
    if args.action == "add": manager.add(MCPServerConfig(args.name, "stdio", tuple(args.command)))
    elif args.action == "remove": manager.remove(args.name)
    elif args.action == "enable": manager.set_enabled(args.name, True)
    elif args.action == "disable": manager.set_enabled(args.name, False)
    else: print(json.dumps(manager.list(), ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
