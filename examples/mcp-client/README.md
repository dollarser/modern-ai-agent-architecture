# MCP Client - MCP 客户端协议模型示例

> 本示例是离线协议模型，不是可连接任意真实 MCP Server 的完整 SDK Client。它用于演示 Host/Client/Server 边界、Tool 发现、命名空间和调用结果；真实传输、版本协商、OAuth、取消和重连应替换为官方 MCP SDK Adapter。

## 学习目标
理解 MCP Client 如何发现和调用 MCP Server 提供的 Tool、Server 连接管理与多 Server 聚合，并区分协议模型和生产 Transport Adapter

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
模拟连接 filesystem 和 database 两个 MCP Server，列出所有可用 Tool，调用 Tool 并展示结果，最后演示断开连接。代码不声称实现当前 MCP 传输或授权兼容性。

## 相关章节
- 第 13 章 MCP（Model Context Protocol）
- 第 11 章 Tool Registry
