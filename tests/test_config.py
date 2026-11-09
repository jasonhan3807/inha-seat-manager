"""설정 검증: 최소 조회 간격 하한과 잘못된 환경변수 처리."""

import pytest

from app.config import ABSOLUTE_MIN_INTERVAL, Settings
from app.database import Database
from app.monitoring import SeatMonitor
from app.providers import MockSeatProvider


@pytest.fixture
def env(monkeypatch):
    for k in [
        "MONITOR_MIN_INTERVAL_SECONDS",
        "MONITOR_INTERVAL_SECONDS",
        "MONITOR_MAX_FAILURES",
        "NOTIFY_COOLDOWN_SECONDS",
        "PORT",
        "SEAT_PROVIDER",
    ]:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_absolute_floor_is_10():
    assert ABSOLUTE_MIN_INTERVAL == 10


@pytest.mark.parametrize("raw", ["0", "1", "5", "9", "-30"])
def test_env_min_interval_below_floor_is_raised(env, raw):
    env.setenv("MONITOR_MIN_INTERVAL_SECONDS", raw)
    env.setenv("MONITOR_INTERVAL_SECONDS", "1")
    s = Settings()
    assert s.min_interval == 10
    assert s.default_interval == 10


def test_applied_interval_never_below_10_even_with_low_env(env):
    """10초 미만 설정에서도 실제 대기 간격(next_delay)이 10초 이상인지 확인."""
    env.setenv("MONITOR_MIN_INTERVAL_SECONDS", "1")
    env.setenv("MONITOR_INTERVAL_SECONDS", "2")
    db = Database(":memory:")
    m = SeatMonitor(db, MockSeatProvider(seed=1, auto_tick_seconds=None), Settings(db_path=":memory:"))
    assert m.interval >= 10 and m.next_delay() >= 10
    assert m.set_interval(1) == 10 and m.next_delay() == 10
    assert m.status()["min_interval"] == 10


def test_monitor_floor_even_if_settings_bypassed():
    """Settings 검증을 우회(object.__setattr__)해도 모니터가 다시 10초 하한을 적용한다."""
    s = Settings(db_path=":memory:")
    object.__setattr__(s, "min_interval", 1)
    m = SeatMonitor(Database(":memory:"), MockSeatProvider(seed=1, auto_tick_seconds=None), s)
    assert m.clamp_interval(1) == 10
    assert m.set_interval(3) == 10


def test_saved_low_interval_in_db_is_clamped():
    db = Database(":memory:")
    db.set_setting("monitor_interval", "3")  # 예전 설정이 DB 에 남아 있는 경우
    m = SeatMonitor(db, MockSeatProvider(seed=1, auto_tick_seconds=None), Settings(db_path=":memory:"))
    assert m.interval == 10


def test_direct_settings_construction_is_validated():
    s = Settings(db_path=":memory:", min_interval=2, default_interval=99999, max_consecutive_failures=0,
                 notify_cooldown=-5, port=70000, seat_provider="hack")
    assert s.min_interval == 10
    assert s.default_interval == s.max_interval == 3600
    assert s.max_consecutive_failures == 1
    assert s.notify_cooldown == 0
    assert s.port == 65535
    assert s.seat_provider == "mock"


@pytest.mark.parametrize("raw", ["abc", "10s", "1.5", " "])
def test_non_numeric_env_uses_default(env, raw):
    env.setenv("MONITOR_MIN_INTERVAL_SECONDS", raw)
    env.setenv("MONITOR_MAX_FAILURES", raw)
    s = Settings()
    assert s.min_interval == 10
    assert s.max_consecutive_failures == 5


def test_invalid_values_log_warning(env, caplog):
    env.setenv("MONITOR_MIN_INTERVAL_SECONDS", "3")
    env.setenv("MONITOR_MAX_FAILURES", "x")
    with caplog.at_level("WARNING"):
        Settings()
    text = caplog.text
    assert "MONITOR_MIN_INTERVAL_SECONDS" in text and "MONITOR_MAX_FAILURES" in text


def test_valid_higher_values_are_kept(env):
    env.setenv("MONITOR_MIN_INTERVAL_SECONDS", "20")
    env.setenv("MONITOR_INTERVAL_SECONDS", "60")
    s = Settings()
    assert (s.min_interval, s.default_interval) == (20, 60)
