#!/usr/bin/env python3
"""Verify the single quantitative book baseline against tracked content."""

from __future__ import annotations

import ast
from collections import Counter
import json
import re
import subprocess
import sys
from pathlib import Path


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "examples"], cwd=root
    ).decode("utf-8")
    return [root / name for name in output.rstrip("\0").split("\0") if name]


def table_value(text: str, label: str) -> str:
    match = re.search(rf"^\|\s*{re.escape(label)}\s*\|\s*(.*?)\s*\|$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"baseline row {label!r} is missing")
    return match.group(1)


def integers(value: str) -> list[int]:
    return [int(item) for item in re.findall(r"\d+", value)]


def source_test_counts(files: list[Path], root: Path) -> tuple[int, int]:
    methods = 0
    projects: set[str] = set()
    for path in files:
        relative = path.relative_to(root)
        if len(relative.parts) != 4 or relative.parts[2] != "python" or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        found = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
        if found:
            methods += found
            projects.add(relative.parts[1])
    return len(projects), methods


def main(root: Path) -> int:
    baseline_path = root / "specs/book/11-current-baseline.md"
    baseline = baseline_path.read_text(encoding="utf-8")
    files = tracked_files(root)

    chapters = sorted((root / "docs/chapters").glob("[0-9][0-9]-*/README.md"))
    markdown = list((root / "docs").rglob("*.md"))
    mermaid = sum(
        len(re.findall(r"^```mermaid\s*$", path.read_text(encoding="utf-8"), re.MULTILINE))
        for path in markdown
    )
    projects = {
        path.relative_to(root).parts[1]
        for path in files
        if len(path.relative_to(root).parts) >= 3
    }
    entrypoints = sum(
        path.relative_to(root).parts[2:] in (("python", "main.py"), ("typescript", "main.ts"))
        for path in files
        if len(path.relative_to(root).parts) == 4
    )
    python_projects, python_tests = source_test_counts(files, root)

    ts_packages = [
        path for path in files
        if path.relative_to(root).parts[2:] == ("typescript", "package.json")
    ]
    ts_tests = sum(
        "test" in json.loads(path.read_text(encoding="utf-8")).get("scripts", {})
        for path in ts_packages
    )

    mermaid_baseline = integers(table_value(baseline, "Mermaid"))
    expected = {
        "chapters": integers(table_value(baseline, "章节"))[0],
        "mermaid": mermaid_baseline[0],
        "projects": integers(table_value(baseline, "示例工程"))[0],
        "entrypoints": integers(table_value(baseline, "Python/TypeScript 入口"))[0],
        "python_projects": integers(table_value(baseline, "Python 测试"))[0],
        "python_tests": integers(table_value(baseline, "Python 测试"))[1],
        "ts_packages": integers(table_value(baseline, "TypeScript"))[0],
        "ts_tests": integers(table_value(baseline, "TypeScript"))[1],
    }
    actual = {
        "chapters": len(chapters),
        "mermaid": mermaid,
        "projects": len(projects),
        "entrypoints": entrypoints,
        "python_projects": python_projects,
        "python_tests": python_tests,
        "ts_packages": len(ts_packages),
        "ts_tests": ts_tests,
    }

    summary = (root / "docs/SUMMARY.md").read_text(encoding="utf-8")
    summary_chapters = len(re.findall(r"\]\(chapters/[^)]+/README\.md\)", summary))
    index = (root / "docs/mermaid/MermaidIndex.md").read_text(encoding="utf-8")
    index_entries = re.findall(
        r"^\|\s*图 (\d+-\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$",
        index,
        re.MULTILINE,
    )
    indexed_mermaid = len(index_entries)
    indexed_types = Counter(kind for _number, _title, kind in index_entries)

    failures: list[str] = []
    caption_entries: list[tuple[str, str]] = []
    for chapter in chapters:
        chapter_number = int(chapter.parent.name.split("-", 1)[0])
        captions = re.findall(
            r"^> \*\*图 (\d+-\d+)：\*\*\s*([^\n]+)$",
            chapter.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        expected_numbers = [
            f"{chapter_number}-{position}" for position in range(1, len(captions) + 1)
        ]
        actual_numbers = [number for number, _caption in captions]
        if actual_numbers != expected_numbers:
            failures.append(
                f"figure order in chapter {chapter_number}: "
                f"expected={expected_numbers}, actual={actual_numbers}"
            )
        for number, caption in captions:
            caption_entries.append((number, caption.split("。", 1)[0]))

    failures.extend([
        f"{name}: baseline={expected[name]}, actual={actual[name]}"
        for name in expected
        if expected[name] != actual[name]
    ])
    if summary_chapters != actual["chapters"]:
        failures.append(
            f"chapter index: SUMMARY={summary_chapters}, actual={actual['chapters']}"
        )
    if indexed_mermaid != actual["mermaid"]:
        failures.append(
            f"Mermaid index: index={indexed_mermaid}, actual={actual['mermaid']}"
        )
    indexed_titles = [(number, title) for number, title, _kind in index_entries]
    if indexed_titles != caption_entries:
        failures.append("Mermaid index titles or order differ from chapter captions")

    type_labels = ["架构图", "流程图", "时序图", "状态图", "关系图", "对比图"]
    if len(mermaid_baseline) != 1 + len(type_labels):
        failures.append("Mermaid baseline must contain total plus six type counts")
    else:
        for label, expected_count in zip(type_labels, mermaid_baseline[1:]):
            if indexed_types[label] != expected_count:
                failures.append(
                    f"Mermaid type {label}: baseline={expected_count}, "
                    f"index={indexed_types[label]}"
                )

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "Book baseline verified: "
        f"{actual['chapters']} chapters, {actual['mermaid']} Mermaid diagrams, "
        f"{actual['projects']} examples, {actual['python_tests']} Python tests"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
