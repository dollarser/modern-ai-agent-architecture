# MCP Server - MCP 服务端协议模型示例

> 本示例使用标准 JSON-RPC 形状演示 MCP Server 的 Tool 注册、列表和调用响应，但不启动真实 stdio/Streamable HTTP 端点。生产 Server 应使用官方 MCP SDK，并补充版本协商、输入校验、授权、取消、日志和进程隔离。

## 学习目标
理解 MCP Server 的 Tool 注册与暴露、协议消息形状，以及离线协议模型与真实 SDK 实现的边界

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
创建一个 weather-server 协议模型，注册天气查询和预报两个 Tool，展示 Server 信息、Tool 列表和 Tool 调用结果（MCP 消息格式）。它不是可直接部署的 MCP Server。

## 相关章节
- 第 13 章 MCP（Model Context Protocol）
- 第 6 章 Tools 与 Function Calling

## 协议版本边界（2026-10-26）

当前 MCP 正文基线为 `2026-07-28`；本示例仍是离线教学模型，没有验证新版逐请求元数据、MRTR、真实 HTTP / stdio 或旧版回退。修改版本常量不构成协议升级。生产替换须选择支持目标版本的 SDK，并分别验证版本探测、认证、取消、断流和未知副作用；参考[官方版本兼容规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)。
