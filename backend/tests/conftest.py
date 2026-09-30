import os

# Must be set before the app is imported
os.environ["DATABASE_URL"] = "sqlite:///./test_nagari.db"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["RATE_LIMIT_PER_HOUR"] = "1000"
os.environ["RESEND_API_KEY"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASSWORD"] = ""

import pytest
from fastapi.testclient import TestClient

from app import rate_limit
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limit.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    if os.path.exists("test_nagari.db"):
        os.remove("test_nagari.db")
