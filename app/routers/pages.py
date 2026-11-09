from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import __version__

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    st = request.app.state
    return templates.TemplateResponse(
        request,
        "index.html",
        {"is_demo": st.provider.is_demo, "version": __version__, "official_url": st.settings.official_seat_url},
    )
