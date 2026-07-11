# Agent Runtime - 终态、超时与取消

这是第 9 章的可运行 Runtime 状态机示例，重点验证控制流语义，而不是重复实现 Planner、Memory 或 Tool Registry。

## 已实现能力

- `finished`、`exhausted`、`cancelled`、`error` 独立终态
- 只有 Observation 明确返回 `done=true` 才算成功
- Tool 步数上限
- 单步异步超时并及时返回控制权
- 协作式取消，取消状态不会被收尾逻辑覆盖
- Python 和 TypeScript 契约测试

## 运行方式

### Python

```bash
cd python
python main.py
python -m unittest -v test_main.py
```

### TypeScript

```bash
cd typescript
npm install
npm test
npm start
```

## 教学边界

异步超时会取消等待中的协程，但不保证外部系统已经撤销操作。真实 Tool 仍需请求级超时、取消协议、资源隔离和幂等键。暂停与跨进程恢复由第 16 章 Enhanced Agent 的 Checkpoint 示例继续展开。

## 相关章节

- 第 7 章 Agent MVP
- 第 9 章 Runtime
- 第 10 章 Hooks
- 第 16 章 Enhanced Agent
