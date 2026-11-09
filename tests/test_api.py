import time

from app.providers import SeatStatus


def test_index_page_has_demo(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "DEMO" in r.text and "INHA SEAT MANAGER" in r.text
    assert r.headers["x-frame-options"] == "DENY"


def test_static_files(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_health_and_system(client):
    assert client.get("/api/health").json()["db"] is True
    s = client.get("/api/system").json()
    assert s["is_demo"] and s["provider_ok"] and s["monitor"]["running"] is False


def test_rooms_and_seats(client):
    rooms = client.get("/api/rooms").json()
    assert rooms["is_demo"] and rooms["rooms"]
    rid = rooms["rooms"][0]["id"]
    d = client.get(f"/api/rooms/{rid}/seats").json()
    assert d["room"]["id"] == rid and d["seats"]
    s = d["seats"][0]
    assert {"id", "label", "status", "status_label", "watched", "row", "col"} <= s.keys()
    assert client.get("/api/rooms/nope/seats").status_code == 404


def test_watch_crud(client):
    r = client.post("/api/watches", json={"room_id": "demo-a", "seat_id": "3"})
    assert r.status_code == 201
    wid = r.json()["id"]
    assert client.post("/api/watches", json={"room_id": "demo-a", "seat_id": "3"}).status_code == 409
    assert client.post("/api/watches", json={"room_id": "demo-a", "seat_id": "9999"}).status_code == 404
    lst = client.get("/api/watches").json()["watches"]
    assert lst[0]["room_name"] == "DEMO 열람실 A"
    seats = client.get("/api/rooms/demo-a/seats").json()["seats"]
    assert next(s for s in seats if s["id"] == "3")["watched"] is True
    assert client.delete(f"/api/watches/{wid}").status_code == 200
    assert client.delete(f"/api/watches/{wid}").status_code == 404


def test_watch_limit(client):
    for i in range(1, 31):
        assert client.post("/api/watches", json={"room_id": "demo-a", "seat_id": str(i)}).status_code == 201
    assert client.post("/api/watches", json={"room_id": "demo-a", "seat_id": "31"}).status_code == 400


def test_monitor_requires_watch(client):
    assert client.post("/api/monitor/start").status_code == 400


def test_monitor_flow_and_notifications(client, provider):
    provider.set_status("demo-a", "5", SeatStatus.OCCUPIED)
    client.post("/api/watches", json={"room_id": "demo-a", "seat_id": "5"})
    client.post("/api/monitor/check")
    provider.set_status("demo-a", "5", SeatStatus.AVAILABLE)
    r = client.post("/api/monitor/check").json()
    assert len(r["result"]["notified"]) == 1
    n = client.get("/api/notifications").json()
    assert n["unread"] == 1
    first_id = n["notifications"][0]["id"]
    assert client.get(f"/api/notifications?after_id={first_id}").json()["notifications"] == []
    client.post("/api/notifications/read")
    assert client.get("/api/notifications").json()["unread"] == 0
    hist = client.get("/api/history?kind=query").json()["history"]
    assert hist


def test_monitor_start_stop_background(client, provider):
    provider.set_status("demo-a", "5", SeatStatus.AVAILABLE)
    client.post("/api/watches", json={"room_id": "demo-a", "seat_id": "5"})
    assert client.post("/api/monitor/start").json()["running"] is True
    deadline = time.time() + 3
    while time.time() < deadline and not client.get("/api/notifications").json()["notifications"]:
        time.sleep(0.05)
    assert client.get("/api/notifications").json()["notifications"], "백그라운드 조회가 실행되어야 함"
    assert client.post("/api/monitor/stop").json()["running"] is False


def test_interval_api(client):
    assert client.put("/api/monitor/interval", json={"seconds": 2}).json()["interval"] == 10
    assert client.put("/api/monitor/interval", json={"seconds": 0}).status_code == 422


def test_assign_requires_confirm(client, provider):
    provider.set_status("demo-a", "7", SeatStatus.AVAILABLE)
    assert client.post("/api/assign", json={"room_id": "demo-a", "seat_id": "7"}).status_code == 400
    r = client.post("/api/assign", json={"room_id": "demo-a", "seat_id": "7", "confirm": True})
    assert r.status_code == 200 and r.json()["is_demo"] is True
    assert client.post("/api/assign", json={"room_id": "demo-a", "seat_id": "7", "confirm": True}).status_code == 409
    assert client.get("/api/history?kind=assign").json()["history"][0]["detail"].startswith("[DEMO]")


def test_demo_fail_shows_error(client):
    client.post("/api/demo/fail", json={"count": 1})
    assert client.get("/api/rooms").status_code == 503


def test_cross_origin_post_blocked(client):
    r = client.post("/api/monitor/stop", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.post("/api/monitor/stop", headers={"Origin": "http://testserver"}).status_code == 200


def test_non_json_body_rejected(client):
    r = client.post("/api/watches", content="room_id=demo-a&seat_id=1",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 422
