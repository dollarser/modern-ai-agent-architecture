#!/usr/bin/env python3
"""Check maintained Markdown HTTP links once each, preserving HTTP/transport failures."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from datetime import datetime, timezone, timedelta
import re
import subprocess
import sys
from urllib.parse import unquote, urldefrag

REPO_PREFIX = "https://github.com/dollarser/modern-ai-agent-architecture/blob/main/"


def links(text: str) -> set[str]:
    text = re.sub(r"^```.*?^```[^\n]*$", "", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r"`[^`\n]*`", "", text)
    return {urldefrag(url)[0] for url in re.findall(r"\]\((https?://[^\s)]+)\)", text)}


def main(root: Path) -> int:
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0"))
    sources: dict[str, list[str]] = {}
    for name in sorted(tracked):
        if name.endswith(".md") and (name.startswith("docs/") or name in {"README.md", "CONTRIBUTING.md"}):
            for url in links((root / name).read_text()):
                sources.setdefault(url, []).append(name)
    evidence_path = root / "specs/book/link-evidence.json"
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
    def reviewed(url):
        item = evidence.get(url, {})
        try:
            checked = datetime.fromisoformat(item["checked_at"])
            age = datetime.now(timezone.utc) - checked
            return bool(item.get("title") and item.get("method") and timedelta(0) <= age <= timedelta(days=30))
        except (KeyError, ValueError, TypeError):
            return False
    def check(url):
        if url.startswith(REPO_PREFIX):
            path = unquote(url[len(REPO_PREFIX):])
            return {"url": url, "status": "current-checkout" if path in tracked and (root / path).is_file() else "missing-file"}
        try:
            result = subprocess.run(["curl", "--head", "--location", "--silent", "--show-error", "--output", "/dev/null",
                "--write-out", "%{http_code}", "--connect-timeout", "8", "--max-time", "25",
                "--retry", "1", "--retry-all-errors", "--retry-delay", "1", url], capture_output=True, text=True, timeout=60)
            status = result.stdout[-3:]
            return {"url": url, "status": status if not result.returncode else "transport-error",
                    "reviewed_restriction": not result.returncode and status == "403" and reviewed(url),
                    "error": result.stderr.strip() if result.returncode else ""}
        except subprocess.TimeoutExpired:
            return {"url": url, "status": "transport-timeout"}
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for result in pool.map(check, sorted(sources)):
            result["sources"] = sources[result["url"]]
            results.append(result)
            if result.get("reviewed_restriction"):
                print(f'REVIEWED 403 (not HTTP success): {result["url"]}', flush=True)
            elif result["status"] != "current-checkout" and not str(result["status"]).startswith("2"):
                print(f'FAIL: {result["status"]} {result["url"]}', flush=True)
    (root / "link-check-results.txt").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    failed = sum(result["status"] != "current-checkout" and not str(result["status"]).startswith("2") and not result.get("reviewed_restriction") for result in results)
    print(f"Checked {len(results)} unique HTTP links; failed={failed}")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
