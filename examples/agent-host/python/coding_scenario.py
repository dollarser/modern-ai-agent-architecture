"""受限工作区 Coding Agent 教学场景。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from assembly import AgentConfig, AgentHost, ExecutionContext, LLMAdapter, PlanStep, Tool


class CodingPlanAdapter(LLMAdapter):
    """离线确定性计划；真实模型适配器必须生成相同的受治理 Tool 调用。"""

    async def create_plan(
        self, task: str, tool_names: list[str], context: list[str]
    ) -> list[PlanStep]:
        required = {"list_files", "read_file", "search_code", "apply_patch", "run_check", "report_change"}
        missing = sorted(required.difference(tool_names))
        if missing:
            raise ValueError(f"编码计划所需 Tool 未注册: {missing}")
        return [
            PlanStep(1, "列出工作区文件", "list_files"),
            PlanStep(2, "读取目标文件", "read_file", {"path": "calculator.py"}, [1]),
            PlanStep(3, "搜索待修改符号", "search_code", {"query": "def add"}, [1]),
            PlanStep(4, "应用最小补丁", "apply_patch", {
                "path": "calculator.py",
                "old": "def add(a, b):\n    return a - b\n",
                "new": "def add(a, b):\n    return a + b\n",
            }, [2, 3]),
            PlanStep(5, "运行白名单测试", "run_check", {"check": "unit"}, [4]),
            PlanStep(6, "汇报变更与验证结果", "report_change", {}, [4, 5]),
        ]

    async def final_answer(self, task: str, results: dict[int, dict[str, Any]]) -> str:
        return str(results.get(6, {}).get("report", f"任务未完成：{task}"))


class Workspace:
    """将所有文件能力限制在一个已解析的工作区根目录内。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("工作区必须是目录")

    def resolve(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve(strict=False)
        if candidate == self.root or self.root not in candidate.parents:
            raise PermissionError(f"路径越过工作区: {relative}")
        # 已存在文件必须再次 strict 解析，以阻断指向工作区外的符号链接。
        if candidate.exists() and self.root not in candidate.resolve(strict=True).parents:
            raise PermissionError(f"符号链接越过工作区: {relative}")
        return candidate

    def list_files(self) -> list[str]:
        files: list[str] = []
        for item in self.root.rglob("*"):
            if item.is_file():
                resolved = item.resolve(strict=True)
                if self.root in resolved.parents:
                    files.append(item.relative_to(self.root).as_posix())
        return sorted(files)


def install_coding_tools(host: AgentHost, workspace: Workspace) -> None:
    def read(arguments: dict[str, Any], _context: ExecutionContext) -> dict[str, Any]:
        path = workspace.resolve(str(arguments["path"]))
        return {"success": True, "path": path.relative_to(workspace.root).as_posix(), "content": path.read_text("utf-8")}

    def search(arguments: dict[str, Any], _context: ExecutionContext) -> dict[str, Any]:
        query = str(arguments["query"])
        matches: list[dict[str, Any]] = []
        for relative in workspace.list_files():
            path = workspace.resolve(relative)
            try:
                lines = path.read_text("utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            matches.extend({"path": relative, "line": number} for number, line in enumerate(lines, 1) if query in line)
        return {"success": True, "matches": matches}

    def patch(arguments: dict[str, Any], _context: ExecutionContext) -> dict[str, Any]:
        path = workspace.resolve(str(arguments["path"]))
        old, new = str(arguments["old"]), str(arguments["new"])
        content = path.read_text("utf-8")
        if content.count(old) != 1:
            return {"success": False, "error": "补丁旧文本必须且只能匹配一次"}
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content.replace(old, new, 1), "utf-8")
        temporary.replace(path)
        return {"success": True, "path": str(arguments["path"]), "changed": True}

    async def check(arguments: dict[str, Any], _context: ExecutionContext) -> dict[str, Any]:
        if arguments.get("check") != "unit":
            return {"success": False, "error": "检查命令不在白名单"}
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "unittest", "-q", cwd=workspace.root,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return {
            "success": process.returncode == 0, "exit_code": process.returncode,
            "stdout": stdout.decode(errors="replace"), "stderr": stderr.decode(errors="replace"),
        }

    host.tools.register(Tool("list_files", "列出工作区文件", lambda _args, _ctx: {"success": True, "files": workspace.list_files()}, tags=("read",)))
    host.tools.register(Tool("read_file", "读取 UTF-8 文件", read, tags=("read",)))
    host.tools.register(Tool("search_code", "搜索代码文本", search, tags=("read",)))
    host.tools.register(Tool("apply_patch", "精确替换一次文本", patch, tags=("write",), requires_approval=True))
    host.tools.register(Tool("run_check", "运行预注册检查", check, tags=("execute",), requires_approval=True))
    host.tools.register(Tool("report_change", "汇总修改", lambda _args, ctx: {
        "success": True,
        "report": f"已修改 {ctx.results[4]['path']}；测试退出码 {ctx.results[5]['exit_code']}。",
    }, tags=("output",)))


class CodingAgent(AgentHost):
    """通用 Host + 受限工作区编码场景。"""

    def __init__(self, checkpoint_path: str | Path, workspace: str | Path, **kwargs: Any) -> None:
        allowed = frozenset({"list_files", "read_file", "search_code", "apply_patch", "run_check", "report_change"})
        config = kwargs.pop("config", AgentConfig(
            instructions="只在受限工作区内修改文件并运行预注册检查",
            allowed_tools=allowed,
        ))
        super().__init__(checkpoint_path, config, llm=kwargs.pop("llm", CodingPlanAdapter()), **kwargs)
        self.workspace = Workspace(workspace)
        install_coding_tools(self, self.workspace)
