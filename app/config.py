"""환경변수(.env)에서 설정을 읽는다. 비밀정보는 코드에 넣지 않는다."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


log = logging.getLogger(__name__)

# 코드 수준의 절대 하한. .env 로도 이보다 짧게 만들 수 없다 (학교 시스템 부담 방지).
ABSOLUTE_MIN_INTERVAL = 10
MAX_INTERVAL = 3600


def _int(name: str, default: int) -> int:
    """정수 환경변수를 읽는다. 숫자가 아니면 경고를 남기고 기본값을 쓴다."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        log.warning("설정 %s 값이 숫자가 아니어서 기본값 %s 을(를) 사용합니다.", name, default)
        return default


def _bounded(name: str, value: int, low: int, high: int) -> int:
    """허용 범위를 벗어난 값은 경고를 남기고 범위 안으로 맞춘다."""
    if value < low or value > high:
        fixed = max(low, min(high, value))
        log.warning("설정 %s=%s 은(는) 허용 범위(%s~%s) 밖이라 %s(으)로 조정합니다.", name, value, low, high, fixed)
        return fixed
    return value


@dataclass(frozen=True)
class Settings:
    # mock: 모의 데이터 / official: 공식 시스템 (허용된 연동 방식 확인 전까지 비활성)
    seat_provider: str = field(default_factory=lambda: os.getenv("SEAT_PROVIDER", "mock").lower())
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", str(BASE_DIR / "data" / "seat_manager.db")))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("PORT", 8000))
    # 조회 간격(초). 학교 시스템 부담을 막기 위해 최소값을 강제한다.
    default_interval: int = field(default_factory=lambda: _int("MONITOR_INTERVAL_SECONDS", 30))
    min_interval: int = field(default_factory=lambda: _int("MONITOR_MIN_INTERVAL_SECONDS", 10))
    max_interval: int = MAX_INTERVAL
    # 연속 실패가 이 횟수에 도달하면 모니터링을 자동 중지한다.
    max_consecutive_failures: int = field(default_factory=lambda: _int("MONITOR_MAX_FAILURES", 5))
    # 같은 좌석에 대해 다시 알림을 보내기 전 최소 대기 시간(초)
    notify_cooldown: int = field(default_factory=lambda: _int("NOTIFY_COOLDOWN_SECONDS", 300))
    # 사용자가 직접 배정할 공식 페이지 (정석학술정보관 홈페이지)
    official_seat_url: str = field(default_factory=lambda: os.getenv("OFFICIAL_SEAT_URL", "https://lib.inha.ac.kr"))
    # 모의 데이터 무작위 시드 (테스트 재현용)
    mock_seed: int | None = field(default_factory=lambda: _int("MOCK_SEED", 0) or None)
    monitor_autostart: bool = field(default_factory=lambda: os.getenv("MONITOR_AUTOSTART", "1") == "1")


    def __post_init__(self) -> None:
        # 잘못된 값 검증. 직접 Settings(...) 로 만들 때(테스트 등)도 똑같이 적용된다.
        fix = lambda k, v: object.__setattr__(self, k, v)  # noqa: E731 (frozen dataclass)
        fix("max_interval", _bounded("MAX_INTERVAL", self.max_interval, ABSOLUTE_MIN_INTERVAL, MAX_INTERVAL))
        fix(
            "min_interval",
            _bounded("MONITOR_MIN_INTERVAL_SECONDS", self.min_interval, ABSOLUTE_MIN_INTERVAL, self.max_interval),
        )
        fix(
            "default_interval",
            _bounded("MONITOR_INTERVAL_SECONDS", self.default_interval, self.min_interval, self.max_interval),
        )
        fix("max_consecutive_failures", _bounded("MONITOR_MAX_FAILURES", self.max_consecutive_failures, 1, 100))
        fix("notify_cooldown", _bounded("NOTIFY_COOLDOWN_SECONDS", self.notify_cooldown, 0, 86400))
        fix("port", _bounded("PORT", self.port, 1, 65535))
        if self.seat_provider not in ("mock", "official"):
            log.warning("SEAT_PROVIDER=%r 은(는) 알 수 없는 값이라 mock 을 사용합니다.", self.seat_provider)
            fix("seat_provider", "mock")


def get_settings() -> Settings:
    return Settings()
