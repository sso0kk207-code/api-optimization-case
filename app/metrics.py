"""Счётчик SQL-запросов на HTTP-запрос: видно N+1 без профайлера. Результат уходит в заголовок X-DB-Queries."""
import time
from contextvars import ContextVar

from fastapi import FastAPI, Request
from sqlalchemy import event

from app.db import engine


class Counter:
    def __init__(self) -> None:
        self.queries = 0


_current: ContextVar[Counter | None] = ContextVar("query_counter", default=None)


@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):
    counter = _current.get()
    if counter is not None:
        counter.queries += 1


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def measure(request: Request, call_next):
        counter = Counter()
        token = _current.set(counter)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            _current.reset(token)
        response.headers["X-DB-Queries"] = str(counter.queries)
        response.headers["X-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        return response
