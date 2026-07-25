# Tool Registry - 工具注册与调度示例

## 学习目标
理解动态 Tool 注册、标签分类、关键词搜索、OpenAI 格式定义生成、参数校验、结构化错误与动态注销

## 前置知识
- 第 11 章「Tool Registry」
- 第 6 章「Tools 与 Function Calling」

## 运行方式

### Python
```bash
cd python
pip install -r requirements.txt
python main.py
python -m unittest -v test_main.py
```

### TypeScript
```bash
cd typescript
npm install
npm run start
npm test
```

## 预期输出
注册 4 个带标签的 Tool（search_web、read_file、search_files、calculate），展示按标签过滤、关键词搜索、动态注销和 OpenAI 格式定义生成；测试重复注册、必填参数、参数类型、未知参数和计算表达式安全边界。

## 相关章节
- 第 11 章 Tool Registry
- 第 6 章 Tools 与 Function Calling

本示例只负责 Registry 的注册、发现、Schema 校验和 Handler 调度，不实现 Policy、Approval、Sandbox、超时或审计。生产执行仍须经过第 9、16、17 章的 Runtime/Agent Host。
