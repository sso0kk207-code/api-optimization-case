"""Главное правило оптимизации: ответы не меняются. Все три версии должны отдавать одно и то же."""
import pytest

from app import indexes
from app.db import engine
from tests.conftest import LONELY


def get_all(client, template: str) -> list:
    return [client.get(template.format(v=v)) for v in ("v1", "v2", "v3")]


@pytest.mark.parametrize("limit", [1, 10, 50, 200])
def test_recent_orders_identical(client, limit):
    a, b, c = get_all(client, f"/{{v}}/orders/recent?limit={limit}")
    assert a.json() == b.json() == c.json()
    assert len(a.json()) == min(limit, 250)


def test_recent_orders_sorted_newest_first(client):
    data = client.get("/v2/orders/recent?limit=30").json()
    stamps = [o["created_at"] for o in data]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.parametrize("cid", [1, 7, 23, 40, LONELY])
def test_customer_stats_identical(client, cid):
    a, b, c = get_all(client, f"/{{v}}/customers/{cid}/stats")
    assert a.json() == b.json() == c.json()


def test_customer_without_orders(client):
    data = client.get(f"/v2/customers/{LONELY}/stats").json()
    assert data == {"customer_id": LONELY, "orders_count": 0, "total_spent_cents": 0, "avg_order_cents": 0, "last_order_at": None}


def test_unknown_customer_is_404_in_all_versions(client):
    assert [r.status_code for r in get_all(client, "/{v}/customers/424242/stats")] == [404, 404, 404]


@pytest.mark.parametrize("limit", [1, 5, 10, 100])
def test_top_products_identical(client, limit):
    a, b, c = get_all(client, f"/{{v}}/reports/top-products?limit={limit}")
    assert a.json() == b.json() == c.json()


def test_top_products_ordered_by_revenue(client):
    rev = [p["revenue_cents"] for p in client.get("/v2/reports/top-products?limit=15").json()]
    assert rev == sorted(rev, reverse=True)


def test_results_are_the_same_with_and_without_indexes(client):
    before = client.get("/v2/reports/top-products?limit=5").json()
    indexes.create_all(engine)
    assert client.get("/v1/reports/top-products?limit=5").json() == before


def test_validation(client):
    assert client.get("/v2/orders/recent?limit=0").status_code == 422
    assert client.get("/v2/orders/recent?limit=500").status_code == 422
