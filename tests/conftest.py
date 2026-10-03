import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app import cache, indexes
from app.db import Base, engine
from app.main import app
from app.models import Customer
from app.seed import seed

SMALL = dict(customers=40, products=15, orders=250)
LONELY = 9999  # клиент без заказов


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    seed(**SMALL)
    with engine.begin() as conn:
        conn.execute(insert(Customer), [{"id": LONELY, "name": "No Orders", "email": "n@x.io", "city": "Berlin"}])
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    indexes.drop_all(engine)
    yield
