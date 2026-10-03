"""Бенчмарк: python -m app.bench [runs]

Прогоняет каждый эндпоинт на четырёх стадиях оптимизации, проверяет, что ответы одинаковы, и пишет docs/benchmark.json.
"""
import json
import statistics
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import cache, indexes
from app.db import engine
from app.main import app
from app.models import Customer, Order, OrderItem

OUT = Path(__file__).parent.parent / "docs" / "benchmark.json"

ENDPOINTS = [
    ("Последние 50 заказов", "/{v}/orders/recent?limit=50"),
    ("Статистика клиента", "/{v}/customers/7/stats"),
    ("Топ-10 товаров по выручке", "/{v}/reports/top-products?limit=10"),
]

STAGES = [
    ("Исходная версия", "v1", "drop"),
    ("+ индексы", "v1", "create"),
    ("+ JOIN и агрегаты в SQL", "v2", "keep"),
    ("+ кэш", "v3", "keep"),
]


def measure(client: TestClient, path: str, runs: int) -> tuple[dict, object]:
    first = client.get(path)
    assert first.status_code == 200, (path, first.text)
    times, queries = [], first.headers["X-DB-Queries"]
    for _ in range(runs):
        t = time.perf_counter()
        r = client.get(path)
        times.append((time.perf_counter() - t) * 1000)
        queries = r.headers["X-DB-Queries"]
    times.sort()
    return {"median_ms": round(statistics.median(times), 2), "p95_ms": round(times[min(len(times) - 1, int(len(times) * 0.95))], 2), "queries": int(queries)}, first.json()


def run(runs: int = 7) -> dict:
    results = [{"name": name, "path": path, "stages": []} for name, path in ENDPOINTS]
    answers: dict[int, list] = {i: [] for i in range(len(ENDPOINTS))}
    with TestClient(app) as client:
        for stage, version, idx in STAGES:
            if idx == "drop":
                indexes.drop_all(engine)
            elif idx == "create":
                indexes.create_all(engine)
            cache.clear()
            for i, (_, path) in enumerate(ENDPOINTS):
                stats, body = measure(client, path.format(v=version), runs)
                results[i]["stages"].append({"stage": stage, "version": version, **stats})
                answers[i].append(body)
                print(f"{results[i]['name']:<28} {stage:<26} {stats['median_ms']:>9.1f} ms  {stats['queries']:>4} queries")
    for i, bodies in answers.items():
        assert all(b == bodies[0] for b in bodies), f"Ответы разных версий не совпали: {ENDPOINTS[i][0]}"  # оптимизация не должна менять результат
    with engine.connect() as conn:
        dataset = {
            "customers": conn.scalar(select(func.count()).select_from(Customer)),
            "orders": conn.scalar(select(func.count()).select_from(Order)),
            "order_items": conn.scalar(select(func.count()).select_from(OrderItem)),
        }
    payload = {"dataset": dataset, "runs": runs, "database": engine.dialect.name, "endpoints": results}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
