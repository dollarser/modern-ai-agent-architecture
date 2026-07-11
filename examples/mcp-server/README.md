# MCP Server - MCP 服务端示例

## 学习目标
理解如何实现 MCP Server、Tool 注册与暴露、MCP 协议格式的 Tool 列表与调用响应

## 前置知识
- 第 9 章「MCP（Model Context Protocol）」

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
创建一个 weather-server MCP Server，注册天气查询和预报两个 Tool，展示 Server 信息、Tool 列表和 Tool 调用结果（MCP 协议格式）。

## 相关章节
- 第 9 章 MCP（Model Context Protocol）
- 第 6 章 Tools 与 Function Calling
