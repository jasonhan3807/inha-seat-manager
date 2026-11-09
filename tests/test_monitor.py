from datetime import datetime, timedelta

from app.providers import OfficialSeatProvider, SeatStatus
from app.monitoring import SeatMonitor
from tests.conftest import make_settings


def watch(db, provider, seat="1", room="demo-a", status=SeatStatus.OCCUPIED):
    provider.set_status(room, seat, status)
    return db.add_watch(room, seat, f"{seat}번")


def notes(db, kind="seat_available"):
    return [n for n in db.list_notifications() if n["kind"] == kind]


def test_no_watches_no_query(monitor):
    r = monitor.check_once()
    assert r["checked_rooms"] == 0 and r["notified"] == []


def test_detects_available_and_message(monitor, db, provider):
    watch(db, provider)
    monitor.check_once()
    assert notes(db) == []
    provider.set_status("demo-a", "1", SeatStatus.AVAILABLE)
    r = monitor.check_once()
    assert r["notified"] == [{"room_id": "demo-a", "seat_id": "1"}]
    msg = notes(db)[0]["message"]
    for part in ["[DEMO]", "DEMO 열람실 A", "1번", "감지 시각", "현재 상태: 빈자리", "lib.inha.ac.kr"]:
        assert part in msg


def test_no_duplicate_while_still_available(monitor, db, provider):
    watch(db, provider, status=SeatStatus.AVAILABLE)
    monitor.check_once()
    monitor.check_once()
    monitor.check_once()
    assert len(notes(db)) == 1


def test_cooldown_blocks_flapping(monitor, db, provider):
    watch(db, provider, status=SeatStatus.AVAILABLE)
    monitor.check_once()
    provider.set_status("demo-a", "1", SeatStatus.OCCUPIED)
    monitor.check_once()
    provider.set_status("demo-a", "1", SeatStatus.AVAILABLE)
    monitor.check_once()
    assert len(notes(db)) == 1  # 쿨다운(300초) 안이라 재알림 없음


def test_renotify_after_cooldown(monitor, db, provider):
    w = watch(db, provider, status=SeatStatus.AVAILABLE)
    monitor.check_once()
    old = (datetime.now().astimezone() - timedelta(seconds=301)).isoformat()
    db._exec("UPDATE watch_seats SET last_notified_at=? WHERE id=?", (old, w["id"]))
    provider.set_status("demo-a", "1", SeatStatus.OCCUPIED)
    monitor.check_once()
    provider.set_status("demo-a", "1", SeatStatus.AVAILABLE)
    monitor.check_once()
    assert len(notes(db)) == 2


def test_multiple_seats_one_query_per_room(monitor, db, provider):
    calls = []
    orig = provider.get_seats
    provider.get_seats = lambda rid: calls.append(rid) or orig(rid)
    watch(db, provider, "1", status=SeatStatus.AVAILABLE)
    watch(db, provider, "2", status=SeatStatus.AVAILABLE)
    watch(db, provider, "1", room="demo-b", status=SeatStatus.AVAILABLE)
    r = monitor.check_once()
    assert sorted(calls) == ["demo-a", "demo-b"]
    assert len(r["notified"]) == 3


def test_failures_backoff_and_autostop(monitor, db, provider):
    watch(db, provider)
    monitor.running = True  # 루프 없이 상태만
    provider.fail_next = 10
    monitor.check_once()
    assert monitor.consecutive_failures == 1 and monitor.next_delay() == 60
    monitor.check_once()
    assert monitor.next_delay() == 120
    monitor.check_once()  # 한도 3
    assert monitor.running is False
    assert "자동 중지" in monitor.stopped_reason
    assert len(notes(db, "system")) == 1
    assert len(db.list_history(kind="query_error")) == 3


def test_failure_counter_resets_on_success(monitor, db, provider):
    watch(db, provider)
    provider.fail_next = 1
    monitor.check_once()
    assert monitor.consecutive_failures == 1
    monitor.check_once()
    assert monitor.consecutive_failures == 0 and monitor.last_error is None


def test_backoff_capped(monitor):
    monitor.consecutive_failures = 10
    assert monitor.next_delay() == monitor.interval * 8


def test_interval_clamped(monitor, db):
    assert monitor.set_interval(1) == 10
    assert monitor.set_interval(999999) == 3600
    assert monitor.set_interval(45) == 45
    assert db.get_setting("monitor_interval") == "45"


def test_interval_persisted(db, provider, settings):
    SeatMonitor(db, provider, settings).set_interval(77)
    assert SeatMonitor(db, provider, settings).interval == 77


def test_official_provider_stops_immediately(db):
    m = SeatMonitor(db, OfficialSeatProvider(), make_settings(seat_provider="official"))
    db.add_watch("x", "1", "1번")
    m.running = True
    m.check_once()
    assert m.running is False
    assert "설정되지 않아" in m.stopped_reason


def test_start_stop_persist_flag(monitor, db):
    monitor.start()
    assert db.get_setting("monitor_running") == "1"
    monitor.stop()
    assert db.get_setting("monitor_running") == "0"
    assert monitor.stopped_reason == "사용자가 중지함"
