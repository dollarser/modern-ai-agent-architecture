"""第 16 章 DatabaseReviewAgent 演示入口。"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from assembly import *  # noqa: F401,F403 - 教学入口同时重导出公共契约
from application import ConversationApplication, JsonSessionStore  # noqa: F401
from coding_scenario import CodingAgent  # noqa: F401
from database_review_scenario import DatabaseReviewAgent  # noqa: F401
from installed_adapters import (  # noqa: F401
    CatalogPluginProvider, CatalogSkillProvider, ManagerMCPProvider,
)


async def demo() -> None:
    with tempfile.TemporaryDirectory(prefix="database-review-agent-") as directory:
        checkpoint = Path(directory) / "checkpoints.json"
        task = "查找数据库配置并给出变更建议"
        first = await DatabaseReviewAgent(
            checkpoint, AgentConfig(interrupt_after_steps=2), approval=AutoApproveGate()
        ).run(task, "demo-run")
        print(json.dumps(first, ensure_ascii=False, indent=2))
        completed = await DatabaseReviewAgent(
            checkpoint, approval=AutoApproveGate()
        ).run(task, "demo-run")
        print(json.dumps(completed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(demo())
