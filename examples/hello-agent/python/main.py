"""
Hello Agent - 最小 Agent 实现
===============================
展示 Agent 核心循环：Reasoning → Planning → Execute → Observe

运行环境：Python 3.10+
依赖：无
"""


class MinimalAgent:
    """最小 Agent 实现，展示核心循环"""

    def __init__(self, name: str):
        self.name = name
        self.memory: list[str] = []
        self.step_count = 0

    def reason(self, task: str) -> str:
        """推理阶段：分析任务需求"""
        self.step_count += 1
        thought = f"[Step {self.step_count}] [{self.name}] 思考: 我需要完成 '{task}'"
        self.memory.append(thought)
        return thought

    def plan(self, task: str) -> list[str]:
        """规划阶段：将任务分解为可执行步骤"""
        steps = [
            f"1. 分析任务: {task}",
            "2. 确定所需资源",
            "3. 执行操作",
            "4. 验证结果",
        ]
        plan_msg = f"[{self.name}] 规划: 制定 {len(steps)} 步计划"
        self.memory.append(plan_msg)
        return steps

    def act(self, step: str) -> str:
        """执行阶段：执行具体步骤"""
        result = f"[{self.name}] 执行: {step} ✓"
        self.memory.append(result)
        return result

    def observe(self, result: str) -> str:
        """观察阶段：评估执行结果"""
        observation = f"[{self.name}] 观察: {result}"
        self.memory.append(observation)
        return observation

    def run(self, task: str) -> list[str]:
        """Agent 主循环"""
        outputs: list[str] = []

        outputs.append(self.reason(task))
        plan = self.plan(task)
        outputs.extend(plan)

        for step in plan:
            result = self.act(step)
            outputs.append(self.observe(result))

        outputs.append(f"[{self.name}] 完成! 总步数: {self.step_count}, 记忆条目: {len(self.memory)}")
        return outputs


def main():
    agent = MinimalAgent("HelloAgent")
    results = agent.run("向世界问好")

    print("=" * 60)
    print("  Agent 执行过程")
    print("=" * 60)
    for r in results:
        print(f"  {r}")
    print("=" * 60)


if __name__ == "__main__":
    main()