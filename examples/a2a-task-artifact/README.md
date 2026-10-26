# A2A Task / Artifact 契约

这是一个不依赖网络的协议模型示例，用最小的内存实现演示 A2A 风格的 `Agent Card → Task → Status Update → Artifact` 链路。

示例刻意不伪装成完整 HTTP A2A Server：它关注跨系统协作必须保留的任务状态、幂等、结果引用和访问控制边界，真实传输层可替换为 JSON-RPC、HTTP、Streaming 或 Push Notification。

```bash
# Python
cd examples/a2a-task-artifact/python
python -m unittest -v
python main.py

# TypeScript
cd ../typescript
npm install
npm test
```

覆盖的契约：

- 重复 `task_id` / 幂等键不会重复创建任务；
- `submitted`、`working` 和 `completed` 不混淆；
- 大型结果写入 Artifact Store，Task 只保存引用；
- Artifact 读取需要匹配调用方和租户；
- 取消请求不能伪装成下游副作用已撤销。

## 可选远程 Adapter 边界

本例不内置 HTTP/Streaming 客户端，以保持零依赖和可重复测试。生产接入可以实现 `RemoteTaskClient`，将 `submit`、`getTask`、`getArtifact` 映射到 A2A JSON/HTTP、Streaming 或 Push Notification；Adapter 必须把认证、租户、幂等键、断线重连、超时和原始协议错误映射到 Agent Host 的统一 Error Contract。不要把内存模型直接宣称为网络互操作测试。

## v1.0 线格式边界（2026-10-26）

示例的 `AgentCard`、`task_id` 和小写状态是内部教学对象，不是官方 v1.0 JSON DTO。真实 Adapter 应按所选接口的 `protocolVersion / protocolBinding` 映射字段、ProtoJSON 枚举和消息包装；例如完成状态使用 `TASK_STATE_COMPLETED`。本例没有进行跨 SDK 或远程协议兼容测试，详见[A2A 官方规范](https://a2a-protocol.org/latest/specification/)。
