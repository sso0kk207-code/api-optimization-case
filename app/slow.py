"""v1 - «как написано в первом прототипе». Работает, но на реальных объёмах тормозит.

Проблемы (каждая помечена): выборка всей таблицы, сортировка и срез в Python, N+1 lazy-load, агрегация в Python, запрос в цикле.
"""
from sqlalchemy.orm import Session

from app.models import Customer, Order, OrderItem, Product


def recent_orders(db: Session, limit: int) -> list[dict]:
    orders = db.query(Order).all()                                  # ❌ вся таблица заказов в память
    orders.sort(key=lambda o: (o.created_at, o.id), reverse=True)   # ❌ сортировка в Python
    result = []
    for o in orders[:limit]:                                        # ❌ LIMIT применяется после загрузки всего
        items = o.items                                             # ❌ N+1: запрос позиций на каждый заказ
        result.append(
            {
                "order_id": o.id,
                "created_at": o.created_at.isoformat(),
                "customer": o.customer.name,                        # ❌ N+1: ещё один запрос на клиента
                "items_count": len(items),
                "total_cents": sum(i.qty * i.unit_price_cents for i in items),
            }
        )
    return result


def customer_stats(db: Session, customer_id: int) -> dict | None:
    customer = db.get(Customer, customer_id)
    if not customer:
        return None
    orders = db.query(Order).filter(Order.customer_id == customer_id).all()  # ❌ без индекса: полный скан orders
    total = 0
    for o in orders:
        for item in o.items:                                        # ❌ N+1 + полный скан order_items на каждый заказ
            total += item.qty * item.unit_price_cents               # ❌ сумма считается в Python
    last = max((o.created_at for o in orders), default=None)
    return {
        "customer_id": customer_id,
        "orders_count": len(orders),
        "total_spent_cents": total,
        "avg_order_cents": total // len(orders) if orders else 0,
        "last_order_at": last.isoformat() if last else None,
    }


def top_products(db: Session, limit: int) -> list[dict]:
    rows = []
    for p in db.query(Product).all():
        items = db.query(OrderItem).filter(OrderItem.product_id == p.id).all()  # ❌ запрос в цикле, каждый - полный скан
        rows.append({"product_id": p.id, "name": p.name, "units": sum(i.qty for i in items), "revenue_cents": sum(i.qty * i.unit_price_cents for i in items)})
    rows.sort(key=lambda r: (-r["revenue_cents"], r["product_id"]))
    return rows[:limit]
