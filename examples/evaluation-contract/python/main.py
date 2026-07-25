from __future__ import annotations

import json
import sys
from pathlib import Path


def run_case(case: dict, trace: list[dict]) -> dict:
    tools = [event["tool"] for event in trace if event.get("event") == "tool_call"]
    forbidden = sorted(set(tools) & set(case["forbidden_tools"]))
    allowed = all(tool in case["allowed_tools"] for tool in tools)
    passed = (
        trace[-1].get("status") == case["expected_status"]
        and allowed
        and not forbidden
        and len(tools) <= case["max_tool_calls"]
    )
    return {"case_id": case["case_id"], "passed": passed, "tool_calls": tools,
            "forbidden_tools": forbidden, "versions": case["versions"]}


def main(path: str) -> None:
    case = json.loads(Path(path).read_text())
    trace = [
        {"event": "tool_call", "tool": "orders.search", "arguments": {"period": "week"}},
        {"event": "run_finished", "status": "completed"},
    ]
    print(json.dumps(run_case(case, trace), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../cases/readonly.json")
