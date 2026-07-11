# MCP Client - MCP 客户端示例

## 学习目标
理解 MCP Client 如何发现和调用 MCP Server 提供的 Tool、Server 连接管理与多 Server 聚合

## 前置知识
- 第 13 章「MCP（Model Context Protocol）」

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
模拟连接 filesystem 和 database 两个 MCP Server，列出所有可用 Tool，调用 Tool 并展示结果，最后演示断开连接。

## 相关章节
- 第 13 章 MCP（Model Context Protocol）
- 第 11 章 Tool Registry
