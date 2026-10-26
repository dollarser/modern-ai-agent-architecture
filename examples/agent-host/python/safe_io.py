"""单进程教学存储的安全原子替换；不提供跨进程事务或目录竞态隔离。"""

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, preserve_mode: bool = False) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".agent-write-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
        if preserve_mode:
            temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
