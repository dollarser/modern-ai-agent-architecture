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

## 协议版本边界（2026-10-26）

当前 MCP 正文基线为 `2026-07-28`；本示例仍是离线教学模型，没有验证新版逐请求元数据、MRTR、真实 HTTP / stdio 或旧版回退。修改版本常量不构成协议升级。生产替换须选择支持目标版本的 SDK，并分别验证版本探测、认证、取消、断流和未知副作用；参考[官方版本兼容规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)。
