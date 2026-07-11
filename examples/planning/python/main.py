"""
Planning - Agent 任务规划示例
===============================
展示 Plan-and-Execute 模式

运行环境：Python 3.10+
依赖：无
"""

from dataclasses import dataclass, field
from enum import Enum


class StepStatus(Enum):
    PENDING = "⏳"
    RUNNING = "🔄"
    DONE = "✅"
    FAILED = "❌"


@dataclass
class PlanStep:
    """计划步骤"""
    id: int
    description: str
    tool: str
    status: StepStatus = StepStatus.PENDING
    result: str = ""


@dataclass
class Plan:
    """执行计划"""
    task: str
    steps: list[PlanStep] = field(default_factory=list)
    current_step: int = 0

    def add_step(self, description: str, tool: str):
        step = PlanStep(id=len(self.steps) + 1, description=description, tool=tool)
        self.steps.append(step)

    def get_current(self) -> PlanStep | None:
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def advance(self):
        self.current_step += 1


class Planner:
    """规划器"""

    def create_plan(self, task: str) -> Plan:
        """根据任务创建计划（简化实现）"""
        plan = Plan(task=task)

        if "搜索" in task or "查询" in task:
            plan.add_step("分析搜索需求", "reasoning")
            plan.add_step("执行搜索", "search_web")
            plan.add_step("整理搜索结果", "reasoning")
            plan.add_step("格式化输出", "output")
        elif "计算" in task:
            plan.add_step("解析表达式", "reasoning")
            plan.add_step("执行计算", "calculate")
            plan.add_step("验证结果", "reasoning")
            plan.add_step("格式化输出", "output")
        else:
            plan.add_step("理解任务", "reasoning")
            plan.add_step("确定策略", "reasoning")
            plan.add_step("执行操作", "tool")
            plan.add_step("检查结果", "reasoning")

        return plan


def execute_plan(plan: Plan) -> list[str]:
    """执行计划"""
    results = []

    for step in plan.steps:
        step.status = StepStatus.RUNNING
        results.append(f"  {step.status.value} Step {step.id}: {step.description}")

        # 模拟执行
        step.status = StepStatus.DONE
        step.result = f"完成: {step.description}"
        results.append(f"    -> {step.result}")

    return results


def main():
    planner = Planner()

    tasks = [
        "搜索 AI Agent 架构设计",
        "计算 2^10 + 3*5",
        "分析用户需求"
    ]

    for task in tasks:
        print(f"\n{'='*60}")
        print(f"  任务: {task}")
        print(f"{'='*60}")

        plan = planner.create_plan(task)
        print(f"  计划步骤数: {len(plan.steps)}")

        results = execute_plan(plan)
        for r in results:
            print(r)

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
