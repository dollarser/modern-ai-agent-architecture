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
                if event.startswith("before_"):
                    raise
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

    def run(self, task: str = "demo",
            tool_name: str = "search_web") -> dict | None:
        """运行 Agent 生命周期；Before Hook 拒绝时不执行 Tool。"""
        self.hooks.trigger("before_load", task)
        self.hooks.trigger("after_load", task)
        self.hooks.trigger("before_reasoning", task)
        self.hooks.trigger("after_reasoning", "分析完成")

        try:
            self.hooks.trigger("before_tool_call", tool_name)
        except Exception as error:
            print(f"  [BLOCKED] {error}")
            return None

        tool_result = {
            "success": True,
            "content": f"{tool_name} 执行完成；token=sk-demo",
        }
        self.hooks.trigger("after_tool_call", tool_name, tool_result)
        self.hooks.trigger("before_finish")
        self.hooks.trigger("after_finish")
        return tool_result


def main():
    print("=" * 60)
    print("  Agent Hooks 系统示例")
    print("=" * 60)

    agent = AgentWithHooks()

    # 注册自定义 Hook
    def permission_check(tool_name: str):
        allowed = ["search_web", "read_file", "calculate"]
        if tool_name not in allowed:
            raise PermissionError(f"拒绝 Tool: {tool_name}")
        print(f"  [PERMISSION] ✅ 允许 Tool: {tool_name}")

    agent.register_custom_hook("before_tool_call", permission_check)

    def mask_secret(_tool_name: str, result: dict):
        result["content"] = result["content"].replace("sk-demo", "sk-***")

    agent.register_custom_hook("after_tool_call", mask_secret)

    def timing_hook(*args):
        import time
        print(f"  [TIMING] {time.strftime('%H:%M:%S')}")

    agent.register_custom_hook("before_reasoning", timing_hook)
    agent.register_custom_hook("before_finish", timing_hook)

    print("\n  运行 Agent 生命周期:")
    print("  " + "-" * 40)
    agent.run("搜索 AI 新闻")
    agent.run("尝试危险操作", tool_name="delete_all")
    print("  " + "-" * 40)
    print("=" * 60)


if __name__ == "__main__":
    main()
