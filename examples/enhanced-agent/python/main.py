"""第 16 章 Enhanced Agent 入口。完整组装见 assembly.py。"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from assembly import *  # noqa: F401,F403 - 教学入口同时重导出公共契约


async def demo() -> None:
    with tempfile.TemporaryDirectory(prefix="enhanced-agent-") as directory:
        checkpoint = Path(directory) / "checkpoints.json"
        task = "查找数据库配置并给出变更建议"
        first = await EnhancedAgent(
            checkpoint, AgentConfig(interrupt_after_steps=2)
        ).run(task, "demo-session")
        print(json.dumps(first, ensure_ascii=False, indent=2))
        completed = await EnhancedAgent(checkpoint).run(task, "demo-session")
        print(json.dumps(completed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(demo())
