"""JSON API. 화면(static/app.js)이 이 API를 사용한다."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import __version__
from app.providers import AssignmentNotPermitted, MockSeatProvider, ProviderError, SeatStatus

router = APIRouter(prefix="/api")


def _state(request: Request):
    return request.app.state


def _provider_error(exc: Exception) -> HTTPException:
    _ = exc
    return HTTPException(status_code=503, detail=f"좌석 정보를 가져오지 못했습니다: {str(exc)[:200]}")


# ---------- 시스템 ----------
@router.get("/health")
def health(request: Request):
    st = _state(request)
    return {"ok": True, "db": st.db.ping(), "provider": st.provider.name, "version": __version__}


@router.get("/system")
def system(request: Request):
    st = _state(request)
    provider_ok, provider_error = True, None
    try:
        st.provider.list_rooms()
    except ProviderError as exc:
        provider_ok, provider_error = False, str(exc)[:300]
    return {
        "version": __version__,
        "provider": st.provider.name,
        "is_demo": st.provider.is_demo,
        "provider_ok": provider_ok,
        "provider_error": provider_error,
        "supports_assignment": st.provider.supports_assignment,
        "db_ok": st.db.ping(),
        "official_url": st.settings.official_seat_url,
        "monitor": st.monitor.status(),
        "unread": st.db.unread_count(),
        "server_time": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# ---------- 열람실/좌석 ----------
@router.get("/rooms")
def rooms(request: Request):
    st = _state(request)
    try:
        result = []
        for room in st.provider.list_rooms():
            seats = st.provider.get_seats(room.id)
            d = room.to_dict()
            d["available"] = sum(1 for s in seats if s.status == SeatStatus.AVAILABLE)
            result.append(d)
        return {"is_demo": st.provider.is_demo, "rooms": result}
    except ProviderError as exc:
        raise _provider_error(exc) from exc


@router.get("/rooms/{room_id}/seats")
def room_seats(room_id: str, request: Request):
    st = _state(request)
    try:
        room = st.provider.get_room(room_id)
        if room is None:
            raise HTTPException(404, "열람실을 찾을 수 없습니다.")
        seats = st.provider.get_seats(room_id)
    except ProviderError as exc:
        raise _provider_error(exc) from exc
    watched = {w["seat_id"] for w in st.db.list_watches() if w["room_id"] == room_id}
    items = []
    for s in seats:
        d = s.to_dict()
        d["watched"] = s.id in watched
        items.append(d)
    return {
        "is_demo": st.provider.is_demo,
        "room": room.to_dict(),
        "seats": items,
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# ---------- 희망 좌석 ----------
class WatchIn(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)
    seat_id: str = Field(min_length=1, max_length=64)


MAX_WATCHES = 30


@router.get("/watches")
def list_watches(request: Request):
    st = _state(request)
    names = {}
    try:
        names = {r.id: r.name for r in st.provider.list_rooms()}
    except ProviderError:
        pass
    items = []
    for w in st.db.list_watches():
        w["room_name"] = names.get(w["room_id"], w["room_id"])
        items.append(w)
    return {"watches": items}


@router.post("/watches", status_code=201)
def add_watch(body: WatchIn, request: Request):
    st = _state(request)
    if len(st.db.list_watches()) >= MAX_WATCHES:
        raise HTTPException(400, f"희망 좌석은 최대 {MAX_WATCHES}개까지 등록할 수 있습니다.")
    try:
        room = st.provider.get_room(body.room_id)
        seat = next((s for s in st.provider.get_seats(body.room_id) if s.id == body.seat_id), None) if room else None
    except ProviderError as exc:
        raise _provider_error(exc) from exc
    if room is None or seat is None:
        raise HTTPException(404, "열람실 또는 좌석을 찾을 수 없습니다.")
    created = st.db.add_watch(body.room_id, body.seat_id, seat.label)
    if created is None:
        raise HTTPException(409, "이미 등록된 희망 좌석입니다.")
    st.db.log("watch", f"희망 좌석 등록: {room.name} {seat.label}")
    return created


@router.delete("/watches/{watch_id}")
def remove_watch(watch_id: int, request: Request):
    st = _state(request)
    w = st.db.get_watch(watch_id)
    if not w or not st.db.remove_watch(watch_id):
        raise HTTPException(404, "등록되지 않은 희망 좌석입니다.")
    st.db.log("watch", f"희망 좌석 삭제: {w['room_id']} {w['seat_label']}")
    st.monitor.on_watches_changed()  # 마지막 희망 좌석이면 모니터링 중지
    return {"ok": True, "monitor_running": st.monitor.running}


# ---------- 모니터링 ----------
class IntervalIn(BaseModel):
    seconds: int = Field(ge=1, le=86400)


@router.get("/monitor")
def monitor_status(request: Request):
    return _state(request).monitor.status()


@router.post("/monitor/start")
async def monitor_start(request: Request):
    st = _state(request)
    if not st.db.list_watches():
        raise HTTPException(400, "먼저 희망 좌석을 1개 이상 등록하세요.")
    st.monitor.start()  # async 엔드포인트여야 이벤트 루프에서 백그라운드 작업이 생성된다
    return st.monitor.status()


@router.post("/monitor/stop")
def monitor_stop(request: Request):
    st = _state(request)
    st.monitor.stop("사용자가 중지함")
    return st.monitor.status()


@router.post("/monitor/check")
def monitor_check(request: Request):
    """지금 한 번 확인 (수동)."""
    st = _state(request)
    result = st.monitor.check_once()
    return {"result": result, "status": st.monitor.status()}


@router.put("/monitor/interval")
def monitor_interval(body: IntervalIn, request: Request):
    st = _state(request)
    applied = st.monitor.set_interval(body.seconds)
    return {"interval": applied, "requested": body.seconds}


# ---------- 알림/이력 ----------
@router.get("/notifications")
def notifications(request: Request, after_id: int = 0, limit: int = 100):
    st = _state(request)
    limit = max(1, min(limit, 500))
    return {"notifications": st.db.list_notifications(limit, after_id), "unread": st.db.unread_count()}


@router.post("/notifications/read")
def notifications_read(request: Request):
    st = _state(request)
    st.db.mark_all_read()
    return {"ok": True}


@router.get("/history")
def history(request: Request, kind: str | None = None, limit: int = 200):
    st = _state(request)
    limit = max(1, min(limit, 1000))
    return {"history": st.db.list_history(limit, kind)}


# ---------- 배정 ----------
class AssignIn(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)
    seat_id: str = Field(min_length=1, max_length=64)
    confirm: bool = False


@router.post("/assign")
def assign(body: AssignIn, request: Request):
    """좌석 배정. 현재는 DEMO 시뮬레이션만 가능하다.

    실제 학교 시스템 자동 배정은 허용 여부가 확인되지 않아 구현하지 않았다.
    """
    st = _state(request)
    if not st.provider.supports_assignment:
        raise HTTPException(
            403,
            "자동 배정은 허용 여부가 확인되지 않아 사용할 수 없습니다. 공식 페이지에서 직접 배정하세요.",
        )
    if not body.confirm:
        raise HTTPException(400, "배정 전 사용자 확인(confirm=true)이 필요합니다.")
    try:
        seat = st.provider.assign_seat(body.room_id, body.seat_id)
    except AssignmentNotPermitted as exc:
        raise HTTPException(403, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "좌석을 찾을 수 없습니다.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    prefix = "[DEMO] " if st.provider.is_demo else ""
    st.db.log("assign", f"{prefix}좌석 배정: {body.room_id} {seat.label}")
    return {"ok": True, "is_demo": st.provider.is_demo, "seat": seat.to_dict()}


# ---------- DEMO 도구 (모의 데이터에서만) ----------
class DemoFailIn(BaseModel):
    count: int = Field(ge=0, le=20)


class DemoStatusIn(BaseModel):
    room_id: str
    seat_id: str
    status: SeatStatus


def _mock(request: Request) -> MockSeatProvider:
    p = _state(request).provider
    if not isinstance(p, MockSeatProvider):
        raise HTTPException(404, "DEMO 모드에서만 사용할 수 있습니다.")
    return p


@router.post("/demo/fail")
def demo_fail(body: DemoFailIn, request: Request):
    p = _mock(request)
    p.fail_next = body.count
    return {"fail_next": p.fail_next}


@router.post("/demo/status")
def demo_status(body: DemoStatusIn, request: Request):
    p = _mock(request)
    try:
        p.set_status(body.room_id, body.seat_id, body.status)
    except KeyError as exc:
        raise HTTPException(404, "좌석을 찾을 수 없습니다.") from exc
    return {"ok": True}
