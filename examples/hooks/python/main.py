"""
Hooks - Agent 生命周期钩子示例
================================
展示 Before/After Hook 的注册和触发

运行环境：Python 3.10+
依赖：无
"""

from typing import Callable
from dataclasses import dataclass, field


@dataclass
class HookSystem:
    """Hook 系统"""

    hooks: dict[str, list[Callable]] = field(default_factory=dict)

    def register(self, event: str, callback: Callable):
        """注册 Hook"""
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append(callback)

    def trigger(self, event: str, *args, **kwargs):
        """触发 Hook"""
        for hook in self.hooks.get(event, []):
            try:
                hook(*args, **kwargs)
            except Exception as e:
                print(f"  [Hook Error] {event}: {e}")


class AgentWithHooks:
    """带 Hook 系统的 Agent"""

    LIFECYCLE_EVENTS = [
        "before_load",
        "after_load",
        "before_reasoning",
        "after_reasoning",
        "before_tool_call",
        "after_tool_call",
        "before_finish",
        "after_finish",
    ]

    def __init__(self):
        self.hooks = HookSystem()
        self._setup_default_hooks()

    def _setup_default_hooks(self):
        """设置默认 Hook"""

        def log_hook(event: str):
            def hook(*args):
                print(f"  [LOG] {event}: {args if args else 'no args'}")
            return hook

        for event in self.LIFECYCLE_EVENTS:
            self.hooks.register(event, log_hook(event))

    def register_custom_hook(self, event: str, callback: Callable):
        """注册自定义 Hook"""
        self.hooks.register(event, callback)

    def run(self, task: str = "demo"):
        """运行 Agent 生命周期"""
        events = [
            ("before_load", task),
            ("after_load", task),
            ("before_reasoning", task),
            ("after_reasoning", "分析完成"),
            ("before_tool_call", "search_web"),
            ("after_tool_call", "search_web", "搜索完成"),
            ("before_finish",),
            ("after_finish",),
        ]

        for event_args in events:
            event = event_args[0]
            args = event_args[1:]
            self.hooks.trigger(event, *args)


def main():
    print("=" * 60)
    print("  Agent Hooks 系统示例")
    print("=" * 60)

    agent = AgentWithHooks()

    # 注册自定义 Hook
    def permission_check(tool_name: str):
        allowed = ["search_web", "read_file", "calculate"]
        if tool_name not in allowed:
            print(f"  [PERMISSION] ⛔ 拒绝 Tool: {tool_name}")
        else:
            print(f"  [PERMISSION] ✅ 允许 Tool: {tool_name}")

    agent.register_custom_hook("before_tool_call", permission_check)

    def timing_hook(*args):
        import time
        print(f"  [TIMING] {time.strftime('%H:%M:%S')}")

    agent.register_custom_hook("before_reasoning", timing_hook)
    agent.register_custom_hook("before_finish", timing_hook)

    print("\n  运行 Agent 生命周期:")
    print("  " + "-" * 40)
    agent.run("搜索 AI 新闻")
    print("  " + "-" * 40)
    print("=" * 60)


if __name__ == "__main__":
    main()
