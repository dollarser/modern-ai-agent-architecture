# MCP Server Manager

第 13 章的 Host 管理层参考实现，负责 Server 配置持久化、启用/禁用、连接生命周期、Tool 刷新和敏感环境变量脱敏。`connect_enabled/connectEnabled` 将已启用 Connection 交给第 16 章 Provider Adapter；Connection 同时保留 Tool 发现和调用接口，避免只能列出 Tool 却无法进入 Runtime。Fake Transport 使所有测试离线运行。

```bash
cd python
python -m unittest -v test_main.py
python main.py --config .agent/mcp.json add catalog catalog-server
python main.py --config .agent/mcp.json list
python main.py --config .agent/mcp.json disable catalog
```

真实实现应以官方 SDK 替换 Transport Factory，并补充 OAuth、超时、重连、Server 身份校验和进程沙箱。
