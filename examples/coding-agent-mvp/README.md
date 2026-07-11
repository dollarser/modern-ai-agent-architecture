# Coding Agent MVP - 编程 Agent 完整组合版

## 学习目标
在读完第 8--11 章后，观察轻量 Memory、Tool 映射和回调如何与 Reasoning、Planning、Tool Calling 组合。第 7 章的首个可运行闭环请使用 `examples/agent-mvp-minimal/`。

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
展示一个完整的编程 Agent 生命周期：接收任务、制定计划、调用工具（文件读写、代码执行）、管理上下文、输出最终结果。

## 相关章节
- 第 7 章 Agent MVP：从零实现
- 第 15 章 Agent 设计模式
- 第 16 章 增强版 Agent
