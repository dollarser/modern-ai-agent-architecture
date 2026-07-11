/**
 * Hello Agent - Minimal Agent Implementation
 * ===========================================
 * Demonstrates the core Agent loop: Reasoning → Planning → Execute → Observe
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

class MinimalAgent {
  private name: string;
  private memory: string[] = [];
  private stepCount: number = 0;

  constructor(name: string) {
    this.name = name;
  }

  reason(task: string): string {
    this.stepCount++;
    const thought = `[Step ${this.stepCount}] [${this.name}] 思考: 我需要完成 '${task}'`;
    this.memory.push(thought);
    return thought;
  }

  plan(task: string): string[] {
    const steps = [
      `1. 分析任务: ${task}`,
      "2. 确定所需资源",
      "3. 执行操作",
      "4. 验证结果",
    ];
    const planMsg = `[${this.name}] 规划: 制定 ${steps.length} 步计划`;
    this.memory.push(planMsg);
    return steps;
  }

  act(step: string): string {
    const result = `[${this.name}] 执行: ${step} ✓`;
    this.memory.push(result);
    return result;
  }

  observe(result: string): string {
    const observation = `[${this.name}] 观察: ${result}`;
    this.memory.push(observation);
    return observation;
  }

  run(task: string): string[] {
    const outputs: string[] = [];

    outputs.push(this.reason(task));
    const plan = this.plan(task);
    outputs.push(...plan);

    for (const step of plan) {
      const result = this.act(step);
      outputs.push(this.observe(result));
    }

    outputs.push(
      `[${this.name}] 完成! 总步数: ${this.stepCount}, 记忆条目: ${this.memory.length}`
    );
    return outputs;
  }
}

function main(): void {
  const agent = new MinimalAgent("HelloAgent");
  const results = agent.run("向世界问好");

  console.log("=".repeat(60));
  console.log("  Agent 执行过程");
  console.log("=".repeat(60));
  for (const r of results) {
    console.log(`  ${r}`);
  }
  console.log("=".repeat(60));
}

main();