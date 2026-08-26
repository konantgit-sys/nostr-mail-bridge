"""Мосты (MailBridge): по одному на владельца ящика, каждый в своём потоке.

Все мосты пишут в общую БД (inbox.db), письма помечаются owner (pubkey владельца).
NO_BRIDGE=1 (тесты) — мосты не стартуют, get_bridge() вернёт None.
"""
from __future__ import annotations

import logging
import os
import sys
import threading

from .config import BASE, CFG, DB, OWNERS, RELAYS

_bridges: dict[str, object] = {}
_lock = threading.Lock()


def init_bridge():
    """Стартует мост для каждого владельца. NO_BRIDGE=1 — пропустить (тесты)."""
    global _bridges
    with _lock:
        if _bridges or os.environ.get("NO_BRIDGE") == "1":
            return
        _setup_logging()
        sys.path.insert(0, os.path.join(BASE, "..", "..", "projects", "nostr-mail-bridge", "src"))
        from mailbridge.mail_bridge import MailBridge  # local import: тяжёлый

        telegram_token = CFG.get("telegram_token", "")
        telegram_chat_id = CFG.get("telegram_chat_id", "")

        for o in OWNERS:
            b = MailBridge(
                privkey_hex=o["nsec_hex"],
                relays=RELAYS,
                db_path=DB,
                telegram_token=telegram_token,
                telegram_chat_id=telegram_chat_id,
                owner=o["pubkey_hex"],
                label=o["label"],
            )
            _bridges[o["pubkey_hex"]] = b
            t = threading.Thread(target=b.start, daemon=True)
            t.start()

        # старые письма (до мульти-ящика) — первому владельцу
        try:
            import sqlite3
            with sqlite3.connect(DB, timeout=15) as conn:
                conn.execute("UPDATE inbox SET owner=? WHERE owner=''", (OWNERS[0]["pubkey_hex"],))
                conn.commit()
        except Exception:
            pass


def get_bridge(owner: str | None = None):
    """Мост владельца (по умолчанию — первый). None в тестах (NO_BRIDGE)."""
    if not _bridges:
        return None
    if owner and owner in _bridges:
        return _bridges[owner]
    return _bridges[list(_bridges)[0]]


def _setup_logging():
    """Логи моста в веб-режиме: mailbridge → INFO → stdout (backend.log).
    Раньше basicConfig был только в CLI main() — в веб-режиме логи терялись."""
    logger = logging.getLogger("mailbridge")
    if logger.handlers:  # уже настроен
        return
    logger.setLevel(logging.INFO)
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(h)
    logger.propagate = False
