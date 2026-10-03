import time
from collections.abc import Callable
from typing import Any

_store: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl: float, fn: Callable[[], Any], now: Callable[[], float] = time.monotonic) -> Any:
    """TTL-кэш в памяти. В продакшене с несколькими процессами здесь Redis, интерфейс тот же."""
    hit = _store.get(key)
    if hit and hit[0] > now():
        return hit[1]
    value = fn()
    _store[key] = (now() + ttl, value)
    return value


def clear() -> None:
    _store.clear()
