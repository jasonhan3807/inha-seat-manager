"""알림 문구 생성. 알림은 DB에 저장되고 웹 대시보드/브라우저 알림으로 전달된다."""

from __future__ import annotations

from datetime import datetime


def build_seat_available_message(
    room_name: str, seat_label: str, status_label: str, detected_at: datetime, official_url: str, is_demo: bool
) -> str:
    prefix = "[DEMO] " if is_demo else ""
    return (
        f"{prefix}빈자리 감지: {room_name} {seat_label}\n"
        f"감지 시각: {detected_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"현재 상태: {status_label}\n"
        f"배정은 공식 페이지에서 직접 진행하세요: {official_url}"
    )


def build_system_message(text: str) -> str:
    return f"[시스템] {text}"
