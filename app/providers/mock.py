"""모의(DEMO) 좌석 데이터.

주의: 아래 열람실 이름/좌석 수/배치는 실제 정석학술정보관 구조가 아니다.
화면에는 항상 DEMO 표시가 붙는다.
"""

from __future__ import annotations

import random
import threading
import time

from .base import ProviderError, Room, Seat, SeatProvider, SeatStatus

DEMO_ROOMS = [
    Room("demo-a", "DEMO 열람실 A", "가상 위치 (실제 아님)", 0, 6, 10, True),
    Room("demo-b", "DEMO 열람실 B", "가상 위치 (실제 아님)", 0, 5, 8, True),
    Room("demo-c", "DEMO 열람실 C (소형)", "가상 위치 (실제 아님)", 0, 4, 6, True),
]


class MockSeatProvider(SeatProvider):
    name = "mock"
    is_demo = True
    supports_assignment = True  # DEMO 배정 시뮬레이션만 (실제 학교 시스템과 무관)

    def __init__(
        self,
        seed: int | None = None,
        change_rate: float = 0.08,
        auto_tick_seconds: float | None = 10.0,
    ):
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self.change_rate = change_rate
        self.fail_next = 0  # 테스트/데모용: 다음 N번 조회를 실패시킴
        # 조회 시 이 시간(초)이 지났으면 자동으로 상태를 조금 바꾼다. None이면 끔(테스트용).
        self.auto_tick_seconds = auto_tick_seconds
        self._last_tick = time.monotonic()
        self._rooms: dict[str, Room] = {}
        self._seats: dict[str, dict[str, Seat]] = {}
        for tmpl in DEMO_ROOMS:
            seats: dict[str, Seat] = {}
            n = 0
            for r in range(tmpl.rows):
                for c in range(tmpl.cols):
                    # 통로 표현: 가운데 열은 비워둔다
                    if tmpl.cols >= 8 and c == tmpl.cols // 2:
                        continue
                    n += 1
                    seats[str(n)] = Seat(str(n), f"{n}번", r, c, self._random_status())
            room = Room(tmpl.id, tmpl.name, tmpl.location, len(seats), tmpl.rows, tmpl.cols, True)
            self._rooms[room.id] = room
            self._seats[room.id] = seats

    def _random_status(self) -> SeatStatus:
        x = self._rng.random()
        if x < 0.25:
            return SeatStatus.AVAILABLE
        if x < 0.85:
            return SeatStatus.OCCUPIED
        if x < 0.95:
            return SeatStatus.AWAY
        return SeatStatus.DISABLED

    def _check_fail(self) -> None:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ProviderError("DEMO: 의도적으로 발생시킨 조회 실패")

    def tick(self) -> None:
        """시간 경과를 흉내내어 일부 좌석 상태를 바꾼다."""
        with self._lock:
            self._last_tick = time.monotonic()
            for seats in self._seats.values():
                for seat in seats.values():
                    if seat.status == SeatStatus.DISABLED:
                        continue
                    if self._rng.random() < self.change_rate:
                        seat.status = self._rng.choice(
                            [SeatStatus.AVAILABLE, SeatStatus.OCCUPIED, SeatStatus.OCCUPIED, SeatStatus.AWAY]
                        )

    def set_status(self, room_id: str, seat_id: str, status: SeatStatus) -> None:
        with self._lock:
            self._seats[room_id][seat_id].status = status

    def list_rooms(self) -> list[Room]:
        self._check_fail()
        return list(self._rooms.values())

    def get_seats(self, room_id: str) -> list[Seat]:
        self._check_fail()
        if room_id not in self._seats:
            raise KeyError(room_id)
        if self.auto_tick_seconds is not None and time.monotonic() - self._last_tick >= self.auto_tick_seconds:
            self.tick()
        with self._lock:
            return [Seat(s.id, s.label, s.row, s.col, s.status) for s in self._seats[room_id].values()]

    def assign_seat(self, room_id: str, seat_id: str) -> Seat:
        with self._lock:
            seat = self._seats.get(room_id, {}).get(seat_id)
            if seat is None:
                raise KeyError(seat_id)
            if seat.status != SeatStatus.AVAILABLE:
                raise ValueError("빈자리가 아니어서 배정할 수 없습니다.")
            seat.status = SeatStatus.OCCUPIED
            return Seat(seat.id, seat.label, seat.row, seat.col, seat.status)
