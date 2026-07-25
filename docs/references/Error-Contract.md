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
| `handler_error` | Tool Handler 返回业务失败 | 取决于 Tool |
| `provider_timeout` | 模型或下游 Provider 超时 | 是，需幂等 |
| `cancelled` | 用户或 Runtime 取消 | 否，除非重新创建任务 |
| `checkpoint_mismatch` | 恢复时任务、能力或版本不兼容 | 否 |
| `budget_exceeded` | 步数、Token、时间或费用预算耗尽 | 否 |
| `unknown_side_effect` | 下游副作用结果未知 | 否，先核对状态 |

`retryable` 不是错误严重程度，而是当前错误在满足幂等、预算和恢复条件下是否允许再次尝试。Tool Registry 的 `tool_not_found`、`invalid_arguments`、`handler_error`，A2A 的权限失败和 Host 的恢复失败都应映射到同一套语义。

> 该契约不替代具体协议的错误码；MCP、A2A 和 Provider Adapter 可以保留原始错误，但必须同时提供本书的规范化映射。
