"""v2 - те же ответы, но работу делает БД: JOIN + агрегаты, LIMIT на стороне SQL, один-два запроса вместо сотен."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer, Order, OrderItem, Product


def recent_orders(db: Session, limit: int) -> list[dict]:
    # Сначала выбираем нужные N заказов по индексу created_at, и только потом считаем агрегаты - только для них
    recent = select(Order.id, Order.created_at, Order.customer_id).order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).subquery()
    rows = db.execute(
        select(
            recent.c.id,
            recent.c.created_at,
            Customer.name,
            func.count(OrderItem.id),
            func.coalesce(func.sum(OrderItem.qty * OrderItem.unit_price_cents), 0),
        )
        .join(Customer, Customer.id == recent.c.customer_id)
        .outerjoin(OrderItem, OrderItem.order_id == recent.c.id)
        .group_by(recent.c.id, recent.c.created_at, Customer.name)
        .order_by(recent.c.created_at.desc(), recent.c.id.desc())
    ).all()
    return [{"order_id": oid, "created_at": ts.isoformat(), "customer": name, "items_count": cnt, "total_cents": int(total)} for oid, ts, name, cnt, total in rows]


def customer_stats(db: Session, customer_id: int) -> dict | None:
    if not db.get(Customer, customer_id):
        return None
    orders_count, last = db.execute(select(func.count(), func.max(Order.created_at)).where(Order.customer_id == customer_id)).one()
    total = db.scalar(select(func.coalesce(func.sum(OrderItem.qty * OrderItem.unit_price_cents), 0)).join(Order, Order.id == OrderItem.order_id).where(Order.customer_id == customer_id))
    total = int(total)
    return {
        "customer_id": customer_id,
        "orders_count": orders_count,
        "total_spent_cents": total,
        "avg_order_cents": total // orders_count if orders_count else 0,
        "last_order_at": last.isoformat() if last else None,
    }


def top_products(db: Session, limit: int) -> list[dict]:
    revenue = func.sum(OrderItem.qty * OrderItem.unit_price_cents)
    rows = db.execute(
        select(Product.id, Product.name, func.coalesce(func.sum(OrderItem.qty), 0), func.coalesce(revenue, 0))
        .outerjoin(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Product.id, Product.name)
        .order_by(func.coalesce(revenue, 0).desc(), Product.id)
        .limit(limit)
    ).all()
    return [{"product_id": pid, "name": name, "units": int(units), "revenue_cents": int(rev)} for pid, name, units, rev in rows]
