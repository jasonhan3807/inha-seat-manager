"""희망 좌석 빈자리 모니터링.

규칙
- 조회 간격은 설정된 최소값보다 짧아질 수 없다 (학교 시스템 부담 방지).
- 희망 좌석이 여러 개여도 열람실당 한 번만 조회한다.
- 빈자리로 '바뀌는 순간'에만 알림을 보내고, 같은 좌석은 쿨다운 동안 다시 알리지 않는다.
- 조회 실패 시 간격을 점점 늘리고(백오프), 연속 실패가 한도에 도달하면 자동 중지한다.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from app.config import Settings
from app.database import Database
from app.database.db import now_iso
from app.notifications import build_seat_available_message, build_system_message
from app.providers import ProviderError, ProviderNotConfigured, SeatProvider, SeatStatus
from app.providers.base import STATUS_LABEL

log = logging.getLogger(__name__)

MAX_BACKOFF_FACTOR = 8


class SeatMonitor:
    def __init__(self, db: Database, provider: SeatProvider, settings: Settings):
        self.db = db
        self.provider = provider
        self.settings = settings
        saved = db.get_setting("monitor_interval")
        self.interval = self.clamp_interval(int(saved) if saved and saved.isdigit() else settings.default_interval)
        self.running = False
        self.consecutive_failures = 0
        self.last_check_at: str | None = None
        self.last_success_at: str | None = None
        self.last_error: str | None = None
        self.stopped_reason: str | None = None
        self.check_count = 0
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ---------- 설정 ----------
    def clamp_interval(self, seconds: int) -> int:
        return max(self.settings.min_interval, min(self.settings.max_interval, int(seconds)))

    def set_interval(self, seconds: int) -> int:
        self.interval = self.clamp_interval(seconds)
        self.db.set_setting("monitor_interval", str(self.interval))
        return self.interval

    def next_delay(self) -> int:
        factor = min(2 ** self.consecutive_failures, MAX_BACKOFF_FACTOR) if self.consecutive_failures else 1
        return min(self.interval * factor, self.settings.max_interval)

    # ---------- 1회 조회 ----------
    def check_once(self) -> dict:
        """희망 좌석을 한 번 확인한다. 동기 함수라 테스트하기 쉽다."""
        self.last_check_at = now_iso()
        self.check_count += 1
        watches = self.db.list_watches()
        result = {"checked_rooms": 0, "notified": [], "error": None}
        if not watches:
            return result

        by_room: dict[str, list[dict]] = defaultdict(list)
        for w in watches:
            by_room[w["room_id"]].append(w)

        try:
            for room_id, room_watches in by_room.items():
                room = self.provider.get_room(room_id)
                seats = {s.id: s for s in self.provider.get_seats(room_id)}
                result["checked_rooms"] += 1
                for w in room_watches:
                    seat = seats.get(w["seat_id"])
                    if seat is None:
                        continue
                    if self._should_notify(w, seat.status):
                        detected = datetime.now()
                        msg = build_seat_available_message(
                            room.name if room else room_id,
                            seat.label,
                            STATUS_LABEL[seat.status],
                            detected,
                            self.settings.official_seat_url,
                            self.provider.is_demo,
                        )
                        self.db.add_notification(
                            "seat_available",
                            msg,
                            room_id=room_id,
                            room_name=room.name if room else room_id,
                            seat_id=seat.id,
                            seat_label=seat.label,
                            status=seat.status.value,
                        )
                        self.db.update_watch_state(w["id"], seat.status.value, notified=True)
                        result["notified"].append({"room_id": room_id, "seat_id": seat.id})
                    elif w["last_status"] != seat.status.value:
                        self.db.update_watch_state(w["id"], seat.status.value, notified=False)
        except (ProviderError, KeyError, OSError) as exc:
            self._on_failure(exc)
            result["error"] = self.last_error
            return result

        self.consecutive_failures = 0
        self.last_error = None
        self.last_success_at = self.last_check_at
        self.db.log(
            "query",
            f"{result['checked_rooms']}개 열람실 조회, 희망 좌석 {len(watches)}개, 새 알림 {len(result['notified'])}건",
        )
        return result

    def _should_notify(self, watch: dict, status: SeatStatus) -> bool:
        if status != SeatStatus.AVAILABLE:
            return False
        if watch["last_status"] == SeatStatus.AVAILABLE.value:
            return False  # 이미 빈자리였음 → 중복 알림 방지
        if watch["last_notified_at"]:
            last = datetime.fromisoformat(watch["last_notified_at"])
            if datetime.now(last.tzinfo) - last < timedelta(seconds=self.settings.notify_cooldown):
                return False
        return True

    def _on_failure(self, exc: Exception) -> None:
        self.consecutive_failures += 1
        # 예외 메시지에 민감정보가 섞이지 않도록 타입과 짧은 메시지만 남긴다.
        self.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        self.db.log("query_error", f"조회 실패 ({self.consecutive_failures}회 연속): {self.last_error}")
        limit = self.settings.max_consecutive_failures
        if isinstance(exc, ProviderNotConfigured) or self.consecutive_failures >= limit:
            reason = (
                "데이터 제공자가 설정되지 않아 모니터링을 중지했습니다."
                if isinstance(exc, ProviderNotConfigured)
                else f"조회가 {self.consecutive_failures}회 연속 실패하여 모니터링을 자동 중지했습니다."
            )
            self.stop(reason)
            self.db.add_notification("system", build_system_message(f"{reason} 마지막 오류: {self.last_error}"))

    # ---------- 시작/중지 ----------
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.stopped_reason = None
        self.consecutive_failures = 0
        self.db.set_setting("monitor_running", "1")
        self.db.log("monitor", f"모니터링 시작 (간격 {self.interval}초)")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # 이벤트 루프 밖(테스트)에서는 상태만 바꾼다
        self._loop = loop
        self._wake = asyncio.Event()
        self._task = loop.create_task(self._run())

    def stop(self, reason: str = "사용자가 중지함") -> None:
        if not self.running:
            return
        self.running = False
        self.stopped_reason = reason
        self.db.set_setting("monitor_running", "0")
        self.db.log("monitor", f"모니터링 중지: {reason}")
        self._signal()

    def _signal(self) -> None:
        # stop()은 조회 스레드에서도 불릴 수 있으므로 이벤트 루프에 안전하게 전달한다.
        if self._loop is None or self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._wake.set)
        except RuntimeError:
            pass

    async def shutdown(self) -> None:
        self.running = False
        self._signal()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def _run(self) -> None:
        while self.running:
            try:
                await asyncio.to_thread(self.check_once)
            except Exception as exc:  # 예상치 못한 오류도 루프를 죽이지 않는다
                log.exception("monitor loop error")
                self._on_failure(exc)
            if not self.running:
                break
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.next_delay())
            except asyncio.TimeoutError:
                pass

    def status(self) -> dict:
        return {
            "running": self.running,
            "interval": self.interval,
            "min_interval": self.settings.min_interval,
            "next_delay": self.next_delay(),
            "consecutive_failures": self.consecutive_failures,
            "max_failures": self.settings.max_consecutive_failures,
            "last_check_at": self.last_check_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "stopped_reason": self.stopped_reason,
            "check_count": self.check_count,
        }
