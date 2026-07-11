/**
 * Memory - Agent 记忆管理示例
 * =================================
 * 展示短期记忆、对话历史、上下文窗口管理
 *
 * Runtime: Node.js 18+, TypeScript 5.5+
 * Usage: npm run start
 */

interface Message {
  role: string;
  content: string;
}

class Memory {
  private shortTerm: Message[] = [];
  private readonly maxShortTerm: number;
  private longTerm: Map<string, string> = new Map();
  private readonly contextWindow: number;

  constructor(contextWindow: number = 4000, maxShortTerm: number = 10) {
    this.contextWindow = contextWindow;
    this.maxShortTerm = maxShortTerm;
  }

  /** 添加消息到短期记忆 */
  addMessage(role: string, content: string): void {
    this.shortTerm.push({ role, content });
    if (this.shortTerm.length > this.maxShortTerm) {
      this.shortTerm.shift();
    }
  }

  /** 生成短期记忆摘要 */
  summarize(): string {
    if (this.shortTerm.length === 0) {
      return "（无记忆）";
    }
    return this.shortTerm
      .map((m) => `  [${m.role}] ${m.content.slice(0, 50)}...`)
      .join("\n");
  }

  /** 保存到长期记忆 */
  save(key: string, value: string): void {
    this.longTerm.set(key, value);
  }

  /** 从长期记忆检索 */
  recall(key: string): string | undefined {
    return this.longTerm.get(key);
  }

  /** 估算当前 token 使用量 */
  estimateTokens(): number {
    const total = this.shortTerm.reduce((sum, m) => sum + m.content.length, 0);
    return Math.floor(total / 4); // 粗略估算：4 字符 ≈ 1 token
  }

  /** 检查是否接近上下文窗口限制 */
  isNearLimit(): boolean {
    return this.estimateTokens() > this.contextWindow * 0.8;
  }
}

// ── Main ───────────────────────────────────────

function main(): void {
  const memory = new Memory(2000);

  console.log("=".repeat(60));
  console.log("  Agent Memory 示例");
  console.log("=".repeat(60));

  // 模拟对话
  const conversations: Array<[string, string]> = [
    ["user", "帮我搜索 Python 异步编程的最新资料"],
    ["assistant", "好的，让我搜索一下..."],
    ["tool", "搜索结果: Python asyncio 教程, FastAPI 文档..."],
    ["assistant", "找到了关于 asyncio 和 FastAPI 的资料"],
    ["user", "帮我总结一下 asyncio 的核心概念"],
    ["assistant", "asyncio 的核心概念包括: event loop, coroutine, task, future..."],
    ["user", "把这些内容保存到笔记"],
    ["assistant", "已保存到长期记忆"],
  ];

  for (const [role, content] of conversations) {
    memory.addMessage(role, content);
    const tokens = memory.estimateTokens();
    const near = memory.isNearLimit() ? "⚠️ 接近限制" : "✓";
    console.log(`  [${role}] ${content.slice(0, 60)}... | tokens: ${tokens} ${near}`);
  }

  console.log();
  console.log("  短期记忆摘要:");
  console.log(memory.summarize());

  // 保存到长期记忆
  memory.save("asyncio_notes", "event loop, coroutine, task, future, await/async");
  const recalled = memory.recall("asyncio_notes");
  console.log(`\n  长期记忆检索: asyncio_notes = ${recalled}`);
  console.log("=".repeat(60));
}

main();
