"""Демо: python scripts/demo.py http://127.0.0.1:8000 - одна и та же ручка на разных стадиях оптимизации."""
from _demo import client, section

PATH = "/{v}/reports/top-products?limit=10"


def call(label: str, version: str, path: str = PATH) -> None:
    r = client.get(path.format(v=version))
    top = r.json()[0] if r.status_code == 200 and isinstance(r.json(), list) else {}
    print(f"{label:<34} HTTP {r.status_code}   {r.headers['X-Time-Ms']:>8} ms   SQL-запросов: {r.headers['X-DB-Queries']:>3}   топ-1: {top.get('name')} ({top.get('revenue_cents', 0) / 100:,.0f})")


client.delete("/admin/indexes")  # начинаем с «как было»
client.get("/v1/reports/top-products")  # прогрев процесса

section("Топ-10 товаров по выручке: 2 000 клиентов, 20 000 заказов, ~60 000 позиций")
print("$ curl /v1/reports/top-products   (первый прототип: запрос в цикле по 300 товарам, индексов нет)")
call("v1  исходная версия", "v1")
print()
print("$ curl -X POST /admin/indexes     (шаг 1: индексы по EXPLAIN)")
client.post("/admin/indexes")
call("v1  + индексы", "v1")
print()
print("$ curl /v2/reports/top-products   (шаг 2: один запрос с JOIN и GROUP BY вместо 300)")
call("v2  + JOIN и агрегаты в SQL", "v2")
print()
print("$ curl /v3/reports/top-products   (шаг 3: TTL-кэш на 60 секунд)")
call("v3  первый запрос (кэш пуст)", "v3")
call("v3  повторный запрос (из кэша)", "v3")
print()

section("Вывод: ответ при этом остаётся тем же (проверяется тестами и в бенчмарке)")
a, b = client.get("/v1/reports/top-products").json(), client.get("/v3/reports/top-products").json()
print(f"v1 == v3: {a == b}   (десять позиций, совпадают поле в поле)")
