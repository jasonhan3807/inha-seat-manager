"""좌석 데이터 제공자 인터페이스.

모의 데이터(MockSeatProvider)와 실제 학교 시스템(OfficialSeatProvider)을
같은 인터페이스로 분리해 서로 독립적으로 동작하게 한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum


class SeatStatus(str, Enum):
    AVAILABLE = "available"      # 빈자리
    OCCUPIED = "occupied"        # 사용 중
    AWAY = "away"                # 외출/자리비움 (배정은 유지)
    DISABLED = "disabled"        # 사용 불가


STATUS_LABEL = {
    SeatStatus.AVAILABLE: "빈자리",
    SeatStatus.OCCUPIED: "사용 중",
    SeatStatus.AWAY: "자리비움",
    SeatStatus.DISABLED: "사용 불가",
}


@dataclass
class Seat:
    id: str
    label: str
    row: int
    col: int
    status: SeatStatus

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["status_label"] = STATUS_LABEL[self.status]
        return d


@dataclass
class Room:
    id: str
    name: str
    location: str
    total_seats: int
    rows: int
    cols: int
    is_demo: bool

    def to_dict(self) -> dict:
        return asdict(self)


class ProviderError(Exception):
    """조회 실패 (네트워크 오류, 응답 이상 등)."""


class ProviderNotConfigured(ProviderError):
    """허용된 연동 방식이 아직 확인/설정되지 않음."""


class AssignmentNotPermitted(Exception):
    """자동 배정이 허용되지 않음."""


class SeatProvider(ABC):
    name: str = "base"
    is_demo: bool = False
    # 자동 배정 지원 여부. 학교 규정상 허용이 확인된 경우에만 True.
    supports_assignment: bool = False

    @abstractmethod
    def list_rooms(self) -> list[Room]: ...

    @abstractmethod
    def get_seats(self, room_id: str) -> list[Seat]: ...

    def get_room(self, room_id: str) -> Room | None:
        return next((r for r in self.list_rooms() if r.id == room_id), None)

    def assign_seat(self, room_id: str, seat_id: str) -> Seat:
        raise AssignmentNotPermitted("이 데이터 제공자는 자동 배정을 지원하지 않습니다.")
