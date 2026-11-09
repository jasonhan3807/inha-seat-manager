"""INHA SEAT MANAGER 진입점.

실행:  python -m app.main   (또는 scripts/run.sh)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.database import Database
from app.monitoring import SeatMonitor
from app.providers import SeatProvider, create_provider
from app.routers import api, pages

STATIC_DIR = Path(__file__).resolve().parent / "static"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(
    settings: Settings | None = None, provider: SeatProvider | None = None, db: Database | None = None
) -> FastAPI:
    settings = settings or get_settings()
    provider = provider or create_provider(settings.seat_provider, settings.mock_seed)
    db = db or Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 이전 실행에서 모니터링 중이었다면 다시 켠다.
        if settings.monitor_autostart and db.get_setting("monitor_running") == "1" and db.list_watches():
            app.state.monitor.start()
        yield
        # 종료 시에는 실행 여부 설정을 바꾸지 않는다 (다음 실행 때 이어서 모니터링).
        await app.state.monitor.shutdown()

    app = FastAPI(title="INHA SEAT MANAGER", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.settings = settings
    app.state.provider = provider
    app.state.db = db
    app.state.monitor = SeatMonitor(db, provider, settings)

    @app.middleware("http")
    async def same_origin_guard(request: Request, call_next):
        # 다른 웹사이트가 이 로컬 서버로 요청을 보내는 것(CSRF)을 막는다.
        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host", ""):
                return JSONResponse({"detail": "허용되지 않은 출처의 요청입니다."}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    app.include_router(api.router)
    app.include_router(pages.router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    uvicorn.run(create_app(s), host=s.host, port=s.port)


if __name__ == "__main__":
    run()
