# Memory - Agent 记忆管理示例

## 学习目标
理解短期记忆、长期记忆、租户与主体隔离、同意/来源/信任/保留期，以及上下文 Token 预算和 Artifact View

## 前置知识
- 第 4 章「Context 管理」
- 第 8 章「Memory」

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
# 契约测试
npm test
```

## 预期输出
模拟对话流程，展示短期记忆的添加与摘要、长期记忆的保存与检索、Token 使用量估算和上下文窗口限制检查；契约测试验证 Memory 治理字段、保留期、租户隔离、Artifact View 与确定性历史裁剪。

## 相关章节
- 第 4 章 Context 管理
- 第 8 章 Memory
