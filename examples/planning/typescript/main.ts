/**
 * Planning - Agent 任务规划示例
 * ===============================
 * 展示 Plan-and-Execute 模式
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

enum StepStatus {
  PENDING = "⏳",
  RUNNING = "🔄",
  DONE = "✅",
  FAILED = "❌",
}

interface PlanStep {
  id: number;
  description: string;
  tool: string;
  status: StepStatus;
  result: string;
}

class Plan {
  task: string;
  steps: PlanStep[] = [];
  currentStep: number = 0;

  constructor(task: string) {
    this.task = task;
  }

  addStep(description: string, tool: string): void {
    this.steps.push({
      id: this.steps.length + 1,
      description,
      tool,
      status: StepStatus.PENDING,
      result: "",
    });
  }

  getCurrent(): PlanStep | null {
    if (this.currentStep < this.steps.length) {
      return this.steps[this.currentStep];
    }
    return null;
  }

  advance(): void {
    this.currentStep++;
  }
}

class Planner {
  /** 根据任务创建计划（简化实现） */
  createPlan(task: string): Plan {
    const plan = new Plan(task);

    if (task.includes("搜索") || task.includes("查询")) {
      plan.addStep("分析搜索需求", "reasoning");
      plan.addStep("执行搜索", "search_web");
      plan.addStep("整理搜索结果", "reasoning");
      plan.addStep("格式化输出", "output");
    } else if (task.includes("计算")) {
      plan.addStep("解析表达式", "reasoning");
      plan.addStep("执行计算", "calculate");
      plan.addStep("验证结果", "reasoning");
      plan.addStep("格式化输出", "output");
    } else {
      plan.addStep("理解任务", "reasoning");
      plan.addStep("确定策略", "reasoning");
      plan.addStep("执行操作", "tool");
      plan.addStep("检查结果", "reasoning");
    }

    return plan;
  }
}

function executePlan(plan: Plan): string[] {
  const results: string[] = [];

  for (const step of plan.steps) {
    step.status = StepStatus.RUNNING;
    results.push(`  ${step.status} Step ${step.id}: ${step.description}`);

    // 模拟执行
    step.status = StepStatus.DONE;
    step.result = `完成: ${step.description}`;
    results.push(`    -> ${step.result}`);
  }

  return results;
}

// ── Main ───────────────────────────────────────

function main(): void {
  const planner = new Planner();

  const tasks = [
    "搜索 AI Agent 架构设计",
    "计算 2^10 + 3*5",
    "分析用户需求",
  ];

  for (const task of tasks) {
    console.log(`\n${"=".repeat(60)}`);
    console.log(`  任务: ${task}`);
    console.log("=".repeat(60));

    const plan = planner.createPlan(task);
    console.log(`  计划步骤数: ${plan.steps.length}`);

    const results = executePlan(plan);
    for (const r of results) {
      console.log(r);
    }
  }

  console.log(`\n${"=".repeat(60)}`);
}

main();
