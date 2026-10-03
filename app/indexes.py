"""Индексы, добавленные по итогам анализа EXPLAIN. Каждый закрывает конкретный запрос."""
from sqlalchemy import Engine, inspect, text

INDEXES = [
    ("ix_orders_created_at", "orders", "created_at"),        # ORDER BY created_at DESC LIMIT 50
    ("ix_orders_customer_id", "orders", "customer_id"),      # заказы клиента
    ("ix_order_items_order_id", "order_items", "order_id"),  # позиции заказа (JOIN и lazy load)
    ("ix_order_items_product_id", "order_items", "product_id"),  # агрегаты по товару
]


def create_all(engine: Engine) -> None:
    with engine.begin() as conn:
        for name, table, column in INDEXES:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"))
        if engine.dialect.name == "sqlite":
            conn.execute(text("ANALYZE"))  # статистика для планировщика


def drop_all(engine: Engine) -> None:
    with engine.begin() as conn:
        for name, _, _ in INDEXES:
            conn.execute(text(f"DROP INDEX IF EXISTS {name}"))


def existing(engine: Engine) -> list[str]:
    names = {name for name, _, _ in INDEXES}
    insp = inspect(engine)
    return sorted(ix["name"] for table in {t for _, t, _ in INDEXES} for ix in insp.get_indexes(table) if ix["name"] in names)
