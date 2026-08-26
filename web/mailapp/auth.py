"""Авторизация: пароль → токен-сессия (persistent), logout чистит cookie.

Семантика ответов: 200 + {"ok": false, "error": "auth"} вместо 401 —
внешний прокси *.v2.site конвертирует 401 в 502 (проверено 2026-08-26).
"""
from __future__ import annotations

import json
import os
import secrets

from fastapi import Response
from fastapi.responses import JSONResponse

from .config import AUTH_PASSWORD, SESSIONS_FILE, SESSIONS_TTL


def _load_sessions() -> set[str]:
    try:
        with open(SESSIONS_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_sessions(sessions: set[str]):
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sorted(sessions), f)
        os.chmod(SESSIONS_FILE, 0o600)
    except Exception:
        pass


SESSIONS: set[str] = _load_sessions()


def _authed(session: str | None) -> bool:
    """Только реальный токен из хранилища. (v2: раньше пускала ЛЮБАЯ cookie)"""
    return bool(session) and session in SESSIONS


def auth_error() -> JSONResponse:
    return JSONResponse({"ok": False, "error": "auth"})


def login(body: dict, response: Response):
    if body.get("password") != AUTH_PASSWORD:
        return JSONResponse({"ok": False, "error": "wrong password"})
    token = secrets.token_hex(16)
    SESSIONS.add(token)
    _save_sessions(SESSIONS)
    response.set_cookie(
        "mail_session", token, httponly=True, samesite="lax",
        max_age=SESSIONS_TTL, path="/",
    )
    return {"ok": True}


def logout(response: Response, session: str | None):
    if session:
        SESSIONS.discard(session)
        _save_sessions(SESSIONS)
    response.delete_cookie("mail_session", path="/")
    return {"ok": True}
