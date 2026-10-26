#!/usr/bin/env python3
"""Write deterministic provenance for the built book; used locally and by Pages CI."""
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parent.parent
version = re.search(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", (root / "docs/CHANGELOG.md").read_text(), re.MULTILINE)
if version is None or not (root / "site/index.html").is_file():
    raise SystemExit("Version or built site missing")
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
(root / "site/release.json").write_text(json.dumps({"version": version[1], "commit": commit}, indent=2) + "\n")
