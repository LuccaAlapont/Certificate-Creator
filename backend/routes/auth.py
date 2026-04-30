"""Auth routes — session-based login/logout."""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

_USER = os.environ.get("APP_USER", "admin")
_PASS = os.environ.get("APP_PASSWORD", "")

# In-memory sessions: {token: expiry_datetime}
_sessions: dict[str, datetime] = {}
_SESSION_DAYS = 7
_COOKIE = "cc_session"


def _is_valid(token: str | None) -> bool:
    if not token or token not in _sessions:
        return False
    if datetime.utcnow() > _sessions[token]:
        del _sessions[token]
        return False
    return True


def require_session(cc_session: str | None = Cookie(default=None)) -> bool:
    return _is_valid(cc_session)


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/api/auth/login")
def login(body: LoginBody, response: Response):
    if not _PASS:
        return JSONResponse({"error": "Servidor sem senha configurada (APP_PASSWORD)."}, status_code=500)
    ok = (
        secrets.compare_digest(body.username, _USER)
        and secrets.compare_digest(body.password, _PASS)
    )
    if not ok:
        return JSONResponse({"error": "Usuário ou senha incorretos."}, status_code=401)

    token = secrets.token_urlsafe(32)
    _sessions[token] = datetime.utcnow() + timedelta(days=_SESSION_DAYS)
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_SESSION_DAYS * 86400,
    )
    return {"ok": True}


@router.post("/api/auth/logout")
def logout(response: Response, cc_session: str | None = Cookie(default=None)):
    if cc_session and cc_session in _sessions:
        del _sessions[cc_session]
    response.delete_cookie(_COOKIE)
    return {"ok": True}


@router.get("/api/auth/check")
def check(cc_session: str | None = Cookie(default=None)):
    if _is_valid(cc_session):
        return {"authenticated": True, "user": _USER}
    return JSONResponse({"authenticated": False}, status_code=401)
