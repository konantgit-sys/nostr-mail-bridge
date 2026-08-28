"""
Nostr Mail — Blossom (NIP-96) тесты.

Покрытие:
- Внутренний upload (session) → скачивание по /media/<sha256> → содержимое совпадает.
- Внешний NIP-96 upload: /upload с Authorization: Nostr (kind 27235) → 200 + url.
- Невалидный NIP-98 auth → 401.
- Лимит размера → 413.
- DELETE /media/<sha> без владельца → 403.

Запуск: cd sites/cryter-mail && NO_BRIDGE=1 python3 -m pytest tests/test_blossom.py -v
"""

import os
import sys
import base64
import json
import time

import pytest

os.environ["NO_BRIDGE"] = "1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# mailbridge (src) — как в start.sh (PYTHONPATH при запуске uvicorn)
sys.path.insert(0, "/home/agent/data/projects/nostr-mail-bridge/src")
sys.path.insert(0, "/home/agent/data/projects/nostr-mail-bridge/deps")
import app as appmod  # noqa: E402
import mailapp.config as cfg  # noqa: E402
import mailapp.auth as auth  # noqa: E402
import mailapp.routers.blossom as blossom  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

PASSWORD = cfg.AUTH_PASSWORD
TEST_CONTENT = b"NIP-96 Blossom test payload \x00\x01\x02\xff" * 100


@pytest.fixture()
def db(tmp_path):
    import sqlite3
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT, sender_pubkey TEXT, from_addr TEXT, to_addr TEXT,
            subject TEXT, body TEXT, received_at INTEGER, is_read INTEGER DEFAULT 0,
            raw_event TEXT, owner TEXT DEFAULT ''
        );
        CREATE TABLE outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT, recipient_pubkey TEXT, subject TEXT, body TEXT,
            sent_at INTEGER, raw_event TEXT, owner TEXT DEFAULT ''
        );
        """
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def client(db, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "DB", db)
    monkeypatch.setattr(cfg, "DEFAULT_OWNER", "OWNER_A")
    monkeypatch.setattr(cfg, "OWNERS", [{"nsec_hex": cfg.NSEC, "pubkey_hex": "OWNER_A", "address": "a@x", "label": "Крайтер", "npub": cfg.NPUB}])
    monkeypatch.setattr(cfg, "OWNER_INDEX", {"OWNER_A": {"nsec_hex": cfg.NSEC, "pubkey_hex": "OWNER_A", "address": "a@x", "label": "Крайтер", "npub": cfg.NPUB}})
    monkeypatch.setattr(cfg, "ACCOUNTS_FILE", str(tmp_path / "mail_accounts.json"))
    monkeypatch.setattr(cfg, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(auth, "SESSIONS", {})
    monkeypatch.setattr(blossom, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(blossom, "PUBLIC_BASE", "https://test.local")
    os.makedirs(str(tmp_path / "uploads"), exist_ok=True)
    with TestClient(appmod.app) as c:
        yield c


def _login(client):
    return client.post("/api/login", json={"password": PASSWORD})


def _nip98_auth(privkey_hex: str, url: str, method: str = "POST") -> str:
    from mailbridge.nip44 import pubkey_from_privkey
    from mailbridge.nip59 import sign_event
    pub = pubkey_from_privkey(privkey_hex)
    created = int(time.time())
    eid, sig = sign_event(pub, created, 27235, [["u", url], ["method", method]], "", privkey_hex)
    ev = {"id": eid, "pubkey": pub, "created_at": created, "kind": 27235,
          "tags": [["u", url], ["method", method]], "content": "", "sig": sig}
    return "Nostr " + base64.b64encode(json.dumps(ev).encode()).decode()


# ── внутренний upload (session) ─────────────────────────

def test_internal_upload_download_roundtrip(client):
    _login(client)
    b64 = base64.b64encode(TEST_CONTENT).decode()
    r = client.post("/api/blossom/upload", json={"filename": "t.bin", "mime": "application/octet-stream", "data_base64": b64})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["url"].startswith("https://test.local/media/")
    sha = data["url"].rsplit("/", 1)[1]
    assert len(sha) == 64

    r2 = client.get(f"/media/{sha}")
    assert r2.status_code == 200
    assert r2.content == TEST_CONTENT


def test_internal_upload_requires_auth(client):
    r = client.post("/api/blossom/upload", json={"data_base64": base64.b64encode(b"x").decode()})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_internal_upload_too_large(client, monkeypatch):
    _login(client)
    monkeypatch.setattr(blossom, "MAX_UPLOAD", 10)  # 10 байт
    r = client.post("/api/blossom/upload", json={"data_base64": base64.b64encode(b"x" * 100).decode()})
    assert r.status_code == 413


# ── внешний NIP-96 upload ───────────────────────────────

def test_nip96_upload_with_auth(client):
    r = client.post("/upload", content=TEST_CONTENT,
                    headers={"Content-Type": "application/octet-stream",
                             "Authorization": _nip98_auth(cfg.NSEC, "http://testserver/upload", "POST")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["url"].startswith("https://test.local/media/")
    sha = data["url"].rsplit("/", 1)[1]
    r2 = client.get(f"/media/{sha}")
    assert r2.content == TEST_CONTENT


def test_nip96_upload_bad_auth(client):
    # без заголовка
    r = client.post("/upload", content=TEST_CONTENT)
    assert r.status_code == 401
    # мусор в заголовке
    r = client.post("/upload", content=TEST_CONTENT,
                    headers={"Authorization": "Nostr aGVsbG8="})
    assert r.status_code == 401


def test_nip96_upload_wrong_url_tag(client):
    # auth-событие подписано для другого URL
    r = client.post("/upload", content=TEST_CONTENT,
                    headers={"Authorization": _nip98_auth(cfg.NSEC, "https://evil.local/upload", "POST")})
    assert r.status_code == 401


# ── DELETE ───────────────────────────────────────────────

def test_delete_requires_owner(client):
    r = client.post("/upload", content=b"delete me",
                    headers={"Authorization": _nip98_auth(cfg.NSEC, "http://testserver/upload", "POST")})
    sha = r.json()["url"].rsplit("/", 1)[1]
    # чужой ключ
    import secp256k1
    other = secp256k1.PrivateKey()
    r = client.request("DELETE", f"/media/{sha}",
                       headers={"Authorization": _nip98_auth(other.serialize(), f"http://testserver/media/{sha}", "DELETE")})
    assert r.status_code == 403
    # владелец
    r = client.request("DELETE", f"/media/{sha}",
                       headers={"Authorization": _nip98_auth(cfg.NSEC, f"http://testserver/media/{sha}", "DELETE")})
    assert r.status_code == 200
    assert r.json()["ok"] is True
