# 第 17 章：工程实践与生产部署

> **维护边界：** 本章只补充生产环境的安全、供应链、可观测性、部署与运维约束；Hook 机制以第 10 章为准，评估反模式以第 18 章为准。

> **难度等级：** ⭐⭐⭐⭐
> **所属模块：** 第五部分：规模化与生产
> **来源可信度：** 官方文档 / 源码 / 推导 / 观点
> **状态：** ✅ 已完成

---

## 学习目标

完成本章学习后，你将能够：

1. 掌握 Agent 项目的工程化实践
2. 理解 Agent 的测试策略和质量保证
3. 掌握 Agent 的安全设计和权限控制
4. 理解 Agent 的部署方案和运维监控
5. 掌握成本控制和性能优化

---

## 前置知识

- 建议完成第 7 章 MVP；生产实现还应理解第 8--16 章中的状态、运行时、扩展与增强能力
- 了解 CI/CD、Docker、Kubernetes 基本概念
- 了解测试驱动开发（TDD）

---

## 1. 工程化实践

### 1.1 项目结构

```
agent-project/
├── src/
│   ├── core/           # Agent 核心
│   ├── tools/          # Tool 实现
│   ├── memory/         # Memory 管理
│   ├── hooks/          # Hook 系统
│   ├── skills/         # Skill 模板
│   ├── mcp/            # MCP 集成
│   └── llm/            # LLM 接口
├── tests/
│   ├── unit/           # 单元测试
│   ├── integration/    # 集成测试
│   └── e2e/            # 端到端测试
├── config/
│   ├── dev.yaml        # 开发环境
│   ├── staging.yaml    # 预发布环境
│   └── prod.yaml       # 生产环境
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── k8s/
├── scripts/
│   ├── setup.sh
│   └── migrate.sh
├── docs/
├── .github/workflows/
├── Makefile
├── pyproject.toml
└── README.md
```

### 1.2 配置管理

```python
"""
配置管理 - 多环境支持
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentDeployConfig:
    """Agent 部署配置"""
    # LLM
    llm_provider: str = "provider-name"
    llm_model: str = "provider-configured-model"
    llm_api_key_env: str = "LLM_API_KEY"

    # Runtime
    max_steps: int = 10
    step_timeout: float = 30.0
    total_timeout: float = 300.0

    # Memory
    memory_backend: str = "sqlite"
    memory_path: str = "data/memory.db"

    # Tool
    max_parallel_tools: int = 5
    tool_cache_size: int = 128

    # Security
    allowed_tools: list[str] = field(default_factory=list)
    require_user_approval: bool = True
    sandbox_enabled: bool = True


class ConfigLoader:
    """配置加载器"""

    @staticmethod
    def load(env: str = "dev") -> AgentDeployConfig:
        config_path = f"config/{env}.yaml"
        if os.path.exists(config_path):
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return AgentDeployConfig(**data)
        return AgentDeployConfig()  # 默认配置
```

---

## 2. 测试策略

### 2.1 测试金字塔

```
         ╱─────╲
        ╱  E2E  ╲        少量端到端测试
       ╱─────────╲
      ╱ Integration╲     中等集成测试
     ╱───────────────╲
    ╱   Unit Tests    ╲   大量单元测试
   ╱───────────────────╲
```

### 2.2 单元测试

单元测试应针对稳定契约，而不是复制某一章已经淘汰的组合类。第 7 章最小示例使用标准库 `unittest`，测试直接导入同目录的真实实现：

```python
import unittest

from main import MinimalAgent, TaskState, ToolCall, ToolDispatcher


class MinimalAgentTest(unittest.TestCase):
    def test_success_contract(self):
        state = MinimalAgent().run("查找数据库连接配置")
        self.assertTrue(state.finished)
        self.assertIsNone(state.error)
        self.assertEqual(state.step_count, 2)

    def test_limit_is_not_success(self):
        state = MinimalAgent(max_steps=1).run("查找数据库连接配置")
        self.assertFalse(state.finished)
        self.assertEqual(state.error, "达到最大步数: 1")

    def test_unknown_tool_is_structured_failure(self):
        result = ToolDispatcher().execute(
            ToolCall("missing_tool", {}), TaskState(task="test")
        )
        self.assertFalse(result["ok"])
```

