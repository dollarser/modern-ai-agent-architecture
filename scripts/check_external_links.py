#!/usr/bin/env python3
"""Run the pinned Markdown link checker with bounded parallelism and real exit codes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys


def main(root: Path) -> int:
    names = subprocess.check_output(["git", "ls-files", "-z", "--", "*.md"], cwd=root).decode().split("\0")
    # Archived design/review snapshots are historical evidence, not maintained link inventories.
    paths = [name for name in names if name and (name.startswith("docs/") or name in {"README.md", "CONTRIBUTING.md"})]
    def check(name):
        try:
            result = subprocess.run(["markdown-link-check", name, "--quiet", "--retry"], cwd=root,
                                    capture_output=True, text=True, timeout=90)
            return name, result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return name, 1, "link check exceeded 90 seconds\n"
    failed = []
    with (root / "link-check-results.txt").open("w") as report:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for name, status, output in pool.map(check, paths):
                report.write(f"{name}: exit={status}\n{output}\n")
                if status:
                    failed.append(name)
                    print(f"FAIL: {name}\n{output}", flush=True)
    print(f"Checked {len(paths)} maintained Markdown files; failed={len(failed)}")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
