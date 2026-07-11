#!/usr/bin/env python3
"""Fail when a relative Markdown link points to a missing local target."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split(maxsplit=1)[0]


def check(root: Path) -> list[str]:
    failures: list[str] = []
    for markdown in sorted(root.rglob("*.md")):
        if "node_modules" in markdown.parts:
            continue

        in_fence = False
        for line_number, line in enumerate(markdown.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in LINK.finditer(line):
                target = unquote(destination(match.group(1))).split("#", 1)[0]
                if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                if target.startswith("/"):
                    continue
                resolved = (markdown.parent / target).resolve()
                if not resolved.exists():
                    failures.append(f"{markdown.relative_to(root)}:{line_number}: missing {target}")
    return failures


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    failures = check(root)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"All relative Markdown links resolve under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