对应的唯一事实来源是 `examples/agent-mvp-minimal/python/test_main.py`。Memory、Hooks 和 Tool Registry 应分别测试各章定义的接口，不要为了测试方便重新创造一个同时拥有所有组件的旧版 `AgentMVP`。

### 2.3 集成测试

集成测试关注跨组件契约和状态迁移。第 16 章可运行示例覆盖中断后由新实例恢复，以及重试耗尽不得误报成功：

```python
import asyncio
import tempfile
from pathlib import Path

from main import AgentConfig, AutoApproveGate, DatabaseReviewAgent


def test_checkpoint_resume():
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "cp.json"
        task = "查找数据库配置"

        first = asyncio.run(DatabaseReviewAgent(
            checkpoint,
            AgentConfig(interrupt_after_steps=1),
            approval=AutoApproveGate(),
        ).run(task, "session-1"))
        second = asyncio.run(
            DatabaseReviewAgent(
                checkpoint,
                approval=AutoApproveGate(),
            ).run(task, "session-1")
        )

        assert first["status"] == "interrupted"
        assert second["success"] is True
        assert second["resumed"] is True
```

这里显式注入 `AutoApproveGate` 仅用于确定性的测试环境。第 16 章的生产安全默认值是拒绝高风险操作；生产代码应替换为真实审批实现，不能复制测试门禁。

对应的完整测试位于 `examples/agent-host/python/test_main.py` 和 `examples/agent-host/typescript/test.ts`。测试层次建议如下：

| 层次 | 隔离边界 | 重点断言 |
|------|----------|----------|
| Unit | Adapter、Planner、Tool、Policy、序列化器 | schema、纯函数结果、拒绝规则、错误映射 |
| Integration | Runtime + Registry + Checkpoint Store | 状态迁移、恢复位置、依赖顺序、幂等键 |
| Extension integration | Skill/Plugin Installer + MCP Manager + Runtime | 原子安装、配置恢复、启动注册、禁用/卸载清理、失败回滚 |
| E2E | 固定模型版本 + 沙箱 + 测试外部系统 | 最终结果、轨迹约束、权限、成本与延迟预算 |

运行仓库中的真实契约测试：

```bash
python -m unittest discover -s examples/agent-mvp-minimal/python -p 'test_*.py' -v
python -m unittest discover -s examples/runtime/python -p 'test_*.py' -v
python -m unittest discover -s examples/hooks/python -p 'test_*.py' -v
python -m unittest discover -s examples/agent-host/python -p 'test_*.py' -v
python -m unittest discover -s examples/skills/python -p 'test_*.py' -v
python -m unittest discover -s examples/mcp-manager/python -p 'test_*.py' -v
python -m unittest discover -s examples/plugin-manager/python -p 'test_*.py' -v
npm --prefix examples/runtime/typescript test
npm --prefix examples/hooks/typescript test
npm --prefix examples/agent-host/typescript test
```

---

## 3. 安全设计

### 3.1 安全原则

| 原则 | 说明 | 实现 |
|------|------|------|
| 最小权限 | Agent 只拥有完成任务所需的最小权限 | Tool 白名单 |
| 用户确认 | 敏感操作需用户确认 | 权限 Hook |
| 沙箱隔离 | Agent 在受限环境中运行 | Docker 容器 |
| 输入校验 | 校验所有外部输入 | 参数 Schema 校验 |
| 审计日志 | 记录所有关键操作 | 日志 Hook |
| 密钥管理 | 不在代码中硬编码密钥 | 环境变量/密钥管理服务 |

对于 Coding Agent，Sandbox 不只是 Docker 是否存在，还包括工作区快照、网络出口、Secret 挂载和资源配额。建议至少明确以下四类边界：

