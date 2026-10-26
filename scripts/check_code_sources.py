#!/usr/bin/env python3
"""Verify Markdown code blocks that explicitly name a source region."""

from __future__ import annotations

import re
import sys
from pathlib import Path


BLOCK = re.compile(
    r"<!-- code-source: ([^#\s]+)#([A-Za-z0-9_.-]+) -->\s*"
    r"```[^\n]*\n(.*?)\n```",
    re.DOTALL,
)


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.strip("\n").splitlines()]
    return "\n".join(lines)


def source_region(path: Path, region: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start_pattern = re.compile(rf"^\s*# docs:start {re.escape(region)}\s*$")
    end_pattern = re.compile(rf"^\s*# docs:end {re.escape(region)}\s*$")
    starts = [index for index, line in enumerate(lines) if start_pattern.match(line)]
    ends = [index for index, line in enumerate(lines) if end_pattern.match(line)]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError(f"source region {region!r} must have exactly one ordered marker pair")
    return "\n".join(lines[starts[0] + 1:ends[0]])


def main(root: Path) -> int:
    failures: list[str] = []
    checked = 0
    for markdown in root.rglob("*.md"):
        if "node_modules" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for match in BLOCK.finditer(text):
            source_name, region, documented = match.groups()
            source = root / source_name
            checked += 1
            try:
                actual = source_region(source, region)
            except (OSError, ValueError) as exc:
                failures.append(f"{markdown}: {exc}")
                continue
            if normalize(documented) != normalize(actual):
                failures.append(
                    f"{markdown}: code-source {source_name}#{region} drifted"
                )
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    if checked == 0:
        print("No documented source regions found", file=sys.stderr)
        return 1
    print(f"Verified {checked} documented source regions")
    return 0


if __name__ == "__main__":
    repository = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    raise SystemExit(main(repository))
