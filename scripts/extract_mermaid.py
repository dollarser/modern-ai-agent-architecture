#!/usr/bin/env python3
"""Extract Mermaid fences from Markdown into standalone .mmd files."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def extract(root: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for markdown in sorted(root.rglob("*.md")):
        if "node_modules" in markdown.parts:
            continue

        text = markdown.read_text(encoding="utf-8")
        blocks = re.findall(r"^```mermaid\s*\n(.*?)^```\s*$", text, re.MULTILINE | re.DOTALL)
        for index, block in enumerate(blocks, start=1):
            relative = markdown.relative_to(root).with_suffix("")
            safe_name = "__".join(relative.parts)
            target = output_dir / f"{safe_name}-{index}.mmd"
            target.write_text(block.rstrip() + "\n", encoding="utf-8")
            count += 1

    print(f"Extracted {count} Mermaid diagrams to {output_dir}")
    return count


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_mermaid.py <book-root> <output-dir>", file=sys.stderr)
        return 2

    count = extract(Path(sys.argv[1]), Path(sys.argv[2]))
    if count == 0:
        print("No Mermaid diagrams found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
