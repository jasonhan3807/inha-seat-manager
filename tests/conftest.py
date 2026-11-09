import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.main import create_app
from app.monitoring import SeatMonitor
from app.providers import MockSeatProvider


def make_settings(**kw) -> Settings:
    base = dict(
        seat_provider="mock",
        db_path=":memory:",
        default_interval=30,
        min_interval=10,
        max_consecutive_failures=3,
        notify_cooldown=300,
        official_seat_url="https://lib.inha.ac.kr",
        mock_seed=1,
        monitor_autostart=False,
    )
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def settings():
    return make_settings()


@pytest.fixture
def provider():
    return MockSeatProvider(seed=1, auto_tick_seconds=None)


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


@pytest.fixture
def monitor(db, provider, settings):
    return SeatMonitor(db, provider, settings)


@pytest.fixture
def client(settings, provider, db):
    app = create_app(settings, provider, db)
    with TestClient(app) as c:
        c.app_state = app.state
        yield c
