"""
Memory - Agent 记忆管理示例
=============================
展示短期记忆、对话历史、上下文窗口管理

运行环境：Python 3.10+
依赖：无
"""

from dataclasses import dataclass, field
from collections import deque


@dataclass
class Memory:
    """Agent 记忆管理"""

    short_term: deque = field(default_factory=lambda: deque(maxlen=10))
    long_term: dict = field(default_factory=dict)
    context_window: int = 4000  # 模拟上下文窗口大小

    def add_message(self, role: str, content: str):
        """添加消息到短期记忆"""
        self.short_term.append({"role": role, "content": content})

    def summarize(self) -> str:
        """生成短期记忆摘要"""
        if not self.short_term:
            return "（无记忆）"
        items = [f"  [{m['role']}] {m['content'][:50]}..." for m in self.short_term]
        return "\n".join(items)

    def save(self, key: str, value: str):
        """保存到长期记忆"""
        self.long_term[key] = value

    def recall(self, key: str) -> str | None:
        """从长期记忆检索"""
        return self.long_term.get(key)

    def estimate_tokens(self) -> int:
        """估算当前 token 使用量"""
        total = sum(len(m["content"]) for m in self.short_term)
        return total // 4  # 粗略估算：4 字符 ≈ 1 token

    def is_near_limit(self) -> bool:
        """检查是否接近上下文窗口限制"""
        return self.estimate_tokens() > self.context_window * 0.8


def main():
    memory = Memory(context_window=2000)

    print("=" * 60)
    print("  Agent Memory 示例")
    print("=" * 60)

    # 模拟对话
    conversations = [
        ("user", "帮我搜索 Python 异步编程的最新资料"),
        ("assistant", "好的，让我搜索一下..."),
        ("tool", "搜索结果: Python asyncio 教程, FastAPI 文档..."),
        ("assistant", "找到了关于 asyncio 和 FastAPI 的资料"),
        ("user", "帮我总结一下 asyncio 的核心概念"),
        ("assistant", "asyncio 的核心概念包括: event loop, coroutine, task, future..."),
        ("user", "把这些内容保存到笔记"),
        ("assistant", "已保存到长期记忆"),
    ]

    for role, content in conversations:
        memory.add_message(role, content)
        tokens = memory.estimate_tokens()
        near = "⚠️ 接近限制" if memory.is_near_limit() else "✓"
        print(f"  [{role}] {content[:60]}... | tokens: {tokens} {near}")

    print()
    print("  短期记忆摘要:")
    print(memory.summarize())

    # 保存到长期记忆
    memory.save("asyncio_notes", "event loop, coroutine, task, future, await/async")
    recalled = memory.recall("asyncio_notes")
    print(f"\n  长期记忆检索: asyncio_notes = {recalled}")
    print("=" * 60)


if __name__ == "__main__":
    main()
