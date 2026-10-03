"""Регрессионные тесты производительности: считаем SQL-запросы, а не миллисекунды - это стабильно на любой машине."""
from sqlalchemy import text

from app import cache, indexes
from app.db import engine
from tests.conftest import SMALL


def queries(client, path: str) -> int:
    r = client.get(path)
    assert r.status_code == 200
    return int(r.headers["X-DB-Queries"])


def test_v1_has_n_plus_one_on_recent_orders(client):
    # 1 запрос всех заказов + запрос позиций на каждый из 20 + запросы клиентов
    # (на маленькой базе часть клиентов повторяется и берётся из identity map, поэтому «≥», а не точное равенство)
    n = queries(client, "/v1/orders/recent?limit=20")
    assert n >= 1 + 20 + 10
    assert queries(client, "/v1/orders/recent?limit=40") > n  # число запросов растёт вместе с limit - признак N+1


def test_v2_recent_orders_is_single_query_regardless_of_limit(client):
    assert queries(client, "/v2/orders/recent?limit=5") == 1
    assert queries(client, "/v2/orders/recent?limit=100") == 1


def test_v1_top_products_runs_query_per_product(client):
    assert queries(client, "/v1/reports/top-products") >= SMALL["products"] + 1


def test_v2_top_products_is_single_query(client):
    assert queries(client, "/v2/reports/top-products") == 1


def test_v2_customer_stats_has_constant_query_count(client):
    assert queries(client, "/v2/customers/3/stats") <= 3
    assert queries(client, "/v2/customers/30/stats") <= 3


def test_v3_serves_repeat_requests_from_cache(client):
    first = queries(client, "/v3/reports/top-products")
    second = queries(client, "/v3/reports/top-products")
    assert first == 1 and second == 0


def test_cache_entries_are_independent_per_parameter(client):
    queries(client, "/v3/orders/recent?limit=5")
    assert queries(client, "/v3/orders/recent?limit=5") == 0
    assert queries(client, "/v3/orders/recent?limit=6") == 1


def test_cache_expires_after_ttl():
    now = [100.0]
    calls = []

    def fn():
        calls.append(1)
        return "value"

    clock = lambda: now[0]  # noqa: E731
    assert cache.cached("k", 10, fn, clock) == "value"
    now[0] = 105
    cache.cached("k", 10, fn, clock)
    assert len(calls) == 1
    now[0] = 111
    cache.cached("k", 10, fn, clock)
    assert len(calls) == 2


def test_query_counter_headers_present(client):
    r = client.get("/v2/reports/top-products")
    assert "X-DB-Queries" in r.headers and float(r.headers["X-Time-Ms"]) >= 0


def test_indexes_created_idempotently_and_removed(client):
    assert indexes.existing(engine) == []
    indexes.create_all(engine)
    indexes.create_all(engine)
    assert len(indexes.existing(engine)) == 4
    assert client.delete("/admin/indexes").json()["indexes"] == []
    assert len(client.post("/admin/indexes").json()["indexes"]) == 4


def test_query_planner_uses_the_new_indexes(client):
    def plan(sql: str) -> str:
        with engine.connect() as conn:
            return " ".join(str(row[3]) for row in conn.execute(text("EXPLAIN QUERY PLAN " + sql)))

    q = "SELECT * FROM orders WHERE customer_id = 5"
    assert "SCAN" in plan(q) and "ix_orders" not in plan(q)  # до: полный скан таблицы
    indexes.create_all(engine)
    assert "ix_orders_customer_id" in plan(q)                # после: поиск по индексу
    assert "ix_order_items_order_id" in plan("SELECT * FROM order_items WHERE order_id = 1")


def test_report_page_renders():
    from app.report import render_report

    data = {
        "dataset": {"customers": 1, "orders": 2, "order_items": 3}, "runs": 5, "database": "sqlite",
        "endpoints": [{"name": "X", "path": "/x", "stages": [
            {"stage": "a", "version": "v1", "median_ms": 100.0, "p95_ms": 120.0, "queries": 50},
            {"stage": "b", "version": "v2", "median_ms": 2.0, "p95_ms": 3.0, "queries": 1}]}],
    }
    html = render_report(data)
    assert "×50 быстрее" in html and "50" in html
