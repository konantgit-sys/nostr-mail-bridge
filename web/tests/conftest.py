"""Conftest: пути + общие фикстуры (db, client) для ВСЕХ тестов.

db/client продублированы из test_api.py (файловые фикстуры имеют приоритет
над conftest-овскими — test_api.py продолжит использовать свои).
"""
import json
import os
import sqlite3
import sys

import pytest

_WEB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MB = os.path.join(_WEB_ROOT, "..", "src")
_DEPS = os.path.join(_WEB_ROOT, "..", "deps")
for _p in (_MB, _DEPS):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# ── чистый клон: mailapp.config читает web/config.json при импорте ──
# Если конфига нет (репо свежее, config.json в .gitignore) — создаём
# из config.example.json с ВАЛИДНЫМ тестовым ключом, чтобы тесты
# (включая NIP-98 подпись) работали без ручной настройки.
_CFG_PATH = os.path.join(_WEB_ROOT, "config.json")
if not os.path.exists(_CFG_PATH):
    import secrets

    from mailbridge.nip44 import pubkey_from_privkey

    _example = os.path.join(_WEB_ROOT, "config.example.json")
    with open(_example) as _f:
        _cfg = json.load(_f)
    _cfg["auth_password"] = "test-password"
    _nsec = secrets.token_hex(32)
    _cfg["nsec_hex"] = _nsec
    _cfg["pubkey_hex"] = pubkey_from_privkey(_nsec)
    with open(_CFG_PATH, "w") as _f:
        json.dump(_cfg, _f, ensure_ascii=False, indent=2)


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
            raw_event TEXT, attachments TEXT DEFAULT '[]', owner TEXT DEFAULT ''
        );
        CREATE TABLE outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT, recipient_pubkey TEXT, subject TEXT, body TEXT,
            sent_at INTEGER, raw_event TEXT, owner TEXT DEFAULT ''
        );
        INSERT INTO inbox (message_id, sender_pubkey, from_addr, to_addr, subject, body, received_at, is_read, owner)
        VALUES ('<m1@test>', 'aaa', 'npub1a…@snin-mail.v2.site', 'npub1b…@snin-mail.v2.site', 'Привет', 'Тело 1', 1000, 0, 'OWNER_A'),
               ('<m2@test>', 'bbb', 'npub1c…@snin-mail.v2.site', 'npub1b…@snin-mail.v2.site', 'Срочно', 'Тело 2', 2000, 1, 'OWNER_A');
        INSERT INTO outbox (message_id, recipient_pubkey, subject, body, sent_at, owner)
        VALUES ('<o1@test>', 'ccc', 'Отправленное', 'Тело', 1500, 'OWNER_A');
        """
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def client(db, tmp_path, monkeypatch):
    """Чистый клиент: временная БД, чистые сессии."""
    import app as appmod
    import mailapp.config as cfg
    import mailapp.auth as auth
    from fastapi.testclient import TestClient

    monkeypatch.setattr(cfg, "DB", db)
    monkeypatch.setattr(cfg, "DEFAULT_OWNER", "OWNER_A")
    owner = {"nsec_hex": cfg.NSEC, "pubkey_hex": "OWNER_A",
             "address": "a@x", "label": "Крайтер", "npub": cfg.NPUB}
    monkeypatch.setattr(cfg, "OWNERS", [owner])
    monkeypatch.setattr(cfg, "OWNER_INDEX", {"OWNER_A": owner})
    monkeypatch.setattr(cfg, "ACCOUNTS_FILE", str(tmp_path / "mail_accounts.json"))
    monkeypatch.setattr(cfg, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(auth, "SESSIONS", {})
    with TestClient(appmod.app) as c:
        yield c
