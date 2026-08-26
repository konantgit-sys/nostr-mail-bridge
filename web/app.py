"""
Nostr Mail — веб-клиент + мост (Фаза 2, v2).

FastAPI: статика (inbox UI), API (auth/mails/send/outbox), NIP-05 discovery.
В фоне (lifespan) крутится MailBridge — приём писем с релеев в inbox.db.

v2 (2026-08-26):
- Реальная авторизация: токен-сессии (persistent), logout очищает cookie.
  Раньше _authed() пускал ЛЮБУЮ cookie — почта была открыта всем.
- CRUD писем: удаление, отметка прочитано/непрочитано.
- Валидация адресата (npub или полный адрес npub@домен).
- Отдельный outbox (вкладка «Отправленные» раньше показывала входящие).

Запуск: uvicorn app:app --host 0.0.0.0 --port 8123
Тесты: NO_BRIDGE=1 pytest tests/test_api.py (мост не стартует)
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time

from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")

with open(CONFIG_PATH) as f:
    CFG = json.load(f)

NSEC = CFG["nsec_hex"]
PUBKEY = CFG["pubkey_hex"]
NPUB = CFG["npub"]
MAIL_ADDR = CFG["mail_address"]
DOMAIN = CFG["mail_domain"]
DB = CFG["db"]
RELAYS = CFG["relays"]
LIGHTNING = CFG.get("lightning", "")
AUTH_PASSWORD = CFG.get("auth_password", "cryter-mail")
SESSIONS_FILE = os.path.join(BASE, ".sessions.json")
SESSIONS_TTL = 86400 * 7  # 7 дней

# ── мост (фоновый поток) ─────────────────────────────────
import sys

sys.path.insert(0, os.path.join(BASE, "..", "..", "projects", "nostr-mail-bridge", "src"))

from mailbridge.mail_bridge import MailBridge  # noqa: E402
from mailbridge.nip44 import pubkey_from_privkey  # noqa: E402
from mailbridge.nip59 import wrap_mail  # noqa: E402
from mailbridge.mail_message import build_mail, parse_mail, MAIL_KIND  # noqa: E402

_bridge = None


def _start_bridge():
    global _bridge
    if os.environ.get("NO_BRIDGE") == "1":
        return  # тесты: мост не стартуем
    b = MailBridge(
        privkey_hex=NSEC,
        relays=RELAYS,
        db_path=DB,
        telegram_token=CFG.get("telegram_token", ""),
        telegram_chat_id=CFG.get("telegram_chat_id", ""),
    )
    _bridge = b
    t = threading.Thread(target=b.start, daemon=True)
    t.start()


app = FastAPI(title="Nostr Mail", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup():
    _start_bridge()


# ── статика ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "static", "index.html"))


# ── NIP-05: discovery моста для nostrmail.org ────────────
@app.get("/.well-known/nostr.json")
def nip05(name: str = ""):
    names = {"_smtp": PUBKEY, NPUB: PUBKEY}
    return JSONResponse({"names": names})


# ── auth (пароль → токен-сессия, cookie) ─────────────────
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


@app.post("/api/login")
def login(body: dict, response: Response):
    if body.get("password") != AUTH_PASSWORD:
        return JSONResponse({"ok": False, "error": "wrong password"}, status_code=401)
    token = secrets.token_hex(16)
    SESSIONS.add(token)
    _save_sessions(SESSIONS)
    response.set_cookie(
        "mail_session", token, httponly=True, samesite="lax",
        max_age=SESSIONS_TTL, path="/",
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response, session: str | None = Cookie(default=None, alias="mail_session")):
    if session:
        SESSIONS.discard(session)
        _save_sessions(SESSIONS)
    response.delete_cookie("mail_session", path="/")
    return {"ok": True}


# ── API ──────────────────────────────────────────────────
@app.get("/api/status")
def status(session: str | None = Cookie(default=None, alias="mail_session")):
    return {
        "ok": _authed(session),
        "address": MAIL_ADDR,
        "npub": NPUB,
        "pubkey": PUBKEY,
        "domain": DOMAIN,
        "relays": RELAYS,
        "lightning": LIGHTNING,
    }


@app.get("/api/mails")
def mails(session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    with sqlite3.connect(DB) as conn:
        rows = conn.execute(
            "SELECT id, message_id, from_addr, subject, body, received_at, is_read FROM inbox "
            "ORDER BY received_at DESC LIMIT 200"
        ).fetchall()
    return {"ok": True, "mails": [
        {
            "id": r[0], "message_id": r[1], "from": r[2], "subject": r[3],
            "body": r[4], "received_at": r[5], "is_read": bool(r[6]),
        } for r in rows
    ]}


@app.get("/api/mails/{mid}")
def mail_detail(mid: int, session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    with sqlite3.connect(DB) as conn:
        cur = conn.execute("UPDATE inbox SET is_read=1 WHERE id=?", (mid,))
        if cur.rowcount == 0:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        row = conn.execute(
            "SELECT id, message_id, sender_pubkey, from_addr, to_addr, subject, body, received_at, is_read "
            "FROM inbox WHERE id=?", (mid,)
        ).fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return {"ok": True, "mail": {
        "id": row[0], "message_id": row[1], "sender_pubkey": row[2],
        "from": row[3], "to": row[4], "subject": row[5], "body": row[6],
        "received_at": row[7], "is_read": bool(row[8]),
    }}


@app.post("/api/mails/{mid}/read")
def mail_set_read(mid: int, body: dict, session: str | None = Cookie(default=None, alias="mail_session")):
    """Отметить письмо прочитанным/непрочитанным: {"read": true|false}"""
    if not _authed(session):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    read = bool(body.get("read", True))
    with sqlite3.connect(DB) as conn:
        cur = conn.execute("UPDATE inbox SET is_read=? WHERE id=?", (1 if read else 0, mid))
        if cur.rowcount == 0:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return {"ok": True, "id": mid, "is_read": read}


@app.delete("/api/mails/{mid}")
def mail_delete(mid: int, session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    with sqlite3.connect(DB) as conn:
        cur = conn.execute("DELETE FROM inbox WHERE id=?", (mid,))
        if cur.rowcount == 0:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return {"ok": True, "deleted": mid}


class SendBody(BaseModel):
    to_npub: str
    subject: str
    body: str
    in_reply_to: str = ""


def _parse_recipient(to_npub: str) -> str | None:
    """Принимает npub или полный адрес npub@домен → hex pubkey."""
    to = to_npub.strip()
    if not to:
        return None
    if "@" in to:
        to = to.split("@")[0].strip()
    from mailbridge.mail_bridge import _npub_to_hex
    return _npub_to_hex(to)


@app.post("/api/send")
def send_mail_api(body: SendBody, session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    try:
        subject = body.subject.strip()
        mail_body = body.body.strip()
        if not subject:
            return JSONResponse({"ok": False, "error": "пустая тема"}, status_code=400)
        if len(subject) > 200:
            return JSONResponse({"ok": False, "error": "тема слишком длинная (макс 200)"}, status_code=400)
        if not mail_body:
            return JSONResponse({"ok": False, "error": "пустое письмо"}, status_code=400)
        if len(mail_body) > 20000:
            return JSONResponse({"ok": False, "error": "письмо слишком длинное (макс 20000)"}, status_code=400)
        to_pub = _parse_recipient(body.to_npub)
        if not to_pub:
            return JSONResponse({"ok": False, "error": "не удалось распознать npub адресата"}, status_code=400)
        to_npub = body.to_npub.strip()
        if "@" in to_npub:
            to_npub = to_npub.split("@")[0].strip()
        mail_text = build_mail(MAIL_ADDR, to_npub, subject, mail_body,
                               in_reply_to=body.in_reply_to or None)
        gw = wrap_mail(NSEC, to_pub, MAIL_KIND, mail_text, [["p", to_pub]])
        accepted = _bridge.publish(gw) if _bridge else []
        with sqlite3.connect(DB) as conn:
            conn.execute(
                "INSERT INTO outbox (message_id, recipient_pubkey, subject, body, sent_at, raw_event) "
                "VALUES (?,?,?,?,?,?)",
                (parse_mail(mail_text)["message_id"], to_pub, subject, mail_body,
                 int(time.time()), json.dumps(gw, ensure_ascii=False)),
            )
        return {"ok": True, "published": len(accepted), "event_id": gw["id"][:16]}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/outbox")
def outbox(session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    with sqlite3.connect(DB) as conn:
        rows = conn.execute(
            "SELECT id, message_id, recipient_pubkey, subject, body, sent_at FROM outbox "
            "ORDER BY sent_at DESC LIMIT 100"
        ).fetchall()
    return {"ok": True, "outbox": [
        {"id": r[0], "message_id": r[1], "to": r[2], "subject": r[3], "body": r[4], "sent_at": r[5]} for r in rows
    ]}
