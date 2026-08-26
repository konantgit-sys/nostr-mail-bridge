"""
Nostr Mail — API тесты (pytest).

Покрытие:
- Авторизация: неверный пароль, вход, выход, защита API.
- РЕГРЕССИЯ v1: раньше ЛЮБАЯ cookie пускала — теперь только реальный токен.
- CRUD писем: список, деталь, прочитано/непрочитано, удаление.
- Отправка: валидация (тема/тело/адресат), успех.
- Outbox, NIP-05 discovery.

Запуск:  cd sites/cryter-mail && NO_BRIDGE=1 python3 -m pytest tests/test_api.py -v
"""

import os
import sys
import sqlite3

import pytest

os.environ["NO_BRIDGE"] = "1"  # мост не стартуем в тестах

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

NPUB = appmod.NPUB
PUBKEY = appmod.PUBKEY
PASSWORD = appmod.AUTH_PASSWORD


@pytest.fixture()
def db(tmp_path):
    """Временная БД со схемой inbox/outbox + 2 письма."""
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT, sender_pubkey TEXT, from_addr TEXT, to_addr TEXT,
            subject TEXT, body TEXT, received_at INTEGER, is_read INTEGER DEFAULT 0,
            raw_event TEXT
        );
        CREATE TABLE outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT, recipient_pubkey TEXT, subject TEXT, body TEXT,
            sent_at INTEGER, raw_event TEXT
        );
        INSERT INTO inbox (message_id, sender_pubkey, from_addr, to_addr, subject, body, received_at, is_read)
        VALUES ('<m1@test>', 'aaa', 'npub1a…@cryter-mail.v2.site', 'npub1b…@cryter-mail.v2.site', 'Привет', 'Тело 1', 1000, 0),
               ('<m2@test>', 'bbb', 'npub1c…@cryter-mail.v2.site', 'npub1b…@cryter-mail.v2.site', 'Срочно', 'Тело 2', 2000, 1);
        INSERT INTO outbox (message_id, recipient_pubkey, subject, body, sent_at)
        VALUES ('<o1@test>', 'ccc', 'Отправленное', 'Тело', 1500);
        """
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def client(db, tmp_path, monkeypatch):
    """Чистый клиент: временная БД, чистые сессии."""
    monkeypatch.setattr(appmod, "DB", db)
    monkeypatch.setattr(appmod, "SESSIONS", set())
    monkeypatch.setattr(appmod, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    with TestClient(appmod.app) as c:
        yield c


def _login(client, password=PASSWORD):
    return client.post("/api/login", json={"password": password})


# ── авторизация ─────────────────────────────────────────

def test_login_wrong_password(client):
    r = _login(client, "wrong")
    assert r.status_code == 401
    assert r.json()["ok"] is False


def test_login_ok_sets_cookie(client):
    r = _login(client)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "mail_session" in r.cookies


def test_mails_requires_auth(client):
    r = client.get("/api/mails")
    assert r.status_code == 401


def test_any_cookie_rejected(client):
    """РЕГРЕССИЯ v1: раньше любая cookie пускала. Теперь — только реальный токен."""
    r = client.get("/api/mails", cookies={"mail_session": "deadbeef"})
    assert r.status_code == 401


def test_logout_invalidates_session(client):
    r = _login(client)
    token = r.cookies["mail_session"]
    assert client.get("/api/mails", cookies={"mail_session": token}).status_code == 200
    r2 = client.post("/api/logout", cookies={"mail_session": token})
    assert r2.status_code == 200
    assert client.get("/api/mails", cookies={"mail_session": token}).status_code == 401


def test_status_ok_flag(client):
    assert client.get("/api/status").json()["ok"] is False
    r = _login(client)
    assert client.get("/api/status", cookies={"mail_session": r.cookies["mail_session"]}).json()["ok"] is True


# ── письма: список/деталь ────────────────────────────────

def test_mails_list(client):
    r = _login(client)
    d = client.get("/api/mails", cookies={"mail_session": r.cookies["mail_session"]})
    assert d.status_code == 200
    mails = d.json()["mails"]
    assert len(mails) == 2
    assert mails[0]["subject"] == "Срочно"  # DESC by received_at
    assert mails[0]["is_read"] is True
    assert mails[1]["subject"] == "Привет"
    assert mails[1]["is_read"] is False


def test_mail_detail_marks_read(client):
    r = _login(client)
    s = r.cookies["mail_session"]
    d = client.get("/api/mails/2", cookies={"mail_session": s})
    assert d.status_code == 200
    assert d.json()["mail"]["subject"] == "Срочно"
    # повторный запрос списка — письмо 2 прочитано (уже было), письмо 1 — не тронуто
    d2 = client.get("/api/mails/1", cookies={"mail_session": s})
    assert d2.json()["mail"]["is_read"] is True  # деталь автоматически прочитала


def test_mail_detail_404(client):
    r = _login(client)
    assert client.get("/api/mails/999", cookies={"mail_session": r.cookies["mail_session"]}).status_code == 404


# ── прочитано/непрочитано ────────────────────────────────

def test_mail_set_read_unread(client):
    r = _login(client)
    s = r.cookies["mail_session"]
    d = client.post("/api/mails/1/read", json={"read": True}, cookies={"mail_session": s})
    assert d.status_code == 200 and d.json()["is_read"] is True
    d = client.post("/api/mails/1/read", json={"read": False}, cookies={"mail_session": s})
    assert d.json()["is_read"] is False
    # проверить в списке
    lst = client.get("/api/mails", cookies={"mail_session": s}).json()["mails"]
    assert lst[1]["is_read"] is False


def test_mail_set_read_404(client):
    r = _login(client)
    assert client.post("/api/mails/999/read", json={"read": True},
                       cookies={"mail_session": r.cookies["mail_session"]}).status_code == 404


# ── удаление ─────────────────────────────────────────────

def test_mail_delete(client):
    r = _login(client)
    s = r.cookies["mail_session"]
    d = client.delete("/api/mails/1", cookies={"mail_session": s})
    assert d.status_code == 200 and d.json()["deleted"] == 1
    assert client.get("/api/mails/1", cookies={"mail_session": s}).status_code == 404
    assert client.delete("/api/mails/1", cookies={"mail_session": s}).status_code == 404


# ── отправка ─────────────────────────────────────────────

def test_send_requires_auth(client):
    assert client.post("/api/send", json={"to_npub": NPUB, "subject": "s", "body": "b"}).status_code == 401


def test_send_validation(client):
    r = _login(client)
    s = r.cookies["mail_session"]
    # пустая тема
    assert client.post("/api/send", json={"to_npub": NPUB, "subject": "", "body": "b"},
                       cookies={"mail_session": s}).status_code == 400
    # пустое тело
    assert client.post("/api/send", json={"to_npub": NPUB, "subject": "s", "body": "  "},
                       cookies={"mail_session": s}).status_code == 400
    # мусорный адресат
    assert client.post("/api/send", json={"to_npub": "not-a-npub", "subject": "s", "body": "b"},
                       cookies={"mail_session": s}).status_code == 400


def test_send_ok_writes_outbox(client):
    r = _login(client)
    s = r.cookies["mail_session"]
    d = client.post("/api/send", json={"to_npub": NPUB, "subject": "Тема", "body": "Тело"},
                    cookies={"mail_session": s})
    assert d.status_code == 200
    assert d.json()["ok"] is True
    assert "event_id" in d.json()
    # в outbox появилось
    ob = client.get("/api/outbox", cookies={"mail_session": s}).json()["outbox"]
    assert len(ob) == 2
    assert ob[0]["subject"] == "Тема"


def test_send_full_address(client):
    """Адресат в формате npub@домен тоже принимается."""
    r = _login(client)
    s = r.cookies["mail_session"]
    d = client.post("/api/send", json={"to_npub": f"{NPUB}@cryter-mail.v2.site",
                                       "subject": "Полный адрес", "body": "Тело"},
                    cookies={"mail_session": s})
    assert d.status_code == 200 and d.json()["ok"] is True


# ── outbox / nip05 ────────────────────────────────────────

def test_outbox_requires_auth(client):
    assert client.get("/api/outbox").status_code == 401


def test_outbox_list(client):
    r = _login(client)
    d = client.get("/api/outbox", cookies={"mail_session": r.cookies["mail_session"]})
    assert d.status_code == 200
    assert len(d.json()["outbox"]) == 1
    assert d.json()["outbox"][0]["subject"] == "Отправленное"


def test_nip05_discovery(client):
    d = client.get("/.well-known/nostr.json")
    assert d.status_code == 200
    names = d.json()["names"]
    assert names["_smtp"] == PUBKEY
    assert names[NPUB] == PUBKEY


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
