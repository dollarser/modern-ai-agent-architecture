"""第 12～14 章安装/管理子系统到 AgentHost Provider Port 的适配器。"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from assembly import MCPToolDefinition, Plugin, Skill


class SkillCatalogPort(Protocol):
    def list(self) -> list[Any]: ...


class CatalogSkillProvider:
    def __init__(self, catalog: SkillCatalogPort) -> None:
        self.catalog = catalog

    def load_skills(self) -> list[Skill]:
        return [
            Skill(
                item.manifest.name,
                tuple(item.manifest.keywords),
                item.instructions,
                owner=f"installed-skill:{item.manifest.name}",
            )
            for item in self.catalog.list()
        ]


class ManagedConnectionPort(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class ManagedMCPClient:
    def __init__(self, connection: ManagedConnectionPort) -> None:
        self.connection = connection

    def list_tools(self) -> list[MCPToolDefinition]:
        return [
            MCPToolDefinition(
                str(item["name"]), str(item.get("description", "")),
                dict(item.get("inputSchema", item.get("input_schema", {}))),
            )
            for item in self.connection.list_tools()
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.connection.call_tool(name, arguments)


class MCPManagerPort(Protocol):
    def connect_enabled(self) -> list[tuple[str, ManagedConnectionPort]]: ...
    def close(self) -> None: ...


class ManagerMCPProvider:
    def __init__(self, manager: MCPManagerPort) -> None:
        self.manager = manager

    def connect_enabled(self) -> list[tuple[str, ManagedMCPClient]]:
        return [
            (server_name, ManagedMCPClient(connection))
            for server_name, connection in self.manager.connect_enabled()
        ]

    def close(self) -> None:
        self.manager.close()


class PluginCatalogPort(Protocol):
    def list(self, *, enabled_only: bool = False) -> list[Any]: ...


PluginFactory = Callable[[Any], Plugin]


class CatalogPluginProvider:
    """仅调用 Host 预注册 Factory；不从 Manifest 动态导入代码。"""

    def __init__(
        self, catalog: PluginCatalogPort, factories: dict[str, PluginFactory]
    ) -> None:
        self.catalog, self.factories = catalog, factories

    def load_plugins(self) -> list[Plugin]:
        records = self._dependency_order(self.catalog.list(enabled_only=True))
        plugins: list[Plugin] = []
        for record in records:
            factory_id = record.manifest.entrypoint
            factory = self.factories.get(factory_id)
            if factory is None:
                raise ValueError(f"Plugin Factory 未注册: {factory_id}")
            plugin = factory(record)
            if (
                plugin.manifest.name != record.manifest.name
                or plugin.manifest.version != record.manifest.version
            ):
                raise ValueError(f"Plugin Factory 身份不匹配: {record.manifest.name}")
            plugins.append(plugin)
        return plugins

    @staticmethod
    def _dependency_order(records: list[Any]) -> list[Any]:
        by_name = {item.manifest.name: item for item in records}
        ordered: list[Any] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                raise ValueError(f"Plugin 依赖存在循环: {name}")
            if name not in by_name:
                raise ValueError(f"已启用 Plugin 缺少依赖: {name}")
            visiting.add(name)
            for dependency in by_name[name].manifest.dependencies:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)
            ordered.append(by_name[name])

        for item in records:
            visit(item.manifest.name)
        return ordered
