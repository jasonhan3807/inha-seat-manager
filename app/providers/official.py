"""실제 정석학술정보관 좌석 시스템 연동 (현재 비활성).

docs/SEAT_SYSTEM_RESEARCH.md 참고:
- 공식 API 또는 허용된 자동 조회 방식이 확인되지 않았다.
- 실제 URL/HTML 구조를 추측해서 호출하지 않는다.
- 자동 배정은 구현하지 않는다 (규정상 허용 여부 미확인).

허용된 조회 방식이 확인되면 이 클래스에 구현한다.
"""

from __future__ import annotations

from .base import ProviderNotConfigured, Room, Seat, SeatProvider


class OfficialSeatProvider(SeatProvider):
    name = "official"
    is_demo = False
    supports_assignment = False

    MESSAGE = (
        "공식 좌석 시스템 연동은 아직 비활성 상태입니다. 학교의 공식 API 또는 허용된 조회 방식이 "
        "확인되지 않았습니다. docs/SEAT_SYSTEM_RESEARCH.md를 참고하세요."
    )

    def list_rooms(self) -> list[Room]:
        raise ProviderNotConfigured(self.MESSAGE)

    def get_seats(self, room_id: str) -> list[Seat]:
        raise ProviderNotConfigured(self.MESSAGE)
