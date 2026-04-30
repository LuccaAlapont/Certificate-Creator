"""Certificate Creator — FastAPI application."""
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.routes.auth import router as auth_router, _is_valid
from backend.routes.templates import router as templates_router
from backend.routes.generate import router as generate_router
from backend.routes.convert import router as convert_router
from backend.routes.drive import router as drive_router
from backend.services.cleanup import start_cleanup_scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

BASE_DIR     = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOADS_DIR  = BASE_DIR / "uploads"
OUTPUTS_DIR  = BASE_DIR / "outputs"

_AUTH_ENABLED = bool(os.environ.get("APP_PASSWORD", ""))

# Routes that are always public (no session required)
_PUBLIC_PREFIXES = (
    "/login",
    "/api/auth/login",
    "/static/css/",
    "/static/js/auth.js",
)

app = FastAPI(title="Certificate Creator")


@app.middleware("http")
async def session_guard(request: Request, call_next):
    if not _AUTH_ENABLED:
        return await call_next(request)

    path = request.url.path
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return await call_next(request)

    token = request.cookies.get("cc_session")
    if _is_valid(token):
        return await call_next(request)

    # API requests → 401 JSON; page requests → redirect to /login
    if path.startswith("/api/"):
        return Response('{"detail":"Não autenticado"}', status_code=401,
                        media_type="application/json")
    return RedirectResponse("/login", status_code=302)


UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "fonts").mkdir(parents=True, exist_ok=True)

init_db()

_output_max_days = int(os.environ.get("OUTPUT_MAX_DAYS", "7"))
start_cleanup_scheduler(OUTPUTS_DIR, max_age_days=_output_max_days)

app.include_router(auth_router)
app.include_router(templates_router, prefix="/api")
app.include_router(generate_router,  prefix="/api")
app.include_router(convert_router,   prefix="/api")
app.include_router(drive_router,     prefix="/api")

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static",  StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/login")
def login_page():
    return FileResponse(str(FRONTEND_DIR / "login.html"))


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
