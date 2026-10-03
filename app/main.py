import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app import cache, fast, indexes, metrics, slow
from app.db import Base, engine, get_db
from app.report import render_report
from app.seed import is_seeded, seed

RESULTS = Path(__file__).parent.parent / "docs" / "benchmark.json"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if not is_seeded():
        seed()
    yield


app = FastAPI(
    title="API Optimization Case",
    version="1.0.0",
    description=(
        "Один и тот же API в трёх версиях. **v1** - медленная (N+1, без индексов, агрегация в Python), "
        "**v2** - оптимизирована (индексы, JOIN, агрегаты в SQL), **v3** - v2 + кэш. Заголовки `X-DB-Queries` и `X-Time-Ms` показывают число SQL-запросов и время."
    ),
    lifespan=lifespan,
)
metrics.install(app)


def version_router(tag: str, mod, wrap=lambda key, ttl, fn: fn()) -> APIRouter:
    r = APIRouter(prefix=f"/{tag}", tags=[tag])

    @r.get("/orders/recent")
    def recent(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
        return wrap(f"recent:{limit}", 5, lambda: mod.recent_orders(db, limit))

    @r.get("/customers/{customer_id}/stats")
    def stats(customer_id: int, db: Session = Depends(get_db)):
        data = wrap(f"stats:{customer_id}", 30, lambda: mod.customer_stats(db, customer_id))
        if data is None:
            raise HTTPException(404, "Customer not found")
        return data

    @r.get("/reports/top-products")
    def top(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
        return wrap(f"top:{limit}", 60, lambda: mod.top_products(db, limit))

    return r


app.include_router(version_router("v1", slow))
app.include_router(version_router("v2", fast))
app.include_router(version_router("v3", fast, wrap=lambda key, ttl, fn: cache.cached(key, ttl, fn)))


@app.get("/health", tags=["service"])
def health():
    return {"status": "ok", "indexes": indexes.existing(engine)}


@app.post("/admin/indexes", tags=["admin"], summary="Создать индексы (шаг оптимизации №1)")
def add_indexes():
    indexes.create_all(engine)
    return {"indexes": indexes.existing(engine)}


@app.delete("/admin/indexes", tags=["admin"], summary="Удалить индексы (вернуться к «до»)")
def remove_indexes():
    indexes.drop_all(engine)
    cache.clear()
    return {"indexes": indexes.existing(engine)}


@app.get("/report", response_class=HTMLResponse, include_in_schema=False)
def report():
    if not RESULTS.exists():
        raise HTTPException(404, "Run `python -m app.bench` first")
    return render_report(json.loads(RESULTS.read_text(encoding="utf-8")))
