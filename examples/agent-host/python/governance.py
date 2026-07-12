"""运行治理：统一策略决策与可复现能力快照工具。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class ConfigScope(str, Enum):
    MANAGED = "managed"
    PROJECT = "project"
    USER = "user"
    LOCAL = "local"
    SESSION = "session"


@dataclass(frozen=True)
class PolicyLayer:
    scope: ConfigScope
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()


def merge_policy_layers(layers: list[PolicyLayer]) -> tuple[frozenset[str], frozenset[str]]:
    """合并作用域；任何层的 deny 都不能被低层 allow 放宽。"""
    allowed: set[str] = set()
    denied: set[str] = set()
    for layer in layers:
        allowed.update(layer.allow)
        denied.update(layer.deny)
    allowed.difference_update(denied)
    return frozenset(allowed), frozenset(denied)


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyRequest:
    subject: str
    capability: str
    arguments: dict[str, Any]
    resource: str
    run_id: str
    source: str
    risk: str


class PolicyEngine(Protocol):
    version: str
    def evaluate(self, request: PolicyRequest) -> PolicyDecision: ...


class DefaultPolicyEngine:
    """统一运行时授权：未知 Tool 拒绝，高风险 Tool 进入人工审批。"""

    version = "default-policy-v1"

    def __init__(
        self, allowed_tools: frozenset[str], layers: list[PolicyLayer] | None = None
    ) -> None:
        layered_allow, self.denied_tools = merge_policy_layers(layers or [])
        self.allowed_tools = frozenset(set(allowed_tools).union(layered_allow))

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if (
            request.capability in self.denied_tools
            or request.capability not in self.allowed_tools
        ):
            return PolicyDecision.DENY
        return PolicyDecision.ASK if request.risk == "high" else PolicyDecision.ALLOW


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def with_snapshot_hash(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {**payload, "snapshot_hash": sha256_text(encoded)}
