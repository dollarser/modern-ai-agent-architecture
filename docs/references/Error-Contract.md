# Agent 错误契约

本书所有可执行组件都应把“失败原因”和“是否可以重试”分开表达。异常可以在进程内部使用，但跨 Runtime、Checkpoint、Event Bus、Tool Adapter 和评估报告时，应转换为以下稳定结构：

```json
{
  "success": false,
  "error_code": "invalid_arguments",
  "error_message": "缺少必填参数: query",
  "retryable": false,
  "details": {}
}
```

## 错误分类

| `error_code` | 含义 | 默认可重试 |
|--------------|------|------------|
| `tool_not_found` | 当前能力视图中不存在 Tool | 否 |
| `invalid_arguments` | Schema、类型或业务前置条件不满足 | 否，先修正参数 |
| `policy_denied` | Policy 明确拒绝 | 否 |
| `approval_required` | 需要人工决定 | 不是自动重试 |
| `approval_expired` | 审批超时或已失效 | 否，重新请求 |
| `approval_denied` | 人工审批明确拒绝 | 否 |
| `runtime_error` | 编排、Hook、Memory 或交付链发生异常 | 否，先判断阶段和副作用 |
| `interrupted` | 到达显式暂停点 | 显式恢复原 Run |
| `handler_error` | Tool Handler 返回业务失败 | 取决于 Tool |
| `provider_timeout` | 模型或下游 Provider 超时 | 是，需幂等 |
| `cancelled` | 用户或 Runtime 取消 | 否，除非重新创建任务 |
| `checkpoint_mismatch` | 恢复时任务、能力或版本不兼容 | 否 |
| `capability_unsupported` | 当前 Provider、模型或 Adapter 不支持请求的能力 | 否，改用受支持能力或 Provider |
| `budget_exceeded` | 步数、Token、时间或费用预算耗尽 | 否 |
| `unknown_side_effect` | 下游副作用结果未知 | 否，先核对状态 |

AgentHost 遇到工具超时或恢复时未收尾的派发，返回 `status=reconciliation_required`、`error_code=unknown_side_effect`、`retryable=false`；`details.reason=execution_outcome_unknown` 保留内部原因。可信 Adapter 可通过 Host 的 `reconcile` 补录确定回执；核对时本地调用必须已结束。普通工具失败按稳定枚举归类，自由错误文本保留在 `error_message/details.reason`。这表示需要先核对下游状态，不能因为停止等待就创建新 Run 重试。

`retryable` 不是错误严重程度，而是当前错误在满足幂等、预算和恢复条件下是否允许再次尝试。Tool Registry 的 `tool_not_found`、`invalid_arguments`、`handler_error`，Provider 的 `capability_unsupported`，A2A 的权限失败和 Host 的恢复失败都应映射到同一套语义。恢复时任务不同、能力快照不同等细分原因统一映射为 `checkpoint_mismatch`，原始原因放入 `details.reason`。

> 该契约不替代具体协议的错误码；MCP、A2A 和 Provider Adapter 可以保留原始错误，但必须同时提供本书的规范化映射。
