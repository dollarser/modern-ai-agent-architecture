"""SandboxProfile 的配置契约；不声称自己创建了进程、网络或 Secret 隔离。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxProfile:
    workspace_roots: tuple[str, ...]
    process_allowlist: tuple[str, ...] = ()
    network_allowlist: tuple[str, ...] = ()
    secret_names: tuple[str, ...] = ()
    max_runtime_seconds: int = 30

    def validate(self) -> None:
        if not self.workspace_roots or any(not Path(root).is_absolute() for root in self.workspace_roots):
            raise ValueError("Sandbox workspace_roots 必须是非空绝对路径")
        if any("/" in item or "\\" in item for item in self.process_allowlist):
            raise ValueError("process_allowlist 只能使用可执行文件名")
        if any(item == "*" or "://" in item for item in self.network_allowlist):
            raise ValueError("network_allowlist 不允许通配符或 URL")
        if any(not item or "\n" in item for item in self.secret_names):
            raise ValueError("secret_names 不能为空且不能包含换行")
        if self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds 必须为正数")

    def allows_process(self, executable: str) -> bool:
        return Path(executable).name in self.process_allowlist

    def allows_network(self, host: str) -> bool:
        return host in self.network_allowlist

    def may_log_secret(self, _name: str) -> bool:
        return False
