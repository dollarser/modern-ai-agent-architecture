"""Memory 与 Context 的最小治理契约，保持确定性且不依赖模型或向量库。"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryRecord:
    key: str
    content: str
    tenant_id: str
    subject_id: str
    provenance: str
    trust: str
    consent: bool
    retention_until: float | None = None


class GovernedMemory:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], MemoryRecord] = {}

    def put(self, record: MemoryRecord) -> None:
        if not record.tenant_id or not record.subject_id:
            raise ValueError("Memory 必须绑定 tenant_id 和 subject_id")
        if record.provenance not in {"user_input", "tool_result", "conversation_compaction"}:
            raise ValueError("未知 Memory provenance")
        if record.trust not in {"untrusted", "verified", "user_confirmed"}:
            raise ValueError("未知 Memory trust")
        if record.key.startswith("preference/") and not record.consent:
            raise PermissionError("用户偏好写入需要明确 consent")
        self._records[(record.tenant_id, record.subject_id, record.key)] = record

    def get(self, key: str, *, tenant_id: str, subject_id: str) -> MemoryRecord | None:
        record = self._records.get((tenant_id, subject_id, key))
        if record and record.retention_until is not None and record.retention_until <= time.time():
            self._records.pop((tenant_id, subject_id, key), None)
            return None
        return record

    def forget(self, key: str, *, tenant_id: str, subject_id: str) -> bool:
        return self._records.pop((tenant_id, subject_id, key), None) is not None


@dataclass(frozen=True)
class ArtifactView:
    artifact_id: str
    summary: str
    media_type: str
    checksum: str

    def render(self) -> str:
        return f"[artifact:{self.artifact_id} {self.media_type} sha256={self.checksum}] {self.summary}"


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def build_context(system: str, history: list[str], artifacts: list[ArtifactView], *, token_budget: int) -> list[str]:
    """保留系统规则、Artifact 引用和最新历史；不把 Artifact 内容伪装成普通历史。"""
    fixed = [system, *(item.render() for item in artifacts)]
    used = sum(estimate_tokens(item) for item in fixed)
    if used > token_budget:
        raise ValueError("固定 Context 已超过 token budget")
    selected: list[str] = []
    for item in reversed(history):
        cost = estimate_tokens(item)
        if used + cost > token_budget:
            break
        selected.insert(0, item)
        used += cost
    return [*fixed, *selected]
