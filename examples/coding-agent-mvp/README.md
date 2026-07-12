# Coding Agent 组合示例（非最终架构）

## 学习目标
在读完第 8--11 章后，观察轻量 Memory、Tool 映射和回调如何与 Reasoning、Planning、Tool Calling 组合。它是补充演示，不是第 7 章主实现，也不是第 16 章的功能完备架构。第 7 章的首个可运行闭环请使用 `examples/agent-mvp-minimal/`。

## 前置知识
- 第 7 章「Agent MVP：从零实现」
- 第 2 章「总体架构与生命周期」
- 第 5 章「Reasoning 与 Planning」
- 第 6 章「Tools 与 Function Calling」

## 运行方式

### Python
```bash
cd python
pip install -r requirements.txt
python main.py
```

### TypeScript
```bash
cd typescript
npm install
npm run start
```

## 预期输出
展示一次简化的编程任务处理：接收任务、生成固定计划、选择一个模拟 Tool、记录进程内 Memory 并输出结果。示例不调用真实 LLM，不执行真实文件读写或 Shell，也不实现动态重规划。

## 相关章节
- 第 7 章 Agent MVP：从零实现
- 第 15 章 Agent 设计模式
- 第 16 章 Agent Host
