# Agent MVP Minimal - 最小纵向切片

这是第 7 章的主示例：一个无外部依赖、可直接运行的 Agent 闭环。

## 包含的能力

- 规则化 Reasoning 与 Planning
- 两个无副作用的内置 Tool
- 当前任务的 `TaskState`
- 最大步数与结构化执行结果

它**不**实现持久化 Memory、完整 Runtime、Hook Pipeline、动态 Tool Registry、MCP 或 Plugin。这些能力分别在第 8--14 章展开。

## 运行方式

### Python

```bash
cd python
python main.py
```

### TypeScript

```bash
cd typescript
npm install
npm run build
npm start
```

## 预期输出

程序会依次打印 `reason → plan → execute → observe → finish`，并输出两次 Tool 调用的结构化结果。所有 Tool 都是确定性的内存模拟，因此可安全地用作测试和学习起点。

## 相关章节

- 第 5 章 Reasoning 与 Planning
- 第 6 章 Tools 与 Function Calling
- 第 7 章 Agent MVP：从零实现
- 第 8--11 章：将最小实现逐项演进为可靠运行组件