本书提供的 [SandboxProfile 契约测试](https://github.com/dollarser/modern-ai-agent-architecture/tree/main/examples/agent-host) 将四类边界压缩为可审查配置：Workspace、Process、Network、Secrets。它只验证配置是否显式、默认拒绝和 Secret 不进入日志；真正的 namespace、seccomp、网络防火墙、进程树终止和 Secret 注入仍必须由运行环境强制执行。

| 边界 | 需要冻结的内容 | 典型失败语义 |
|------|----------------|--------------|
| Workspace | 根目录、读写路径、符号链接和 Snapshot | 越界拒绝，不能回退到宿主目录 |
| Process | 可执行文件、参数、进程树和超时 | 终止进程树并记录未知副作用 |
| Network | 域名、端口、代理和出站凭据 | 默认拒绝或转审批 |
| Secrets | 可见 Secret、挂载位置、生命周期 | 不进入 Prompt、日志、Trace 或 Artifact |

浏览器、Computer Use 和 Realtime Agent 也应沿用同一模型：截图/音频属于 Observation，鼠标键盘/语音动作属于高风险 Tool，页面域名、设备和麦克风权限属于 Policy 与 Sandbox 边界，不应因为输入从文本变成视觉或语音就绕过审批。

### 3.2 权限系统

```python
class PermissionSystem:
    """权限系统"""

    def __init__(self):
        self._permissions: dict[str, set[str]] = {}  # role -> {permissions}
        self._tool_permissions: dict[str, str] = {}   # tool -> required_permission

    def set_role_permissions(self, role: str, permissions: set[str]):
        self._permissions[role] = permissions

    def set_tool_permission(self, tool: str, permission: str):
        self._tool_permissions[tool] = permission

    def check(self, role: str, tool: str) -> bool:
        """检查角色是否有权限使用 Tool"""
        required = self._tool_permissions.get(tool)
        if not required:
            return False  # 未注册策略的 Tool 默认拒绝
        return required in self._permissions.get(role, set())

    def create_permission_hook(self, role: str):
        """创建权限检查 Hook"""
        def hook(ctx):
            tool_name = ctx.data.get("tool_name", "")
            if not self.check(role, tool_name):
                raise PermissionError(f"角色 '{role}' 无权使用 Tool '{tool_name}'")
        return hook
```

权限表采用 fail-closed：Tool 必须先注册所需权限，再由角色显式获得该权限。确需匿名访问的只读 Tool，也应注册明确的 `public` 策略，而不是依靠“没有配置即允许”。

#### 身份、认证、授权与委派

| 对象/阶段 | 含义 | 关键约束 |
|-----------|------|----------|
| User Identity | 发起或批准操作的人 | 与租户、组织和当前 Session 绑定 |
| Agent Identity | Agent 定义及其运行身份 | 不是用户身份的复制品 |
| Run Identity | 某次 Agent/Subagent 执行 | 带父子关系、预算和 Trace |
| Service Identity | Connector/MCP Server 访问下游的服务主体 | Credential 不可进入 Prompt |
| Credential | 证明身份的 Secret、Token 或证书 | 只保存引用，最小 Scope、短期和可轮换 |
| Delegation Grant | 上游主体授予子 Run 的有限权限 | 只能收窄，带资源范围与过期时间 |

Authentication 证明“是谁”，Authorization 判断“该身份是否可访问资源”，Policy 将身份、主体、参数、环境和风险组合成 `allow/ask/deny`，Approval 只处理 `ask` 的决定。Agent 使用用户授权不表示 Agent 就是用户；Subagent 也不得自动继承父 Run 的全部 Credential、Tool 或网络范围。

### 3.3 沙箱执行

```python
class SandboxExecutor:
    """沙箱执行器"""

    def __init__(self, allowed_paths: list[str] = None,
                 allowed_commands: list[str] = None,
                 max_file_size: int = 10 * 1024 * 1024):
        self.allowed_paths = (
            allowed_paths if allowed_paths is not None else ["/tmp", "./workspace"]
        )
        self.allowed_commands = (
            allowed_commands if allowed_commands is not None
            else ["ls", "cat", "grep", "find"]
        )
        self.max_file_size = max_file_size

    def validate_path(self, path: str) -> bool:
        """验证路径是否在允许范围内"""
        import os
        real_path = os.path.realpath(path)
        return any(real_path == os.path.realpath(p) or real_path.startswith(os.path.realpath(p) + os.sep)
                   for p in self.allowed_paths)

    def validate_command(self, command: str) -> bool:
        """验证命令是否允许"""
        if not command:
            return False
        parts = command.split()
        cmd_name = parts[0]
        # 检查是否包含命令分隔符
        if any(sep in command for sep in [';', '|', '&', '&&', '||']):
            return False
        return cmd_name in self.allowed_commands

    def validate(self, tool_name: str, args: dict) -> dict:
        """验证工具调用是否安全（不执行实际操作）"""
        if tool_name == "read_file":
            if not self.validate_path(args.get("path", "")):
                return {"success": False, "error": "路径不在允许范围内"}
        elif tool_name == "execute_command":
            if not self.validate_command(args.get("command", "")):
                return {"success": False, "error": "命令不允许"}
        return {"success": True}
```

### 3.4 Guardrails：贯穿执行路径的控制

Guardrails 不是只在 System Prompt 中写一条“请遵守规则”，而是一组分布在输入、模型、Tool 和输出边界上的可执行控制。它们应与权限系统、Hook、Sandbox 和审计日志配合；任一单点都不能完整防御提示注入、越权调用或敏感信息泄露。

| 边界 | 主要风险 | 推荐控制 | 失败后的默认行为 |
|------|----------|----------|------------------|
| 外部输入与检索内容 | 提示注入、恶意指令、错误来源 | 标记不可信数据、隔离指令与数据、来源校验 | 不提升权限，不把内容当作系统指令 |
| 模型输出 | 格式错误、敏感内容、虚构调用 | 结构化 Schema 校验、内容策略、人工复核阈值 | 拒绝执行或要求模型修正 |
| Tool 调用 | 越权、破坏性操作、数据外传 | 参数校验、最小权限、用户确认、速率限制 | 拒绝、降级为只读或转人工 |
| Sandbox 与网络 | 路径逃逸、命令注入、资源耗尽 | 文件/网络隔离、命令白名单、CPU/内存/时间限制 | 终止执行并记录审计事件 |
| 最终输出与日志 | 泄露凭据、个人数据或内部内容 | 输出脱敏、字段级日志过滤、保留期控制 | 隐藏敏感字段并提示用户 |

对每个高风险 Tool，应把“允许、需要确认、拒绝”设计为可测试的策略，而不是依赖模型自行判断。第 10 章的 Guard Hook 可以作为调用 Policy 的生命周期挂载点，但不能成为唯一授权边界；第 6 章的 Schema 承载参数约束，第 9 章的 Runtime 负责在 Handler 前强制执行决定，并把拒绝、超时和取消变成一致终态。

> **来源类型：** 推导分析 —— 基于纵深防御原则和本书 Tool、Hook、Runtime、Sandbox 的职责划分

#### 统一安全控制链

```mermaid
flowchart LR
    Request["Agent Tool Request"] --> Guard["Input Guardrail<br/>参数与内容检查"]
    Guard --> Policy["Policy Engine<br/>allow / ask / deny"]
    Policy -->|deny| Reject["结构化拒绝"]
    Policy -->|ask| Approval["Approval Adapter<br/>用户或工作流决定"]
    Policy -->|allow| Runtime["Runtime"]
    Approval -->|批准且请求未变化| Runtime
    Approval -->|拒绝/超时| Reject
    Runtime --> Hook["Guard Hook<br/>生命周期挂载点"]
    Hook --> Sandbox["Sandbox<br/>资源隔离与硬限制"]
    Sandbox --> Handler["Tool Handler"]
    Handler --> Output["Output Guardrail<br/>脱敏与契约校验"]
    Output --> Audit["Trace / Audit"]
```

> **图 17-2：** 生产安全控制的唯一职责链。第 10 章只说明 Hook 如何挂载 Guard/Observer，第 18 章只保留检查清单；Hook 是挂载机制，不天然是安全控制，Sandbox 也不能被上层批准关闭。

| 概念 | 回答的问题 | 失败语义 |
|------|------------|----------|
| Policy | 当前主体对具体资源和参数是 allow、ask 还是 deny？ | 规则冲突或引擎错误默认拒绝 |
| Approval | 如何取得并持久化 `ask` 的决定？ | 拒绝、超时或请求变化均不得执行 |
| Guardrail | 输入、模型输出、Tool 和最终输出是否满足可执行约束？ | 安全 Guardrail fail-closed |
| Hook | 在哪个生命周期点运行 Guard 或 Observer？ | Guard 失败阻断；Observer 失败隔离并告警 |
| Sandbox | 即使上层判断错误，进程实际能访问哪些资源？ | 越界由执行环境强制终止 |

因此 `Approval ≠ Authorization`、`Hook ≠ Guardrail`、`Policy ≠ Prompt Rule`、`Sandbox ≠ Tool Allowlist`。审批应绑定规范化 Tool 名、最终参数、资源预览、主体、能力快照、过期时间和幂等键；任一绑定值变化都需要重新决策。

### 3.5 Human-in-the-Loop：审批不是一次弹窗

人工介入（Human-in-the-Loop）适用于写文件、执行命令、访问敏感数据、发送外部请求等后果不可逆或难以撤回的动作。审批请求应是 Runtime 可持久化的状态，而不是临时 UI 分支：用户批准、拒绝、超时或会话恢复后都应能得到确定结果。

| 状态 | Runtime 行为 | 审计信息 |
|------|--------------|----------|
| Pending | 暂停受保护动作，不继续执行依赖步骤 | 操作摘要、参数摘要、风险和请求时间 |
| Approved | 在原有权限范围内恢复执行 | 审批人、时间、批准范围 |
| Rejected | 返回结构化拒绝，让 Agent 选择安全替代方案 | 拒绝原因与后续处理 |
| Expired / Cancelled | 终止或重新请求，不默认为批准 | 超时/取消来源与状态快照 |

审批 UI 应让用户理解“将要做什么、影响什么、使用什么数据”，而不只显示 Tool 名称。对于批量或可重复动作，可设计有范围和有效期的审批；不得把一次批准升级成无边界的长期权限。

> **来源类型：** 推导分析 —— 参考 [OpenAI Agents SDK 的 Human-in-the-Loop 文档](https://openai.github.io/openai-agents-python/human_in_the_loop/) 及本书 Runtime/Guardrails 的设计原则

### 3.6 扩展供应链与运行时信任

Skill、Plugin 和 MCP Server 都可能把新的指令、Tool、脚本或网络访问能力带入 Host。安装成功不代表运行时可信，也不代表当前用户已经授权。建议把扩展治理拆成四个阶段：

```text
发现 → 验证来源与完整性 → 安装到隔离位置 → 运行时重新授权
```

| 阶段 | 至少检查什么 | 失败语义 |
|------|--------------|----------|
| 发现 | 来源、发布者、版本、依赖和声明能力 | 不进入候选目录 |
| 验证 | 签名/校验和、锁文件、SBOM、已知漏洞 | 拒绝安装或标记不可信 |
| 安装 | 目标路径、覆盖范围、脚本和网络权限 | 原子回滚，不留下半安装状态 |
| 运行 | Tool Policy、用户身份、租户、参数和 Sandbox | 逐次 `allow / ask / deny` |
| 更新/撤销 | 版本迁移、撤销列表、凭据失效和正在运行的 Run | 新 Run 不再加载，旧 Run 按策略终止或冻结 |

扩展的 Tool 描述、注释和 README 都应视为不可信输入，不能把“描述自己是只读”当作安全证明。最终的文件、网络、进程和凭据边界必须由 Host Policy 与 Sandbox 强制执行。Trace 中只记录来源引用、版本和摘要，不默认记录扩展携带的全部源码、Secret 或用户数据。

教学实现也应验证“安装后内容没有被静默篡改”：`SkillCatalog.verify_integrity()` 和 `PluginCatalog.verify_integrity()` 会重新计算安装目录的校验和；Plugin 另提供 `revoke()` 的禁用语义。它们不是签名验证或全球撤销服务，但可以把来源、校验和变化、权限拒绝、原子替换和撤销变成回归测试，而不是只停留在表格里。

> **来源类型：** Fact + 推导分析 —— MCP 规范明确提醒 Tool 可能代表任意代码执行，Tool 注释在非可信来源下不能直接视为安全依据；签名、SBOM、撤销和沙箱属于本书的生产治理建议。

---

## 4. 部署方案

```mermaid
graph TD
    A[代码提交] --> B[CI 阶段]
    subgraph CI["CI 流水线"]
        B --> C[Lint / 类型检查]
        C --> D[单元测试]
        D --> E[集成测试]
        E --> F[Docker 构建]
        F --> G[安全扫描]
    end
    G --> H{全部通过?}
    H -->|否| X["❌ 阻止合并"]
    H -->|是| I[CD 阶段]
    subgraph CD["CD 流水线"]
        I --> J[Staging 部署]
        J --> K[冒烟测试]
        K --> L[Canary 发布]
        L --> M[生产部署]
    end
    M --> N{Canary 健康?}
    N -->|否| O["🔄 自动回滚"]
    N -->|是| P["✅ 发布完成"]
```

> **图 17-1：** CI/CD 流水线全景。构建、测试和安全扫描失败会阻止发布；生产流量只在 Staging、冒烟测试和 Canary 健康检查通过后逐步放开。

### 4.1 Docker 部署

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system agent && useradd --system --gid agent --home /app agent

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt

COPY --chown=agent:agent src/ ./src/
COPY --chown=agent:agent config/ ./config/

ENV AGENT_ENV=prod PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1

USER agent

CMD ["python", "-m", "src.main"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  agent:
    build: .
    environment:
      - AGENT_ENV=prod
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
    secrets:
      - openai_api_key
    volumes:
      - ./data:/app/data
      - ./workspace:/app/workspace
    read_only: true
    tmpfs:
      - /tmp:size=128m,noexec,nosuid,nodev
    cap_drop: [ALL]
    security_opt:
      - no-new-privileges:true
    pids_limit: 256
    mem_limit: 1g
    cpus: 1.0
    restart: unless-stopped

  agent-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8080:8080"
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
    secrets:
      - openai_api_key
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    read_only: true
    cap_drop: [ALL]
    security_opt:
      - no-new-privileges:true
    networks: [frontend, backend]

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks: [backend]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=agent
      - POSTGRES_USER=agent
      - POSTGRES_PASSWORD_FILE=/run/secrets/db_password
    secrets:
      - db_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d agent"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks: [backend]

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key
  db_password:
    file: ./secrets/db_password

networks:
  frontend: {}
  backend:
    internal: true

volumes:
  postgres_data:
```

`*_FILE` 只是常见的容器 Secret 注入约定，应用必须显式读取对应文件；生产编排应优先使用云 Secret Manager、Kubernetes Secret CSI 或同类短期凭据机制。Compose 示例中的本地 Secret 文件不得提交到版本库。绑定的业务目录仍是显式可写例外，应配合工作区级路径策略；其余根文件系统保持只读。

### 4.2 部署检查清单

| 检查项 | 说明 |
|--------|------|
| ✅ 环境变量配置 | API Key、数据库密码等通过环境变量注入 |
| ✅ 健康检查 | 提供 `/health` 端点 |
| ✅ 日志收集 | 结构化日志，输出到 stdout |
| ✅ 指标暴露 | Prometheus metrics 端点 |
| ✅ 优雅关闭 | 处理 SIGTERM，完成当前任务后退出 |
| ✅ 资源限制 | CPU/内存限制，防止资源耗尽 |
| ✅ 网络策略 | 限制出站/入站流量 |
| ✅ 备份策略 | 定期备份 Memory 和 Checkpoint |
| ✅ 非 root 与最小能力 | `USER`、只读根文件系统、`cap_drop`、`no-new-privileges` |
| ✅ Secret 生命周期 | 不提交 Secret 文件；使用短期凭据、轮换与 Secret Manager |
| ✅ 供应链 | 锁定依赖 Hash 和基础镜像 Digest，生成 SBOM 并执行镜像签名/扫描 |

---

## 5. 监控与可观测性

### 5.1 关键指标

| 指标 | 类型 | 说明 |
|------|------|------|
| agent_step_count | Counter | Agent 执行步数 |
| tool_call_count | Counter | Tool 调用次数 |
| tool_call_latency | Histogram | Tool 调用延迟 |
| tool_error_count | Counter | Tool 错误次数 |
| llm_token_usage | Counter | LLM Token 使用量 |
| agent_run_duration | Histogram | Agent 运行时长 |
| memory_entries | Gauge | Memory 条目数 |
| circuit_breaker_state | Gauge | 熔断器状态 |

### 5.2 结构化日志

```python
import structlog

logger = structlog.get_logger()

class StructuredLogger:
    """结构化日志"""

    @staticmethod
    def log_agent_start(run_id: str, task: str):
        logger.info("agent_start", run_id=run_id, task=task[:200])

    @staticmethod
    def log_tool_call(run_id: str, tool: str, args: dict, duration: float):
        logger.info("tool_call", run_id=run_id, tool=tool,
                     args_summary=str(args)[:200], duration_ms=duration * 1000)

    @staticmethod
    def log_tool_error(run_id: str, tool: str, error: str):
        logger.error("tool_error", run_id=run_id, tool=tool, error=error)

    @staticmethod
    def log_agent_finish(run_id: str, success: bool, steps: int, duration: float):
        logger.info("agent_finish", run_id=run_id, success=success,
                     steps=steps, duration_s=duration)
```

### 5.3 Trace、回放与数据最小化

可观测性不仅是“多打日志”。一次可诊断的 Agent Trace 至少需要关联任务版本、模型/Prompt 版本、Tool 调用、审批决定、重试和最终结果，才能区分模型、上下文、Tool 或策略导致的问题。回放应优先使用脱敏或合成数据；若必须使用生产上下文，应限制访问、记录审批并设定保留期，避免 Trace 本身成为新的敏感数据源。

---

## 6. 成本控制

### 6.1 成本优化策略

| 策略 | 说明 | 主要影响与验证方式 |
|------|------|---------|
| 模型选择 | 简单任务用较低成本模型，复杂任务使用高能力模型 | 先以任务质量基线验证路由是否损害结果 |
| 上下文压缩 | 压缩历史消息 | 输入 Token 与延迟可能下降，需检查信息损失 |
| Tool 结果视图 | 大结果进入 Artifact，只向 Context 注入有界摘要/分页视图 | 减少输入量，同时保留来源、校验和与按需读取能力 |
| 缓存复用 | 在时效与权限允许时复用相同查询 | 减少重复下游调用，需防止过期或越权复用 |
| 批处理 | 合并独立请求 | 可减少连接和调度开销，未必降低 Token 成本 |

### 6.2 Token 使用追踪

```python
class TokenTracker:
    """Token 使用追踪"""

    def __init__(self, budget: int = 1000000):
        self.budget = budget
        self.used = 0
        self.calls = 0

    def record(self, prompt_tokens: int, completion_tokens: int):
        self.used += prompt_tokens + completion_tokens
        self.calls += 1

    def remaining(self) -> int:
        return max(0, self.budget - self.used)

    def is_over_budget(self) -> bool:
        return self.used >= self.budget

    def cost_estimate(self, price_per_token: float) -> float:
        """价格由当前模型与区域的计费元数据传入，不在代码中硬编码。"""
        return self.used * price_per_token
```

---

## 7. 最佳实践

1. **配置即代码：** 所有配置通过 YAML/环境变量管理，纳入版本控制。
2. **测试驱动：** 核心路径必须有测试覆盖，变更前先写测试。
3. **安全左移：** 在开发阶段就考虑安全，而非上线后补救。
4. **可观测性内置：** 日志、指标、追踪从第一天就集成。
5. **渐进式发布：** 使用 Canary/Blue-Green 部署，逐步引流。

---

## 8. 官方参考

| 编号 | 来源 | 类型 | 说明 |
|------|------|------|------|
| REF-1 | [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/) | 官方文档 | Docker 部署最佳实践 |
| REF-2 | [OpenAI Rate Limits](https://platform.openai.com/docs/guides/rate-limits) | 官方文档 | API 速率限制 |
| REF-3 | [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | 社区 | LLM 安全风险 |

---

## 本章小结

生产化的重点从“能运行”转向“可控制、可观察、可恢复”。权限、沙箱、密钥、日志、追踪、部署和成本控制需要形成纵深防御；高风险动作保留明确的人类决策点，且日志与回放本身也必须遵循最小化和访问控制。

---

## 本章 Checklist

- [ ] 理解 Agent 项目的工程化结构
- [ ] 能编写单元测试、集成测试和 E2E 测试
- [ ] 理解安全设计原则和权限系统
- [ ] 能使用 Docker 部署 Agent
- [ ] 理解监控指标和成本控制策略
- [ ] 运行了测试示例代码
