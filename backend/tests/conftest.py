import os

import pytest
from starlette.testclient import TestClient

# Set testing environment variable before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["FRONTEND_URL"] = "http://localhost:5173"

from app.db.session import engine, init_db
from app.main import app
from app.models.base import Base


@pytest.fixture(autouse=True)
def clean_database():
    """Ensures each test starts with a clean database schema when using SQLite."""
    if str(engine.url).startswith("sqlite"):
        Base.metadata.drop_all(bind=engine)
        init_db()
    yield


@pytest.fixture
def client():
    """Provides a TestClient for FastAPI routes."""
    with TestClient(app) as test_client:
        yield test_client
