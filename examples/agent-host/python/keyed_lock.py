"""同一进程/事件循环中的存储作用域互斥；不代替数据库租约。"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from weakref import WeakKeyDictionary

_locks = WeakKeyDictionary()


def store_scope(store) -> str:
    path = getattr(store, "path", None)
    return str(Path(path).resolve()) if path is not None else f"object:{id(store)}"


@asynccontextmanager
async def keyed_lock(scope: str, identity: str):
    locks = _locks.setdefault(asyncio.get_running_loop(), {})
    key = (scope, identity)
    entry = locks.setdefault(key, [asyncio.Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            yield
    finally:
        entry[1] -= 1
        if not entry[1]:
            del locks[key]


_active = WeakKeyDictionary()


def track_execution(scope, run_id, task):
    registry = _active.setdefault(asyncio.get_running_loop(), {})
    key = (scope, run_id)
    calls = registry.setdefault(key, set())
    calls.add(task)
    def finished(completed):
        calls.discard(completed)
        if not calls:
            registry.pop(key, None)
    task.add_done_callback(finished)


def has_active_execution(scope, run_id):
    return bool(_active.get(asyncio.get_running_loop(), {}).get((scope, run_id)))
