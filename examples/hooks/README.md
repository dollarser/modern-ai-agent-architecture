# Hooks - Agent 生命周期钩子示例

## 学习目标
理解 Before/After Hook 机制、Hook 注册与触发、权限检查与计时拦截器

## 前置知识
- 第 10 章「Hooks」
- 第 2 章「总体架构与生命周期」

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
展示 Agent 生命周期中的关键 Hook：允许列表内的 Tool 正常执行并脱敏结果，未授权 Tool 在 Handler 前被阻止；观测 Hook 失败会记录但不影响业务结果。

契约测试覆盖 Guard 拦截、After Hook 结果传播和观测失败隔离：

```bash
python -m unittest -v python/test_main.py
npm --prefix typescript test
```

## 相关章节
- 第 10 章 Hooks
- 第 17 章 工程实践
