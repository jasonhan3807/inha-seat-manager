"""모니터링 실행/중지 경쟁 조건 회귀 테스트 (실제 asyncio 루프 사용)."""

import asyncio
import threading
import time

from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app
from app.monitoring import SeatMonitor
from app.monitoring.monitor import NO_WATCHES_REASON
from app.providers import MockSeatProvider, SeatStatus
from tests.conftest import make_settings


class CountingProvider(MockSeatProvider):
    """get_seats 호출(=학교 시스템 조회에 해당) 횟수를 센다."""

    def __init__(self, delay: float = 0.0):
        super().__init__(seed=1, auto_tick_seconds=None)
        self.calls = 0
        self.delay = delay
        self._calls_lock = threading.Lock()

    def get_seats(self, room_id):
        with self._calls_lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        return super().get_seats(room_id)


async def _wait_for(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > end:
            raise AssertionError("시간 안에 조건이 충족되지 않음")
        await asyncio.sleep(0.01)


def test_last_watch_removed_stops_loop_and_no_more_queries():
    async def scenario():
        db = Database(":memory:")
        p = CountingProvider()
        m = SeatMonitor(db, p, make_settings())
        w1 = db.add_watch("demo-a", "1", "1번")
        w2 = db.add_watch("demo-a", "2", "2번")
        m.start()
        await _wait_for(lambda: p.calls >= 1)

        db.remove_watch(w1["id"])
        m.on_watches_changed()
        assert m.running is True  # 아직 1개 남음

        db.remove_watch(w2["id"])
        m.on_watches_changed()
        assert m.running is False
        assert m.stopped_reason == NO_WATCHES_REASON
        assert db.get_setting("monitor_running") == "0"

        # 백그라운드 작업이 (10초 대기를 기다리지 않고) 즉시 끝나야 한다
        await asyncio.wait_for(m._task, timeout=1)
        calls = p.calls
        await asyncio.sleep(0.2)
        assert p.calls == calls  # 중지 후 추가 조회 없음

    asyncio.run(scenario())


def test_watch_removed_during_inflight_query():
    """조회가 진행 중일 때 마지막 좌석이 삭제돼도 알림 없이 멈추고 이후 조회가 없다."""

    async def scenario():
        db = Database(":memory:")
        p = CountingProvider(delay=0.3)
        p.set_status("demo-a", "1", SeatStatus.AVAILABLE)
        m = SeatMonitor(db, p, make_settings())
        w = db.add_watch("demo-a", "1", "1번")
        m.start()
        await _wait_for(lambda: p.calls >= 1)  # 조회 중 (0.3초 지연)
        db.remove_watch(w["id"])
        m.on_watches_changed()
        assert m.running is False
        await asyncio.wait_for(m._task, timeout=2)
        assert p.calls == 1
        assert [n for n in db.list_notifications() if n["kind"] == "seat_available"] == []

    asyncio.run(scenario())


def test_loop_stops_itself_if_watches_vanish_without_notice():
    """API 를 거치지 않고 좌석이 사라져도 다음 조회에서 스스로 멈춘다."""
    db = Database(":memory:")
    m = SeatMonitor(db, CountingProvider(), make_settings())
    m.running = True
    m.check_once()
    assert m.running is False and m.stopped_reason == NO_WATCHES_REASON


def test_quick_stop_start_runs_single_loop():
    async def scenario():
        db = Database(":memory:")
        p = CountingProvider(delay=0.2)
        m = SeatMonitor(db, p, make_settings())
        db.add_watch("demo-a", "1", "1번")
        m.start()
        old = m._task
        await _wait_for(lambda: p.calls >= 1)
        m.stop()
        m.start()  # 이전 조회가 끝나기 전에 재시작
        new = m._task
        assert old is not new
        await asyncio.wait_for(old, timeout=2)  # 이전 루프는 스스로 끝난다
        assert not new.done() and m.running
        await asyncio.sleep(0.3)
        assert p.calls == 2  # 이전 1회 + 새 루프 1회. 루프가 2개면 더 많아진다
        await m.shutdown()
        assert new.done()

    asyncio.run(scenario())


def test_concurrent_checks_do_not_duplicate_notifications():
    db = Database(":memory:")
    p = CountingProvider(delay=0.1)
    p.set_status("demo-a", "1", SeatStatus.AVAILABLE)
    m = SeatMonitor(db, p, make_settings())
    db.add_watch("demo-a", "1", "1번")
    threads = [threading.Thread(target=m.check_once) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len([n for n in db.list_notifications() if n["kind"] == "seat_available"]) == 1


def test_api_delete_last_watch_stops_monitoring():
    p = CountingProvider()
    app = create_app(make_settings(), p, Database(":memory:"))
    with TestClient(app) as c:
        a = c.post("/api/watches", json={"room_id": "demo-a", "seat_id": "1"}).json()
        b = c.post("/api/watches", json={"room_id": "demo-a", "seat_id": "2"}).json()
        assert c.post("/api/monitor/start").json()["running"] is True
        end = time.time() + 2
        while p.calls < 1 and time.time() < end:
            time.sleep(0.01)
        assert p.calls >= 1

        r = c.delete(f"/api/watches/{a['id']}").json()
        assert r["monitor_running"] is True

        r = c.delete(f"/api/watches/{b['id']}").json()
        assert r["monitor_running"] is False
        st = c.get("/api/monitor").json()
        assert st["running"] is False and st["stopped_reason"] == NO_WATCHES_REASON

        task = app.state.monitor._task
        end = time.time() + 2
        while not task.done() and time.time() < end:
            time.sleep(0.01)
        assert task.done()  # 백그라운드 루프 종료
        calls = p.calls
        time.sleep(0.3)
        assert p.calls == calls  # 이후 추가 조회 없음
        hist = c.get("/api/history?kind=monitor").json()["history"]
        assert NO_WATCHES_REASON in hist[0]["detail"]


def test_api_delete_when_not_running_keeps_stopped():
    app = create_app(make_settings(), CountingProvider(), Database(":memory:"))
    with TestClient(app) as c:
        a = c.post("/api/watches", json={"room_id": "demo-a", "seat_id": "1"}).json()
        r = c.delete(f"/api/watches/{a['id']}").json()
        assert r["monitor_running"] is False
        assert c.get("/api/monitor").json()["stopped_reason"] is None  # 원래 안 돌던 상태 그대로
