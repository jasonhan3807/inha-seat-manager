"""환경변수(.env)에서 설정을 읽는다. 비밀정보는 코드에 넣지 않는다."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


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
    max_interval: int = 3600
    # 연속 실패가 이 횟수에 도달하면 모니터링을 자동 중지한다.
    max_consecutive_failures: int = field(default_factory=lambda: _int("MONITOR_MAX_FAILURES", 5))
    # 같은 좌석에 대해 다시 알림을 보내기 전 최소 대기 시간(초)
    notify_cooldown: int = field(default_factory=lambda: _int("NOTIFY_COOLDOWN_SECONDS", 300))
    # 사용자가 직접 배정할 공식 페이지 (정석학술정보관 홈페이지)
    official_seat_url: str = field(default_factory=lambda: os.getenv("OFFICIAL_SEAT_URL", "https://lib.inha.ac.kr"))
    # 모의 데이터 무작위 시드 (테스트 재현용)
    mock_seed: int | None = field(default_factory=lambda: _int("MOCK_SEED", 0) or None)
    monitor_autostart: bool = field(default_factory=lambda: os.getenv("MONITOR_AUTOSTART", "1") == "1")


def get_settings() -> Settings:
    return Settings()
