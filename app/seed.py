"""Детерминированные тестовые данные. python -m app.seed  (по умолчанию 2 000 клиентов, 20 000 заказов, ~60 000 позиций)."""
import random
import sys
from datetime import datetime, timedelta

from sqlalchemy import func, insert, select

from app.db import Base, engine
from app.models import Customer, Order, OrderItem, Product

CITIES = ["Moscow", "Berlin", "Lisbon", "Tbilisi", "Warsaw", "Prague", "Belgrade", "Yerevan"]
CATEGORIES = ["books", "tools", "toys", "garden", "kitchen", "sport"]


def seed(customers: int = 2000, products: int = 300, orders: int = 20000, seed_value: int = 42) -> dict:
    rnd = random.Random(seed_value)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(Customer), [{"id": i, "name": f"Customer {i}", "email": f"c{i}@example.com", "city": rnd.choice(CITIES)} for i in range(1, customers + 1)])
        conn.execute(insert(Product), [{"id": i, "name": f"Product {i:04d}", "category": rnd.choice(CATEGORIES), "price_cents": rnd.randint(300, 20000)} for i in range(1, products + 1)])
        prices = {i: p for i, p in conn.execute(select(Product.id, Product.price_cents))}
        start = datetime(2025, 1, 1)
        order_rows, item_rows, item_id = [], [], 1
        for oid in range(1, orders + 1):
            order_rows.append({"id": oid, "customer_id": rnd.randint(1, customers), "created_at": start + timedelta(minutes=oid * 7 + rnd.randint(0, 6)), "status": rnd.choice(["paid", "paid", "paid", "shipped", "cancelled"])})
            for _ in range(rnd.randint(1, 5)):
                pid = rnd.randint(1, products)
                item_rows.append({"id": item_id, "order_id": oid, "product_id": pid, "qty": rnd.randint(1, 4), "unit_price_cents": prices[pid]})
                item_id += 1
        conn.execute(insert(Order), order_rows)
        conn.execute(insert(OrderItem), item_rows)
    return {"customers": customers, "products": products, "orders": orders, "items": item_id - 1}


def is_seeded() -> bool:
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        return (conn.scalar(select(func.count()).select_from(Customer)) or 0) > 0


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:4]]
    print(seed(*args))
