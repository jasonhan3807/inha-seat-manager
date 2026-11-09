from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app
from app.providers import OfficialSeatProvider
from tests.conftest import make_settings


def test_official_mode_degrades_gracefully():
    app = create_app(make_settings(seat_provider="official"), OfficialSeatProvider(), Database(":memory:"))
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert "DEMO 모드" not in c.get("/").text
        s = c.get("/api/system").json()
        assert s["provider_ok"] is False and "비활성" in s["provider_error"]
        assert c.get("/api/rooms").status_code == 503
        assert c.post("/api/assign", json={"room_id": "a", "seat_id": "1", "confirm": True}).status_code == 403
        assert c.post("/api/demo/fail", json={"count": 1}).status_code == 404
        assert c.get("/api/watches").status_code == 200
