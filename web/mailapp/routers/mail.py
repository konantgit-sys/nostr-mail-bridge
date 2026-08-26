"""API-роутеры: status, mails (CRUD), send, outbox.

Каждый эндпоинт независим — можно вынести на отдельный сервер
(горизонтальное развитие), заменив только конфиг DB.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import config as cfg
from ..config import MAIL_ADDR, NPUB, PUBKEY, RELAYS, LIGHTNING, DOMAIN
from ..db import connect, execute, query
from ..auth import _authed, auth_error, login as do_login, logout as do_logout
from .. import bridge as bridge_mod

router = APIRouter()


# ── статус / NIP-05 ─────────────────────────────────────
@router.get("/api/status")
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


@router.get("/.well-known/nostr.json")
def nip05(name: str = ""):
    return JSONResponse({"names": {"_smtp": PUBKEY, NPUB: PUBKEY}})


# ── auth ────────────────────────────────────────────────
@router.post("/api/login")
def login(body: dict, response: Response):
    return do_login(body, response)


@router.post("/api/logout")
def logout(response: Response, session: str | None = Cookie(default=None, alias="mail_session")):
    return do_logout(response, session)


# ── входящие ────────────────────────────────────────────
@router.get("/api/mails")
def mails(session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return auth_error()
    rows = query(
        cfg.DB,
        "SELECT id, message_id, from_addr, subject, body, received_at, is_read "
        "FROM inbox ORDER BY received_at DESC LIMIT 200",
    )
    for r in rows:
        r["is_read"] = bool(r["is_read"])
        r["from"] = r.pop("from_addr")
    return {"ok": True, "mails": rows}


@router.get("/api/mails/{mid}")
def mail_detail(mid: int, session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return auth_error()
    with connect(cfg.DB) as conn:
        cur = conn.execute("UPDATE inbox SET is_read=1 WHERE id=?", (mid,))
        if cur.rowcount == 0:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        row = conn.execute(
            "SELECT id, message_id, sender_pubkey, from_addr, to_addr, subject, body, received_at, is_read "
            "FROM inbox WHERE id=?", (mid,)
        ).fetchone()
    m = dict(row)
    m["is_read"] = bool(m["is_read"])
    m["from"] = m.pop("from_addr")
    m["to"] = m.pop("to_addr")
    return {"ok": True, "mail": m}


@router.post("/api/mails/{mid}/read")
def mail_set_read(mid: int, body: dict, session: str | None = Cookie(default=None, alias="mail_session")):
    """Отметить письмо прочитанным/непрочитанным: {"read": true|false}"""
    if not _authed(session):
        return auth_error()
    read = bool(body.get("read", True))
    n = execute(cfg.DB, "UPDATE inbox SET is_read=? WHERE id=?", (1 if read else 0, mid))
    if n == 0:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return {"ok": True, "id": mid, "is_read": read}


@router.delete("/api/mails/{mid}")
def mail_delete(mid: int, session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return auth_error()
    n = execute(cfg.DB, "DELETE FROM inbox WHERE id=?", (mid,))
    if n == 0:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return {"ok": True, "deleted": mid}


# ── отправка / исходящие ────────────────────────────────
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
    from mailbridge.mail_bridge import _npub_to_hex  # local import
    return _npub_to_hex(to)


@router.post("/api/send")
def send_mail_api(body: SendBody, session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return auth_error()
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

        from mailbridge.nip44 import pubkey_from_privkey  # noqa: F401
        from mailbridge.nip59 import wrap_mail  # noqa: F401
        from mailbridge.mail_message import build_mail, parse_mail, MAIL_KIND  # noqa: F401
        

        mail_text = build_mail(MAIL_ADDR, to_npub, subject, mail_body,
                               in_reply_to=body.in_reply_to or None)
        gw = wrap_mail(cfg.NSEC, to_pub, MAIL_KIND, mail_text, [["p", to_pub]])
        br = bridge_mod.get_bridge()
        accepted = br.publish(gw) if br else []
        with connect(cfg.DB) as conn:
            conn.execute(
                "INSERT INTO outbox (message_id, recipient_pubkey, subject, body, sent_at, raw_event) "
                "VALUES (?,?,?,?,?,?)",
                (parse_mail(mail_text)["message_id"], to_pub, subject, mail_body,
                 int(time.time()), json.dumps(gw, ensure_ascii=False)),
            )
        return {"ok": True, "published": len(accepted), "event_id": gw["id"][:16]}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/outbox")
def outbox(session: str | None = Cookie(default=None, alias="mail_session")):
    if not _authed(session):
        return auth_error()
    rows = query(
        cfg.DB,
        "SELECT id, message_id, recipient_pubkey, subject, body, sent_at FROM outbox "
        "ORDER BY sent_at DESC LIMIT 100",
    )
    for r in rows:
        r["to"] = r.pop("recipient_pubkey")
    return {"ok": True, "outbox": rows}
